from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from journey.errors import (
    OrderNotFoundError,
    RecommendationNotFoundError,
    RecoveryAlreadyAttemptedError,
)
from journey.models.booking import OrderOutcome, PaymentOutcome
from journey.models.events import EventType
from journey.models.recovery_execution import (
    CancellationAttempt,
    CancellationOutcome,
    RecoveryExecution,
    RecoveryExecutionStatus,
    ReplacementOutcome,
)
from journey.models.verification import VerificationOutcome

if TYPE_CHECKING:
    from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine
    from journey.services.booking_service import BookingService
    from journey.services.event_service import EventService
    from journey.services.verification_service import VerificationService
    from journey.storage.repository import JourneyRepository

_ATLAS_VOID_URL = "https://sandbox.atriptech.com/void.do"
_ATLAS_QUERY_URL = "https://sandbox.atriptech.com/queryOrderDetails.do"


class RecoveryExecutionService:
    def __init__(
        self,
        repo: "JourneyRepository",
        http_client: httpx.Client,
        event_service: "EventService",
        booking_service: "BookingService",
        verification_service: "VerificationService",
        authorisation_engine: "AuthorisationPolicyEngine",
    ) -> None:
        self._repo = repo
        self._http = http_client
        self._events = event_service
        self._booking = booking_service
        self._verification = verification_service
        self._authorisation = authorisation_engine

    def execute(self, recommendation_id: str, now: datetime) -> RecoveryExecution:
        recommendation = self._repo.get_recommendation(recommendation_id)
        if recommendation is None:
            raise RecommendationNotFoundError(recommendation_id)

        if self._repo.get_recovery_execution_by_recommendation(recommendation_id) is not None:
            raise RecoveryAlreadyAttemptedError(recommendation_id)

        journey_id = self._journey_id_for(recommendation)

        execution = RecoveryExecution(
            recovery_execution_id=str(uuid.uuid4()),
            recommendation_id=recommendation_id,
            journey_id=journey_id,
            started_at=now,
        )
        self._repo.save_recovery_execution(execution)

        # FR-002: fresh re-verification immediately before executing
        verification = self._verification.verify(
            journey_id=journey_id, option_id=recommendation.option_id, now=now
        )
        if verification.outcome == VerificationOutcome.PRICE_CHANGED:
            return self._abandon(execution, "price_changed", now)
        if verification.outcome != VerificationOutcome.VERIFIED:
            return self._abandon(execution, "alternative_unavailable", now)

        option = self._repo.get_flight_option(recommendation.option_id)
        assert option is not None  # guaranteed by a VERIFIED verification outcome above
        current_cost_amount = option.adult_price + option.adult_tax

        # FR-001: authorisation must already be granted for this exact action/price
        authorised = self._authorisation.enforce_authorised(
            journey_id=journey_id,
            action_id=recommendation_id,
            current_cost_amount=current_cost_amount,
        )
        if not authorised:
            return self._abandon(execution, "not_authorised", now)

        # research.md R3: capture the superseded order before it exists
        execution.superseded_order_no = self._repo.get_order_no_for_journey(journey_id)

        order = self._booking.create_order(journey_id, recommendation.option_id, now)
        if order.outcome != OrderOutcome.CREATED or order.order_no is None:
            execution.replacement_outcome = ReplacementOutcome.FAILED
            execution.cancellation_outcome = CancellationOutcome.NOT_ATTEMPTED
            return self._abandon(execution, "replacement_creation_failed", now)

        payment = self._booking.submit_payment(journey_id, order.order_no, now)
        if payment.outcome != PaymentOutcome.SUCCESS:
            execution.replacement_outcome = ReplacementOutcome.FAILED
            execution.cancellation_outcome = CancellationOutcome.NOT_ATTEMPTED
            return self._abandon(execution, "replacement_payment_failed", now)

        ticketing = self._booking.confirm_ticketing(journey_id, order.order_no, now)
        if not ticketing.confirmed:
            execution.replacement_outcome = ReplacementOutcome.FAILED
            execution.cancellation_outcome = CancellationOutcome.NOT_ATTEMPTED
            return self._abandon(execution, "replacement_creation_failed", now)

        # FR-009: replacement confirmed — only now update the journey's current booking
        execution.replacement_order_no = order.order_no
        execution.replacement_outcome = ReplacementOutcome.SUCCEEDED
        self._repo.set_current_order(journey_id, order.order_no)
        self._events.append(
            journey_id,
            EventType.REPLACEMENT_SECURED,
            {
                "recovery_execution_id": execution.recovery_execution_id,
                "recommendation_id": recommendation_id,
                "replacement_order_no": order.order_no,
                "superseded_order_no": execution.superseded_order_no,
            },
        )

        # FR-005: initiate cancellation of the superseded booking, only now
        if execution.superseded_order_no is not None:
            cancellation_outcome = self._cancel_superseded_booking(
                journey_id, execution.superseded_order_no, now, execution.recovery_execution_id
            )
            execution.cancellation_outcome = cancellation_outcome
        else:
            execution.cancellation_outcome = CancellationOutcome.NOT_ATTEMPTED

        execution.final_position_description = self._final_position(journey_id)
        execution.status = RecoveryExecutionStatus.COMPLETED
        execution.concluded_at = now
        self._repo.update_recovery_execution(execution)
        self._events.append(
            journey_id,
            EventType.RECOVERY_EXECUTION_COMPLETED,
            {
                "recovery_execution_id": execution.recovery_execution_id,
                "recommendation_id": recommendation_id,
                "replacement_outcome": execution.replacement_outcome.value,
                "cancellation_outcome": execution.cancellation_outcome.value,
                "final_position_description": execution.final_position_description,
            },
        )
        return execution

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _journey_id_for(self, recommendation: Any) -> str:
        # Recommendation carries no journey_id directly; resolve it via the
        # flight option it references (every FlightOption is journey-scoped).
        option = self._repo.get_flight_option(recommendation.option_id)
        if option is None:
            raise ValueError(f"Flight option not found: {recommendation.option_id!r}")
        return option.journey_id

    def _abandon(
        self, execution: RecoveryExecution, reason: str, now: datetime
    ) -> RecoveryExecution:
        execution.status = RecoveryExecutionStatus.ABANDONED
        execution.abandonment_reason = reason
        execution.concluded_at = now
        self._repo.update_recovery_execution(execution)
        self._events.append(
            execution.journey_id,
            EventType.RECOVERY_EXECUTION_ABANDONED,
            {
                "recovery_execution_id": execution.recovery_execution_id,
                "recommendation_id": execution.recommendation_id,
                "abandonment_reason": reason,
            },
        )
        return execution

    def _cancel_superseded_booking(
        self, journey_id: str, order_no: str, now: datetime, recovery_execution_id: str
    ) -> CancellationOutcome:
        attempt_id = str(uuid.uuid4())
        try:
            response = self._http.post(
                _ATLAS_VOID_URL,
                json={"cid": "<client id>", "orderNo": order_no, "requestSource": "antabay"},
            )
            raw_response_json = response.text
            outcome = "INITIATED"
        except httpx.HTTPError:
            raw_response_json = None
            outcome = "ERROR"

        # NFR-002: the cancellation call's own response is never trusted on
        # its own — an independent reconciliation query decides the outcome
        # (research.md R1's provisional success predicate).
        reconciliation_response = self._http.post(
            _ATLAS_QUERY_URL,
            json={"cid": "<client id>", "orderNo": order_no, "requestSource": "antabay"},
        )
        try:
            reconciliation_json: dict[str, Any] = reconciliation_response.json()
        except Exception:
            reconciliation_json = {}

        pax_infos = reconciliation_json.get("paxTicketInfos") or []
        ticket_numbers = [p.get("ticketNos", []) for p in pax_infos]
        still_ticketed = bool(ticket_numbers) and all(bool(nos) for nos in ticket_numbers)
        confirmed_cancelled = not still_ticketed

        cancellation_attempt = CancellationAttempt(
            attempt_id=attempt_id,
            journey_id=journey_id,
            order_no=order_no,
            requested_at=now,
            responded_at=now,
            outcome=outcome,
            raw_response_json=raw_response_json,
            reconciliation_raw_json=json.dumps(reconciliation_json),
            confirmed_cancelled=confirmed_cancelled,
        )
        self._repo.save_cancellation_attempt(cancellation_attempt)

        cancellation_outcome = (
            CancellationOutcome.SUCCEEDED if confirmed_cancelled else CancellationOutcome.FAILED
        )
        self._events.append(
            journey_id,
            EventType.CANCELLATION_OUTCOME_RECORDED,
            {
                "recovery_execution_id": recovery_execution_id,
                "order_no": order_no,
                "outcome": cancellation_outcome.value,
            },
        )
        return cancellation_outcome

    def _final_position(self, journey_id: str) -> str:
        journey = self._repo.get_journey(journey_id)
        if journey.objective.latest_arrival is not None:
            return "latest_arrival now satisfied by the replacement booking"
        return "objective satisfied by the replacement booking"
