"""Failing unit tests for authorisation outcome recording (T033)."""
from __future__ import annotations

import os

import pytest

from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective


def _setup_db() -> None:
    os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
    from journey.storage.db import reset_engine
    from journey.storage.tables import metadata
    from journey.storage.db import get_engine
    reset_engine()
    metadata.create_all(get_engine())


class TestAuthorisationRecording:
    def setup_method(self) -> None:
        _setup_db()

    def test_record_approval_appends_authorisation_audit_entry(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        state_svc.record_authorisation_outcome(
            journey_id=record.journey_id,
            request_desc="Book SIN-LHR flight £1200",
            outcome="APPROVED",
            recorded_by="policy-engine",
        )
        trail = repo.get_audit_trail(record.journey_id)
        auth_entries = [e for e in trail if e.entry_type == "AUTHORISATION"]
        assert len(auth_entries) == 1

    def test_record_refusal_is_stored(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        state_svc.record_authorisation_outcome(
            journey_id=record.journey_id,
            request_desc="Book expensive flight",
            outcome="REFUSED",
            recorded_by="policy-engine",
        )
        trail = repo.get_audit_trail(record.journey_id)
        auth_entries = [e for e in trail if e.entry_type == "AUTHORISATION"]
        assert len(auth_entries) == 1
        assert "REFUSED" in auth_entries[0].content

    def test_authorisation_does_not_change_journey_state(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository
        from journey.models.journey import JourneyState

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        state_svc.record_authorisation_outcome(
            journey_id=record.journey_id,
            request_desc="Some request",
            outcome="APPROVED",
            recorded_by="policy-engine",
        )
        reloaded = repo.get_journey(record.journey_id)
        assert reloaded.state == JourneyState.OBJECTIVE_CONFIRMED

    def test_authorisation_entry_content_includes_outcome_and_request(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        state_svc.record_authorisation_outcome(
            journey_id=record.journey_id,
            request_desc="Book hotel SGD 400",
            outcome="REFUSED",
            recorded_by="policy-engine",
        )
        trail = repo.get_audit_trail(record.journey_id)
        auth_entry = next(e for e in trail if e.entry_type == "AUTHORISATION")
        assert "Book hotel SGD 400" in auth_entry.content
        assert "REFUSED" in auth_entry.content
