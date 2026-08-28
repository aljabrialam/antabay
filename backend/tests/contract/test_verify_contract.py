"""VCR contract test for VerificationService against Atlas verify.do (T009).

Cassette: fixtures/atlas/cassettes/verification/verify_ze605.yaml
Transcribed from the verified ZE605 capture in
.antabay/atlas-capability-map.md section 7a (2026-08-15).

TDD gate (T013): must fail with NotImplementedError against the Phase 2
skeleton before implementation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest


def _fresh_db() -> None:
    os.environ["JOURNEY_DB_URL"] = "sqlite:///:memory:"
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_option(repo: Any) -> tuple[str, str]:
    from journey.models.flight import FlightOption
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="ICN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)

    now = datetime(2026, 8, 15, 9, 21, 3, tzinfo=timezone.utc)
    option = FlightOption(
        option_id="opt-ze605",
        journey_id=journey.journey_id,
        search_record_id="search-ze605",
        fid="fid-ze605",
        routing_identifier="RID-ZE605-CONTRACT-TEST",
        currency="USD",
        adult_price=Decimal("66.43"),
        adult_tax=Decimal("23.96"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now + timedelta(minutes=7, seconds=43),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )
    repo.save_flight_options([option])
    return journey.journey_id, option.option_id


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    """Override base VCR dir to use the verification cassette subdirectory."""
    return "fixtures/atlas/cassettes/verification"


@pytest.mark.vcr("verify_ze605.yaml")
class TestVerifyContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_verify_returns_verified_outcome_from_cassette(self) -> None:
        from journey.models.verification import VerificationOutcome
        from journey.services.verification_service import VerificationService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_journey_with_option(repo)

        svc = VerificationService(repo=repo, http_client=httpx.Client())
        result = svc.verify(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        assert result.outcome is VerificationOutcome.VERIFIED
        assert result.session_id == "<REDACTED>"
        assert result.max_seats == 7
        assert result.price_change is not None
        assert result.price_change.is_price_change is False

        # Identifier integrity (FR-002) is covered by
        # TestVerifyIdentifierIntegrity in tests/unit/test_verification_service.py
        # via an httpx.MockTransport that observes the real outgoing request.
        # vcrpy's `vcr.requests` exposes the cassette's *stored* request
        # object (cassette.py: "Use stored ... request, not the raw incoming
        # request"), not what this test run actually sent, so it can't be
        # used for that assertion here.

    def test_raw_response_persisted_in_full(self, vcr) -> None:
        from journey.services.verification_service import VerificationService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_journey_with_option(repo)

        svc = VerificationService(repo=repo, http_client=httpx.Client())
        result = svc.verify(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        persisted = repo.get_latest_verification(journey_id, option_id)
        assert persisted is not None
        raw = json.loads(persisted.raw_response_json)
        assert raw["status"] == 0
        assert raw["bookingRequirement"]["passenger"]["name"]["required"] is True
