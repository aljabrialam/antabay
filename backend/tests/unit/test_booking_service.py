"""Unit tests for BookingService (T011-T014, T023-T025, T033-T036, T046-T047).

TDD gate (T015, T026, T037, T048): these tests must fail with
NotImplementedError or AttributeError against the Phase 2 skeleton before
implementation begins.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'booking_service.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _service(repo: Any, http_client: httpx.Client | None = None) -> Any:
    from journey.services.booking_service import BookingService

    return BookingService(repo=repo, http_client=http_client or httpx.Client())


def _seed_verified_journey(
    repo: Any,
    session_id: str = "sess-abc123",
    session_stale_after_seconds: int = 3600,
    passenger_requirements: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    """Seed a journey through SEARCHING -> VERIFIED with a held session, mirroring
    what spec 004's VerificationService would have already done."""
    from journey.models.flight import FlightOption
    from journey.models.journey import JourneyState
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.models.verification import (
        PassengerRequirementField,
        VerificationOutcome,
        VerificationResult,
    )
    from journey.services.journey_service import JourneyService
    from journey.services.state_service import JourneyStateService

    objective = TravelObjective(
        origin=ConstrainedField(value="JKT", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="SUB", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)
    now = datetime.now(tz=timezone.utc)

    option = FlightOption(
        option_id="opt-1",
        journey_id=journey.journey_id,
        search_record_id="search-1",
        fid="fid-1",
        routing_identifier="RID-BOOKING-TEST",
        currency="USD",
        adult_price=Decimal("66.43"),
        adult_tax=Decimal("23.96"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now + timedelta(minutes=7),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )
    repo.save_flight_options([option])

    state_svc = JourneyStateService(repository=repo)
    state_svc.transition(journey.journey_id, JourneyState.SEARCHING, reason="options held", now=now)
    state_svc.transition(journey.journey_id, JourneyState.VERIFIED, reason="verified", now=now)

    requirements = passenger_requirements or [
        {"field_name": "name", "type": "string", "required": True, "description": "Full name", "max_length": 100},
        {"field_name": "birthday", "type": "string", "required": True, "description": "DOB", "max_length": 10},
    ]
    result = VerificationResult(
        verification_id="verif-1",
        journey_id=journey.journey_id,
        option_id=option.option_id,
        requested_at=now,
        responded_at=now,
        raw_response_json="{}",
        status_code=200,
        atlas_status=0,
        outcome=VerificationOutcome.VERIFIED,
        budget_before=20,
        budget_after=19,
        session_id=session_id,
        max_seats=7,
        passenger_requirements=[
            PassengerRequirementField(
                field_name=f["field_name"],
                type=f["type"],
                required=f["required"],
                description=f["description"],
                max_length=f["max_length"],
            )
            for f in requirements
        ],
    )
    repo.save_verification(result)

    repo.add_held_identifier(
        journey_id=journey.journey_id,
        value=session_id,
        issued_at=now,
        stale_after_seconds=session_stale_after_seconds,
    )

    return journey.journey_id, option.option_id


def _order_response(order_no: str = "TESTA20260815172246746", pnr: str = "TZKZYA") -> dict[str, Any]:
    return {
        "orderNo": order_no,
        "pnrCode": pnr,
        "tktLimitTime": (datetime.now(tz=timezone.utc) + timedelta(minutes=30)).isoformat(),
        "sessionId": "sess-abc123",
        "duplicateOrders": None,
        "status": 0,
        "msg": "success",
    }


def _duplicate_response(existing_order_no: str = "TESTA20260815172246746") -> dict[str, Any]:
    return {
        "orderNo": None,
        "pnrCode": None,
        "tktLimitTime": None,
        "sessionId": None,
        "duplicateOrders": [existing_order_no],
        "status": 318,
        "msg": None,
    }


def _query_response(ticket_numbers: list[list[str]], error_code: str | None = None) -> dict[str, Any]:
    return {
        "orderStatus": "1",
        "ticketStatus": "0",
        "paxTicketInfos": [{"ticketNos": nos} for nos in ticket_numbers],
        "errorCode": error_code,
        "errorMessage": None,
    }


def _client_returning(response_json: dict[str, Any], status_code: int = 200) -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_json)

    return httpx.Client(transport=httpx.MockTransport(_handler))


class TestCreateOrderIdentifierIntegrity:
    def test_sends_stored_session_id_unmodified(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo, session_id="SESS-EXACT-VALUE")

        sent_bodies: list[dict[str, Any]] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            sent_bodies.append(_json.loads(request.content))
            return httpx.Response(200, json=_order_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        svc = _service(repo, client)
        svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert sent_bodies[0]["sessionId"] == "SESS-EXACT-VALUE"


class TestCreateOrderPassengerForm:
    def test_populates_exactly_recorded_requirement_fields(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(
            repo,
            passenger_requirements=[
                {"field_name": "name", "type": "string", "required": True, "description": "d", "max_length": 100},
                {"field_name": "nationality", "type": "string", "required": True, "description": "d", "max_length": 2},
            ],
        )

        sent_bodies: list[dict[str, Any]] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            sent_bodies.append(_json.loads(request.content))
            return httpx.Response(200, json=_order_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        svc = _service(repo, client)
        svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        passenger = sent_bodies[0]["passengers"][0]
        assert set(passenger.keys()) == {"name", "nationality"}


class TestCreateOrderNeverTreatsBookingReferenceAsTicketing:
    def test_created_order_has_no_ticketing_confirmation(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)

        svc = _service(repo, _client_returning(_order_response()))
        order = svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert order.booking_reference == "TZKZYA"
        # No ticketing confirmation exists anywhere the Order result exposes.
        assert not hasattr(order, "ticketed")
        assert repo.get_ticketing_queries(order.order_no) == []


class TestSessionExpiredPrecondition:
    def test_refuses_when_session_already_expired(self, tmp_path: Any) -> None:
        from journey.errors import SessionExpiredError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo, session_stale_after_seconds=1)

        called = {"count": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json=_order_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        svc = _service(repo, client)
        far_future = datetime.now(tz=timezone.utc) + timedelta(hours=1)

        with pytest.raises(SessionExpiredError):
            svc.create_order(journey_id=journey_id, option_id=option_id, now=far_future)
        assert called["count"] == 0


class TestSubmitPaymentPrecondition:
    def test_raises_when_no_created_order_exists(self, tmp_path: Any) -> None:
        from journey.errors import OrderNotFoundError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, _ = _seed_verified_journey(repo)

        called = {"count": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json={"status": 0})

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        svc = _service(repo, client)

        with pytest.raises(OrderNotFoundError):
            svc.submit_payment(journey_id=journey_id, order_no="no-such-order", now=datetime.now(tz=timezone.utc))
        assert called["count"] == 0


class TestSubmitPaymentSuccessDoesNotConfirmTicketing:
    def test_success_leaves_journey_state_unchanged(self, tmp_path: Any) -> None:
        from journey.models.journey import JourneyState

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        pay_response = {"orderNo": order.order_no, "pnrCode": "TZKZYA", "paymentMethod": 1, "status": 0, "msg": "success"}
        svc = _service(repo, _client_returning(pay_response))
        payment = svc.submit_payment(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))

        assert payment.outcome.value == "SUCCESS"
        assert repo.get_journey(journey_id).state is JourneyState.VERIFIED


class TestPaymentDeclineNoRetry:
    def test_decline_recorded_and_second_attempt_refused(self, tmp_path: Any) -> None:
        from journey.errors import PaymentDeclinedError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        decline_response = {"orderNo": order.order_no, "status": 604, "msg": "declined"}
        svc = _service(repo, _client_returning(decline_response))
        payment = svc.submit_payment(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))
        assert payment.outcome.value == "DECLINED"

        called = {"count": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json={"status": 0})

        svc2 = _service(repo, httpx.Client(transport=httpx.MockTransport(_handler)))
        with pytest.raises(PaymentDeclinedError):
            svc2.submit_payment(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))
        assert called["count"] == 0


class TestConfirmTicketingPartialResult:
    def test_some_but_not_all_passengers_ticketed_is_not_confirmed(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        response = _query_response(ticket_numbers=[["S46659"], []])
        svc = _service(repo, _client_returning(response))
        query = svc.confirm_ticketing(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))

        assert query.confirmed is False


class TestConfirmTicketingAllPassengers:
    def test_all_passengers_ticketed_confirms_and_transitions(self, tmp_path: Any) -> None:
        from journey.models.journey import JourneyState

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        response = _query_response(ticket_numbers=[["S46659"], ["S46660"]])
        svc = _service(repo, _client_returning(response))
        query = svc.confirm_ticketing(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))

        assert query.confirmed is True
        assert repo.get_journey(journey_id).state is JourneyState.MONITORING


