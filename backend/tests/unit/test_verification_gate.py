"""Unit tests for PostActionVerifier (T008-T010, T017-T019, T025-T029,
T039-T040).

TDD gate (T012, T021, T030, T041): these tests must fail with
NotImplementedError against the Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'verification_gate.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _seed_journey(repo: Any) -> str:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    return JourneyService(repository=repo).create_journey(objective).journey_id


class _StubCondition:
    """A minimal SuccessCondition for exercising the general gate without
    depending on any real action type's shape."""

    def __init__(
        self,
        classify_result: Any = None,
        discrepancy: bool = False,
        max_attempts: int | None = None,
        max_duration_seconds: int | None = None,
        classify_sequence: list[Any] | None = None,
    ) -> None:
        from journey.models.verification_gate import ReconciliationBound

        self._classify_result = classify_result
        self._discrepancy = discrepancy
        self._bound = ReconciliationBound(
            max_attempts=max_attempts, max_duration_seconds=max_duration_seconds
        )
        self._classify_sequence = list(classify_sequence) if classify_sequence else None

    def classify(self, query_result: Any) -> Any:
        if self._classify_sequence is not None:
            return self._classify_sequence.pop(0)
        return self._classify_result

    def has_discrepancy(self, action_response: Any, query_result: Any) -> bool:
        return self._discrepancy

    def reconciliation_bound(self) -> Any:
        return self._bound


def _verifier(repo: Any, conditions: dict[str, Any]) -> Any:
    from journey.services.verification_gate import PostActionVerifier

    return PostActionVerifier(repo=repo, conditions=conditions)


class TestVerifyDerivesFromQueryNotAction:
    def test_classification_follows_query_not_claimed_success(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.FAILURE)
        verifier = _verifier(repo, {"test-action": condition})

        def _query_fn() -> tuple[Any, datetime]:
            return {"whatever": "the query says"}, datetime.now(tz=timezone.utc)

        attempt = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-1",
            query_fn=_query_fn,
            now=datetime.now(tz=timezone.utc),
            action_response={"status": "success, trust me"},
        )

        assert attempt.classification is VerificationOutcome.FAILURE


class TestUnregisteredActionTypeRejected:
    def test_raises_before_query_fn_is_called(self, tmp_path: Any) -> None:
        from journey.errors import UnregisteredActionTypeError

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        verifier = _verifier(repo, {})

        called = {"count": 0}

        def _query_fn() -> tuple[Any, datetime]:
            called["count"] += 1
            return {}, datetime.now(tz=timezone.utc)

        with pytest.raises(UnregisteredActionTypeError):
            verifier.verify(
                journey_id=journey_id,
                action_type="unregistered",
                affected_record_id="rec-1",
                query_fn=_query_fn,
                now=datetime.now(tz=timezone.utc),
            )
        assert called["count"] == 0


class TestConcurrencyOrdering:
    def test_later_observed_wins_regardless_of_processing_order(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.SUCCESS)
        verifier = _verifier(repo, {"test-action": condition})

        base = datetime.now(tz=timezone.utc)
        earlier_observed = base
        later_observed = base + timedelta(seconds=10)

        # Processed SECOND, but observed EARLIER — must not win.
        def _query_fn_earlier() -> tuple[Any, datetime]:
            return {"seq": "earlier"}, earlier_observed

        # Processed FIRST, but observed LATER — must win.
        def _query_fn_later() -> tuple[Any, datetime]:
            return {"seq": "later"}, later_observed

        verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-concurrent",
            query_fn=_query_fn_later,
            now=base,
        )
        verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-concurrent",
            query_fn=_query_fn_earlier,
            now=base,
        )

        latest = repo.get_latest_applied_attempt("rec-concurrent")
        assert latest is not None
        assert latest.observed_at == later_observed


