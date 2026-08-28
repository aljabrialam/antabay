from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from journey.models.objective import TravelObjective


class JourneyState(str, Enum):
    OBJECTIVE_CONFIRMED = "OBJECTIVE_CONFIRMED"
    # SEARCHING is reserved for a future feature (option-search capability)
    SEARCHING = "SEARCHING"
    # VERIFIED: a verify.do call has succeeded (with or without a reported
    # price change) for the journey's currently held option (spec 004).
    VERIFIED = "VERIFIED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"


class IdentifierFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"


class InvalidTransitionError(Exception):
    pass


_ALLOWED_TRANSITIONS: dict[JourneyState, set[JourneyState]] = {
    JourneyState.OBJECTIVE_CONFIRMED: {
        JourneyState.SEARCHING,
        JourneyState.CANCELLED,
        JourneyState.ABANDONED,
    },
    JourneyState.SEARCHING: {
        JourneyState.VERIFIED,
        JourneyState.CANCELLED,
        JourneyState.ABANDONED,
    },
    JourneyState.VERIFIED: {
        # FR-009 (004): an unavailable re-verification sends the journey back to search.
        JourneyState.SEARCHING,
        JourneyState.CANCELLED,
        JourneyState.ABANDONED,
    },
    JourneyState.CANCELLED: set(),
    JourneyState.ABANDONED: set(),
}


class JourneyStateMachine:
    def transition(self, from_state: JourneyState, to_state: JourneyState) -> None:
        if to_state not in _ALLOWED_TRANSITIONS.get(from_state, set()):
            raise InvalidTransitionError(
                f"Transition from {from_state.value} to {to_state.value} is not permitted"
            )


@dataclass
class AuditEntry:
    entry_id: str
    journey_id: str
    entry_type: str
    content: str
    recorded_at: datetime
    sequence: int


@dataclass
class HeldIdentifier:
    identifier_id: str
    journey_id: str
    value: str
    issued_at: datetime
    stale_after_seconds: int
    stale_at: datetime

    def is_stale(self, now: datetime) -> bool:
        return now >= self.stale_at


@dataclass
class AuthorisationOutcome:
    outcome_id: str
    journey_id: str
    request_desc: str
    outcome: str
    recorded_by: str
    timestamp: datetime


@dataclass
class JourneyRecord:
    journey_id: str
    state: JourneyState
    objective: TravelObjective  # confirmed parsed objective
    schema_version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    call_budget: int = 20
    audit_entries: list[AuditEntry] = field(default_factory=list)
    held_identifiers: list[HeldIdentifier] = field(default_factory=list)
    authorisation_outcomes: list[AuthorisationOutcome] = field(default_factory=list)


@dataclass
class JourneyDisplay:
    journey_id: str
    state: JourneyState
    objective: TravelObjective
    audit_trail: list[AuditEntry] = field(default_factory=list)
