from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from journey.models.events import EventType, JourneyEvent
from journey.models.journey import JourneyState
from journey.models.verification_gate import VerificationOutcome
from journey.models.webhook import InboundNotification
from journey.services.conditions.ticketing_condition import TicketingSuccessCondition
from journey.services.event_service import EventService
from journey.services.verification_gate import PostActionVerifier
from journey.storage.repository import JourneyRepository

# Same endpoint and request shape as BookingService._query_order() — reused
# at the contract level only, not as a shared import (research.md R2).
_ATLAS_QUERY_URL = "https://sandbox.atriptech.com/queryOrderDetails.do"

_EVENT_TYPE_HANDLERS: dict[str, str] = {
    "order.ticketed": "ticketing",
}

# Mirrors event_service.py's own _TERMINAL_STATES — not imported/shared,
# consistent with this codebase's existing convention of each service
# defining what it needs locally.
_TERMINAL_STATES = {JourneyState.CANCELLED, JourneyState.ABANDONED}

# FR-013: confirmation-query volume per journey is bounded within this
# window (also satisfies FR-009's duplicate tolerance — research.md R3).
_CONFIRMATION_BUDGET_WINDOW_SECONDS = 300


class WebhookService:
    def __init__(
        self,
        repository: JourneyRepository | None = None,
        http_client: httpx.Client | None = None,
        event_service: EventService | None = None,
        on_wake: Callable[[str, JourneyEvent], object] | None = None,
    ) -> None:
        self._repo = repository if repository is not None else JourneyRepository()
        self._http = http_client if http_client is not None else httpx.Client()
        self._events = event_service if event_service is not None else EventService(self._repo)
        self._verifier = PostActionVerifier(
            self._repo, {"ticketing": TicketingSuccessCondition()}
        )
        self._on_wake = on_wake

    def receive(
        self, raw_body: bytes, received_at: datetime, simulated: bool = False
    ) -> InboundNotification:
        declared_event_type = ""
        order_reference: str | None = None
        try:
            parsed = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            parsed = {}
        if isinstance(parsed, dict):
            declared_event_type = parsed.get("type") or ""
            data = parsed.get("data")
            if isinstance(data, dict):
                order_reference = data.get("orderNo")

        journey_id: str | None = None
        associated = False
        if order_reference is not None:
            order = self._repo.get_order_by_order_no(order_reference)
            if order is not None:
                journey_id = order.journey_id
                associated = True

        confirmation_triggered = (
            associated
            and journey_id is not None
            and declared_event_type in _EVENT_TYPE_HANDLERS
            and self._repo.get_journey(journey_id).state not in _TERMINAL_STATES
            and order_reference is not None
            and not self._within_confirmation_budget_window(order_reference, received_at)
        )

        notification = InboundNotification(
            notification_id=str(uuid.uuid4()),
            received_at=received_at,
            declared_event_type=declared_event_type,
            order_reference=order_reference,
            raw_payload_json=raw_body.decode("utf-8", errors="replace"),
            journey_id=journey_id,
            associated=associated,
            confirmation_triggered=confirmation_triggered,
            simulated=simulated,
        )
        self._repo.save_notification(notification)
        return notification

    def confirm(self, notification: InboundNotification) -> None:
        assert notification.journey_id is not None
        assert notification.order_reference is not None
        order_reference = notification.order_reference
        action_type = _EVENT_TYPE_HANDLERS[notification.declared_event_type]
        action_response = self._extract_claim(notification)

        def _query_fn() -> tuple[Any, datetime]:
            return self._query_order_details(order_reference)

        attempt = self._verifier.verify(
            journey_id=notification.journey_id,
            action_type=action_type,
            affected_record_id=order_reference,
            query_fn=_query_fn,
            now=datetime.now(tz=timezone.utc),
            action_response=action_response,
        )

        if attempt.classification in (VerificationOutcome.SUCCESS, VerificationOutcome.FAILURE):
            wake_event = self._events.append(
                notification.journey_id,
                EventType.WAKE_REQUESTED,
                {
                    "order_reference": order_reference,
                    "declared_event_type": notification.declared_event_type,
                    "classification": attempt.classification.value,
                },
                simulated=notification.simulated,
            )
            if self._on_wake is not None:
                self._on_wake(notification.journey_id, wake_event)

    def _extract_claim(self, notification: InboundNotification) -> Any:
        parsed = json.loads(notification.raw_payload_json)
        return parsed.get("data")

    def _query_order_details(self, order_no: str) -> tuple[Any, datetime]:
        response = self._http.post(
            _ATLAS_QUERY_URL,
            json={"cid": "<client id>", "orderNo": order_no, "requestSource": "antabay"},
        )
        return response.json(), datetime.now(tz=timezone.utc)

    def _within_confirmation_budget_window(self, order_reference: str, now: datetime) -> bool:
        """True if a confirmation for this order was already triggered, or
        already completed, within the window. Both sources are checked:
        `confirm()` runs as a background task, so a burst of `receive()`
        calls arriving before the first `confirm()` completes would have
        no VerificationAttempt yet to compare against — checking prior
        notifications' `confirmation_triggered` flag catches that case."""
        window = timedelta(seconds=_CONFIRMATION_BUDGET_WINDOW_SECONDS)

        attempts = self._repo.get_verification_attempts(order_reference)
        if attempts and (now - attempts[-1].observed_at) < window:
            return True

        prior_triggers = [
            n for n in self._repo.get_notifications_for_order(order_reference)
            if n.confirmation_triggered
        ]
        if prior_triggers and (now - prior_triggers[-1].received_at) < window:
            return True

        return False

    def reconcile_active_journeys(self, now: datetime) -> None:
        for journey_id, order_no in self._repo.get_active_journeys_with_order_reference():
            if self._within_confirmation_budget_window(order_no, now):
                continue

            action_type = _EVENT_TYPE_HANDLERS["order.ticketed"]

            def _query_fn(order_no: str = order_no) -> tuple[Any, datetime]:
                return self._query_order_details(order_no)

            attempt = self._verifier.verify(
                journey_id=journey_id,
                action_type=action_type,
                affected_record_id=order_no,
                query_fn=_query_fn,
                now=now,
            )

            if attempt.classification in (VerificationOutcome.SUCCESS, VerificationOutcome.FAILURE):
                wake_event = self._events.append(
                    journey_id,
                    EventType.WAKE_REQUESTED,
                    {
                        "order_reference": order_no,
                        "declared_event_type": "reconciliation_sweep",
                        "classification": attempt.classification.value,
                    },
                )
                if self._on_wake is not None:
                    self._on_wake(journey_id, wake_event)
