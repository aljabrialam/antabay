from __future__ import annotations

from typing import Any

from journey.models.verification_gate import ConditionResult, ReconciliationBound

# Matches the observed tktLimitTime window from
# .antabay/atlas-capability-map.md section 7b (17:22:46 -> 17:52:46).
_TICKETING_RECONCILIATION_SECONDS = 30 * 60


def normalise_status(value: str | int | None) -> str | None:
    """Normalise a status value to a common (string) type before comparing
    it across surfaces that report it differently (FR-008, research.md R5).
    The one proven instance: orderStatus as a string from
    queryOrderDetails.do vs. an integer from the order.ticketed webhook."""
    return None if value is None else str(value)


class TicketingSuccessCondition:
    """The flagship SuccessCondition (FR-004), reproducing spec 005's own
    ticketing rule independently (research.md R7) — not imported from
    booking_service.py."""

    def classify(self, query_result: Any) -> ConditionResult:
        pax_infos = query_result.get("paxTicketInfos") or []
        ticket_numbers = [p.get("ticketNos", []) for p in pax_infos]
        confirmed = bool(ticket_numbers) and all(bool(nos) for nos in ticket_numbers)

        if confirmed:
            return ConditionResult.SUCCESS
        if query_result.get("errorCode") is not None:
            return ConditionResult.FAILURE
        return ConditionResult.INCONCLUSIVE

    def has_discrepancy(self, action_response: Any, query_result: Any) -> bool:
        action_status = normalise_status(action_response.get("orderStatus"))
        query_status = normalise_status(query_result.get("orderStatus"))
        if action_status is None:
            return False
        return action_status != query_status

    def reconciliation_bound(self) -> ReconciliationBound:
        return ReconciliationBound(max_duration_seconds=_TICKETING_RECONCILIATION_SECONDS)
