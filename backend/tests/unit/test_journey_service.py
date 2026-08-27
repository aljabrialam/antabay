"""Failing unit tests for JourneyService.create_journey (T018)."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
from journey.models.journey import JourneyRecord, JourneyState
from journey.services.journey_service import JourneyService


def _minimal_objective() -> TravelObjective:
    return TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
    )


class TestJourneyServiceCreateJourney:
    def test_returns_journey_record(self) -> None:
        repo = MagicMock()
        repo.insert_journey.return_value = None
        svc = JourneyService(repository=repo)
        record = svc.create_journey(_minimal_objective())
        assert isinstance(record, JourneyRecord)

    def test_state_is_objective_confirmed(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        record = svc.create_journey(_minimal_objective())
        assert record.state == JourneyState.OBJECTIVE_CONFIRMED

    def test_journey_id_is_unique_across_calls(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        r1 = svc.create_journey(_minimal_objective())
        r2 = svc.create_journey(_minimal_objective())
        assert r1.journey_id != r2.journey_id

    def test_repository_insert_called_once(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        record = svc.create_journey(_minimal_objective())
        repo.insert_journey.assert_called_once()

    def test_repository_receives_correct_record(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        obj = _minimal_objective()
        record = svc.create_journey(obj)
        inserted = repo.insert_journey.call_args[0][0]
        assert inserted.journey_id == record.journey_id
        assert inserted.objective == obj

    def test_one_decision_audit_entry_appended(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        record = svc.create_journey(_minimal_objective())
        # The insert call must pass a record with exactly one audit entry
        inserted: JourneyRecord = repo.insert_journey.call_args[0][0]
        assert len(inserted.audit_entries) == 1
        entry = inserted.audit_entries[0]
        assert entry.entry_type == "DECISION"

    def test_audit_entry_text_describes_creation(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        svc.create_journey(_minimal_objective())
        inserted: JourneyRecord = repo.insert_journey.call_args[0][0]
        entry = inserted.audit_entries[0]
        assert "confirmed objective" in entry.content.lower()

    def test_schema_version_is_one(self) -> None:
        repo = MagicMock()
        svc = JourneyService(repository=repo)
        record = svc.create_journey(_minimal_objective())
        assert record.schema_version == 1
