"""Integration tests for capture_runner (014-demonstration-capture,
T008-T017, T036-T038).

Exercises the full orchestration logic against a throwaway SQLite
database with every Atlas call mocked via httpx.MockTransport — no live
sandbox or DashScope credentials are needed to prove the orchestration
itself is correct (a pre-built TravelObjective is injected directly,
bypassing ObjectiveParser, exactly as backend/scripts/seed_console_fixture.py
already does for fixture/test purposes).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

_ATLAS_SEARCH_URL = "https://sandbox.atriptech.com/search.do"
_ATLAS_VERIFY_URL = "https://sandbox.atriptech.com/verify.do"
_ATLAS_ORDER_URL = "https://sandbox.atriptech.com/order.do"
_ATLAS_PAY_URL = "https://sandbox.atriptech.com/pay.do"
_ATLAS_QUERY_URL = "https://sandbox.atriptech.com/queryOrderDetails.do"
_ATLAS_VOID_URL = "https://sandbox.atriptech.com/void.do"

_ORIGIN = "ICN"
_DEST = "NRT"
_DEP_DATE = "20260905"
_DEADLINE = "202609051000"


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'capture_runner.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    os.environ["DISRUPTION_INJECTOR_ENABLED"] = "true"
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _objective() -> Any:
    from scripts.capture_runner import _default_objective

    return _default_objective()


def _routing(routing_identifier: str, dep_time: str, arr_time: str, price: str, legs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    far_future = (datetime.now(tz=timezone.utc) + timedelta(days=1000)).isoformat()
    if legs is None:
        legs = [
            {
                "segmentIndex": 0,
                "carrier": "SQ",
                "flightNumber": "SQ1",
                "depAirport": _ORIGIN,
                "depTime": dep_time,
                "arrAirport": _DEST,
                "arrTime": arr_time,
                "duration": 300,
                "stopCities": "",
                "cabinClass": "Y",
                "seatCount": 9,
                "riskSellout": False,
                "codeShare": False,
                "aircraftCode": "77W",
                "fareFamily": None,
            }
        ]
    return {
        "fid": f"fid-{routing_identifier}",
        "routingIdentifier": routing_identifier,
        "currency": "USD",
        "adultPrice": price,
        "adultTax": "0.00",
        "transactionFeePerPax": "0.00",
        "refreshTime": now_iso,
        "expireTime": far_future,
        "separateBookings": False,
        "fromSegments": legs,
    }


def _busan_trap_legs() -> list[dict[str, Any]]:
    return [
        {
            "segmentIndex": 0, "carrier": "7C", "flightNumber": "7C907",
            "depAirport": _ORIGIN, "depTime": "202609050100",
            "arrAirport": "PUS", "arrTime": "202609050440",
            "duration": 240, "stopCities": "", "cabinClass": "Y", "seatCount": 5,
            "riskSellout": False, "codeShare": False, "aircraftCode": "738", "fareFamily": None,
        },
        {
            "segmentIndex": 1, "carrier": "7C", "flightNumber": "7C1151",
            "depAirport": "PUS", "depTime": "202609050930",
            "arrAirport": _DEST, "arrTime": "202609050955",
            "duration": 120, "stopCities": "", "cabinClass": "Y", "seatCount": 5,
            "riskSellout": False, "codeShare": False, "aircraftCode": "738", "fareFamily": None,
        },
    ]


def _initial_search_response() -> dict[str, Any]:
    return {
        "status": 0,
        "routings": [
            _routing("RID-ZE605", "202609050725", "202609050950", "90.39"),
            _routing("RID-BUSAN", "", "", "98.93", legs=_busan_trap_legs()),
        ],
    }


def _recovery_search_response() -> dict[str, Any]:
    return {
        "status": 0,
        "routings": [_routing("RID-LJ201", "202609050725", "202609050955", "96.63")],
    }


def _verify_response() -> dict[str, Any]:
    return {
        "status": 0,
        "sessionId": f"sess-{id(object())}",
        "maxSeats": 9,
        "priceChange": {"isPriceChange": False},
        "bookingRequirement": {"passenger": {}},
    }


def _order_response(order_no: str) -> dict[str, Any]:
    return {
        "orderNo": order_no,
        "pnrCode": "PNR1",
        "tktLimitTime": (datetime.now(tz=timezone.utc) + timedelta(minutes=30)).isoformat(),
        "sessionId": "sess-order",
        "duplicateOrders": None,
        "status": 0,
        "msg": "success",
    }


def _pay_response() -> dict[str, Any]:
    return {"status": 0}


def _query_response(ticketed: bool) -> dict[str, Any]:
    return {
        "orderStatus": "1",
        "ticketStatus": "0",
        "paxTicketInfos": [{"ticketNos": ["TKT1"] if ticketed else []}],
        "errorCode": None,
    }


class _Dispatcher:
    def __init__(self) -> None:
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.calls: dict[str, list[dict[str, Any]]] = {}

    def set(self, url: str, *responses: dict[str, Any]) -> None:
        self.responses[url] = list(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        try:
            body = json.loads(request.content or b"{}")
        except ValueError:
            body = {}
        self.calls.setdefault(url, []).append(body)
        queue = self.responses.get(url, [])
        payload = queue.pop(0) if queue else (queue[-1] if queue else {"status": 0})
        return httpx.Response(200, json=payload)


def _full_success_dispatcher() -> _Dispatcher:
    d = _Dispatcher()
    d.set(_ATLAS_SEARCH_URL, _initial_search_response(), _recovery_search_response())
    d.set(_ATLAS_VERIFY_URL, _verify_response(), _verify_response(), _verify_response())
    d.set(_ATLAS_ORDER_URL, _order_response("ORIGINAL-1"), _order_response("REPLACEMENT-1"))
    d.set(_ATLAS_PAY_URL, _pay_response(), _pay_response())
    d.set(
        _ATLAS_QUERY_URL,
        _query_response(True),  # confirm_ticketing (original)
        _query_response(True),  # confirm_ticketing (replacement)
        _query_response(False),  # cancellation reconciliation (original)
    )
    d.set(_ATLAS_VOID_URL, {"status": 0})
    return d


class TestPrimaryScenarioPassesEveryStep:
    def test_full_pipeline_completes_and_passes(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        d = _full_success_dispatcher()
        client = httpx.Client(transport=httpx.MockTransport(d))

        from scripts.capture_runner import run

        result = run(
            "primary",
            objective=_objective(),
            atlas_http_client=client,
            now=datetime.now(tz=timezone.utc),
        )

        assert result.status == "PASSED", result.failed_step
        assert "search" in result.steps_completed
        assert "scoring" in result.steps_completed
        assert "booking" in result.steps_completed
        assert "disruption_injected" in result.steps_completed
        assert "impact_evaluation" in result.steps_completed
        assert "recommendation" in result.steps_completed
        assert "authorisation_approved" in result.steps_completed
        assert "recovery_execution" in result.steps_completed

    def test_two_consecutive_runs_both_pass_without_manual_reset(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from scripts.capture_runner import run

        for _ in range(2):
            d = _full_success_dispatcher()
            client = httpx.Client(transport=httpx.MockTransport(d))
            result = run(
                "primary",
                objective=_objective(),
                atlas_http_client=client,
                now=datetime.now(tz=timezone.utc),
            )
            assert result.status == "PASSED", result.failed_step


class TestPrimaryScenarioHaltsOnFirstFailure:
    def test_disruption_injector_disabled_halts_run(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        os.environ["DISRUPTION_INJECTOR_ENABLED"] = "false"
        d = _full_success_dispatcher()
        client = httpx.Client(transport=httpx.MockTransport(d))

        from scripts.capture_runner import run

        result = run(
            "primary",
            objective=_objective(),
            atlas_http_client=client,
            now=datetime.now(tz=timezone.utc),
        )

        assert result.status == "FAILED"
        assert result.failed_step == "disruption_injected"
        assert "recommendation" not in result.steps_completed
        assert "recovery_execution" not in result.steps_completed


class TestRefusalScenario:
    def test_refusal_scenario_zero_spend(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        d = _full_success_dispatcher()
        client = httpx.Client(transport=httpx.MockTransport(d))

        from scripts.capture_runner import run

        result = run(
            "refusal",
            objective=_objective(),
            atlas_http_client=client,
            now=datetime.now(tz=timezone.utc),
        )

        assert result.status == "PASSED", result.failed_step
        assert _ATLAS_VOID_URL not in d.calls
        assert len(d.calls.get(_ATLAS_ORDER_URL, [])) == 1

    def test_refusal_durably_recorded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        d = _full_success_dispatcher()
        client = httpx.Client(transport=httpx.MockTransport(d))

        from scripts.capture_runner import run

        result = run(
            "refusal",
            objective=_objective(),
            atlas_http_client=client,
            now=datetime.now(tz=timezone.utc),
        )

        events = repo.get_events_from_sequence(result.journey_id, from_sequence=0)
        outcomes = [e for e in events if e.event_type.value == "authorisation_outcome"]
        assert len(outcomes) == 1
        assert outcomes[0].payload["outcome"] == "refused"

    def test_refusal_journey_independent_from_primary(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from scripts.capture_runner import run

        primary_client = httpx.Client(transport=httpx.MockTransport(_full_success_dispatcher()))
        primary = run(
            "primary", objective=_objective(), atlas_http_client=primary_client, now=datetime.now(tz=timezone.utc)
        )
        refusal_client = httpx.Client(transport=httpx.MockTransport(_full_success_dispatcher()))
        refusal = run(
            "refusal", objective=_objective(), atlas_http_client=refusal_client, now=datetime.now(tz=timezone.utc)
        )

        assert primary.status == "PASSED"
        assert refusal.status == "PASSED"
        assert primary.journey_id != refusal.journey_id
