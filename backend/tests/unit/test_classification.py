"""Unit tests for HARD/SOFT classification correctness — FR-003, SC-006."""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from journey.models.objective import ConstraintType
from journey.services.objective_parser import ObjectiveParser


def _make_response(fields: dict) -> MagicMock:
    tool_call = MagicMock()
    tool_call.function.arguments = json.dumps(fields)
    choice = MagicMock()
    choice.message.tool_calls = [tool_call]
    response = MagicMock()
    response.output.choices = [choice]
    response.status_code = 200
    return response


class TestConstraintTypeClassification:
    def test_hard_budget_constraint(self) -> None:
        """'maximum budget £2000' → budget HARD (cannot exceed)."""
        parser = ObjectiveParser()
        response = _make_response(
            {
                "budget_amount": {"value": "2000", "constraint_type": "HARD"},
                "budget_currency": {"value": "GBP", "constraint_type": "HARD"},
            }
        )
        with patch("journey.services.objective_parser.Generation.call", return_value=response):
            result = parser.parse("maximum budget £2000")
        assert result.objective.budget_amount is not None
        assert result.objective.budget_amount.constraint_type == ConstraintType.HARD
        assert result.objective.budget_amount.value == Decimal("2000")

    def test_soft_preference_classification(self) -> None:
        """'window seat preferred' → preferences SOFT."""
        parser = ObjectiveParser()
        response = _make_response(
            {
                "preferences": {"value": ["window seat"], "constraint_type": "SOFT"},
            }
        )
        with patch("journey.services.objective_parser.Generation.call", return_value=response):
            result = parser.parse("window seat preferred")
        assert result.objective.preferences is not None
        assert result.objective.preferences.constraint_type == ConstraintType.SOFT
        assert "window seat" in result.objective.preferences.value

    def test_hard_arrival_deadline(self) -> None:
        """'must arrive by Friday' → latest_arrival HARD."""
        parser = ObjectiveParser()
        response = _make_response(
            {
                "latest_arrival": {"value": "2026-09-04T23:59:00", "constraint_type": "HARD"},
            }
        )
        with patch("journey.services.objective_parser.Generation.call", return_value=response):
            result = parser.parse("must arrive by Friday")
        assert result.objective.latest_arrival is not None
        assert result.objective.latest_arrival.constraint_type == ConstraintType.HARD

    def test_ambiguous_classification_reported_in_ambiguous_fields(self) -> None:
        """Genuinely ambiguous constraint type → field in ambiguous_fields, not silently defaulted."""
        parser = ObjectiveParser()
        response = _make_response(
            {
                "budget_amount": {"value": "500", "constraint_type": "SOFT"},
                "budget_currency": {"value": "USD", "constraint_type": "SOFT"},
                "_ambiguous_fields": ["budget_amount"],
            }
        )
        with patch("journey.services.objective_parser.Generation.call", return_value=response):
            result = parser.parse("around $500 maybe")
        assert "budget_amount" in result.ambiguous_fields

    def test_constraint_type_preserved_for_each_field_independently(self) -> None:
        """Each field carries its own constraint_type independently."""
        parser = ObjectiveParser()
        response = _make_response(
            {
                "origin": {"value": "SIN", "constraint_type": "HARD"},
                "destination": {"value": "LHR", "constraint_type": "HARD"},
                "preferences": {"value": ["aisle seat"], "constraint_type": "SOFT"},
                "budget_amount": {"value": "1500", "constraint_type": "SOFT"},
                "budget_currency": {"value": "SGD", "constraint_type": "SOFT"},
            }
        )
        with patch("journey.services.objective_parser.Generation.call", return_value=response):
            result = parser.parse(
                "I must fly SIN to LHR, aisle seat if possible, budget around SGD 1500"
            )
        obj = result.objective
        assert obj.origin is not None and obj.origin.constraint_type == ConstraintType.HARD
        assert obj.destination is not None and obj.destination.constraint_type == ConstraintType.HARD
        assert obj.preferences is not None and obj.preferences.constraint_type == ConstraintType.SOFT
        assert obj.budget_amount is not None and obj.budget_amount.constraint_type == ConstraintType.SOFT
