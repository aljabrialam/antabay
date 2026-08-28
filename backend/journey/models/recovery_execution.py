"""Recovery execution output models for feature 011-recovery-execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RecoveryExecutionStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class ReplacementOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class CancellationOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


@dataclass
class CancellationAttempt:
    attempt_id: str
    journey_id: str
    order_no: str
    requested_at: datetime
    outcome: str  # "INITIATED" | "ERROR"
    responded_at: datetime | None = None
    raw_response_json: str | None = None
    reconciliation_raw_json: str | None = None
    confirmed_cancelled: bool = False


@dataclass
class RecoveryExecution:
    recovery_execution_id: str
    recommendation_id: str
    journey_id: str
    started_at: datetime
    status: RecoveryExecutionStatus = RecoveryExecutionStatus.IN_PROGRESS
    concluded_at: datetime | None = None
    abandonment_reason: str | None = None
    superseded_order_no: str | None = None
    replacement_order_no: str | None = None
    replacement_outcome: ReplacementOutcome | None = None
    cancellation_outcome: CancellationOutcome | None = None
    final_position_description: str | None = None
