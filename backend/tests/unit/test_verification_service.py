"""Unit tests for VerificationService (T010-T012, T021, T026-T028).

TDD gate (T013): these tests must fail with NotImplementedError or
AttributeError against the Phase 2 skeleton before implementation begins.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx
import pytest


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'verification_service.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_option(repo: Any, routing_identifier: str = "RID-ZE605-ABC123") -> tuple[str, str]:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.models.flight import FlightOption
    from journey.services.journey_service import JourneyService

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
        routing_identifier=routing_identifier,
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


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _service(repo: Any) -> Any:
    from journey.services.verification_service import VerificationService

    return VerificationService(repo=repo, http_client=httpx.Client())


def _price_changed_response() -> dict[str, Any]:
    return {
        "sessionId": "sess-price-changed-1",
        "maxSeats": 7,
        "routing": {"expireTime": None, "refreshTime": None},
        "bookingRequirement": {
            "passenger": {
                "name": {"type": "string", "required": True, "description": "Full name", "maxLength": 100},
            }
        },
        "priceChange": {
            "isPriceChange": True,
            "originalAdultPrice": 66.43,
            "newAdultPrice": 72.10,
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


class TestVerifyPriceChanged:
    def test_price_change_outcome_and_invalidation_signal(self, tmp_path: Any) -> None:
        from journey.models.verification import VerificationOutcome

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        svc = _service(repo)

        result = svc._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=_price_changed_response(),
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            status_code=200,
            budget_before=20,
            budget_after=19,
        )

        assert result.outcome is VerificationOutcome.PRICE_CHANGED
        assert result.invalidates_authorisation is True
        assert result.price_change is not None
        assert result.price_change.is_price_change is True
        assert result.price_change.new_adult_price == Decimal("72.10")


class TestVerifyIdentifierIntegrity:
    def test_verify_sends_stored_routing_identifier_unmodified(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo, routing_identifier="RID-EXACT-VALUE")

        sent_bodies: list[dict[str, Any]] = []

        def _handler(request: httpx.Request) -> httpx.Response:
            import json as _json

            sent_bodies.append(_json.loads(request.content))
            return httpx.Response(200, json=_price_changed_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from journey.services.verification_service import VerificationService

        svc = VerificationService(repo=repo, http_client=client)
        svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert sent_bodies[0]["routingIdentifier"] == "RID-EXACT-VALUE"


class TestVerifyCallBudget:
    def test_budget_decremented_by_one_and_recorded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_price_changed_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from journey.services.verification_service import VerificationService

        svc = VerificationService(repo=repo, http_client=client)
        result = svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        assert result.budget_before == 20
        assert result.budget_after == 19

    def test_raises_budget_exhausted_without_http_call_when_zero(self, tmp_path: Any) -> None:
        from journey.errors import BudgetExhaustedError
        from journey.storage.db import get_connection
        from journey.storage.tables import journeys
        from sqlalchemy import update

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        with get_connection() as conn:
            conn.execute(update(journeys).where(journeys.c.journey_id == journey_id).values(call_budget=0))
            conn.commit()

        called = {"count": 0}

        def _handler(request: httpx.Request) -> httpx.Response:
            called["count"] += 1
            return httpx.Response(200, json=_price_changed_response())

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from journey.services.verification_service import VerificationService

        svc = VerificationService(repo=repo, http_client=client)
        with pytest.raises(BudgetExhaustedError):
            svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))
        assert called["count"] == 0


class TestNeedsReverification:
    def test_true_inside_margin_false_outside(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        issued_at = datetime.now(tz=timezone.utc)
        repo.add_held_identifier(
            journey_id=journey_id, value="sess-1", issued_at=issued_at, stale_after_seconds=3600
        )

        svc = _service(repo)
        far_from_expiry = issued_at + timedelta(minutes=1)
        near_expiry = issued_at + timedelta(minutes=59, seconds=1)

        assert svc.needs_reverification(journey_id, far_from_expiry, safety_margin_seconds=300) is False
        assert svc.needs_reverification(journey_id, near_expiry, safety_margin_seconds=300) is True

    def test_raises_identifier_not_found_before_any_verification(self, tmp_path: Any) -> None:
        from journey.services.state_service import IdentifierNotFoundError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, _ = _seed_journey_with_option(repo)
        svc = _service(repo)

        with pytest.raises(IdentifierNotFoundError):
            svc.needs_reverification(journey_id, datetime.now(tz=timezone.utc), safety_margin_seconds=300)


class TestPassengerRequirementsCapture:
    def test_matches_response_exactly(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        svc = _service(repo)

        response = _price_changed_response()
        response["bookingRequirement"] = {
            "passenger": {
                "name": {"type": "string", "required": True, "description": "Full name", "maxLength": 100},
                "birthday": {"type": "string", "required": True, "description": "DOB", "maxLength": 10},
            }
        }
        result = svc._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=response,
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            status_code=200,
            budget_before=20,
            budget_after=19,
        )

        field_names = {f.field_name for f in result.passenger_requirements}
        assert field_names == {"name", "birthday"}


class TestPassengerRequirementsEmptySet:
    def test_empty_object_yields_empty_list_not_a_default(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        svc = _service(repo)

        response = _price_changed_response()
        response["bookingRequirement"] = {"passenger": {}}
        result = svc._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=response,
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            status_code=200,
            budget_before=20,
            budget_after=19,
        )

        assert result.passenger_requirements == []


class TestVerifyRateLimited:
    def test_rate_limited_persists_raw_response_and_raises(self, tmp_path: Any) -> None:
        """NFR-002: raw_response_json must be persisted even on a 429 (T039)."""
        from journey.errors import RateLimitError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"status": 429, "retryAfter": 5, "msg": "rate limited"})

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from journey.services.verification_service import VerificationService

        svc = VerificationService(repo=repo, http_client=client)
        with pytest.raises(RateLimitError):
            svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        persisted = repo.get_latest_verification(journey_id, option_id)
        assert persisted is not None
        assert persisted.outcome.value == "RATE_LIMITED"
        assert persisted.raw_response_json
        assert '"retryAfter": 5' in persisted.raw_response_json or "retryAfter" in persisted.raw_response_json


class TestVerifyError:
    def test_unparseable_body_persists_raw_bytes_and_raises(self, tmp_path: Any) -> None:
        """NFR-002: raw response must be persisted even when unparseable (T039)."""
        from journey.errors import AtlasVerifyError

        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)

        def _handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all")

        client = httpx.Client(transport=httpx.MockTransport(_handler))
        from journey.services.verification_service import VerificationService

        svc = VerificationService(repo=repo, http_client=client)
        with pytest.raises(AtlasVerifyError):
            svc.verify(journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc))

        persisted = repo.get_latest_verification(journey_id, option_id)
        assert persisted is not None
        assert persisted.outcome.value == "ERROR"
        assert persisted.raw_response_json == "not json at all"


class TestMaxSeatsCapture:
    def test_max_seats_matches_response_no_cross_option_leakage(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        journey_id, option_id = _seed_journey_with_option(repo)
        svc = _service(repo)

        response_a = _price_changed_response()
        response_a["maxSeats"] = 7
        result_a = svc._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=response_a,
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            status_code=200,
            budget_before=20,
            budget_after=19,
        )

        response_b = _price_changed_response()
        response_b["maxSeats"] = 2
        result_b = svc._parse_response(
            journey_id=journey_id,
            option_id=option_id,
            response_json=response_b,
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            status_code=200,
            budget_before=19,
            budget_after=18,
        )

        assert result_a.max_seats == 7
        assert result_b.max_seats == 2
