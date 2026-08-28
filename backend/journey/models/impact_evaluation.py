"""Impact evaluation output models for feature 009-impact-evaluation.

All dataclasses are plain (mutable) unlike scoring's frozen dataclasses,
since an ImpactEvaluation is a durable record whose status/outcome fields
are updated in place as evaluate_wake() progresses (data-model.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EvaluationStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"
    INERT_PAST_DEPARTURE = "INERT_PAST_DEPARTURE"


@dataclass
class Recommendation:
    recommendation_id: str
    evaluation_id: str
    option_id: str
    verification_id: str
    cost_relative_description: str
    rationale: str
    constraint_breach: bool = False
    constraint_breach_detail: str | None = None


@dataclass
class ImpactEvaluation:
    evaluation_id: str
    journey_id: str
    triggering_event_id: str
    triggering_sequence: int
    started_at: datetime
    status: EvaluationStatus = EvaluationStatus.IN_PROGRESS
    concluded_at: datetime | None = None
    objective_satisfied: bool | None = None
    violation_description: str | None = None
    violated_constraints: list[str] = field(default_factory=list)
    violation_extent: str | None = None
    recommendation_id: str | None = None
    no_alternative_reason: str | None = None
