"""Orchestrates the complete journey pipeline unattended, asserting a
structural expectation after every step (014-demonstration-capture,
FR-001, FR-004, contracts/capture_runner.md).
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx

from scripts.capture_assertions import (
    CaptureAssertionError,
    assert_eliminated_candidate_excluded_for_connection_rule,
    assert_objective_violated,
    assert_recommendation_traces_to_verified_result,
    assert_recovery_completed_succeeded,
    assert_selected_option_satisfies_hard_constraints,
)

if TYPE_CHECKING:
    from journey.models.objective import TravelObjective
    from journey.storage.repository import JourneyRepository

_DEMO_ORIGIN = "ICN"
_DEMO_DEST = "NRT"
_DEMO_DEPARTURE_DATE = "20260905"  # the locked demo scenario's real, verified date
_DEMO_LATEST_ARRIVAL = "202609051000"  # 10:00 local, per .antabay/demo-scenario.md
_DEMO_REVISED_ARRIVAL = datetime(2026, 9, 5, 11, 50, tzinfo=timezone.utc)
_TICKETING_MAX_ATTEMPTS = 5
_TICKETING_RETRY_SECONDS = 0.0


@dataclass
class RunResult:
    journey_id: str
    run_kind: str  # "PRIMARY" | "REFUSAL_PATH"
    status: str = "IN_PROGRESS"  # "PASSED" | "FAILED"
    failed_step: str | None = None
    steps_completed: list[str] = field(default_factory=list)


def _default_objective() -> "TravelObjective":
    """The reference goal (.antabay/demo-scenario.md): Tokyo before 10am,
    under USD 120, no overnight connections."""
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

    return TravelObjective(
        origin=ConstrainedField(value=_DEMO_ORIGIN, constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value=_DEMO_DEST, constraint_type=ConstraintType.HARD),
        departure_date=ConstrainedField(value=_DEMO_DEPARTURE_DATE, constraint_type=ConstraintType.HARD),
        latest_arrival=ConstrainedField(value=_DEMO_LATEST_ARRIVAL, constraint_type=ConstraintType.HARD),
        budget_amount=ConstrainedField(value=Decimal("120.00"), constraint_type=ConstraintType.HARD),
        budget_currency=ConstrainedField(value="USD", constraint_type=ConstraintType.HARD),
        pax_count=ConstrainedField(value=1, constraint_type=ConstraintType.HARD),
        preferences=ConstrainedField(value=["direct_only"], constraint_type=ConstraintType.SOFT),
    )


def _confirm_ticketing_with_retry(booking_service: Any, journey_id: str, order_no: str, now: datetime) -> Any:
    last = None
    for _ in range(_TICKETING_MAX_ATTEMPTS):
        last = booking_service.confirm_ticketing(journey_id, order_no, now)
        if last.confirmed:
            return last
        time.sleep(_TICKETING_RETRY_SECONDS)
    return last


def _authorisation_request_id_for(repo: "JourneyRepository", journey_id: str, action_id: str) -> str:
    """Reads back the request_id AuthorisationPolicyEngine.request_if_required()
    just appended (research.md R11 — the missing Recommendation-to-
    authorisation bridge, built locally to this script only)."""
    from journey.models.events import EventType

    events = repo.get_events_from_sequence(journey_id, from_sequence=0)
    matching = [
        e
        for e in events
        if e.event_type is EventType.AUTHORISATION_REQUESTED and e.payload.get("action_id") == action_id
    ]
    if not matching:
        raise CaptureAssertionError(
            "authorisation_request", f"no AUTHORISATION_REQUESTED event found for action_id={action_id!r}"
        )
    return str(matching[-1].payload["request_id"])


def run(
    scenario: str,
    *,
    objective: "TravelObjective | None" = None,
    atlas_http_client: httpx.Client | None = None,
    repo: "JourneyRepository | None" = None,
    now: datetime | None = None,
) -> RunResult:
    from journey.models.authorisation_policy import ProposedAction
    from journey.models.booking import OrderOutcome, PaymentOutcome
    from journey.models.events import EventType
    from journey.models.verification import VerificationOutcome
    from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine
    from journey.services.booking_service import BookingService
    from journey.services.disruption_injector_service import DisruptionInjectorService
    from journey.services.event_service import EventService
    from journey.services.flight_search import FlightSearchService
    from journey.services.impact_evaluation_service import ImpactEvaluationService
    from journey.services.journey_service import JourneyService
    from journey.services.recovery_execution_service import RecoveryExecutionService
    from journey.services.scoring_service import ScoringService
    from journey.services.verification_service import VerificationService
    from journey.storage.repository import JourneyRepository

    run_kind = "PRIMARY" if scenario == "primary" else "REFUSAL_PATH"
    now = now if now is not None else datetime.now(tz=timezone.utc)
    repo = repo if repo is not None else JourneyRepository()
    from journey.atlas_auth import atlas_http_client as build_default_atlas_client

    http_client = atlas_http_client if atlas_http_client is not None else build_default_atlas_client()
    objective = objective if objective is not None else _default_objective()

    events = EventService(repo)
    journey = JourneyService(repository=repo).create_journey(objective)
    result = RunResult(journey_id=journey.journey_id, run_kind=run_kind)

    def _fail(step: str, detail: str) -> RunResult:
        result.status = "FAILED"
        result.failed_step = step
        return result

    try:
        # --- Search ---
        search_result = FlightSearchService(repo=repo, http_client=http_client).search(
            journey.journey_id, now
        )
        result.steps_completed.append("search")

        # --- Score ---
        scoring_run = ScoringService().score(objective, search_result.options, now)
        assert_selected_option_satisfies_hard_constraints(scoring_run)
        assert_eliminated_candidate_excluded_for_connection_rule(scoring_run)
        result.steps_completed.append("scoring")
        assert scoring_run.selected_option is not None  # guaranteed by the assertion above
        selected_option_id = scoring_run.selected_option.option.option_id

        # --- Verify, order, pay, confirm ticketing (original booking) ---
        verification_service = VerificationService(repo=repo, http_client=http_client)
        booking_service = BookingService(repo=repo, http_client=http_client)

        verification = verification_service.verify(journey.journey_id, selected_option_id, now)
        if verification.outcome != VerificationOutcome.VERIFIED:
            return _fail("verify_original", f"outcome was {verification.outcome!r}")

        order = booking_service.create_order(journey.journey_id, selected_option_id, now)
        if order.outcome != OrderOutcome.CREATED or order.order_no is None:
            return _fail("create_order", f"outcome was {order.outcome!r}")

        payment = booking_service.submit_payment(journey.journey_id, order.order_no, now)
        if payment.outcome != PaymentOutcome.SUCCESS:
            return _fail("submit_payment", f"outcome was {payment.outcome!r}")

        ticketing = _confirm_ticketing_with_retry(booking_service, journey.journey_id, order.order_no, now)
        if not ticketing.confirmed:
            return _fail("confirm_ticketing", "ticketing was never confirmed")
        result.steps_completed.append("booking")
        original_order_no = order.order_no

        # --- Disruption (research.md R7: only after ticketing confirmed) ---
        # `enabled` is left unset so the injector's own fail-closed default
        # (DISRUPTION_INJECTOR_ENABLED env var, feature 008) governs whether
        # this step can run at all — the capture never overrides that gate.
        try:
            injector = DisruptionInjectorService(repository=repo)
            injector.inject(journey.journey_id, _DEMO_REVISED_ARRIVAL, now)
        except Exception as exc:  # noqa: BLE001 — e.g. InjectorDisabledError
            return _fail("disruption_injected", str(exc))
        result.steps_completed.append("disruption_injected")

        # --- Trigger impact evaluation immediately, scoped to only this
        # journey (research.md R12) — never a full reconcile_active_journeys()
        # sweep, which would also re-process every prior run's journey
        # still sharing this database. ---
        impact_service = ImpactEvaluationService(
            repo=repo,
            http_client=http_client,
            event_service=events,
            flight_search=FlightSearchService(repo=repo, http_client=http_client),
            scoring_service=ScoringService(),
            verification_service=verification_service,
        )
        wake_event = events.append(
            journey.journey_id,
            EventType.WAKE_REQUESTED,
            {
                "order_reference": original_order_no,
                "declared_event_type": "capture_runner",
                "classification": "SUCCESS",
            },
        )
        impact_service.evaluate_wake(journey.journey_id, wake_event)

        evaluation = repo.get_latest_impact_evaluation(journey.journey_id)
        if evaluation is None:
            return _fail("impact_evaluation", "no evaluation was produced")
        assert_objective_violated(evaluation)
        result.steps_completed.append("impact_evaluation")

        recommendation = (
            repo.get_recommendation(evaluation.recommendation_id)
            if evaluation.recommendation_id
            else None
        )
        assert_recommendation_traces_to_verified_result(evaluation, recommendation)
        result.steps_completed.append("recommendation")
        assert recommendation is not None  # guaranteed by the assertion above

        # --- Authorisation (research.md R11 bridge; R10 direct service call) ---
        alt_option = repo.get_flight_option(recommendation.option_id)
        assert alt_option is not None
        current_cost = alt_option.adult_price + alt_option.adult_tax
        proposed_action = ProposedAction(
            action_id=recommendation.recommendation_id,
            description=f"Rebook alternative {recommendation.option_id}",
            cost_amount=current_cost,
            cost_description=recommendation.cost_relative_description,
            objective_effect="Restores latest_arrival",
            cancels_or_voids_booking=True,
            is_reversible=False,
            breaches_hard_constraint=recommendation.constraint_breach,
        )
        auth_engine = AuthorisationPolicyEngine(repository=repo, event_service=events)
        auth_engine.request_if_required(journey.journey_id, proposed_action)
        request_id = _authorisation_request_id_for(
            repo, journey.journey_id, recommendation.recommendation_id
        )
        result.steps_completed.append("authorisation_requested")

        outcome = "approved" if run_kind == "PRIMARY" else "refused"
        events.record_auth_outcome(journey.journey_id, request_id, outcome)
        result.steps_completed.append(f"authorisation_{outcome}")

        if run_kind == "REFUSAL_PATH":
            post_refusal_order_no = repo.get_order_no_for_journey(journey.journey_id)
            if post_refusal_order_no != original_order_no:
                return _fail("refusal_zero_spend", "a new order exists after refusal")
            result.status = "PASSED"
            return result

        # --- Recovery execution ---
        recovery_service = RecoveryExecutionService(
            repo=repo,
            http_client=http_client,
            event_service=events,
            booking_service=booking_service,
            verification_service=verification_service,
            authorisation_engine=auth_engine,
        )
        execution = recovery_service.execute(recommendation.recommendation_id, now)
        assert_recovery_completed_succeeded(execution)
        result.steps_completed.append("recovery_execution")

        result.status = "PASSED"
        return result

    except CaptureAssertionError as exc:
        return _fail(exc.step, str(exc))
    except Exception as exc:  # noqa: BLE001 — any unhandled service error halts the run, per FR-004
        return _fail(result.steps_completed[-1] if result.steps_completed else "start", str(exc))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["primary", "refusal"], required=True)
    args = parser.parse_args()

    result = run(args.scenario)
    if result.status != "PASSED":
        print(f"FAILED at step: {result.failed_step}", file=sys.stderr)
        sys.exit(1)
    print(f"PASSED: journey_id={result.journey_id}")


if __name__ == "__main__":
    main()