class TestConfirmTicketingTerminalError:
    def test_error_code_stops_without_transition(self, tmp_path: Any) -> None:
        from journey.models.journey import JourneyState

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        response = _query_response(ticket_numbers=[[]], error_code="800")
        svc = _service(repo, _client_returning(response))
        query = svc.confirm_ticketing(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))

        assert query.is_terminal_error is True
        assert query.confirmed is False
        assert repo.get_journey(journey_id).state is JourneyState.VERIFIED


class TestConfirmTicketingDeadlinePassed:
    def test_no_http_call_once_deadline_has_passed(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)

        near_term_response = dict(_order_response())
        order_created_at = datetime.now(tz=timezone.utc)
        near_term_response["tktLimitTime"] = (order_created_at + timedelta(seconds=1)).isoformat()
        order = _service(repo, _client_returning(near_term_response)).create_order(
            journey_id=journey_id, option_id=option_id, now=order_created_at
        )

        called = {"count": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json=_query_response(ticket_numbers=[[]]))

        svc = _service(repo, httpx.Client(transport=httpx.MockTransport(_handler)))
        past_deadline = order_created_at + timedelta(minutes=5)
        svc.confirm_ticketing(journey_id=journey_id, order_no=order.order_no, now=past_deadline)

        assert called["count"] == 0