class TestDiscrepancyRecorded:
    def test_disagreeing_pair_is_flagged(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.FAILURE, discrepancy=True)
        verifier = _verifier(repo, {"test-action": condition})

        attempt = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-1",
            query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
            now=datetime.now(tz=timezone.utc),
            action_response={"claims": "success"},
        )

        assert attempt.has_discrepancy is True


class TestNoDiscrepancyWhenAgreeing:
    def test_agreeing_pair_is_not_flagged(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.SUCCESS, discrepancy=False)
        verifier = _verifier(repo, {"test-action": condition})

        attempt = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-1",
            query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
            now=datetime.now(tz=timezone.utc),
            action_response={"claims": "success"},
        )

        assert attempt.has_discrepancy is False


class TestEveryAttemptAudited:
    def test_all_attempts_recorded_regardless_of_outcome(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)

        for result, discrepancy in [
            (ConditionResult.SUCCESS, False),
            (ConditionResult.FAILURE, True),
            (ConditionResult.INCONCLUSIVE, False),
        ]:
            condition = _StubCondition(classify_result=result, discrepancy=discrepancy)
            verifier = _verifier(repo, {"test-action": condition})
            verifier.verify(
                journey_id=journey_id,
                action_type="test-action",
                affected_record_id="rec-audit",
                query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
                now=datetime.now(tz=timezone.utc),
                action_response={"whatever": True},
            )

        attempts = repo.get_verification_attempts("rec-audit")
        assert len(attempts) == 3


class TestInconclusiveStaysUnresolvedAtBound:
    def test_bound_reached_with_inconclusive_history_stays_unresolved(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(
            classify_sequence=[ConditionResult.INCONCLUSIVE] * 3, max_attempts=3
        )
        verifier = _verifier(repo, {"test-action": condition})

        attempt = None
        for _ in range(3):
            attempt = verifier.verify(
                journey_id=journey_id,
                action_type="test-action",
                affected_record_id="rec-inconclusive",
                query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
                now=datetime.now(tz=timezone.utc),
            )

        assert attempt is not None
        assert attempt.classification is VerificationOutcome.UNRESOLVED


class TestNotFoundBecomesFailureAtBound:
    def test_bound_reached_with_all_not_found_becomes_failure(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(
            classify_sequence=[ConditionResult.NOT_FOUND] * 3, max_attempts=3
        )
        verifier = _verifier(repo, {"test-action": condition})

        attempt = None
        for _ in range(3):
            attempt = verifier.verify(
                journey_id=journey_id,
                action_type="test-action",
                affected_record_id="rec-notfound",
                query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
                now=datetime.now(tz=timezone.utc),
            )

        assert attempt is not None
        assert attempt.classification is VerificationOutcome.FAILURE


class TestMixedHistoryStaysUnresolvedAtBound:
    def test_one_inconclusive_in_history_rules_out_failure(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(
            classify_sequence=[
                ConditionResult.NOT_FOUND,
                ConditionResult.INCONCLUSIVE,
                ConditionResult.NOT_FOUND,
            ],
            max_attempts=3,
        )
        verifier = _verifier(repo, {"test-action": condition})

        attempt = None
        for _ in range(3):
            attempt = verifier.verify(
                journey_id=journey_id,
                action_type="test-action",
                affected_record_id="rec-mixed",
                query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
                now=datetime.now(tz=timezone.utc),
            )

        assert attempt is not None
        assert attempt.classification is VerificationOutcome.UNRESOLVED


class TestQueryFailureIsInconclusive:
    def test_query_fn_raising_is_recorded_as_unresolved(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.SUCCESS, max_attempts=3)
        verifier = _verifier(repo, {"test-action": condition})

        def _failing_query_fn() -> tuple[Any, datetime]:
            raise RuntimeError("provider unreachable")

        attempt = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-query-fails",
            query_fn=_failing_query_fn,
            now=datetime.now(tz=timezone.utc),
        )

        assert attempt.condition_result is ConditionResult.INCONCLUSIVE
        assert attempt.classification is VerificationOutcome.UNRESOLVED


class TestDurationBoundReached:
    def test_duration_only_bound_reaches_failure_for_all_not_found(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        # No max_attempts at all — mirrors TicketingSuccessCondition, which
        # declares only max_duration_seconds (30 minutes).
        condition = _StubCondition(
            classify_result=ConditionResult.NOT_FOUND, max_duration_seconds=1800
        )
        verifier = _verifier(repo, {"test-action": condition})
        start = datetime.now(tz=timezone.utc)

        first = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-duration",
            query_fn=lambda: ({}, start),
            now=start,
        )
        assert first.classification is VerificationOutcome.UNRESOLVED

        later = start + timedelta(seconds=1801)
        second = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-duration",
            query_fn=lambda: ({}, later),
            now=later,
        )
        assert second.classification is VerificationOutcome.FAILURE

    def test_duration_only_bound_stays_unresolved_if_not_all_not_found(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(
            classify_sequence=[ConditionResult.NOT_FOUND, ConditionResult.INCONCLUSIVE],
            max_duration_seconds=1800,
        )
        verifier = _verifier(repo, {"test-action": condition})
        start = datetime.now(tz=timezone.utc)

        verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-duration-mixed",
            query_fn=lambda: ({}, start),
            now=start,
        )

        later = start + timedelta(seconds=1801)
        second = verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-duration-mixed",
            query_fn=lambda: ({}, later),
            now=later,
        )
        assert second.classification is VerificationOutcome.UNRESOLVED


