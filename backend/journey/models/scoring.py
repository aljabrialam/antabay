"""Scoring output models for feature 003-option-scoring.

All dataclasses are frozen (immutable) and carry no database dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from journey.models.flight import FlightOption
from journey.models.objective import TravelObjective


class ScoringOutcome(str, Enum):
    SELECTED = "SELECTED"
    ELIMINATED = "ELIMINATED"
    RANKED = "RANKED"


@dataclass(frozen=True)
class EliminationRecord:
    option_id: str
    reason_code: str
    reason_detail: str
    constraint_id: str | None


@dataclass(frozen=True)
class Rationale:
    option_id: str
    objective_elements: list[str]
    summary: str
    arrival_margin_minutes: int | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class RejectionReason:
    option_id: str
    reason_code: str
    reason_detail: str


@dataclass(frozen=True)
class ConnectionEvaluation:
    option_id: str
    connection_times: list[int]
    connection_excluded: bool
    exclusion_rule: str | None
    impossible_connections: list[int]


@dataclass(frozen=True)
class NoSatisfyingOptionReport:
    unsatisfied_constraints: list[str]
    eliminated_count: int
    summary: str


@dataclass(frozen=True)
class ScoredOption:
    option: FlightOption
    outcome: ScoringOutcome
    rank: int | None
    rationale: Rationale | None
    elimination: EliminationRecord | None
    rejection_reason: RejectionReason | None
    connection_eval: ConnectionEvaluation | None


@dataclass(frozen=True)
class ScoringRun:
    run_id: str
    objective: TravelObjective
    evaluated_at: datetime
    scored_options: list[ScoredOption]
    selected_option: ScoredOption | None
    no_satisfying_option: NoSatisfyingOptionReport | None
