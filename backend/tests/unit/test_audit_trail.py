"""Failing unit tests for append-only audit trail (T032)."""
from __future__ import annotations

import pytest

from journey.models.journey import AuditEntry, JourneyRecord, JourneyState
from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
from journey.storage.repository import JourneyRepository


def _repo_with_journey() -> tuple[JourneyRepository, JourneyRecord]:
    """Return a repo backed by in-memory SQLite with one journey inserted."""
    from journey.storage.db import reset_engine
    from journey.storage.tables import metadata
    from sqlalchemy import create_engine

    engine = create_engine("sqlite:///:memory:", future=True)
    reset_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    reset_engine("sqlite:///:memory:")

    # Re-create so reset_engine shares the same in-memory DB
    import os
    os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
    from journey.storage.db import reset_engine as re
    re()
    from journey.storage.tables import metadata as m
    from journey.storage.db import get_engine
    m.create_all(get_engine())

    obj = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
    )
    from journey.services.journey_service import JourneyService
    repo = JourneyRepository()
    svc = JourneyService(repository=repo)
    record = svc.create_journey(obj)
    return repo, record


class TestAuditTrailAppend:
    def setup_method(self) -> None:
        import os
        os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
        from journey.storage.db import reset_engine
        from journey.storage.tables import metadata
        from journey.storage.db import get_engine
        reset_engine()
        metadata.create_all(get_engine())

    def test_append_increases_entry_count_by_one(self) -> None:
        from journey.services.journey_service import JourneyService
        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        before = len(repo.get_audit_trail(record.journey_id))
        repo.append_audit_entry(record.journey_id, "OBSERVATION", "test observation")
        after = len(repo.get_audit_trail(record.journey_id))
        assert after == before + 1

    def test_sequence_is_monotonically_increasing(self) -> None:
        from journey.services.journey_service import JourneyService
        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        repo.append_audit_entry(record.journey_id, "OBSERVATION", "first")
        repo.append_audit_entry(record.journey_id, "OBSERVATION", "second")
        trail = repo.get_audit_trail(record.journey_id)
        sequences = [e.sequence for e in trail]
        assert sequences == sorted(sequences)
        assert len(set(sequences)) == len(sequences)

    def test_no_update_entry_method_on_repository(self) -> None:
        repo = JourneyRepository()
        assert not hasattr(repo, "update_entry")

    def test_no_delete_entry_method_on_repository(self) -> None:
        repo = JourneyRepository()
        assert not hasattr(repo, "delete_entry")

    def test_get_audit_trail_returns_all_entries_in_order(self) -> None:
        from journey.services.journey_service import JourneyService
        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="KUL", constraint_type=ConstraintType.SOFT),
        )
        record = svc.create_journey(obj)
        repo.append_audit_entry(record.journey_id, "OBSERVATION", "obs-1")
        repo.append_audit_entry(record.journey_id, "OBSERVATION", "obs-2")
        trail = repo.get_audit_trail(record.journey_id)
        assert len(trail) == 3  # 1 DECISION from create + 2 OBSERVATION
        contents = [e.content for e in trail]
        assert "obs-1" in contents
        assert "obs-2" in contents
