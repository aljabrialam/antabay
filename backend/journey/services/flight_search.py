from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx

from journey.errors import AtlasSearchError, RateLimitError
from journey.models.flight import (
    FlightOption,
    Leg,
    SearchOutcome,
    SearchRecord,
    SearchResult,
)

if TYPE_CHECKING:
    from journey.storage.repository import JourneyRepository

_ATLAS_SEARCH_URL = "https://sandbox.atriptech.com/search.do"


class FlightSearchService:
    def __init__(self, repo: "JourneyRepository", http_client: httpx.Client) -> None:
        self._repo = repo
        self._http = http_client
        self._last_call_at: datetime | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(self, journey_id: str, now: datetime) -> SearchResult:
        journey = self._repo.get_journey(journey_id)
        obj = getattr(journey, "confirmed_objective", None) or journey.objective

        # Rate gate: enforce 100ms minimum gap between calls
        self._enforce_rate_gate(now)

        request_body = self._build_request(obj)

        # Decrement budget before HTTP call — raises BudgetExhaustedError if zero
        budget_before, budget_after = self._repo.decrement_call_budget(journey_id)

        requested_at = now
        response = self._http.post(_ATLAS_SEARCH_URL, json=request_body)
        responded_at = now

        self._last_call_at = now

        # FR-012: unparseable body → ERROR outcome; persist raw bytes, raise
        try:
            raw_json: dict[str, Any] = response.json()
        except Exception:
            raw_str = response.text
            rec = SearchRecord(
                search_id=str(uuid.uuid4()),
                journey_id=journey_id,
                requested_at=requested_at,
                responded_at=responded_at,
                raw_response_json=raw_str,
                status_code=response.status_code,
                atlas_status=-1,
                option_count=0,
                budget_before=budget_before,
                budget_after=budget_after,
                outcome=SearchOutcome.ERROR,
            )
            self._repo.save_search_record(rec)
            raise AtlasSearchError(
                "Response body could not be parsed as JSON",
                status_code=response.status_code,
                atlas_status=None,
            )

        raw_str = json.dumps(raw_json)

        # --- 429 rate-limit: save SearchRecord with RATE_LIMITED, then raise ---
        if response.status_code == 429:
            retry_after = float(raw_json.get("retryAfter", 0))
            rec = SearchRecord(
                search_id=str(uuid.uuid4()),
                journey_id=journey_id,
                requested_at=requested_at,
                responded_at=responded_at,
                raw_response_json=raw_str,
                status_code=response.status_code,
                atlas_status=raw_json.get("status", -1),
                option_count=0,
                budget_before=budget_before,
                budget_after=budget_after,
                outcome=SearchOutcome.RATE_LIMITED,
            )
            self._repo.save_search_record(rec)
            raise RateLimitError(retry_after)

        atlas_status: int = int(raw_json.get("status", -1))

        # --- Non-zero Atlas status → error outcome, still commit Tx1 ---
        if atlas_status != 0:
            rec = SearchRecord(
                search_id=str(uuid.uuid4()),
                journey_id=journey_id,
                requested_at=requested_at,
                responded_at=responded_at,
                raw_response_json=raw_str,
                status_code=response.status_code,
                atlas_status=atlas_status,
                option_count=0,
                budget_before=budget_before,
                budget_after=budget_after,
                outcome=SearchOutcome.ERROR,
            )
            self._repo.save_search_record(rec)
            raise AtlasSearchError(
                raw_json.get("msg", "Atlas error"),
                status_code=response.status_code,
                atlas_status=atlas_status,
            )

        # --- Map routings (may be empty) ---
        # FR-012: routings key absent → ERROR, not EMPTY
        if "routings" not in raw_json:
            rec = SearchRecord(
                search_id=str(uuid.uuid4()),
                journey_id=journey_id,
                requested_at=requested_at,
                responded_at=responded_at,
                raw_response_json=raw_str,
                status_code=response.status_code,
                atlas_status=atlas_status,
                option_count=0,
                budget_before=budget_before,
                budget_after=budget_after,
                outcome=SearchOutcome.ERROR,
            )
            self._repo.save_search_record(rec)
            raise AtlasSearchError(
                "Response body missing required 'routings' key",
                status_code=response.status_code,
                atlas_status=atlas_status,
            )

        routings = raw_json.get("routings", [])
        search_id = str(uuid.uuid4())
        options = self._map_routings(routings, journey_id, search_id_placeholder=search_id, now=now)

        outcome = SearchOutcome.EMPTY if not options else SearchOutcome.SUCCESS

        rec = SearchRecord(
            search_id=search_id,
            journey_id=journey_id,
            requested_at=requested_at,
            responded_at=responded_at,
            raw_response_json=raw_str,
            status_code=response.status_code,
            atlas_status=atlas_status,
            option_count=len(options),
            budget_before=budget_before,
            budget_after=budget_after,
            outcome=outcome,
        )

        # Transaction 1: persist SearchRecord
        self._repo.save_search_record(rec)

        # Transaction 2: persist FlightOption + Leg rows (failure must not roll back Tx1)
        if options:
            try:
                self._repo.save_flight_options(options)
            except Exception:
                pass

        carriers = list({leg.carrier for opt in options for leg in opt.legs[:1]})

        return SearchResult(
            search_id=search_id,
            option_count=len(options),
            no_options=len(options) == 0,
            carriers=carriers,
            options=options,
        )

    def _enforce_rate_gate(self, now: datetime) -> None:
        if self._last_call_at is None:
            return
        elapsed = (now - self._last_call_at).total_seconds()
        if elapsed < 0.1:
            raise RateLimitError(retry_after_seconds=0.1 - elapsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_request(self, obj: Any) -> dict[str, Any]:
        currency = (
            obj.budget_currency.value
            if obj.budget_currency is not None
            else "USD"
        )
        return {
            "fromCity": obj.origin.value,
            "toCity": obj.destination.value,
            "fromDate": obj.departure_date.value,
            "adultNum": obj.pax_count.value,
            "currency": currency,
            "tripType": "1",
        }

    def _map_routings(
        self,
        routings: list[dict[str, Any]],
        journey_id: str,
        search_id_placeholder: str,
        now: datetime,
    ) -> list[FlightOption]:
        options: list[FlightOption] = []
        for r in routings:
            fid = r.get("fid", "")
            ri = r.get("routingIdentifier", "")
            if not fid or not ri:
                continue  # FR-011: drop options without identifiers

            segments = r.get("fromSegments", [])
            legs = self._map_legs(segments, option_id_placeholder="")

            option_id = str(uuid.uuid4())
            legs = self._map_legs(segments, option_id_placeholder=option_id)

            refreshed_at = _parse_dt(r.get("refreshTime"))
            expire_at = _parse_dt(r.get("expireTime"))

            options.append(
                FlightOption(
                    option_id=option_id,
                    journey_id=journey_id,
                    search_record_id=search_id_placeholder,
                    fid=fid,
                    routing_identifier=ri,
                    currency=r.get("currency", "USD"),
                    adult_price=Decimal(str(r.get("adultPrice", "0"))),
                    adult_tax=Decimal(str(r.get("adultTax", "0"))),
                    transaction_fee=Decimal(str(r.get("transactionFeePerPax", "0"))),
                    refreshed_at=refreshed_at,
                    expire_at=expire_at,
                    is_multi_leg=len(legs) > 1,
                    separate_bookings=bool(r.get("separateBookings", False)),
                    legs=legs,
                    recorded_at=now,
                )
            )
        return options

    def _map_legs(self, segments: list[dict[str, Any]], option_id_placeholder: str) -> list[Leg]:
        result: list[Leg] = []
        for seg in segments:
            result.append(
                Leg(
                    leg_id=str(uuid.uuid4()),
                    option_id=option_id_placeholder,
                    segment_index=seg.get("segmentIndex", 0),
                    carrier=seg.get("carrier", ""),
                    flight_number=seg.get("flightNumber", ""),
                    dep_airport=seg.get("depAirport", ""),
                    dep_time=seg.get("depTime", ""),
                    arr_airport=seg.get("arrAirport", ""),
                    arr_time=seg.get("arrTime", ""),
                    duration_minutes=seg.get("duration", 0),
                    stop_cities=seg.get("stopCities", ""),
                    cabin_class=str(seg.get("cabinClass", "")),
                    seat_count=seg.get("seatCount", 0),
                    risk_sellout=bool(seg.get("riskSellout", False)),
                    code_share=bool(seg.get("codeShare", False)),
                    aircraft_code=seg.get("aircraftCode", ""),
                    fare_family=seg.get("fareFamily"),
                )
            )
        return result


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