class TestCreateOrderErrorOutcome:
    def test_unparseable_body_persists_raw_bytes(self, tmp_path: Any) -> None:
        """NFR-002: raw response must be persisted even when unparseable (T054)."""
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all")

        svc = _service(repo, httpx.Client(transport=httpx.MockTransport(_handler)))
        order = svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert order.outcome.value == "ERROR"
        assert order.raw_response_json == "not json at all"


class TestSubmitPaymentErrorOutcome:
    def test_unparseable_body_persists_raw_bytes(self, tmp_path: Any) -> None:
        """NFR-002: raw response must be persisted even when unparseable (T054)."""
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)
        order = _service(repo, _client_returning(_order_response())).create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all")

        svc = _service(repo, httpx.Client(transport=httpx.MockTransport(_handler)))
        payment = svc.submit_payment(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))

        assert payment.outcome.value == "ERROR"
        assert payment.raw_response_json == "not json at all"


class TestUncertainOrderRetryReconciliation:
    def test_retry_after_no_response_resolves_via_duplicate(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)

        call_count = {"n": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise httpx.ConnectError("simulated no response")
            if "queryOrderDetails" in str(request.url):
                return httpx.Response(200, json=_query_response(ticket_numbers=[["S46659"]]))
            return httpx.Response(200, json=_duplicate_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        svc = _service(repo, client)
        order = svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert order.outcome.value == "DUPLICATE_REJECTED"
        assert order.order_no == "TESTA20260815172246746"
        assert call_count["n"] >= 3  # failed order attempt, retry, then the reconciling query


class TestMultipleDuplicateOrdersAnomaly:
    def test_more_than_one_duplicate_reference_raises(self, tmp_path: Any) -> None:
        from journey.errors import DuplicateOrderAnomalyError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_verified_journey(repo)

        response = _duplicate_response()
        response["duplicateOrders"] = ["ORDER-A", "ORDER-B"]
        svc = _service(repo, _client_returning(response))

        with pytest.raises(DuplicateOrderAnomalyError):
            svc.create_order(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))
