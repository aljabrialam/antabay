"""Unit tests for ObjectiveParser — uses a mock DashScope client."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from journey.models.objective import (
    ConstrainedField,
    ConstraintType,
    ParseResult,
    TravelObjective,
)
from journey.services.objective_parser import ObjectiveParser


def _make_dashscope_response(fields: dict) -> MagicMock:
    """Build a minimal DashScope function-call response stub."""
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(fields)
    choice = MagicMock()
    choice.message.tool_calls = [tool_call]
    response = MagicMock()
    response.output.choices = [choice]
    response.status_code = 200
    return response


class TestObjectiveParserReturnsParseResult:
    def test_parse_returns_parse_result_type(self) -> None:
        parser = ObjectiveParser()
        response = _make_dashscope_response(
            {
                "origin": {"value": "SIN", "constraint_type": "HARD"},
                "destination": {"value": "LHR", "constraint_type": "HARD"},
                "latest_arrival": {"value": "2026-09-01T14:00:00", "constraint_type": "HARD"},
                "budget_amount": {"value": "1200", "constraint_type": "SOFT"},
                "budget_currency": {"value": "SGD", "constraint_type": "SOFT"},
                "pax_count": {"value": 1, "constraint_type": "HARD"},
                "preferences": {"value": ["aisle seat"], "constraint_type": "SOFT"},
            }
        )
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ):
            result = parser.parse("Fly from SIN to LHR by 1 Sep 2026 for under SGD 1200")
        assert isinstance(result, ParseResult)
        assert isinstance(result.objective, TravelObjective)

    def test_absent_fields_reported_not_defaulted(self) -> None:
        parser = ObjectiveParser()
        # DashScope returns a response with several fields missing
        response = _make_dashscope_response(
            {
                "origin": {"value": "SIN", "constraint_type": "HARD"},
                "destination": {"value": "LHR", "constraint_type": "HARD"},
            }
        )
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ):
            result = parser.parse("Fly from SIN to LHR")
        assert "latest_arrival" in result.absent_fields
        assert "budget_amount" in result.absent_fields
        assert "budget_currency" in result.absent_fields
        assert "pax_count" in result.absent_fields
        assert result.objective.latest_arrival is None
        assert result.objective.budget_amount is None

    def test_absent_fields_are_null_not_defaulted(self) -> None:
        parser = ObjectiveParser()
        response = _make_dashscope_response({})
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ):
            result = parser.parse("I want to travel")
        # All 7 fields absent — none should be defaulted
        assert len(result.absent_fields) == 7
        assert result.objective.origin is None
        assert result.objective.destination is None

    def test_same_input_produces_same_output(self) -> None:
        parser = ObjectiveParser()
        response = _make_dashscope_response(
            {
                "origin": {"value": "SIN", "constraint_type": "HARD"},
                "destination": {"value": "NRT", "constraint_type": "HARD"},
            }
        )
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ) as mock_call:
            result1 = parser.parse("Fly SIN to NRT")
            result2 = parser.parse("Fly SIN to NRT")
        # Same canonical input → same DashScope call args each time
        assert mock_call.call_count == 2
        first_call_args = mock_call.call_args_list[0]
        second_call_args = mock_call.call_args_list[1]
        assert first_call_args == second_call_args
        assert result1.objective.origin == result2.objective.origin
        assert result1.objective.destination == result2.objective.destination

    def test_input_is_nfc_normalised_before_call(self) -> None:
        import unicodedata

        parser = ObjectiveParser()
        response = _make_dashscope_response({})
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ) as mock_call:
            # Decomposed form of "é" (e + combining acute accent)
            parser.parse("Fly to Café\u0301")
        # The messages sent to DashScope must contain NFC-normalised text
        call_kwargs = mock_call.call_args
        messages = call_kwargs[1].get("messages") or call_kwargs[0][1]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert unicodedata.is_normalized("NFC", user_content)

    def test_ambiguous_fields_listed(self) -> None:
        parser = ObjectiveParser()
        # DashScope returns explicit ambiguous markers
        response = _make_dashscope_response(
            {
                "origin": {"value": "SIN", "constraint_type": "HARD"},
                "_ambiguous_fields": ["budget_amount"],
            }
        )
        with patch(
            "journey.services.objective_parser.Generation.call",
            return_value=response,
        ):
            result = parser.parse("Fly from SIN, budget unclear")
        assert "budget_amount" in result.ambiguous_fields
