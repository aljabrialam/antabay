"""Unit tests for capture_assertions (014-demonstration-capture, T008-T012).

These construct scoring/evaluation/execution results directly rather than
running a live pipeline — the assertions themselves are pure functions
over already-produced results, independently testable from any live run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest


def _flight_option(option_id: str = "opt-1") -> object:
    from journey.models.flight import FlightOption

    now = datetime.now(tz=timezone.utc)
    return FlightOption(
        option_id=option_id,
        journey_id="journey-1",
        search_record_id="search-1",
        fid="fid-1",
        routing_identifier="RID-1",
        currency="USD",
        adult_price=Decimal("90.39"),
        adult_tax=Decimal("0.00"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now,
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )


def _scored_selected() -> object:
    from journey.models.scoring import ScoredOption, ScoringOutcome

    return ScoredOption(
        option=_flight_option("opt-selected"),
        outcome=ScoringOutcome.SELECTED,
        rank=1,
        rationale=None,
        elimination=None,
        rejection_reason=None,
        connection_eval=None,
    )


def _scored_eliminated(reason_code: str) -> object:
    from journey.models.scoring import EliminationRecord, ScoredOption, ScoringOutcome

    return ScoredOption(
        option=_flight_option(f"opt-elim-{reason_code}"),
        outcome=ScoringOutcome.ELIMINATED,
        rank=None,
        rationale=None,
        elimination=EliminationRecord(
            option_id=f"opt-elim-{reason_code}",
            reason_code=reason_code,
            reason_detail="detail",
            constraint_id=None,
        ),
        rejection_reason=None,
        connection_eval=None,
    )


def _scoring_run(scored_options: list) -> object:
    from journey.models.objective import TravelObjective
    from journey.models.scoring import ScoringRun

    selected = next((so for so in scored_options if so.outcome.value == "SELECTED"), None)
    return ScoringRun(
        run_id="run-1",
        objective=TravelObjective(),
        evaluated_at=datetime.now(tz=timezone.utc),
        scored_options=scored_options,
        selected_option=selected,
        no_satisfying_option=None,
    )


class TestSelectedOptionSatisfiesHardConstraints:
    def test_passes_when_selected_and_clean(self) -> None:
        from scripts.capture_assertions import assert_selected_option_satisfies_hard_constraints

        run = _scoring_run([_scored_selected(), _scored_eliminated("budget_exceeded")])
        assert_selected_option_satisfies_hard_constraints(run)  # no raise

    def test_fails_when_no_option_selected(self) -> None:
        from scripts.capture_assertions import (
            CaptureAssertionError,
            assert_selected_option_satisfies_hard_constraints,
        )

        run = _scoring_run([_scored_eliminated("budget_exceeded")])
        with pytest.raises(CaptureAssertionError) as exc_info:
            assert_selected_option_satisfies_hard_constraints(run)
        assert exc_info.value.step == "scoring"


class TestEliminatedCandidateExcludedForConnectionRule:
    def test_passes_when_a_candidate_is_excluded_for_overnight_connection(self) -> None:
        from scripts.capture_assertions import (
            assert_eliminated_candidate_excluded_for_connection_rule,
        )

        run = _scoring_run(
            [
                _scored_selected(),
                _scored_eliminated("budget_exceeded"),
                _scored_eliminated("connection_excluded"),
            ]
        )
        assert_eliminated_candidate_excluded_for_connection_rule(run)  # no raise

    def test_fails_when_no_candidate_excluded_for_connection_rule(self) -> None:
        from scripts.capture_assertions import (
            CaptureAssertionError,
            assert_eliminated_candidate_excluded_for_connection_rule,
        )

        run = _scoring_run([_scored_selected(), _scored_eliminated("budget_exceeded")])
        with pytest.raises(CaptureAssertionError) as exc_info:
            assert_eliminated_candidate_excluded_for_connection_rule(run)
        assert exc_info.value.step == "scoring"


class TestObjectiveViolatedAfterDisruption:
    def test_passes_when_latest_arrival_violated_and_quantified(self) -> None:
        from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation
        from scripts.capture_assertions import assert_objective_violated

        evaluation = ImpactEvaluation(
            evaluation_id="eval-1",
            journey_id="journey-1",
            triggering_event_id="event-1",
            triggering_sequence=1,
            started_at=datetime.now(tz=timezone.utc),
            status=EvaluationStatus.COMPLETED,
            objective_satisfied=False,
            violated_constraints=["latest_arrival"],
            violation_extent="110 minutes late",
        )
        assert_objective_violated(evaluation)  # no raise

    def test_fails_when_objective_satisfied(self) -> None:
        from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation
        from scripts.capture_assertions import CaptureAssertionError, assert_objective_violated

        evaluation = ImpactEvaluation(
            evaluation_id="eval-1",
            journey_id="journey-1",
            triggering_event_id="event-1",
            triggering_sequence=1,
            started_at=datetime.now(tz=timezone.utc),
            status=EvaluationStatus.COMPLETED,
            objective_satisfied=True,
        )
        with pytest.raises(CaptureAssertionError) as exc_info:
            assert_objective_violated(evaluation)
        assert exc_info.value.step == "impact_evaluation"

    def test_fails_when_latest_arrival_not_named(self) -> None:
        from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation
        from scripts.capture_assertions import CaptureAssertionError, assert_objective_violated

        evaluation = ImpactEvaluation(
            evaluation_id="eval-1",
            journey_id="journey-1",
            triggering_event_id="event-1",
            triggering_sequence=1,
            started_at=datetime.now(tz=timezone.utc),
            status=EvaluationStatus.COMPLETED,
            objective_satisfied=False,
            violated_constraints=["budget_amount"],
            violation_extent="something",
        )
        with pytest.raises(CaptureAssertionError):
            assert_objective_violated(evaluation)


class TestRecommendationTracesToVerifiedResult:
    def test_passes_when_recommendation_carries_verification_id(self) -> None:
        from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation, Recommendation
        from scripts.capture_assertions import assert_recommendation_traces_to_verified_result

        evaluation = ImpactEvaluation(
            evaluation_id="eval-1",
            journey_id="journey-1",
            triggering_event_id="event-1",
            triggering_sequence=1,
            started_at=datetime.now(tz=timezone.utc),
            status=EvaluationStatus.COMPLETED,
            objective_satisfied=False,
        )
        recommendation = Recommendation(
            recommendation_id="rec-1",
            evaluation_id="eval-1",
            option_id="opt-1",
            verification_id="verif-1",
            cost_relative_description="+$6.24",
            rationale="Restores the objective.",
        )
        assert_recommendation_traces_to_verified_result(evaluation, recommendation)  # no raise

    def test_fails_when_no_recommendation_produced(self) -> None:
        from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation
        from scripts.capture_assertions import (
            CaptureAssertionError,
            assert_recommendation_traces_to_verified_result,
        )

        evaluation = ImpactEvaluation(
            evaluation_id="eval-1",
            journey_id="journey-1",
            triggering_event_id="event-1",
            triggering_sequence=1,
            started_at=datetime.now(tz=timezone.utc),
            status=EvaluationStatus.COMPLETED,
            objective_satisfied=False,
            no_alternative_reason="none_found",
        )
        with pytest.raises(CaptureAssertionError) as exc_info:
            assert_recommendation_traces_to_verified_result(evaluation, None)
        assert exc_info.value.step == "recommendation"


class TestRecoveryCompletedSucceeded:
    def test_passes_when_completed_and_replacement_succeeded(self) -> None:
        from journey.models.recovery_execution import (
            RecoveryExecution,
            RecoveryExecutionStatus,
            ReplacementOutcome,
        )
        from scripts.capture_assertions import assert_recovery_completed_succeeded

        execution = RecoveryExecution(
            recovery_execution_id="exec-1",
            recommendation_id="rec-1",
            journey_id="journey-1",
            started_at=datetime.now(tz=timezone.utc),
            status=RecoveryExecutionStatus.COMPLETED,
            replacement_outcome=ReplacementOutcome.SUCCEEDED,
        )
        assert_recovery_completed_succeeded(execution)  # no raise

    def test_fails_when_abandoned(self) -> None:
        from journey.models.recovery_execution import RecoveryExecution, RecoveryExecutionStatus
        from scripts.capture_assertions import CaptureAssertionError, assert_recovery_completed_succeeded

        execution = RecoveryExecution(
            recovery_execution_id="exec-1",
            recommendation_id="rec-1",
            journey_id="journey-1",
            started_at=datetime.now(tz=timezone.utc),
            status=RecoveryExecutionStatus.ABANDONED,
            abandonment_reason="not_authorised",
        )
        with pytest.raises(CaptureAssertionError) as exc_info:
            assert_recovery_completed_succeeded(execution)
        assert exc_info.value.step == "recovery_execution"
