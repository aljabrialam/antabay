"""Unit tests for TicketingSuccessCondition (T011, T020, T035).

Reuses the exact query-result shapes already proven by spec 005's
cassette-backed contract tests (backend/tests/unit/test_booking_service.py's
_query_response() helper and its TestConfirmTicketing* fixtures) — per
Constitution Principle XI, this feature adds no new cassette of its own
since the underlying provider contract is already verified there.

TDD gate (T012, T021, T036): must fail with NotImplementedError against
the Phase 2 skeleton before implementation.
"""
from __future__ import annotations

from typing import Any


def _query_response(ticket_numbers: list[list[str]], error_code: str | None = None) -> dict[str, Any]:
    """Identical to test_booking_service.py's helper of the same name."""
    return {
        "orderStatus": "1",
        "ticketStatus": "0",
        "paxTicketInfos": [{"ticketNos": nos} for nos in ticket_numbers],
        "errorCode": error_code,
        "errorMessage": None,
    }


def _condition() -> Any:
    from journey.services.conditions.ticketing_condition import TicketingSuccessCondition

    return TicketingSuccessCondition()


class TestTicketingConditionMatchesSpec005:
    def test_all_passengers_ticketed_is_success(self) -> None:
        from journey.models.verification_gate import ConditionResult

        # Matches test_booking_service.py::TestConfirmTicketingAllPassengers
        response = _query_response(ticket_numbers=[["S46659"], ["S46660"]])
        assert _condition().classify(response) is ConditionResult.SUCCESS

    def test_partial_passengers_ticketed_is_inconclusive(self) -> None:
        from journey.models.verification_gate import ConditionResult

        # Matches test_booking_service.py::TestConfirmTicketingPartialResult
        response = _query_response(ticket_numbers=[["S46659"], []])
        assert _condition().classify(response) is ConditionResult.INCONCLUSIVE

    def test_error_code_present_is_failure(self) -> None:
        from journey.models.verification_gate import ConditionResult

        # Matches test_booking_service.py::TestConfirmTicketingTerminalError
        response = _query_response(ticket_numbers=[[]], error_code="800")
        assert _condition().classify(response) is ConditionResult.FAILURE


class TestTicketingConditionDiscrepancy:
    def test_webhook_claims_ticketed_but_query_disagrees(self) -> None:
        # The webhook (order.ticketed) reports orderStatus as an integer;
        # capability map section 7c's inferred enum: 2 == ticketed.
        action_response = {"orderStatus": 2}
        query_result = _query_response(ticket_numbers=[[]])  # not yet ticketed, orderStatus "1"

        assert _condition().has_discrepancy(action_response, query_result) is True


class TestNormalizedStatusNoFalseDiscrepancy:
    def test_same_status_different_types_is_not_a_discrepancy(self) -> None:
        # The exact type mismatch documented in
        # .antabay/atlas-capability-map.md section 7c: the order.ticketed
        # webhook reports orderStatus as an integer (2), while
        # queryOrderDetails.do reports the equivalent status as a string ("2").
        action_response = {"orderStatus": 2}
        query_result = _query_response(ticket_numbers=[["S46659"]])
        query_result["orderStatus"] = "2"

        assert _condition().has_discrepancy(action_response, query_result) is False
