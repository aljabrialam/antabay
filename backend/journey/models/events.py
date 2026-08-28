from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class EventType(str, Enum):
    EXTERNAL_CALL = "external_call"
    DECISION = "decision"
    STATE_CHANGE = "state_change"
    IDENTIFIER_ISSUED = "identifier_issued"
    IDENTIFIER_EXPIRED = "identifier_expired"
    CALL_BUDGET_UPDATED = "call_budget_updated"
    AUTHORISATION_REQUESTED = "authorisation_requested"
    AUTHORISATION_OUTCOME = "authorisation_outcome"
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
    EventType.OPTION_REJECTED: OptionRejectedPayload,
    EventType.OBJECTIVE_VIOLATED: ObjectiveViolatedPayload,
    EventType.OBJECTIVE_SET: ObjectiveSetPayload,
    EventType.REPLAY_STARTED: ReplayStartedPayload,
    EventType.REPLAY_ENDED: ReplayEndedPayload,
}


def payload_model_for(event_type: EventType) -> type[BaseModel]:
    """Return the Pydantic payload model class for an event type."""
    return _PAYLOAD_MODELS[event_type]


@dataclass
class JourneyEvent:
    event_id: str
    journey_id: str
    sequence: int
    event_type: EventType
    payload: dict[str, object]
    simulated: bool
    recorded_at: datetime
