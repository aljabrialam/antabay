"""Structural expectation checks for the demonstration capture runner
(014-demonstration-capture, FR-004, research.md R8).

Each function raises `CaptureAssertionError` naming the failed step on
mismatch. Checks assert the *shape* the scenario requires (a hard
constraint satisfied, a specific elimination reason, an objective
element violated) — never a fixed price, flight number, or option id —
so a run remains verifiable even when the live provider's own data
drifts between calls (spec.md Edge Cases).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from journey.models.impact_evaluation import ImpactEvaluation, Recommendation
    from journey.models.recovery_execution import RecoveryExecution
    from journey.models.scoring import ScoringRun


class CaptureAssertionError(AssertionError):
    """Raised when a demonstration run's step does not match the expected
    observable outcome. Carries the failed step's name (FR-004)."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step


def assert_selected_option_satisfies_hard_constraints(scoring_run: "ScoringRun") -> None:
    """The scoring run's own selected_option, if any, already only exists
    because every hard constraint passed (scoring_service.py's own
    elimination pipeline) — this asserts that guarantee held for this run,
    not that a *specific* option/price won."""
    from journey.models.scoring import ScoringOutcome

    if scoring_run.selected_option is None:
        raise CaptureAssertionError(
            "scoring", "no option was selected — expected a compliant winner"
        )
    if scoring_run.selected_option.outcome != ScoringOutcome.SELECTED:
        raise CaptureAssertionError(
            "scoring",
            f"selected_option outcome was {scoring_run.selected_option.outcome!r}, "
            "expected SELECTED",
        )
    if scoring_run.selected_option.elimination is not None:
        raise CaptureAssertionError(
            "scoring", "the winning option carries an elimination record"
        )


def assert_eliminated_candidate_excluded_for_connection_rule(scoring_run: "ScoringRun") -> None:
    """FR-005's first emphasised moment: at least one eliminated candidate
    must have been excluded specifically for the excluded-connection rule
    (or an impossible/short connection), not for arrival or budget —
    proving reasoning rather than naive sorting (spec.md Reference)."""
    from journey.models.scoring import ScoringOutcome

    connection_reason_codes = {
        "connection_excluded",
        "impossible_connection",
        "min_connection_time",
    }
    reason_codes = [
        so.elimination.reason_code
        for so in scoring_run.scored_options
        if so.outcome == ScoringOutcome.ELIMINATED and so.elimination is not None
    ]
    if not any(code in connection_reason_codes for code in reason_codes):
        raise CaptureAssertionError(
            "scoring",
            "no eliminated candidate was excluded for a connection-rule reason — "
            f"eliminated reason codes were: {sorted(set(reason_codes))}",
        )


def assert_objective_violated(evaluation: "ImpactEvaluation") -> None:
    """FR-005's second emphasised moment: the disruption must have caused
    a real, quantified objective violation naming latest_arrival."""
    if evaluation.objective_satisfied is not False:
        raise CaptureAssertionError(
            "impact_evaluation",
            f"objective_satisfied was {evaluation.objective_satisfied!r}, expected False",
        )
    if "latest_arrival" not in evaluation.violated_constraints:
        raise CaptureAssertionError(
            "impact_evaluation",
            f"violated_constraints {evaluation.violated_constraints!r} does not "
            "name latest_arrival",
        )
    if not evaluation.violation_extent:
        raise CaptureAssertionError(
            "impact_evaluation", "violation_extent was not quantified"
        )


def assert_recommendation_traces_to_verified_result(
    evaluation: "ImpactEvaluation", recommendation: "Recommendation | None"
) -> None:
    """Feature 009's own NFR-001: a recommendation must exist and trace to
    a verified provider response — never presented on a search/score
    result alone."""
    if recommendation is None:
        raise CaptureAssertionError(
            "recommendation",
            f"no recommendation was produced (no_alternative_reason="
            f"{evaluation.no_alternative_reason!r})",
        )
    if not recommendation.verification_id:
        raise CaptureAssertionError(
            "recommendation", "recommendation carries no verification_id"
        )


def assert_recovery_completed_succeeded(execution: "RecoveryExecution") -> None:
    """The recovery must complete, with the replacement outcome recorded
    as succeeded — the safety-critical guarantee feature 011 exists to
    provide."""
    from journey.models.recovery_execution import RecoveryExecutionStatus, ReplacementOutcome

    if execution.status != RecoveryExecutionStatus.COMPLETED:
        raise CaptureAssertionError(
            "recovery_execution",
            f"status was {execution.status!r}, expected COMPLETED "
            f"(abandonment_reason={execution.abandonment_reason!r})",
        )
    if execution.replacement_outcome != ReplacementOutcome.SUCCEEDED:
        raise CaptureAssertionError(
            "recovery_execution",
            f"replacement_outcome was {execution.replacement_outcome!r}, "
            "expected SUCCEEDED",
        )
