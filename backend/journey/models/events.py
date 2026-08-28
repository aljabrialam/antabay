from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from journey.models.objective import TravelObjective


class EventType(str, Enum):
    EXTERNAL_CALL = "external_call"
    DECISION = "decision"
    STATE_CHANGE = "state_change"
    IDENTIFIER_ISSUED = "identifier_issued"
    IDENTIFIER_EXPIRED = "identifier_expired"
    CALL_BUDGET_UPDATED = "call_budget_updated"
    AUTHORISATION_REQUESTED = "authorisation_requested"
    AUTHORISATION_OUTCOME = "authorisation_outcome"
    AUTHORISATION_VOIDED = "authorisation_voided"
    WAKE_REQUESTED = "wake_requested"
    OPTION_REJECTED = "option_rejected"
    OBJECTIVE_VIOLATED = "objective_violated"
    OBJECTIVE_SET = "objective_set"
    REPLAY_STARTED = "replay_started"
    REPLAY_ENDED = "replay_ended"


class ObjectiveConstraint(BaseModel):
    field: str
    value: str


class ExternalCallPayload(BaseModel):
    endpoint: str
    outcome: str
    elapsed_ms: int


class DecisionPayload(BaseModel):
    description: str
    reason: str


class StateChangePayload(BaseModel):
    from_state: str
    to_state: str


class IdentifierIssuedPayload(BaseModel):
    identifier_id: str
    value: str
    stale_after_seconds: int
    stale_at: str


class IdentifierExpiredPayload(BaseModel):
    identifier_id: str


class CallBudgetUpdatedPayload(BaseModel):
    budget_remaining: int


class AuthorisationRequestedPayload(BaseModel):
    request_id: str
    action: str
    cost: str
    objective_effect: str
    rule_id: str
    action_id: str | None = None
    cost_amount: str | None = None


class AuthorisationVoidedPayload(BaseModel):
    request_id: str
    granted_cost: str
    current_cost: str


class WakeRequestedPayload(BaseModel):
    order_reference: str
    declared_event_type: str
    classification: Literal["SUCCESS", "FAILURE"]


class AuthorisationOutcomePayload(BaseModel):
    request_id: str
    outcome: Literal["approved", "refused"]
    rule_id: str


class OptionRejectedPayload(BaseModel):
    option_id: str
    constraint_violated: str
    satisfies_numeric_constraints: bool


class ObjectiveViolatedPayload(BaseModel):
    description: str
    violated_constraints: list[str]


class ObjectiveSetPayload(BaseModel):
    hard_constraints: list[ObjectiveConstraint]
    preferences: list[ObjectiveConstraint]


class ReplayStartedPayload(BaseModel):
    source_journey_id: str
    speed_multiplier: float


class ReplayEndedPayload(BaseModel):
    pass


_PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.EXTERNAL_CALL: ExternalCallPayload,
    EventType.DECISION: DecisionPayload,
    EventType.STATE_CHANGE: StateChangePayload,
    EventType.IDENTIFIER_ISSUED: IdentifierIssuedPayload,
    EventType.IDENTIFIER_EXPIRED: IdentifierExpiredPayload,
    EventType.CALL_BUDGET_UPDATED: CallBudgetUpdatedPayload,
    EventType.AUTHORISATION_REQUESTED: AuthorisationRequestedPayload,
    EventType.AUTHORISATION_OUTCOME: AuthorisationOutcomePayload,
    EventType.AUTHORISATION_VOIDED: AuthorisationVoidedPayload,
    EventType.WAKE_REQUESTED: WakeRequestedPayload,
    EventType.OPTION_REJECTED: OptionRejectedPayload,
    EventType.OBJECTIVE_VIOLATED: ObjectiveViolatedPayload,
    EventType.OBJECTIVE_SET: ObjectiveSetPayload,
    EventType.REPLAY_STARTED: ReplayStartedPayload,
    EventType.REPLAY_ENDED: ReplayEndedPayload,
}


def payload_model_for(event_type: EventType) -> type[BaseModel]:
    """Return the Pydantic payload model class for an event type."""
    return _PAYLOAD_MODELS[event_type]


def objective_set_payload_from(objective: "TravelObjective") -> dict[str, object]:
    """Build an ObjectiveSetPayload dict from a TravelObjective (FR-001).

    Each scalar field is bucketed by its own `constraint_type` (a field can
    be a hard constraint or a preference independently of any other field);
    `preferences` carries a list of free-text strings that are always
    bucketed as preferences. Callers append the result via
    `EventService.append(journey_id, EventType.OBJECTIVE_SET, payload)`
    after the journey has been created.
    """
    from journey.models.objective import ConstraintType

    hard_constraints: list[dict[str, str]] = []
    preferences: list[dict[str, str]] = []

    def _bucket(constraint_type: ConstraintType) -> list[dict[str, str]]:
        return hard_constraints if constraint_type is ConstraintType.HARD else preferences

    if objective.origin is not None:
        _bucket(objective.origin.constraint_type).append(
            {"field": "origin", "value": str(objective.origin.value)}
        )
    if objective.destination is not None:
        _bucket(objective.destination.constraint_type).append(
            {"field": "destination", "value": str(objective.destination.value)}
        )
    if objective.latest_arrival is not None:
        _bucket(objective.latest_arrival.constraint_type).append(
            {"field": "latest_arrival", "value": str(objective.latest_arrival.value)}
        )
    if objective.departure_date is not None:
        _bucket(objective.departure_date.constraint_type).append(
            {"field": "departure_date", "value": str(objective.departure_date.value)}
        )
    if objective.budget_amount is not None and objective.budget_currency is not None:
        _bucket(objective.budget_amount.constraint_type).append(
            {
                "field": "budget",
                "value": f"{objective.budget_currency.value} {objective.budget_amount.value}",
            }
        )
    if objective.pax_count is not None:
        _bucket(objective.pax_count.constraint_type).append(
            {"field": "pax_count", "value": str(objective.pax_count.value)}
        )
    if objective.preferences is not None:
        bucket = _bucket(objective.preferences.constraint_type)
        for item in objective.preferences.value:
            bucket.append({"field": "preference", "value": item})

    return {"hard_constraints": hard_constraints, "preferences": preferences}


@dataclass
class JourneyEvent:
    event_id: str
    journey_id: str
    sequence: int
    event_type: EventType
    payload: dict[str, object]
    simulated: bool
    recorded_at: datetime
