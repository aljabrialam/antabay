"""Unit tests for DisruptionInjectorService (T009-T014, T018-T020, T024,
T028).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'disruption_injector.db'}"
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
    from journey.services.disruption_injector_service import DisruptionInjectorService
    from journey.services.webhook_service import WebhookService

    return DisruptionInjectorService(repository=repo, webhook_service=WebhookService(repository=repo))


class TestEnvelopeStructureConformsToObservedShape:
    def test_top_level_keys_match_observed_convention(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        notification = service.inject(
            journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
        )

        envelope = json.loads(notification.raw_payload_json)
        assert set(envelope.keys()) == {"cid", "type", "status", "data"}


class TestEnvelopeReferencesRealOrderUnmodified:
    def test_order_no_matches_seeded_order_exactly(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        notification = service.inject(
            journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
        )

        envelope = json.loads(notification.raw_payload_json)
        assert envelope["data"]["orderNo"] == "TESTA20260815180326173"


class TestEnvelopeCarriesSpecifiedRevisedTime:
    def test_revised_arrival_time_matches_exactly(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        revised = datetime(2026, 9, 1, 14, 30, tzinfo=timezone.utc)

        notification = service.inject(journey_id, revised, datetime.now(tz=timezone.utc))

        envelope = json.loads(notification.raw_payload_json)
        assert envelope["data"]["revisedArrivalTime"] == revised.isoformat()


class TestNoTravelDataFabricated:
    def test_data_object_contains_only_order_and_time(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        notification = service.inject(
            journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
        )

        envelope = json.loads(notification.raw_payload_json)
        assert set(envelope["data"].keys()) == {"orderNo", "revisedArrivalTime"}


class TestNonexistentJourneyRejected:
    def test_journey_not_found_error_raised(self, tmp_path: Any) -> None:
        from journey.errors import JourneyNotFoundError

        _file_db(tmp_path)
        repo = _repo()
        service = _service(repo)

        try:
            service.inject(
                "does-not-exist", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
            )
            assert False, "expected JourneyNotFoundError"
        except JourneyNotFoundError:
            pass


class TestJourneyWithNoOrderRejected:
    def test_journey_has_no_order_error_raised(self, tmp_path: Any) -> None:
        from journey.errors import JourneyHasNoOrderError

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        service = _service(repo)

        try:
            service.inject(
                journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
            )
            assert False, "expected JourneyHasNoOrderError"
        except JourneyHasNoOrderError:
            pass


class TestDeliveredViaSameReceptionPath:
    def test_routing_and_association_match_webhook_service_rules(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        notification = service.inject(
            journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
        )

        assert notification.associated is True
        assert notification.journey_id == journey_id
        # "schedule.changed" has no registered confirmation handler yet
        # (research.md R4) — this is 007's own rule, unmodified.
        assert notification.confirmation_triggered is False


class TestMarkedSimulatedPermanently:
    def test_simulated_flag_persists_across_reads(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        service.inject(journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc))

        first_read = repo.get_notifications_for_order("TESTA20260815180326173")
        second_read = repo.get_notifications_for_order("TESTA20260815180326173")
        assert first_read[0].simulated is True
        assert second_read[0].simulated is True


class TestRealNotificationIndependentOfSimulatedOne:
    def test_real_notification_unaffected_by_simulated_one(self, tmp_path: Any) -> None:
        from journey.services.webhook_service import WebhookService

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)
        service.inject(journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc))

        real_body = json.dumps(
            {
                "cid": "<client id>",
                "type": "order.ticketed",
                "status": -1,
                "data": {"orderNo": "TESTA20260815180326173", "orderStatus": 2},
            }
        ).encode("utf-8")
        real_notification = WebhookService(repository=repo).receive(
            real_body, datetime.now(tz=timezone.utc)
        )

        assert real_notification.associated is True
        assert real_notification.confirmation_triggered is True
        assert real_notification.simulated is False


class TestWakeEventCarriesSimulatedFlag:
    def test_wake_event_from_injected_notification_is_marked_simulated(self, tmp_path: Any) -> None:
        from journey.models.events import EventType
        from journey.models.verification_gate import ConditionResult, ReconciliationBound
        from journey.services import webhook_service as webhook_service_module

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        _seed_order(repo, journey_id, "TESTA20260815180326173")
        service = _service(repo)

        class _StubScheduleChangeCondition:
            def classify(self, query_result: Any) -> Any:
                return ConditionResult.SUCCESS

            def has_discrepancy(self, action_response: Any, query_result: Any) -> bool:
                return False

            def reconciliation_bound(self) -> Any:
                return ReconciliationBound(max_attempts=1)

        # Test-only registration — no production handler exists for
        # schedule-change confirmation yet (research.md R4).
        original_handlers = dict(webhook_service_module._EVENT_TYPE_HANDLERS)
        webhook_service_module._EVENT_TYPE_HANDLERS["schedule.changed"] = "schedule_changed"
        service._webhook_service._verifier._conditions["schedule_changed"] = _StubScheduleChangeCondition()
        service._webhook_service._query_order_details = lambda order_no: (  # type: ignore[method-assign]
            {}, datetime.now(tz=timezone.utc)
        )
        try:
            notification = service.inject(
                journey_id, datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
            )
            assert notification.confirmation_triggered is True

            events = repo.get_events_from_sequence(journey_id, 0)
            wake_events = [e for e in events if e.event_type is EventType.WAKE_REQUESTED]
            assert len(wake_events) == 1
            assert wake_events[0].simulated is True
        finally:
            webhook_service_module._EVENT_TYPE_HANDLERS.clear()
            webhook_service_module._EVENT_TYPE_HANDLERS.update(original_handlers)


class TestDisabledInjectorRejectsInjection:
    def test_disabled_check_happens_before_journey_lookup(self, tmp_path: Any) -> None:
        from journey.errors import InjectorDisabledError
        from journey.services.disruption_injector_service import DisruptionInjectorService
        from journey.services.webhook_service import WebhookService

        _file_db(tmp_path)
        repo = _repo()

        class _RaisingRepo:
            def get_journey(self, journey_id: str) -> Any:
                raise AssertionError("journey lookup must not happen when disabled")

        service = DisruptionInjectorService(
            repository=_RaisingRepo(),  # type: ignore[arg-type]
            webhook_service=WebhookService(repository=repo),
            enabled=False,
        )

        try:
            service.inject(
                "any-journey", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime.now(tz=timezone.utc)
            )
            assert False, "expected InjectorDisabledError"
        except InjectorDisabledError:
            pass
