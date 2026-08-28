"""Unit tests for WebhookService (T008-T009, T016-T020, T025-T029, T034-T036).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'webhook_service.db'}"
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
    from decimal import Decimal

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


def _envelope(order_no: str = "TESTA20260815180326173", status: int = -1) -> bytes:
    """Matches the real captured shape (.antabay/atlas-capability-map.md §7c)."""
    body = {
        "cid": "<client id>",
        "type": "order.ticketed",
        "status": status,
        "data": {
            "orderNo": order_no,
            "orderStatus": 2,
            "paxTicketInfos": [
                {"name": "TEST/ONE", "airlinePNRs": ["S46659"], "ticketNos": ["S46659"]}
            ],
        },
    }
    return json.dumps(body).encode("utf-8")


class _RaisingHTTPClient:
    def post(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("receive() must never call the provider (FR-001, NFR-001)")


def _service(repo: Any, http_client: Any = None) -> Any:
    from journey.services.webhook_service import WebhookService

    return WebhookService(repository=repo, http_client=http_client)


def _associated_notification(
    journey_id: str, order_no: str = "TESTA20260815180326173", raw_body: bytes | None = None
) -> Any:
    """Constructs an already-associated InboundNotification directly, so
    confirm() can be tested in isolation from receive()'s routing/
    association logic (US3), which confirm() itself does not depend on."""
    import uuid

    from journey.models.webhook import InboundNotification

    return InboundNotification(
        notification_id=str(uuid.uuid4()),
        received_at=datetime.now(tz=timezone.utc),
        declared_event_type="order.ticketed",
        order_reference=order_no,
        raw_payload_json=(raw_body or _envelope(order_no=order_no)).decode("utf-8"),
        journey_id=journey_id,
        associated=True,
        confirmation_triggered=True,
    )


class TestReceivePersistsFullRawPayload:
    def test_exact_raw_body_is_persisted(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        raw_body = _envelope()

        notification = service.receive(raw_body, datetime.now(tz=timezone.utc))

        stored = repo.get_notifications_for_order("TESTA20260815180326173")
        assert len(stored) == 1
        assert stored[0].raw_payload_json == raw_body.decode("utf-8")
        assert stored[0].notification_id == notification.notification_id
        assert notification.received_at is not None


class TestReceiveNeverCallsTheProvider:
    def test_no_network_call_during_receive(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo, http_client=_RaisingHTTPClient())

        service.receive(_envelope(), datetime.now(tz=timezone.utc))


class TestConfirmDerivesFromQueryNotClaim:
    def test_classification_follows_query_not_claim(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        notification = _associated_notification(journey_id)

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {
                    "orderStatus": "1",
                    "paxTicketInfos": [{"ticketNos": []}],
                    "errorCode": None,
                },
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert len(attempts) == 1
        assert attempts[0].classification is VerificationOutcome.UNRESOLVED


class TestConfirmIgnoresStatusField:
    def test_status_field_never_read_as_signal(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        # status=-1, matching the real capture, on an envelope claiming ticketed
        notification = _associated_notification(journey_id, raw_body=_envelope(status=-1))

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {
                    "orderStatus": "2",
                    "paxTicketInfos": [{"ticketNos": ["S46659"]}],
                    "errorCode": None,
                },
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert attempts[0].classification is VerificationOutcome.SUCCESS


class TestConfirmRecordsDiscrepancyWhenClaimDisagrees:
    def test_discrepancy_recorded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        # claim (webhook data.orderStatus) is int 2 ("ticketed")
        notification = _associated_notification(journey_id)

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {
                    "orderStatus": "1",  # query disagrees: not yet ticketed
                    "paxTicketInfos": [{"ticketNos": []}],
                    "errorCode": None,
                },
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert attempts[0].has_discrepancy is True


class TestNoWakeWhileUnresolved:
    def test_no_wake_event_when_unresolved(self, tmp_path: Any) -> None:
        from journey.models.events import EventType

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        notification = _associated_notification(journey_id)

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {"orderStatus": "1", "paxTicketInfos": [{"ticketNos": []}], "errorCode": None},
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        events = repo.get_events_from_sequence(journey_id, 0)
        wake_events = [e for e in events if e.event_type is EventType.WAKE_REQUESTED]
        assert wake_events == []


class TestWakeAfterConfirmedOutcome:
    def test_wake_event_appended_on_resolved_outcome(self, tmp_path: Any) -> None:
        from journey.models.events import EventType

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        notification = _associated_notification(journey_id)

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {
                    "orderStatus": "2",
                    "paxTicketInfos": [{"ticketNos": ["S46659"]}],
                    "errorCode": None,
                },
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        events = repo.get_events_from_sequence(journey_id, 0)
        wake_events = [e for e in events if e.event_type is EventType.WAKE_REQUESTED]
        assert len(wake_events) == 1
        assert wake_events[0].payload["order_reference"] == "TESTA20260815180326173"
        assert wake_events[0].payload["classification"] == "SUCCESS"


class TestKnownTypeAndOrderTriggersConfirmation:
    def test_associated_and_triggered(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        notification = service.receive(_envelope(), datetime.now(tz=timezone.utc))

        assert notification.associated is True
        assert notification.journey_id == journey_id
        assert notification.confirmation_triggered is True


class TestUnknownOrderReferenceDiscarded:
    def test_discarded_without_side_effect(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        _seed_journey(repo)  # no order seeded for this order_no
        service = _service(repo)

        notification = service.receive(_envelope(order_no="UNKNOWN-ORDER"), datetime.now(tz=timezone.utc))

        assert notification.associated is False
        assert notification.journey_id is None
        assert notification.confirmation_triggered is False


class TestUnrecognisedEventTypeIsInert:
    def test_no_confirmation_for_unregistered_type(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        body = json.dumps(
            {
                "cid": "<client id>",
                "type": "schedule.changed",
                "status": 0,
                "data": {"orderNo": "TESTA20260815180326173"},
            }
        ).encode("utf-8")

        notification = service.receive(body, datetime.now(tz=timezone.utc))

        assert notification.associated is True
        assert notification.confirmation_triggered is False


class TestTerminalJourneySkipsConfirmation:
    def test_no_confirmation_for_terminal_journey(self, tmp_path: Any) -> None:
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

        notification = service.receive(_envelope(), datetime.now(tz=timezone.utc))

        assert notification.associated is True
        assert notification.confirmation_triggered is False


class TestStatusTypeNormalisationFlowsThroughEndToEnd:
    def test_no_false_discrepancy_through_full_service_path(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        # webhook claims orderStatus int 2
        notification = service.receive(_envelope(), datetime.now(tz=timezone.utc))

        def _query_fn(order_no: str) -> tuple[Any, datetime]:
            return (
                {
                    "orderStatus": "2",  # same status, different type
                    "paxTicketInfos": [{"ticketNos": ["S46659"]}],
                    "errorCode": None,
                },
                datetime.now(tz=timezone.utc),
            )

        service._query_order_details = _query_fn  # type: ignore[method-assign]
        service.confirm(notification)

        attempts = repo.get_verification_attempts("TESTA20260815180326173")
        assert attempts[0].has_discrepancy is False


class TestDuplicateBurstCollapsesToOneConfirmation:
    def test_five_identical_notifications_trigger_once(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        raw_body = _envelope()

        triggered = [
            service.receive(raw_body, datetime.now(tz=timezone.utc)).confirmation_triggered
            for _ in range(5)
        ]

        assert triggered == [True, False, False, False, False]


class TestDistinctNotificationBurstCollapsesToo:
    def test_five_distinct_notifications_trigger_once(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        triggered = [
            service.receive(
                _envelope(status=-1 - i), datetime.now(tz=timezone.utc)
            ).confirmation_triggered
            for i in range(5)
        ]

        assert triggered == [True, False, False, False, False]


class TestOutsideWindowTriggersFreshConfirmation:
    def test_stale_attempt_does_not_absorb_new_notification(self, tmp_path: Any) -> None:
        import uuid

        from journey.models.verification_gate import (
            ConditionResult,
            VerificationAttempt,
            VerificationOutcome,
        )

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        repo.save_verification_attempt(
            VerificationAttempt(
                attempt_id=str(uuid.uuid4()),
                journey_id=journey_id,
                action_type="ticketing",
                affected_record_id="TESTA20260815180326173",
                action_response_json=None,
                queried_at=old_time,
                observed_at=old_time,
                query_result_json="{}",
                classification=VerificationOutcome.UNRESOLVED,
                condition_result=ConditionResult.INCONCLUSIVE,
                has_discrepancy=False,
                applied_to_state=False,
            )
        )
        service = _service(repo)

        notification = service.receive(_envelope(), datetime.now(tz=timezone.utc))

        assert notification.confirmation_triggered is True
