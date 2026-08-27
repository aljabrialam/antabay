"""Contract tests for ObjectiveParser — wired to VCR cassettes (T017).

Cassettes live under fixtures/journey/cassettes/ and are captured from live
DashScope calls (never handwritten — Constitution XI).  For the RED phase these
tests are expected to fail with ImportError; cassettes are not required yet.
"""
from __future__ import annotations

import pytest

from journey.models.objective import ParseResult, TravelObjective
from journey.services.objective_parser import ObjectiveParser


@pytest.fixture(scope="module")
def vcr_cassette_dir() -> str:
    return "fixtures/journey/cassettes"


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    return {"record_mode": "none"}


@pytest.fixture
def parser() -> ObjectiveParser:
    return ObjectiveParser()


@pytest.mark.vcr
class TestObjectiveParserCompleteGoal:
    def test_all_fields_populated_for_complete_goal(self, parser: ObjectiveParser) -> None:
        result = parser.parse(
            "I need to fly from Singapore to London Heathrow, "
            "arriving by 1 September 2026 at 18:00. "
            "Budget is SGD 1500 hard limit. Two travellers. "
            "Prefer aisle seats and direct flights."
        )
        assert isinstance(result, ParseResult)
        assert result.objective.origin is not None
        assert result.objective.destination is not None
        assert result.objective.latest_arrival is not None
        assert result.objective.budget_amount is not None
        assert result.objective.budget_currency is not None
        assert result.objective.pax_count is not None
        assert result.objective.preferences is not None
        assert result.absent_fields == []


@pytest.mark.vcr
class TestObjectiveParserIncompleteGoal:
    def test_absent_fields_non_empty_for_partial_goal(self, parser: ObjectiveParser) -> None:
        result = parser.parse("I want to fly to Tokyo next month.")
        assert isinstance(result, ParseResult)
        assert len(result.absent_fields) > 0
        # Origin not stated — must be absent, not guessed
        assert "origin" in result.absent_fields
        assert result.objective.origin is None

    def test_absent_fields_never_defaulted(self, parser: ObjectiveParser) -> None:
        result = parser.parse("Travel somewhere warm.")
        for field in result.absent_fields:
            assert getattr(result.objective, field) is None


@pytest.mark.vcr
class TestObjectiveParserAmbiguousConstraint:
    def test_ambiguous_constraint_surfaced_not_assumed(self, parser: ObjectiveParser) -> None:
        result = parser.parse(
            "Fly from SIN to NRT, I'd like to spend around SGD 800 but I'm flexible."
        )
        assert isinstance(result, ParseResult)
        # Ambiguous budget constraint must be recorded, not silently classified
        assert len(result.ambiguous_fields) > 0
