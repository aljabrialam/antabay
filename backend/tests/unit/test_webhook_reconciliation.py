"""Unit tests for WebhookService.reconcile_active_journeys() (T037-T040).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'webhook_reconciliation.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey(repo: Any) -> str:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    return JourneyService(repository=repo).create_journey(objective).journey_id


def _seed_order(repo: Any, journey_id: str, order_no: str) -> None:
    from journey.models.booking import Order, OrderOutcome

    order = Order(
        order_id="order-1",
        journey_id=journey_id,
        option_id="option-1",
        requested_at=datetime.now(tz=timezone.utc),
        responded_at=datetime.now(tz=timezone.utc),
        raw_response_json="{}",
        outcome=OrderOutcome.CREATED,
        order_no=order_no,
        booking_reference="PNR123",
        ticketing_deadline=None,
        session_id_used="session-1",
    )
    repo.save_order(order)


def _service(repo: Any) -> Any:
    from journey.services.webhook_service import WebhookService

    return WebhookService(repository=repo)


class _StubQuery:
    def __init__(self, result: Any) -> None:
        self._result = result

    def __call__(self, order_no: str) -> tuple[Any, datetime]:
        return self._result, datetime.now(tz=timezone.utc)


class TestReconciliationCoversJourneyWithNoNotificationHistory:
    def test_sweep_confirms_journey_with_no_prior_notifications(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        service._query_order_details = _StubQuery(  # type: ignore[method-assign]
            {"orderStatus": "2", "paxTicketInfos": [{"ticketNos": ["S46659"]}], "errorCode": None}
        )

        service.reconcile_active_journeys(datetime.now(tz=timezone.utc))

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert len(attempts) == 1


class TestReconciliationSkipsTerminalJourneys:
    def test_sweep_does_not_confirm_cancelled_journey(self, tmp_path: Any) -> None:
        from journey.models.journey import JourneyState
        from journey.services.state_service import JourneyStateService

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        JourneyStateService(repository=repo).transition(
            journey_id, JourneyState.CANCELLED, reason="test"
        )
        service = _service(repo)
        service._query_order_details = _StubQuery(  # type: ignore[method-assign]
            {"orderStatus": "2", "paxTicketInfos": [{"ticketNos": ["S46659"]}], "errorCode": None}
        )

        service.reconcile_active_journeys(datetime.now(tz=timezone.utc))

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert attempts == []


class TestReconciliationRespectsTheSameThrottle:
    def test_sweep_skips_recently_confirmed_journey(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        service._query_order_details = _StubQuery(  # type: ignore[method-assign]
            {"orderStatus": "1", "paxTicketInfos": [{"ticketNos": []}], "errorCode": None}
        )
        from journey.models.webhook import InboundNotification

        notification = InboundNotification(
            notification_id="n1",
            received_at=datetime.now(tz=timezone.utc),
            declared_event_type="order.ticketed",
            order_reference="TESTA20260815180326173",
            raw_payload_json='{"data": {"orderNo": "TESTA20260815180326173"}}',
            journey_id=journey_id,
            associated=True,
            confirmation_triggered=True,
        )
        service.confirm(notification)
        assert len(repo.get_verification_attempts("TESTA20260815180326173")) == 1

        service.reconcile_active_journeys(datetime.now(tz=timezone.utc))

        assert len(repo.get_verification_attempts("TESTA20260815180326173")) == 1
