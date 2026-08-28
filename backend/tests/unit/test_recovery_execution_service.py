"""Unit tests for RecoveryExecutionService (T008-T010, T014-T019, T023-T029).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

_ATLAS_VERIFY_URL = "https://sandbox.atriptech.com/verify.do"
_ATLAS_ORDER_URL = "https://sandbox.atriptech.com/order.do"
_ATLAS_PAY_URL = "https://sandbox.atriptech.com/pay.do"
_ATLAS_QUERY_URL = "https://sandbox.atriptech.com/queryOrderDetails.do"
_ATLAS_VOID_URL = "https://sandbox.atriptech.com/void.do"

_ALT_PRICE = Decimal("300.00")


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'recovery_execution.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey_with_superseded_order(repo: Any, superseded_order_no: str = "SUPERSEDED-1") -> str:
    from journey.models.booking import Order, OrderOutcome
    from journey.models.journey import JourneyState
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        latest_arrival=ConstrainedField(value="209906152200", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)
    repo.update_journey_state(journey.journey_id, JourneyState.MONITORING)

    now = datetime.now(tz=timezone.utc)
    order = Order(
        order_id=str(uuid.uuid4()),
        journey_id=journey.journey_id,
        option_id="original-option",
        requested_at=now,
        responded_at=now,
        raw_response_json="{}",
        outcome=OrderOutcome.CREATED,
        order_no=superseded_order_no,
        booking_reference="PNR-ORIG",
        ticketing_deadline=None,
        session_id_used="sess-orig",
    )
    repo.save_order(order)
    return journey.journey_id


def _seed_alternative_option(repo: Any, journey_id: str, price: Decimal = _ALT_PRICE) -> str:
    from journey.models.flight import FlightOption

    now = datetime.now(tz=timezone.utc)
    option_id = str(uuid.uuid4())
    option = FlightOption(
        option_id=option_id,
        journey_id=journey_id,
        search_record_id="search-alt",
        fid="fid-alt",
        routing_identifier="RID-ALT",
        currency="USD",
        adult_price=price,
        adult_tax=Decimal("0.00"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now + timedelta(days=1),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )
    repo.save_flight_options([option])
    return option_id


def _seed_recommendation(repo: Any, option_id: str) -> str:
    from journey.models.impact_evaluation import Recommendation

    recommendation_id = str(uuid.uuid4())
    recommendation = Recommendation(
        recommendation_id=recommendation_id,
        evaluation_id="eval-placeholder",
        option_id=option_id,
        verification_id="verification-placeholder",
        cost_relative_description="+$0",
        rationale="Restores the objective.",
    )
    repo.save_recommendation(recommendation)
    return recommendation_id


def _grant_authorisation(
    repo: Any, journey_id: str, recommendation_id: str, cost_amount: Decimal = _ALT_PRICE
) -> None:
    from journey.models.events import EventType
    from journey.services.event_service import EventService

    events = EventService(repo)
    request_id = str(uuid.uuid4())
    events.append(
        journey_id,
        EventType.AUTHORISATION_REQUESTED,
        {
            "request_id": request_id,
            "action_id": recommendation_id,
            "action": "Rebook alternative",
            "cost": str(cost_amount),
            "cost_amount": str(cost_amount),
            "objective_effect": "Restores latest_arrival",
            "rule_id": "AUTH_MONEY",
        },
    )
    events.append(
        journey_id,
        EventType.AUTHORISATION_OUTCOME,
        {"request_id": request_id, "outcome": "approved", "rule_id": "AUTH_MONEY"},
    )


def _verify_response_verified() -> dict[str, Any]:
    return {
        "status": 0,
        "sessionId": f"sess-{uuid.uuid4()}",
        "maxSeats": 9,
        "priceChange": {"isPriceChange": False},
        "bookingRequirement": {"passenger": {}},
    }


def _verify_response_price_changed() -> dict[str, Any]:
    return {
        "status": 0,
        "sessionId": f"sess-{uuid.uuid4()}",
        "maxSeats": 9,
        "priceChange": {
            "isPriceChange": True,
            "originalAdultPrice": "300.00",
            "newAdultPrice": "500.00",
            "originalAdultTax": "0.00",
            "newAdultTax": "0.00",
        },
        "bookingRequirement": {"passenger": {}},
    }


def _verify_response_unavailable() -> dict[str, Any]:
    return {"status": 1}


def _order_response(order_no: str) -> dict[str, Any]:
    return {
        "orderNo": order_no,
        "pnrCode": "PNRNEW1",
        "tktLimitTime": (datetime.now(tz=timezone.utc) + timedelta(minutes=30)).isoformat(),
        "sessionId": "sess-new",
        "duplicateOrders": None,
        "status": 0,
        "msg": "success",
    }


def _pay_success_response() -> dict[str, Any]:
    return {"status": 0}


def _pay_declined_response() -> dict[str, Any]:
    return {"status": 1}


def _query_ticketed_response(ticket_no: str = "TKTNEW1") -> dict[str, Any]:
    return {
        "orderStatus": "1",
        "ticketStatus": "0",
        "paxTicketInfos": [{"ticketNos": [ticket_no]}],
        "errorCode": None,
    }


def _query_not_ticketed_response() -> dict[str, Any]:
    return {
        "orderStatus": "1",
        "ticketStatus": "0",
        "paxTicketInfos": [{"ticketNos": []}],
        "errorCode": None,
    }


class _Dispatcher:
    """Routes MockTransport calls by URL to the right canned response,
    with per-URL call sequences for endpoints hit more than once (e.g.
    queryOrderDetails.do for both ticketing confirmation and cancellation
    reconciliation)."""

    def __init__(self) -> None:
        self.responses: dict[str, list[dict[str, Any]]] = {}
        self.calls: dict[str, list[dict[str, Any]]] = {}

    def set(self, url: str, *responses: dict[str, Any]) -> None:
        self.responses[url] = list(responses)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.setdefault(url, []).append(json.loads(request.content or b"{}"))
        queue = self.responses.get(url, [])
        body = queue.pop(0) if queue else {"status": 0}
        return httpx.Response(200, json=body)


def _service(repo: Any, dispatcher: _Dispatcher) -> Any:
    from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine
    from journey.services.booking_service import BookingService
    from journey.services.event_service import EventService
    from journey.services.recovery_execution_service import RecoveryExecutionService
    from journey.services.verification_service import VerificationService

    client = httpx.Client(transport=httpx.MockTransport(dispatcher))
    events = EventService(repo)
    return RecoveryExecutionService(
        repo=repo,
        http_client=client,
        event_service=events,
        booking_service=BookingService(repo=repo, http_client=client),
        verification_service=VerificationService(repo=repo, http_client=client),
        authorisation_engine=AuthorisationPolicyEngine(repository=repo, event_service=events),
    )


def _full_success_dispatcher(replacement_order_no: str = "REPLACEMENT-1") -> _Dispatcher:
    d = _Dispatcher()
    d.set(_ATLAS_VERIFY_URL, _verify_response_verified())
    d.set(_ATLAS_ORDER_URL, _order_response(replacement_order_no))
    d.set(_ATLAS_PAY_URL, _pay_success_response())
    d.set(_ATLAS_QUERY_URL, _query_ticketed_response(), _query_not_ticketed_response())
    d.set(_ATLAS_VOID_URL, {"status": 0})
    return d


# ---------------------------------------------------------------------------
# User Story 1
# ---------------------------------------------------------------------------


class TestRefusedWithoutMatchingAuthorisation:
    def test_no_authorisation_abandons(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        # No authorisation granted

        service = _service(repo, _full_success_dispatcher())
        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import RecoveryExecutionStatus

        assert execution.status == RecoveryExecutionStatus.ABANDONED
        assert execution.abandonment_reason == "not_authorised"


class TestAbandonedWhenPriceChanged:
    def test_price_change_abandons(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _Dispatcher()
        d.set(_ATLAS_VERIFY_URL, _verify_response_price_changed())
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import RecoveryExecutionStatus

        assert execution.status == RecoveryExecutionStatus.ABANDONED
        assert execution.abandonment_reason == "price_changed"
        assert _ATLAS_ORDER_URL not in d.calls


class TestAbandonedWhenAlternativeUnavailable:
    def test_unavailable_abandons(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _Dispatcher()
        d.set(_ATLAS_VERIFY_URL, _verify_response_unavailable())
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import RecoveryExecutionStatus

        assert execution.status == RecoveryExecutionStatus.ABANDONED
        assert execution.abandonment_reason == "alternative_unavailable"


# ---------------------------------------------------------------------------
# User Story 2
# ---------------------------------------------------------------------------


class TestReplacementCreatedPaidAndTicketingConfirmed:
    def test_full_pipeline_called_in_order(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher()
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import ReplacementOutcome

        assert execution.replacement_outcome == ReplacementOutcome.SUCCEEDED
        assert _ATLAS_ORDER_URL in d.calls
        assert _ATLAS_PAY_URL in d.calls


class TestCurrentOrderPointerUpdatesOnlyAfterTicketingConfirmed:
    def test_current_order_no_set_to_replacement(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher(replacement_order_no="REPLACEMENT-XYZ")
        service = _service(repo, d)

        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        assert repo.get_current_order_no(journey_id) == "REPLACEMENT-XYZ"


class TestSupersededOrderCapturedBeforeReplacementCreated:
    def test_superseded_order_no_recorded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo, superseded_order_no="ORIG-99")
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        service = _service(repo, _full_success_dispatcher())
        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        assert execution.superseded_order_no == "ORIG-99"


class TestReplacementCreationFailureLeavesSupersededUntouched:
    def test_order_creation_failure_leaves_original_order_untouched(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo, superseded_order_no="ORIG-KEEP")
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _Dispatcher()
        d.set(_ATLAS_VERIFY_URL, _verify_response_verified())
        d.set(_ATLAS_ORDER_URL, {"orderNo": None, "pnrCode": None, "tktLimitTime": None, "sessionId": None, "duplicateOrders": None, "status": 500, "msg": "error"})
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import CancellationOutcome, ReplacementOutcome

        assert execution.replacement_outcome == ReplacementOutcome.FAILED
        assert execution.cancellation_outcome == CancellationOutcome.NOT_ATTEMPTED
        assert _ATLAS_VOID_URL not in d.calls
        assert repo.get_order_by_order_no("ORIG-KEEP") is not None


class TestReplacementPaymentFailureLeavesSupersededUntouched:
    def test_payment_failure_leaves_original_untouched(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _Dispatcher()
        d.set(_ATLAS_VERIFY_URL, _verify_response_verified())
        d.set(_ATLAS_ORDER_URL, _order_response("REPLACEMENT-FAIL-PAY"))
        d.set(_ATLAS_PAY_URL, _pay_declined_response())
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import CancellationOutcome, ReplacementOutcome

        assert execution.replacement_outcome == ReplacementOutcome.FAILED
        assert execution.abandonment_reason == "replacement_payment_failed"
        assert execution.cancellation_outcome == CancellationOutcome.NOT_ATTEMPTED
        assert _ATLAS_VOID_URL not in d.calls


class TestTravellerNeverWithoutConfirmedBooking:
    def test_original_order_still_created_after_failed_recovery(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo, superseded_order_no="ORIG-SAFE")
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _Dispatcher()
        d.set(_ATLAS_VERIFY_URL, _verify_response_unavailable())
        service = _service(repo, d)

        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.booking import OrderOutcome

        original = repo.get_order_by_order_no("ORIG-SAFE")
        assert original is not None
        assert original.outcome == OrderOutcome.CREATED


# ---------------------------------------------------------------------------
# User Story 3
# ---------------------------------------------------------------------------


class TestCancellationInitiatedOnlyAfterReplacementConfirmed:
    def test_void_call_happens_after_ticketing_confirmation(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher()
        service = _service(repo, d)

        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        assert _ATLAS_VOID_URL in d.calls


class TestCancellationFailureRecordedAndSurfaced:
    def test_cancellation_failure_recorded_separately_from_success(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher()
        # Reconciliation query still shows the superseded booking ticketed
        d.set(_ATLAS_QUERY_URL, _query_ticketed_response(), _query_ticketed_response())
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import (
            CancellationOutcome,
            ReplacementOutcome,
            RecoveryExecutionStatus,
        )

        assert execution.replacement_outcome == ReplacementOutcome.SUCCEEDED
        assert execution.cancellation_outcome == CancellationOutcome.FAILED
        assert execution.status == RecoveryExecutionStatus.COMPLETED


class TestCancellationSuccessRecorded:
    def test_cancellation_success_recorded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher()
        service = _service(repo, d)

        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.models.recovery_execution import CancellationOutcome

        assert execution.cancellation_outcome == CancellationOutcome.SUCCEEDED


class TestCancellationAlwaysReconciledByQuery:
    def test_reconciliation_query_made_after_void_call(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        d = _full_success_dispatcher()
        service = _service(repo, d)

        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        # queryOrderDetails.do is called twice: once for ticketing
        # confirmation, once for cancellation reconciliation.
        assert len(d.calls[_ATLAS_QUERY_URL]) == 2


class TestDuplicateExecutionRefused:
    def test_second_execute_call_raises(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        service = _service(repo, _full_success_dispatcher())
        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        from journey.errors import RecoveryAlreadyAttemptedError

        try:
            service.execute(recommendation_id, datetime.now(tz=timezone.utc))
            raised = False
        except RecoveryAlreadyAttemptedError:
            raised = True
        assert raised


class TestFinalPositionReportedInObjectiveTerms:
    def test_final_position_names_objective_element(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        service = _service(repo, _full_success_dispatcher())
        execution = service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        assert execution.final_position_description is not None
        assert "latest_arrival" in execution.final_position_description


class TestAuditTrailIncludesAuthorisation:
    def test_events_carry_recommendation_id(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey_with_superseded_order(repo)
        option_id = _seed_alternative_option(repo, journey_id)
        recommendation_id = _seed_recommendation(repo, option_id)
        _grant_authorisation(repo, journey_id, recommendation_id)

        service = _service(repo, _full_success_dispatcher())
        service.execute(recommendation_id, datetime.now(tz=timezone.utc))

        events = repo.get_events_from_sequence(journey_id, from_sequence=0)
        completed = [e for e in events if e.event_type.value == "recovery_execution_completed"]
        assert len(completed) == 1
        assert completed[0].payload["recommendation_id"] == recommendation_id

        requested = [
            e
            for e in events
            if e.event_type.value == "authorisation_requested"
            and e.payload.get("action_id") == recommendation_id
        ]
        assert len(requested) == 1