class TestReconcileNeverRepeatsAction:
    def test_reconcile_unresolved_has_no_action_invocation_path(self) -> None:
        import inspect

        from journey.services.verification_gate import PostActionVerifier

        params = inspect.signature(PostActionVerifier.reconcile_unresolved).parameters
        assert "action_response" not in params
        # Only journey/action/record identity, a query function, and time.
        assert set(params) - {"self"} == {
            "journey_id",
            "action_type",
            "affected_record_id",
            "query_fn",
            "now",
        }


class TestBoundAlreadyReachedIsNoOp:
    def test_no_new_query_once_bound_is_reached(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(
            classify_sequence=[ConditionResult.NOT_FOUND] * 2, max_attempts=2
        )
        verifier = _verifier(repo, {"test-action": condition})

        for _ in range(2):
            verifier.reconcile_unresolved(
                journey_id=journey_id,
                action_type="test-action",
                affected_record_id="rec-bound-reached",
                query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
                now=datetime.now(tz=timezone.utc),
            )

        def _should_not_be_called() -> tuple[Any, datetime]:
            raise AssertionError("query_fn must not be called once the bound is reached")

        final = verifier.reconcile_unresolved(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-bound-reached",
            query_fn=_should_not_be_called,
            now=datetime.now(tz=timezone.utc),
        )
        assert final.classification.value == "FAILURE"


class TestReportableOutcomeAbsentWhileUnresolved:
    def test_none_returned_before_resolution(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.INCONCLUSIVE, max_attempts=5)
        verifier = _verifier(repo, {"test-action": condition})

        verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-reportable",
            query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
            now=datetime.now(tz=timezone.utc),
        )

        assert verifier.reportable_outcome("rec-reportable") is None


class TestReportableOutcomeAvailableAfterResolution:
    def test_resolved_outcome_is_returned(self, tmp_path: Any) -> None:
        from journey.models.verification_gate import ConditionResult, VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id = _seed_journey(repo)
        condition = _StubCondition(classify_result=ConditionResult.SUCCESS)
        verifier = _verifier(repo, {"test-action": condition})

        verifier.verify(
            journey_id=journey_id,
            action_type="test-action",
            affected_record_id="rec-resolved",
            query_fn=lambda: ({}, datetime.now(tz=timezone.utc)),
            now=datetime.now(tz=timezone.utc),
        )

        assert verifier.reportable_outcome("rec-resolved") is VerificationOutcome.SUCCESS
