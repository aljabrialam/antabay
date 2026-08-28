"""Contract test for WebhookService's on_wake wiring (T034).

Confirms confirm() and reconcile_active_journeys() both invoke on_wake
immediately after appending WAKE_REQUESTED (research.md R1), and that
existing behaviour is unaffected when on_wake is None.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'impact_evaluation_wiring.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey_with_order(repo: Any, order_no: str) -> str:
    from journey.models.booking import Order, OrderOutcome
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)

    now = datetime.now(tz=timezone.utc)
    order = Order(
        order_id=str(uuid.uuid4()),
        journey_id=journey.journey_id,
        option_id="opt-1",
        requested_at=now,
        responded_at=now,
        raw_response_json="{}",
        outcome=OrderOutcome.CREATED,
        order_no=order_no,
        booking_reference="PNR1",
        ticketing_deadline=None,
        session_id_used="sess-1",
    )
    repo.save_order(order)
    return journey.journey_id


class TestOnWakeFiresFromReconcile:
    def test_on_wake_invoked_for_each_active_journey(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from journey.services.webhook_service import WebhookService

        repo = _repo()
        journey_id = _seed_journey_with_order(repo, "ORDER-1")

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "orderNo": "ORDER-1",
                    "orderStatus": 2,
                    "paxTicketInfos": [{"ticketNos": ["TKT1"]}],
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        calls: list[tuple[str, Any]] = []

        service = WebhookService(
            repository=repo,
            http_client=client,
            on_wake=lambda jid, event: calls.append((jid, event)),
        )
        service.reconcile_active_journeys(datetime.now(tz=timezone.utc))

        assert len(calls) == 1
        assert calls[0][0] == journey_id
        assert calls[0][1].event_type.value == "wake_requested"

    def test_no_error_when_on_wake_is_none(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from journey.services.webhook_service import WebhookService

        repo = _repo()
        _seed_journey_with_order(repo, "ORDER-2")

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "orderNo": "ORDER-2",
                    "orderStatus": 2,
                    "paxTicketInfos": [{"ticketNos": ["TKT2"]}],
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        service = WebhookService(repository=repo, http_client=client)

        service.reconcile_active_journeys(datetime.now(tz=timezone.utc))  # must not raise


class TestOnWakeFiresFromConfirm:
    def test_on_wake_invoked_after_confirm_classifies(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        from journey.models.webhook import InboundNotification
        from journey.services.webhook_service import WebhookService

        repo = _repo()
        journey_id = _seed_journey_with_order(repo, "ORDER-3")

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "orderNo": "ORDER-3",
                    "orderStatus": 2,
                    "paxTicketInfos": [{"ticketNos": ["TKT3"]}],
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        calls: list[tuple[str, Any]] = []

        service = WebhookService(
            repository=repo,
            http_client=client,
            on_wake=lambda jid, event: calls.append((jid, event)),
        )

        envelope = {"cid": "<client id>", "type": "order.ticketed", "status": 0, "data": {"orderNo": "ORDER-3"}}
        notification = service.receive(json.dumps(envelope).encode("utf-8"), datetime.now(tz=timezone.utc))
        assert notification.confirmation_triggered is True

        service.confirm(notification)

        assert len(calls) == 1
        assert calls[0][0] == journey_id
