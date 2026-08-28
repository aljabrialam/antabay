from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from journey.errors import AtlasVerifyError, RateLimitError
from journey.models.journey import HeldIdentifier, JourneyRecord, JourneyState
from journey.models.verification import (
    PassengerRequirementField,
    PriceChange,
    VerificationOutcome,
    VerificationResult,
)
from journey.services.state_service import JourneyStateService

if TYPE_CHECKING:
    from journey.storage.repository import JourneyRepository

_ATLAS_VERIFY_URL = "https://sandbox.atriptech.com/verify.do"

# Session-level freshness window duration. Atlas documents "up to 2 hours"
# for sessionId but verify.do returns no explicit session-expiry field
# (routing.expireTime is null on this response) — see research.md R2.
SESSION_WINDOW_SECONDS = 2 * 60 * 60


class VerificationService:
    def __init__(self, repo: "JourneyRepository", http_client: httpx.Client) -> None:
        self._repo = repo
        self._http = http_client
        self._state_service = JourneyStateService(repository=repo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify(self, journey_id: str, option_id: str, now: datetime) -> VerificationResult:
        option = self._repo.get_flight_option(option_id)
        if option is None:
            raise ValueError(f"Flight option not found: {option_id}")

        budget_before, budget_after = self._repo.decrement_call_budget(journey_id)

        requested_at = now
        request_body = {
            "routingIdentifier": option.routing_identifier,
            "maxResponseTime": None,
            "requestSource": "antabay",
        }
        response = self._http.post(_ATLAS_VERIFY_URL, json=request_body)
        responded_at = now

        try:
            raw_json: dict[str, Any] = response.json()
        except Exception:
            result = self._build_result(
                journey_id=journey_id,
                option_id=option_id,
                outcome=VerificationOutcome.ERROR,
                raw_response_json=response.text,
                status_code=response.status_code,
                atlas_status=None,
                requested_at=requested_at,
                responded_at=responded_at,
                budget_before=budget_before,
                budget_after=budget_after,
            )
            self._repo.save_verification(result)
            raise AtlasVerifyError(
                "Response body could not be parsed as JSON",
                status_code=response.status_code,
                atlas_status=None,
            )

        if response.status_code == 429:
            result = self._build_result(
                journey_id=journey_id,
                option_id=option_id,
                outcome=VerificationOutcome.RATE_LIMITED,
                raw_response_json=json.dumps(raw_json),
                status_code=response.status_code,
                atlas_status=raw_json.get("status", -1),
                requested_at=requested_at,
                responded_at=responded_at,
                budget_before=budget_before,
                budget_after=budget_after,
            )
            self._repo.save_verification(result)
            raise RateLimitError(float(raw_json.get("retryAfter", 0)))

        result = self._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=raw_json,
            requested_at=requested_at,
            responded_at=responded_at,
            status_code=response.status_code,
            budget_before=budget_before,
            budget_after=budget_after,
        )
        self._repo.save_verification(result)

        if result.outcome in (VerificationOutcome.VERIFIED, VerificationOutcome.PRICE_CHANGED):
            self._on_verified(journey_id, result, now)
        elif result.outcome is VerificationOutcome.UNAVAILABLE:
            self._on_unavailable(journey_id, now)

        return result

    def needs_reverification(
        self, journey_id: str, now: datetime, safety_margin_seconds: int
    ) -> bool:
        journey = self._repo.get_journey(journey_id)
        # Raises IdentifierNotFoundError if no session window exists yet —
        # asking "does this need re-verification" is meaningless before a
        # first verification has happened (contracts/verification_service.md).
        session_identifier = self._find_session_identifier(journey)
        remaining_seconds = (session_identifier.stale_at - now).total_seconds()
        return remaining_seconds <= safety_margin_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        journey_id: str,
        option_id: str,
        response_json: dict[str, Any],
        requested_at: datetime,
        responded_at: datetime,
        status_code: int,
        budget_before: int,
        budget_after: int,
    ) -> VerificationResult:
        """Pure classification of a verify.do response into a VerificationResult.

        Split out from verify() so US1/US3's price-change, passenger-
        requirement, and max-seats behaviour can be unit tested directly
        against constructed response dicts, without HTTP mocking for every
        permutation (R3/FR-003/FR-007/FR-008).
        """
        atlas_status = int(response_json.get("status", -1))
        price_change_raw = response_json.get("priceChange")
        is_price_change = bool(price_change_raw and price_change_raw.get("isPriceChange"))

        if atlas_status == 0 and is_price_change:
            outcome = VerificationOutcome.PRICE_CHANGED
        elif atlas_status == 0:
            outcome = VerificationOutcome.VERIFIED
        else:
            outcome = VerificationOutcome.UNAVAILABLE

        price_change = None
        if price_change_raw is not None:
            price_change = _price_change_from_json(price_change_raw)

        passenger_requirements: list[PassengerRequirementField] = []
        session_id = None
        max_seats = None
        if outcome in (VerificationOutcome.VERIFIED, VerificationOutcome.PRICE_CHANGED):
            session_id = response_json.get("sessionId")
            max_seats = response_json.get("maxSeats")
            booking_requirement = response_json.get("bookingRequirement") or {}
            passenger_fields = booking_requirement.get("passenger") or {}
            passenger_requirements = [
                PassengerRequirementField(
                    field_name=name,
                    type=spec.get("type", ""),
                    required=bool(spec.get("required", False)),
                    description=spec.get("description", ""),
                    max_length=spec.get("maxLength"),
                )
                for name, spec in passenger_fields.items()
            ]

        return VerificationResult(
            verification_id=str(uuid.uuid4()),
            journey_id=journey_id,
            option_id=option_id,
            requested_at=requested_at,
            responded_at=responded_at,
            raw_response_json=json.dumps(response_json),
            status_code=status_code,
            atlas_status=atlas_status,
            outcome=outcome,
            budget_before=budget_before,
            budget_after=budget_after,
            session_id=session_id,
            max_seats=max_seats,
            price_change=price_change,
            passenger_requirements=passenger_requirements,
            invalidates_authorisation=(outcome is VerificationOutcome.PRICE_CHANGED),
        )

    def _build_result(
        self,
        journey_id: str,
        option_id: str,
        outcome: VerificationOutcome,
        raw_response_json: str,
        status_code: int,
        atlas_status: int | None,
        requested_at: datetime,
        responded_at: datetime,
        budget_before: int,
        budget_after: int,
    ) -> VerificationResult:
        return VerificationResult(
            verification_id=str(uuid.uuid4()),
            journey_id=journey_id,
            option_id=option_id,
            requested_at=requested_at,
            responded_at=responded_at,
            raw_response_json=raw_response_json,
            status_code=status_code,
            atlas_status=atlas_status,
            outcome=outcome,
            budget_before=budget_before,
            budget_after=budget_after,
        )

    def _on_verified(self, journey_id: str, result: VerificationResult, now: datetime) -> None:
        if result.session_id is not None:
            self._state_service.add_held_identifier(
                journey_id=journey_id,
                value=result.session_id,
                issued_at=now,
                stale_after_seconds=SESSION_WINDOW_SECONDS,
            )
        journey = self._repo.get_journey(journey_id)
        if journey.state is JourneyState.SEARCHING:
            self._state_service.transition(
                journey_id,
                JourneyState.VERIFIED,
                reason=f"verification succeeded ({result.outcome.value})",
                now=now,
            )

    def _on_unavailable(self, journey_id: str, now: datetime) -> None:
        journey = self._repo.get_journey(journey_id)
        if journey.state is JourneyState.VERIFIED:
            self._state_service.transition(
                journey_id,
                JourneyState.SEARCHING,
                reason="verification reported option unavailable",
                now=now,
            )

    def _find_session_identifier(self, journey: JourneyRecord) -> HeldIdentifier:
        from journey.services.state_service import IdentifierNotFoundError

        # The session identifier is the most recently issued held identifier
        # that isn't the offer-level routingIdentifier row. Since this
        # service is the only writer of session-window rows, the latest one
        # by issued_at is the current session.
        candidates = sorted(journey.held_identifiers, key=lambda h: h.issued_at)
        for ident in reversed(candidates):
            return ident
        raise IdentifierNotFoundError(
            f"No session identifier held for journey {journey.journey_id!r}"
        )


def _price_change_from_json(raw: dict[str, Any]) -> PriceChange:
    from decimal import Decimal

    def _dec(value: Any) -> Decimal | None:
        return Decimal(str(value)) if value is not None else None

    return PriceChange(
        is_price_change=bool(raw.get("isPriceChange", False)),
        original_adult_price=_dec(raw.get("originalAdultPrice")) or Decimal("0"),
        new_adult_price=_dec(raw.get("newAdultPrice")) or Decimal("0"),
        original_adult_tax=_dec(raw.get("originalAdultTax")) or Decimal("0"),
        new_adult_tax=_dec(raw.get("newAdultTax")) or Decimal("0"),
        original_child_price=_dec(raw.get("originalChildPrice")),
        new_child_price=_dec(raw.get("newChildPrice")),
        original_infant_price=_dec(raw.get("originalInfantPrice")),
        new_infant_price=_dec(raw.get("newInfantPrice")),
    )
