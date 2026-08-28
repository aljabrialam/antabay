from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from journey.errors import UnregisteredActionTypeError
from journey.models.verification_gate import (
    ConditionResult,
    SuccessCondition,
    VerificationAttempt,
    VerificationOutcome,
)

if TYPE_CHECKING:
    from journey.storage.repository import JourneyRepository

QueryFn = Callable[[], tuple[Any, datetime]]

_RESOLVED_CONDITION_RESULTS = {
    ConditionResult.SUCCESS: VerificationOutcome.SUCCESS,
    ConditionResult.FAILURE: VerificationOutcome.FAILURE,
}


class PostActionVerifier:
    def __init__(self, repo: "JourneyRepository", conditions: dict[str, SuccessCondition]) -> None:
        self._repo = repo
        self._conditions = conditions

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    def verify(
        self,
        journey_id: str,
        action_type: str,
        affected_record_id: str,
        query_fn: QueryFn,
        now: datetime,
        action_response: Any | None = None,
    ) -> VerificationAttempt:
        condition = self._conditions.get(action_type)
        if condition is None:
            raise UnregisteredActionTypeError(action_type)

        queried_at = now
        try:
            query_result, observed_at = query_fn()
        except Exception as exc:
            query_result = {"error": str(exc)}
            observed_at = now
            condition_result = ConditionResult.INCONCLUSIVE
        else:
            condition_result = condition.classify(query_result)

        has_discrepancy = False
        if action_response is not None:
            has_discrepancy = condition.has_discrepancy(action_response, query_result)

        classification = self._resolve_classification(
            affected_record_id, condition, condition_result, now
        )

        attempt = VerificationAttempt(
            attempt_id=str(uuid.uuid4()),
            journey_id=journey_id,
            action_type=action_type,
            affected_record_id=affected_record_id,
            action_response_json=json.dumps(action_response) if action_response is not None else None,
            queried_at=queried_at,
            observed_at=observed_at,
            query_result_json=json.dumps(query_result),
            classification=classification,
            condition_result=condition_result,
            has_discrepancy=has_discrepancy,
            applied_to_state=False,
        )

        if classification in (VerificationOutcome.SUCCESS, VerificationOutcome.FAILURE):
            attempt.applied_to_state = self._should_apply(affected_record_id, observed_at)

        self._repo.save_verification_attempt(attempt)
        return attempt

    # ------------------------------------------------------------------
    # ReconcileUnresolved
    # ------------------------------------------------------------------

    def reconcile_unresolved(
        self,
        journey_id: str,
        action_type: str,
        affected_record_id: str,
        query_fn: QueryFn,
        now: datetime,
    ) -> VerificationAttempt:
        condition = self._conditions.get(action_type)
        if condition is None:
            raise UnregisteredActionTypeError(action_type)

        history = self._repo.get_verification_attempts(affected_record_id)
        if history and self._bound_reached(history, condition, now=now):
            return history[-1]

        return self.verify(
            journey_id=journey_id,
            action_type=action_type,
            affected_record_id=affected_record_id,
            query_fn=query_fn,
            now=now,
        )

    # ------------------------------------------------------------------
    # ReportableOutcome
    # ------------------------------------------------------------------

    def reportable_outcome(self, affected_record_id: str) -> VerificationOutcome | None:
        latest = self._repo.get_latest_applied_attempt(affected_record_id)
        if latest is None:
            return None
        if latest.classification in (VerificationOutcome.SUCCESS, VerificationOutcome.FAILURE):
            return latest.classification
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_classification(
        self,
        affected_record_id: str,
        condition: SuccessCondition,
        condition_result: ConditionResult,
        now: datetime,
    ) -> VerificationOutcome:
        resolved = _RESOLVED_CONDITION_RESULTS.get(condition_result)
        if resolved is not None:
            return resolved

        # INCONCLUSIVE or NOT_FOUND: apply the bound rule (research.md R2)
        # against the reconciliation history so far, INCLUDING this attempt.
        history = self._repo.get_verification_attempts(affected_record_id)
        history_results = [a.condition_result for a in history] + [condition_result]
        first_observed_at = history[0].observed_at if history else now

        if self._bound_reached_for_results(
            history_results, condition, first_observed_at=first_observed_at, now=now
        ):
            if all(r is ConditionResult.NOT_FOUND for r in history_results):
                return VerificationOutcome.FAILURE
            return VerificationOutcome.UNRESOLVED

        return VerificationOutcome.UNRESOLVED

    def _bound_reached(
        self, history: list[VerificationAttempt], condition: SuccessCondition, now: datetime
    ) -> bool:
        results = [a.condition_result for a in history]
        first_observed_at = history[0].observed_at
        return self._bound_reached_for_results(
            results, condition, first_observed_at=first_observed_at, now=now
        )

    def _bound_reached_for_results(
        self,
        results: list[ConditionResult],
        condition: SuccessCondition,
        *,
        first_observed_at: datetime,
        now: datetime,
    ) -> bool:
        bound = condition.reconciliation_bound()
        if bound.max_attempts is not None and len(results) >= bound.max_attempts:
            return True
        if bound.max_duration_seconds is not None:
            elapsed = (now - first_observed_at).total_seconds()
            if elapsed >= bound.max_duration_seconds:
                return True
        return False

    def _should_apply(self, affected_record_id: str, observed_at: datetime) -> bool:
        latest_applied = self._repo.get_latest_applied_attempt(affected_record_id)
        if latest_applied is None:
            return True
        return observed_at > latest_applied.observed_at
