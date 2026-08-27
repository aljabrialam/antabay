"""Integration tests for journey persistence and reconstruction (T041)."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
from journey.models.journey import JourneyState


def _fresh_db() -> None:
    os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
    from journey.storage.db import reset_engine
    from journey.storage.tables import metadata
    from journey.storage.db import get_engine
    reset_engine()
    metadata.create_all(get_engine())


class TestJourneyPersistenceRoundTrip:
    def setup_method(self) -> None:
        _fresh_db()

    def test_get_journey_after_create_returns_same_state(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
            destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        loaded = repo.get_journey(created.journey_id)
        assert loaded.state == created.state
        assert loaded.journey_id == created.journey_id
        assert loaded.schema_version == created.schema_version

    def test_objective_fields_survive_round_trip(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
            destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.SOFT),
            pax_count=ConstrainedField(value=2, constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        loaded = repo.get_journey(created.journey_id)
        assert loaded.objective.origin is not None
        assert loaded.objective.origin.value == "SIN"
        assert loaded.objective.origin.constraint_type == ConstraintType.HARD
        assert loaded.objective.destination is not None
        assert loaded.objective.destination.value == "NRT"
        assert loaded.objective.pax_count is not None
        assert loaded.objective.pax_count.value == 2
        assert loaded.objective.latest_arrival is None

    def test_audit_trail_survives_round_trip(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        repo.append_audit_entry(created.journey_id, "OBSERVATION", "test observation")
        loaded = repo.get_journey(created.journey_id)
        assert len(loaded.audit_entries) == 2
        assert loaded.audit_entries[0].entry_type == "DECISION"
        assert loaded.audit_entries[1].entry_type == "OBSERVATION"

    def test_state_transition_survives_engine_reset(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository
        from journey.storage.db import reset_engine, get_engine
        from journey.storage.tables import metadata

        # Use a named file-based SQLite so we can reset the engine
        db_path = "/tmp/test_journey_persistence.db"
        db_url = f"sqlite:///{db_path}"
        os.environ["JOURNEY_DB_URL"] = db_url
        reset_engine()
        metadata.create_all(get_engine())

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        state_svc.transition(created.journey_id, JourneyState.SEARCHING, "test transition")

        # Simulate process restart by resetting engine
        reset_engine(db_url)
        repo2 = JourneyRepository()
        loaded = repo2.get_journey(created.journey_id)
        assert loaded.state == JourneyState.SEARCHING
        assert len(loaded.audit_entries) == 2

        # Cleanup
        import os as _os
        try:
            _os.remove(db_path)
        except FileNotFoundError:
            pass

    def test_created_at_and_updated_at_survive_round_trip(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="KUL", constraint_type=ConstraintType.SOFT),
        )
        created = svc.create_journey(obj)
        loaded = repo.get_journey(created.journey_id)
        # Timestamps round-trip through ISO 8601 — compare to second precision
        assert loaded.created_at.replace(microsecond=0) == created.created_at.replace(microsecond=0)


class TestHeldIdentifierPersistence:
    def setup_method(self) -> None:
        _fresh_db()

    def test_held_identifier_survives_round_trip(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository
        from datetime import timedelta

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        issued = datetime.now(tz=timezone.utc)
        repo.add_held_identifier(
            journey_id=created.journey_id,
            value="PNR-ABC123",
            issued_at=issued,
            stale_after_seconds=3600,
        )
        loaded = repo.get_journey(created.journey_id)
        assert len(loaded.held_identifiers) == 1
        ident = loaded.held_identifiers[0]
        assert ident.value == "PNR-ABC123"
        assert ident.stale_after_seconds == 3600

    def test_held_identifier_stale_at_computed_correctly(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository
        from datetime import timedelta

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        )
        created = svc.create_journey(obj)
        issued = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        repo.add_held_identifier(
            journey_id=created.journey_id,
            value="SEAT-7A",
            issued_at=issued,
            stale_after_seconds=1800,
        )
        loaded = repo.get_journey(created.journey_id)
        ident = loaded.held_identifiers[0]
        expected_stale = datetime(2026, 9, 1, 12, 30, 0, tzinfo=timezone.utc)
        assert ident.stale_at.replace(tzinfo=timezone.utc) == expected_stale
