"""Failing unit tests for HeldIdentifier staleness (T046)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from journey.models.journey import HeldIdentifier


def _make_identifier(stale_after_seconds: int = 3600) -> HeldIdentifier:
    issued = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    stale_at = datetime.fromtimestamp(
        issued.timestamp() + stale_after_seconds, tz=timezone.utc
    )
    return HeldIdentifier(
        identifier_id="test-id",
        journey_id="journey-1",
        value="PNR-XYZ",
        issued_at=issued,
        stale_after_seconds=stale_after_seconds,
        stale_at=stale_at,
    )


class TestHeldIdentifierStaleness:
    def test_not_stale_before_threshold(self) -> None:
        ident = _make_identifier(stale_after_seconds=3600)
        before = datetime(2026, 9, 1, 12, 30, 0, tzinfo=timezone.utc)
        assert ident.is_stale(before) is False

    def test_stale_after_threshold(self) -> None:
        ident = _make_identifier(stale_after_seconds=3600)
        after = datetime(2026, 9, 1, 13, 30, 0, tzinfo=timezone.utc)
        assert ident.is_stale(after) is True

    def test_stale_at_boundary(self) -> None:
        ident = _make_identifier(stale_after_seconds=3600)
        # Exactly at stale_at → stale
        at_boundary = datetime(2026, 9, 1, 13, 0, 0, tzinfo=timezone.utc)
        assert ident.is_stale(at_boundary) is True

    def test_is_stale_takes_now_as_parameter(self) -> None:
        ident = _make_identifier()
        # Method signature must accept a datetime argument — no internal clock access
        import inspect
        sig = inspect.signature(ident.is_stale)
        assert "now" in sig.parameters

    def test_stale_at_equals_issued_plus_stale_after(self) -> None:
        issued = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
        ident = HeldIdentifier(
            identifier_id="x",
            journey_id="j",
            value="ABC",
            issued_at=issued,
            stale_after_seconds=1800,
            stale_at=datetime(2026, 9, 1, 10, 30, 0, tzinfo=timezone.utc),
        )
        expected = issued + timedelta(seconds=1800)
        assert ident.stale_at.replace(tzinfo=timezone.utc) == expected


class TestJourneyStateServiceIdentifiers:
    def setup_method(self) -> None:
        import os
        os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
        from journey.storage.db import reset_engine
        from journey.storage.tables import metadata
        from journey.storage.db import get_engine
        reset_engine()
        metadata.create_all(get_engine())

    def test_add_held_identifier_via_state_service(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        issued = datetime.now(tz=timezone.utc)
        state_svc.add_held_identifier(
            journey_id=record.journey_id,
            value="PNR-123",
            issued_at=issued,
            stale_after_seconds=3600,
        )
        loaded = repo.get_journey(record.journey_id)
        assert len(loaded.held_identifiers) == 1
        assert loaded.held_identifiers[0].value == "PNR-123"

    def test_check_identifier_freshness_returns_fresh(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        issued = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        ident = repo.add_held_identifier(
            journey_id=record.journey_id,
            value="SEAT-3A",
            issued_at=issued,
            stale_after_seconds=3600,
        )
        before = datetime(2026, 9, 1, 12, 30, 0, tzinfo=timezone.utc)
        freshness = state_svc.check_identifier_freshness(
            journey_id=record.journey_id,
            identifier_id=ident.identifier_id,
            now=before,
        )
        assert freshness.value == "FRESH"

    def test_check_identifier_freshness_returns_stale(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService
        from journey.storage.repository import JourneyRepository
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            origin=ConstrainedField(value="KUL", constraint_type=ConstraintType.SOFT),
        )
        record = svc.create_journey(obj)
        issued = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        ident = repo.add_held_identifier(
            journey_id=record.journey_id,
            value="SEAT-7B",
            issued_at=issued,
            stale_after_seconds=3600,
        )
        after = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
        freshness = state_svc.check_identifier_freshness(
            journey_id=record.journey_id,
            identifier_id=ident.identifier_id,
            now=after,
        )
        assert freshness.value == "STALE"

    def test_check_freshness_raises_for_unknown_identifier(self) -> None:
        from journey.services.journey_service import JourneyService
        from journey.services.state_service import JourneyStateService, IdentifierNotFoundError
        from journey.storage.repository import JourneyRepository
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        repo = JourneyRepository()
        svc = JourneyService(repository=repo)
        state_svc = JourneyStateService(repository=repo)
        obj = TravelObjective(
            destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        )
        record = svc.create_journey(obj)
        with pytest.raises(IdentifierNotFoundError):
            state_svc.check_identifier_freshness(
                journey_id=record.journey_id,
                identifier_id="does-not-exist",
                now=datetime.now(tz=timezone.utc),
            )
