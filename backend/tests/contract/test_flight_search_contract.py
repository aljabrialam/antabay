"""VCR contract tests for FlightSearchService against Atlas search.do (T015).

Tests MUST fail before production code is written (TDD gate T016).
Cassette: fixtures/atlas/cassettes/flight_search/search_sel_tyo.yaml
Created from: fixtures/atlas/sel_tyo_search.json (T002)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal

import pytest


def _fresh_db() -> None:
    os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
    from journey.storage.db import reset_engine
    from journey.storage.tables import metadata
    from journey.storage.db import get_engine

    reset_engine()
    metadata.create_all(get_engine())


def _make_journey(repo):
    from journey.services.journey_service import JourneyService
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

    svc = JourneyService(repository=repo)
    obj = TravelObjective(
        origin=ConstrainedField(value="ICN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        pax_count=ConstrainedField(value=1, constraint_type=ConstraintType.HARD),
        budget_currency=ConstrainedField(value="USD", constraint_type=ConstraintType.SOFT),
        budget_amount=ConstrainedField(value=Decimal("500"), constraint_type=ConstraintType.SOFT),
    )
    obj.departure_date = ConstrainedField(value="20260905", constraint_type=ConstraintType.HARD)
    return svc.create_journey(obj)


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    """Override base VCR dir to use flight_search cassette subdirectory."""
    return "fixtures/atlas/cassettes/flight_search"


@pytest.mark.vcr("search_sel_tyo.yaml")
class TestFlightSearchContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_search_returns_options_from_cassette(self) -> None:
        """Cassette playback returns option_count >= 1, at least one fid, non-empty carriers."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService
        import httpx

        repo = JourneyRepository()
        record = _make_journey(repo)
        now = datetime(2026, 8, 15, 9, 21, 3, tzinfo=timezone.utc)

        svc = FlightSearchService(repo=repo, http_client=httpx.Client())
        result = svc.search(journey_id=record.journey_id, now=now)

        assert result.option_count >= 1, "Expected at least one option from cassette"
        assert len(result.options) >= 1
        assert result.options[0].fid, "fid must be non-empty"
        assert len(result.carriers) > 0, "carriers must be non-empty"

    def test_cassette_options_have_legs(self) -> None:
        """All options from cassette have at least one Leg with seat_count and risk_sellout."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService
        import httpx

        repo = JourneyRepository()
        record = _make_journey(repo)
        now = datetime(2026, 8, 15, 9, 21, 3, tzinfo=timezone.utc)

        svc = FlightSearchService(repo=repo, http_client=httpx.Client())
        result = svc.search(journey_id=record.journey_id, now=now)

        for opt in result.options:
            assert len(opt.legs) >= 1, f"Option {opt.fid} must have at least one leg"
            for leg in opt.legs:
                assert isinstance(leg.seat_count, int), "seat_count must be int"
                assert isinstance(leg.risk_sellout, bool), "risk_sellout must be bool"
