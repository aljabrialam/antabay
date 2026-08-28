from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class VerificationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNRESOLVED = "UNRESOLVED"


class ConditionResult(str, Enum):
    """A registered SuccessCondition's raw classification of one query
    result — before the gate applies its bound/history logic (research.md
    R1/R2). Distinct from VerificationOutcome, which is the gate's final
    classification."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_FOUND = "NOT_FOUND"


@dataclass
class ReconciliationBound:
    """The bound an action type declares for how long an unresolved
    outcome may be reconciled (FR-003). At least one of the two fields
    MUST be set — a condition with neither is a specification error."""

    max_attempts: int | None = None
    max_duration_seconds: int | None = None


class SuccessCondition(Protocol):
    """The per-action-type contract every action registers with the gate
    (research.md R1). The gate never inspects a query_result's shape
    itself — only the registered condition understands it."""

    def classify(self, query_result: Any) -> ConditionResult: ...

    def has_discrepancy(self, action_response: Any, query_result: Any) -> bool: ...

    def reconciliation_bound(self) -> ReconciliationBound: ...


@dataclass
class VerificationAttempt:
    attempt_id: str
    journey_id: str
    action_type: str
    affected_record_id: str
    queried_at: datetime
    observed_at: datetime
    query_result_json: str
    classification: VerificationOutcome
    condition_result: ConditionResult
    has_discrepancy: bool
    applied_to_state: bool
    action_response_json: str | None = None
