from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx

from journey.errors import BudgetExhaustedError
from journey.models.events import EventType, JourneyEvent
from journey.models.impact_evaluation import EvaluationStatus, ImpactEvaluation, Recommendation
from journey.models.objective import ConstraintType
from journey.models.scoring import ScoringOutcome
from journey.models.verification import VerificationOutcome as PriceVerificationOutcome

if TYPE_CHECKING:
    from journey.models.flight import FlightOption
    from journey.models.journey import JourneyRecord
    from journey.models.objective import TravelObjective
    from journey.models.verification import VerificationResult
    from journey.services.event_service import EventService
    from journey.services.flight_search import FlightSearchService
    from journey.services.scoring_service import ScoringService
    from journey.services.verification_service import VerificationService
    from journey.storage.repository import JourneyRepository

_ARRIVAL_TIME_FMT = "%Y%m%d%H%M"
_DATE_FMT = "%Y%m%d"


class ImpactEvaluationService:
    def __init__(
        self,
        repo: "JourneyRepository",
        http_client: httpx.Client,
        event_service: "EventService",
        flight_search: "FlightSearchService",
        scoring_service: "ScoringService",
        verification_service: "VerificationService",
    ) -> None:
        self._repo = repo
        self._http = http_client
        self._events = event_service
        self._search = flight_search
        self._scoring = scoring_service
        self._verification = verification_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_wake(self, journey_id: str, wake_event: JourneyEvent) -> ImpactEvaluation:
        now = datetime.now(tz=timezone.utc)
        evaluation = ImpactEvaluation(
            evaluation_id=str(uuid.uuid4()),
            journey_id=journey_id,
            triggering_event_id=wake_event.event_id,
            triggering_sequence=wake_event.sequence,
            started_at=now,
        )
        self._repo.save_impact_evaluation(evaluation)

        journey = self._repo.get_journey(journey_id)

        # R9: past-departure short-circuit
        if self._has_departed(journey.objective, now):
            evaluation.status = EvaluationStatus.INERT_PAST_DEPARTURE
            evaluation.concluded_at = now
            self._repo.update_impact_evaluation(evaluation)
            return evaluation

        # R3: extract the claimed new value, if any
        order_reference = wake_event.payload.get("order_reference")
        claimed_arrival = self._extract_claimed_arrival(order_reference)

        # R4: evaluate objective elements
        violated_constraints, extent = self._evaluate_latest_arrival(
            journey.objective, claimed_arrival
        )

        if not violated_constraints:
            evaluation.objective_satisfied = True
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.concluded_at = now
            self._repo.update_impact_evaluation(evaluation)
            self._events.append(
                journey_id,
                EventType.IMPACT_EVALUATION_SATISFIED,
                {"evaluation_id": evaluation.evaluation_id},
            )
            return evaluation

        evaluation.objective_satisfied = False
        evaluation.violated_constraints = violated_constraints
        evaluation.violation_extent = extent
        evaluation.violation_description = (
            f"Objective element(s) violated: {', '.join(violated_constraints)}"
            + (f" ({extent})" if extent else "")
        )
        self._repo.update_impact_evaluation(evaluation)
        self._events.append(
            journey_id,
            EventType.OBJECTIVE_VIOLATED,
            {
                "description": evaluation.violation_description,
                "violated_constraints": violated_constraints,
            },
        )

        if self._superseded(journey_id, evaluation.triggering_sequence, wake_event.event_id):
            return self._mark_superseded(evaluation, journey_id, wake_event.event_id)

        return self._search_score_verify_recommend(evaluation, journey, wake_event, now)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_departed(self, objective: "TravelObjective", now: datetime) -> bool:
        if objective.departure_date is None:
            return False
        try:
            departure = datetime.strptime(objective.departure_date.value, _DATE_FMT)
        except (ValueError, TypeError):
            return False
        return departure.date() < now.date()

    def _extract_claimed_arrival(self, order_reference: object) -> datetime | None:
        if not order_reference or not isinstance(order_reference, str):
            return None
        import json

        notifications = self._repo.get_notifications_for_order(order_reference)
        for notification in reversed(notifications):
            if notification.declared_event_type != "schedule.changed":
                continue
            try:
                data = json.loads(notification.raw_payload_json).get("data", {})
            except (ValueError, TypeError):
                continue
            raw = data.get("revisedArrivalTime")
            if not raw:
                continue
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
        return None

    def _evaluate_latest_arrival(
        self, objective: "TravelObjective", claimed_arrival: datetime | None
    ) -> tuple[list[str], str | None]:
        if claimed_arrival is None or objective.latest_arrival is None:
            return [], None
        if objective.latest_arrival.constraint_type != ConstraintType.HARD:
            return [], None

        deadline = datetime.strptime(objective.latest_arrival.value, _ARRIVAL_TIME_FMT)
        claimed_naive = claimed_arrival.replace(tzinfo=None)
        if claimed_naive <= deadline:
            return [], None

        overage_minutes = int((claimed_naive - deadline).total_seconds() // 60)
        return ["latest_arrival"], f"{overage_minutes} minutes late"

    def _superseded(self, journey_id: str, triggering_sequence: int, current_event_id: str) -> bool:
        newer = self._repo.get_events_from_sequence(journey_id, from_sequence=triggering_sequence)
        for event in newer:
            if event.event_type == EventType.WAKE_REQUESTED and event.event_id != current_event_id:
                return True
        return False

    def _mark_superseded(
        self, evaluation: ImpactEvaluation, journey_id: str, current_event_id: str
    ) -> ImpactEvaluation:
        newer = self._repo.get_events_from_sequence(
            journey_id, from_sequence=evaluation.triggering_sequence
        )
        superseding_id = next(
            (e.event_id for e in newer if e.event_type == EventType.WAKE_REQUESTED
             and e.event_id != current_event_id),
            current_event_id,
        )
        evaluation.status = EvaluationStatus.SUPERSEDED
        evaluation.concluded_at = datetime.now(tz=timezone.utc)
        self._repo.update_impact_evaluation(evaluation)
        self._events.append(
            journey_id,
            EventType.IMPACT_EVALUATION_SUPERSEDED,
            {"evaluation_id": evaluation.evaluation_id, "superseded_by_event_id": superseding_id},
        )
        return evaluation

    def _search_score_verify_recommend(
        self,
        evaluation: ImpactEvaluation,
        journey: "JourneyRecord",
        wake_event: JourneyEvent,
        now: datetime,
    ) -> ImpactEvaluation:
        journey_id = evaluation.journey_id
        no_alternative_reason: str | None = "none_found"
        recommendation: Recommendation | None = None

        try:
            search_result = self._search.search(journey_id, now)
        except BudgetExhaustedError:
            search_result = None
            no_alternative_reason = "budget_exhausted"

        if search_result is not None and search_result.options:
            recommendation, reason = self._try_score_and_verify(
                evaluation, journey.objective, search_result.options, now
            )
            if recommendation is None and reason is not None:
                no_alternative_reason = reason

            if recommendation is None and self._has_budget_only_blocker(
                journey.objective, search_result.options, now
            ):
                recommendation = self._try_relaxed_budget_recommendation(
                    evaluation, journey.objective, search_result.options, now
                )
                if recommendation is not None:
                    no_alternative_reason = None

        if self._superseded(journey_id, evaluation.triggering_sequence, wake_event.event_id):
            return self._mark_superseded(evaluation, journey_id, wake_event.event_id)

        if recommendation is not None:
            self._repo.save_recommendation(recommendation)
            evaluation.recommendation_id = recommendation.recommendation_id
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.concluded_at = datetime.now(tz=timezone.utc)
            self._repo.update_impact_evaluation(evaluation)
            self._events.append(
                journey_id,
                EventType.ALTERNATIVE_RECOMMENDED,
                {
                    "evaluation_id": evaluation.evaluation_id,
                    "recommendation_id": recommendation.recommendation_id,
                    "option_id": recommendation.option_id,
                    "cost_relative_description": recommendation.cost_relative_description,
                    "rationale": recommendation.rationale,
                    "constraint_breach": recommendation.constraint_breach,
                    "constraint_breach_detail": recommendation.constraint_breach_detail,
                },
            )
        else:
            evaluation.no_alternative_reason = no_alternative_reason
            evaluation.status = EvaluationStatus.COMPLETED
            evaluation.concluded_at = datetime.now(tz=timezone.utc)
            self._repo.update_impact_evaluation(evaluation)
            self._events.append(
                journey_id,
                EventType.NO_ALTERNATIVE_FOUND,
                {"evaluation_id": evaluation.evaluation_id},
            )

        return evaluation

    def _try_score_and_verify(
        self,
        evaluation: ImpactEvaluation,
        objective: "TravelObjective",
        options: list["FlightOption"],
        now: datetime,
    ) -> tuple[Recommendation | None, str | None]:
        scoring_run = self._scoring.score(objective, options, now)
        survivors = [
            so for so in scoring_run.scored_options if so.outcome != ScoringOutcome.ELIMINATED
        ]
        if not survivors:
            return None, "none_found"

        ranked = sorted(survivors, key=lambda so: (so.rank if so.rank is not None else 10**9))
        any_attempted = False
        for scored in ranked:
            any_attempted = True
            try:
                result = self._verification.verify(
                    journey_id=evaluation.journey_id, option_id=scored.option.option_id, now=now
                )
            except BudgetExhaustedError:
                return None, "budget_exhausted"
            if result.outcome == PriceVerificationOutcome.VERIFIED:
                recommendation = self._build_recommendation(evaluation, scored.option, result)
                return recommendation, None
            if self._superseded(evaluation.journey_id, evaluation.triggering_sequence, evaluation.triggering_event_id):
                return None, "none_found"

        return (None, "all_expired") if any_attempted else (None, "none_found")

    def _has_budget_only_blocker(
        self, objective: "TravelObjective", options: list["FlightOption"], now: datetime
    ) -> bool:
        if objective.budget_amount is None or objective.budget_amount.constraint_type != ConstraintType.HARD:
            return False
        run = self._scoring.score(objective, options, now)
        if run.no_satisfying_option is None:
            return False
        constraints = set(run.no_satisfying_option.unsatisfied_constraints)
        return constraints == {"budget_amount"}

    def _try_relaxed_budget_recommendation(
        self,
        evaluation: ImpactEvaluation,
        objective: "TravelObjective",
        options: list["FlightOption"],
        now: datetime,
    ) -> Recommendation | None:
        if objective.budget_amount is None:
            return None
        relaxed = objective.model_copy(
            update={
                "budget_amount": objective.budget_amount.model_copy(
                    update={"constraint_type": ConstraintType.SOFT}
                )
            }
        )
        run = self._scoring.score(relaxed, options, now)
        survivors = [so for so in run.scored_options if so.outcome != ScoringOutcome.ELIMINATED]
        if not survivors:
            return None
        ranked = sorted(survivors, key=lambda so: (so.rank if so.rank is not None else 10**9))
        for scored in ranked:
            try:
                result = self._verification.verify(
                    journey_id=evaluation.journey_id, option_id=scored.option.option_id, now=now
                )
            except BudgetExhaustedError:
                return None
            if result.outcome == PriceVerificationOutcome.VERIFIED:
                total_cost = scored.option.adult_price + scored.option.adult_tax
                budget = objective.budget_amount.value
                if total_cost > budget:
                    return self._build_recommendation(
                        evaluation,
                        scored.option,
                        result,
                        constraint_breach=True,
                        constraint_breach_detail=(
                            f"Exceeds stated budget of {budget} "
                            f"{objective.budget_currency.value if objective.budget_currency else ''}"
                        ).strip(),
                    )
        return None

    def _build_recommendation(
        self,
        evaluation: ImpactEvaluation,
        option: "FlightOption",
        verification_result: "VerificationResult",
        constraint_breach: bool = False,
        constraint_breach_detail: str | None = None,
    ) -> Recommendation:
        cost_relative_description = self._cost_relative_description(evaluation.journey_id, option)
        rationale = "Restores the objective's arrival requirement, independently verified available."
        return Recommendation(
            recommendation_id=str(uuid.uuid4()),
            evaluation_id=evaluation.evaluation_id,
            option_id=option.option_id,
            verification_id=verification_result.verification_id,
            cost_relative_description=cost_relative_description,
            rationale=rationale,
            constraint_breach=constraint_breach,
            constraint_breach_detail=constraint_breach_detail,
        )

    def _cost_relative_description(self, journey_id: str, option: "FlightOption") -> str:
        alt_total = option.adult_price + option.adult_tax
        order_no = self._repo.get_order_no_for_journey(journey_id)
        current_option = None
        if order_no is not None:
            order = self._repo.get_order_by_order_no(order_no)
            if order is not None:
                current_option = self._repo.get_flight_option(order.option_id)
        if current_option is None:
            return f"{alt_total} {option.currency} (no current booking to compare against)"

        current_total = current_option.adult_price + current_option.adult_tax
        diff: Decimal = alt_total - current_total
        sign = "+" if diff >= 0 else "-"
        return f"{sign}{abs(diff)} {option.currency} vs. current booking"
