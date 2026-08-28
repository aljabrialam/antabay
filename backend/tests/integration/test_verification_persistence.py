"""Integration tests for verification persistence and journey-state effects
(T020, T033).

TDD gate (T022, T034): must fail against the Phase 2 skeleton before
implementation.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'verification_persistence.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_option(repo: Any) -> tuple[str, str]:
    from journey.models.flight import FlightOption
    from journey.models.journey import JourneyState
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService
    from journey.services.state_service import JourneyStateService

    objective = TravelObjective(
        origin=ConstrainedField(value="ICN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)

    now = datetime.now(tz=timezone.utc)
    option = FlightOption(
        option_id="opt-1",
        journey_id=journey.journey_id,
        search_record_id="search-1",
        fid="fid-1",
        routing_identifier="RID-INTEGRATION-TEST",
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

    # Mirror what 002-flight-search already does in the real flow: an
    # offer-window held_identifier row exists before verification runs,
    # and the journey has already moved into SEARCHING.
    repo.add_held_identifier(
        journey_id=journey.journey_id,
        value=option.routing_identifier,
        issued_at=now,
        stale_after_seconds=463,
    )
    JourneyStateService(repository=repo).transition(
        journey.journey_id, JourneyState.SEARCHING, reason="options held", now=now
    )
    return journey.journey_id, option.option_id


def _verified_response() -> dict[str, Any]:
    return {
        "sessionId": "sess-integration-1",
        "maxSeats": 7,
        "routing": {"expireTime": None, "refreshTime": None},
        "bookingRequirement": {
            "passenger": {
                "name": {"type": "string", "required": True, "description": "Full name", "maxLength": 100},
            }
        },
        "priceChange": {
            "isPriceChange": False,
            "originalAdultPrice": 66.43,
            "newAdultPrice": 66.43,
            "originalAdultTax": 23.96,
            "newAdultTax": 23.96,
            "originalChildPrice": None,
            "newChildPrice": None,
            "originalInfantPrice": None,
            "newInfantPrice": None,
        },
        "status": 0,
        "msg": "success",
    }


def _unavailable_response() -> dict[str, Any]:
    return {
        "sessionId": None,
        "maxSeats": None,
        "routing": None,
        "bookingRequirement": None,
        "priceChange": None,
        "status": 404,
        "msg": "option not available",
    }


def _client_returning(response_json: dict[str, Any]) -> httpx.Client:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    return httpx.Client(transport=httpx.MockTransport(_handler))


class TestSessionFreshnessWindow:
    def test_two_held_identifier_rows_after_successful_verify(self, tmp_path: Any) -> None:
        from journey.services.verification_service import (
            SESSION_WINDOW_SECONDS,
            VerificationService,
        )
        from journey.storage.repository import JourneyRepository

        _file_db(tmp_path)
        repo = JourneyRepository()
        journey_id, option_id = _seed_journey_with_option(repo)

        svc = VerificationService(repo=repo, http_client=_client_returning(_verified_response()))
        svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        journey = repo.get_journey(journey_id)
        values = {h.value: h for h in journey.held_identifiers}
        assert "RID-INTEGRATION-TEST" in values, "offer-window row must remain untouched"
        assert "sess-integration-1" in values, "session-window row must be created"
        session_row = values["sess-integration-1"]
        assert session_row.stale_after_seconds == SESSION_WINDOW_SECONDS


class TestUnavailableRecovery:
    def test_unavailable_outcome_returns_journey_to_searching(self, tmp_path: Any) -> None:
        from journey.models.journey import JourneyState
        from journey.models.verification import VerificationOutcome
        from journey.services.state_service import JourneyStateService
        from journey.services.verification_service import VerificationService
        from journey.storage.repository import JourneyRepository

        _file_db(tmp_path)
        repo = JourneyRepository()
        journey_id, option_id = _seed_journey_with_option(repo)

        # Reach VERIFIED first (a prior successful verify).
        svc = VerificationService(repo=repo, http_client=_client_returning(_verified_response()))
        svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))
        assert repo.get_journey(journey_id).state is JourneyState.VERIFIED

        # Re-verify against a response reporting the option is unavailable.
        svc_unavailable = VerificationService(
            repo=repo, http_client=_client_returning(_unavailable_response())
        )
        result = svc_unavailable.verify(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        assert result.outcome is VerificationOutcome.UNAVAILABLE
        assert repo.get_journey(journey_id).state is JourneyState.SEARCHING
