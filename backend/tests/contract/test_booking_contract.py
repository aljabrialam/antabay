"""VCR contract tests for BookingService against Atlas order.do/pay.do/
queryOrderDetails.do (T010, T022, T032, T045).

Cassettes (backend/fixtures/atlas/cassettes/booking/ — matching the
project convention set by 002/004, not backend/tests/fixtures/):
- order_pay_query_jkt_sub.yaml
  (verified JKT->SUB capture, .antabay/atlas-capability-map.md section 7b)
- order_duplicate_318.yaml
  (verified 318 duplicate capture, section 9)

TDD gate (T015, T026, T037, T048): must fail with NotImplementedError
against the Phase 2 skeleton before implementation.
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


def _seed_verified_journey(repo: Any) -> tuple[str, str]:
    from journey.models.flight import FlightOption
    from journey.models.journey import JourneyState
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.models.verification import (
        PassengerRequirementField,
        VerificationOutcome,
        VerificationResult,
    )
    from journey.services.journey_service import JourneyService
    from journey.services.state_service import JourneyStateService

    objective = TravelObjective(
        origin=ConstrainedField(value="JKT", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="SUB", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService(repository=repo).create_journey(objective)
    # Relative to real "now" (not the historical capture date) since the
    # session-freshness precondition (FR-014) compares against wall-clock
    # time when create_order() is called later in each test.
    now = datetime.now(tz=timezone.utc)

    option = FlightOption(
        option_id="opt-jkt-sub",
        journey_id=journey.journey_id,
        search_record_id="search-jkt-sub",
        fid="fid-jkt-sub",
        routing_identifier="RID-JKT-SUB-CONTRACT-TEST",
        currency="USD",
        adult_price=Decimal("66.43"),
        adult_tax=Decimal("23.96"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now + timedelta(minutes=31),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )
    repo.save_flight_options([option])

    state_svc = JourneyStateService(repository=repo)
    state_svc.transition(journey.journey_id, JourneyState.SEARCHING, reason="options held", now=now)
    state_svc.transition(journey.journey_id, JourneyState.VERIFIED, reason="verified", now=now)

    result = VerificationResult(
        verification_id="verif-jkt-sub",
        journey_id=journey.journey_id,
        option_id=option.option_id,
        requested_at=now,
        responded_at=now,
        raw_response_json="{}",
        status_code=200,
        atlas_status=0,
        outcome=VerificationOutcome.VERIFIED,
        budget_before=20,
        budget_after=19,
        session_id="sess-jkt-sub",
        max_seats=7,
        passenger_requirements=[
            PassengerRequirementField(
                field_name="name", type="string", required=True, description="Full name", max_length=100
            ),
            PassengerRequirementField(
                field_name="passengerType", type="int", required=True, description="0=adult", max_length=None
            ),
            PassengerRequirementField(
                field_name="birthday", type="string", required=True, description="DOB", max_length=10
            ),
            PassengerRequirementField(
                field_name="gender", type="string", required=True, description="Gender", max_length=1
            ),
            PassengerRequirementField(
                field_name="nationality", type="string", required=True, description="Nationality", max_length=2
            ),
            PassengerRequirementField(
                field_name="cardNum", type="string", required=False, description="Passport", max_length=30
            ),
            PassengerRequirementField(
                field_name="cardType", type="string", required=False, description="Card type", max_length=10
            ),
            PassengerRequirementField(
                field_name="cardExpired", type="string", required=False, description="Expiry", max_length=10
            ),
        ],
    )
    repo.save_verification(result)

    repo.add_held_identifier(
        journey_id=journey.journey_id, value="sess-jkt-sub", issued_at=now, stale_after_seconds=7200
    )

    return journey.journey_id, option.option_id


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    """Override base VCR dir to use the booking cassette subdirectory."""
    return "fixtures/atlas/cassettes/booking"


@pytest.mark.vcr("order_pay_query_jkt_sub.yaml")
class TestCreateOrderContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_create_order_returns_created_outcome_from_cassette(self) -> None:
        from journey.services.booking_service import BookingService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_verified_journey(repo)

        svc = BookingService(repo=repo, http_client=httpx.Client())
        order = svc.create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        assert order.outcome.value == "CREATED"
        assert order.order_no == "TESTA20260815172246746"
        assert order.booking_reference == "TZKZYA"
        assert order.ticketing_deadline is not None

        # FR-005: a held_identifiers row bounds the ticketing deadline.
        journey = repo.get_journey(journey_id)
        assert any(h.value == order.order_no for h in journey.held_identifiers)

        # NFR-002: full response persisted.
        raw = json.loads(order.raw_response_json)
        assert raw["status"] == 0


@pytest.mark.vcr("order_pay_query_jkt_sub.yaml")
class TestSubmitPaymentContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_payment_success_recorded_from_cassette(self) -> None:
        from journey.services.booking_service import BookingService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_verified_journey(repo)

        svc = BookingService(repo=repo, http_client=httpx.Client())
        order = svc.create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )
        payment = svc.submit_payment(
            journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc)
        )

        assert payment.outcome.value == "SUCCESS"
        assert payment.raw_response_json


@pytest.mark.vcr("order_pay_query_jkt_sub.yaml")
class TestConfirmTicketingContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_paid_but_not_ticketed_is_not_confirmed(self) -> None:
        from journey.models.journey import JourneyState
        from journey.services.booking_service import BookingService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_verified_journey(repo)

        svc = BookingService(repo=repo, http_client=httpx.Client())
        order = svc.create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )
        svc.submit_payment(journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc))
        query = svc.confirm_ticketing(
            journey_id=journey_id, order_no=order.order_no, now=datetime.now(tz=timezone.utc)
        )

        assert query.confirmed is False
        assert repo.get_journey(journey_id).state is JourneyState.VERIFIED


@pytest.mark.vcr("order_duplicate_318.yaml")
class TestDuplicateOrderContract:
    def setup_method(self) -> None:
        _fresh_db()

    def test_duplicate_rejection_resolves_via_referenced_order(self) -> None:
        from journey.services.booking_service import BookingService
        from journey.storage.repository import JourneyRepository

        repo = JourneyRepository()
        journey_id, option_id = _seed_verified_journey(repo)

        svc = BookingService(repo=repo, http_client=httpx.Client())
        order = svc.create_order(
            journey_id=journey_id, option_id=option_id, now=datetime.now(tz=timezone.utc)
        )

        assert order.outcome.value == "DUPLICATE_REJECTED"
        assert order.order_no == "TESTA20260815172246746"
        # The cassette's second interaction (queryOrderDetails.do) must have
        # been consumed to resolve this — confirmed by it having been played
        # (pytest-recording fails the run if a cassette interaction goes
        # unused only when record_mode requires it; here we instead assert
        # the observable result of that query having happened).
        queries = repo.get_ticketing_queries(order.order_no)
        assert len(queries) == 1
        assert queries[0].confirmed is True
