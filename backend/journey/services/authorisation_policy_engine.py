from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal, cast

from journey.models.authorisation_policy import (
    AuthorisationDecision,
    ProposedAction,
    Rule,
)
from journey.models.events import EventType, JourneyEvent
from journey.services.event_service import EventService
from journey.storage.repository import JourneyRepository


class AuthorisationPolicyEngine:
    def __init__(
        self,
        repository: JourneyRepository | None = None,
        event_service: EventService | None = None,
    ) -> None:
        self._repo = repository if repository is not None else JourneyRepository()
        self._events = event_service if event_service is not None else EventService(self._repo)

    def evaluate(self, action: ProposedAction) -> AuthorisationDecision:
        matched: list[Rule] = []
        if action.cost_amount > 0:
            matched.append(Rule.AUTH_MONEY)
        if action.cancels_or_voids_booking:
            matched.append(Rule.AUTH_CANCEL)
        if not action.is_reversible:
            matched.append(Rule.AUTH_IRREVERSIBLE)
        if action.breaches_hard_constraint:
            matched.append(Rule.AUTH_CONSTRAINT)

        classification: Literal["permitted_autonomously", "requires_authorisation"] = (
            "requires_authorisation" if matched else "permitted_autonomously"
        )
        return AuthorisationDecision(
            action_id=action.action_id,
            classification=classification,
            matched_rules=[rule.value for rule in matched],
        )

    def request_if_required(
        self, journey_id: str, action: ProposedAction
    ) -> AuthorisationDecision:
        decision = self.evaluate(action)
        if decision.classification == "permitted_autonomously":
            return decision

        if self.enforce_authorised(journey_id, action.action_id, action.cost_amount):
            return decision

        self._events.append(
            journey_id,
            EventType.AUTHORISATION_REQUESTED,
            {
                "request_id": str(uuid.uuid4()),
                "action_id": action.action_id,
                "action": action.description,
                "cost": action.cost_description,
                "cost_amount": str(action.cost_amount),
                "objective_effect": action.objective_effect,
                "rule_id": "+".join(decision.matched_rules),
            },
        )
        return decision

    def enforce_authorised(
        self, journey_id: str, action_id: str, current_cost_amount: Decimal
    ) -> bool:
        events = self._repo.get_events_from_sequence(journey_id, 0)
        requested = self._latest_request_for(events, action_id)
        if requested is None:
            return False

        request_id = cast(str, requested.payload["request_id"])
        outcome = self._outcome_for(events, request_id)
        if outcome is None or outcome.payload["outcome"] != "approved":
            return False

        granted_cost_amount = requested.payload.get("cost_amount")
        if granted_cost_amount is not None and Decimal(
            cast(str, granted_cost_amount)
        ) != current_cost_amount:
            if self._voided_for(events, request_id) is None:
                self._events.append(
                    journey_id,
                    EventType.AUTHORISATION_VOIDED,
                    {
                        "request_id": request_id,
                        "granted_cost": granted_cost_amount,
                        "current_cost": str(current_cost_amount),
                    },
                )
            return False

        return True

    def _latest_request_for(
        self, events: list[JourneyEvent], action_id: str
    ) -> JourneyEvent | None:
        matching = [
            e
            for e in events
            if e.event_type is EventType.AUTHORISATION_REQUESTED
            and e.payload.get("action_id") == action_id
        ]
        return matching[-1] if matching else None

    def _outcome_for(
        self, events: list[JourneyEvent], request_id: str
    ) -> JourneyEvent | None:
        matching = [
            e
            for e in events
            if e.event_type is EventType.AUTHORISATION_OUTCOME
            and e.payload.get("request_id") == request_id
        ]
        return matching[-1] if matching else None

    def _voided_for(
        self, events: list[JourneyEvent], request_id: str
    ) -> JourneyEvent | None:
        matching = [
            e
            for e in events
            if e.event_type is EventType.AUTHORISATION_VOIDED
            and e.payload.get("request_id") == request_id
        ]
        return matching[-1] if matching else None
