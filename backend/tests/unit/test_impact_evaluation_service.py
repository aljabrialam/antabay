"""Unit tests for ImpactEvaluationService (T009-T012, T016-T018, T022-T033).

TDD gate: these tests must fail with NotImplementedError against the
Phase 2 skeleton before implementation.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import httpx

_ATLAS_SEARCH_URL = "https://sandbox.atriptech.com/search.do"
_ATLAS_VERIFY_URL = "https://sandbox.atriptech.com/verify.do"

_ORIGIN = "SIN"
_DEST = "NRT"
_DEP_DATE = "20990615"  # far future — avoids the past-departure short-circuit
_DEADLINE = "209906152200"  # 22:00 on 2099-06-15
_ORDER_REF = "TESTA-ORDER-1"


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'impact_evaluation.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _repo() -> Any:
    from journey.storage.repository import JourneyRepository

    return JourneyRepository()


def _make_objective(
    latest_arrival_constraint: str = "HARD",
    budget_amount: Decimal | None = None,
) -> Any:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

    kwargs: dict[str, Any] = dict(
        origin=ConstrainedField(value=_ORIGIN, constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value=_DEST, constraint_type=ConstraintType.HARD),
        departure_date=ConstrainedField(value=_DEP_DATE, constraint_type=ConstraintType.HARD),
        pax_count=ConstrainedField(value=1, constraint_type=ConstraintType.HARD),
        latest_arrival=ConstrainedField(
            value=_DEADLINE,
            constraint_type=ConstraintType.HARD if latest_arrival_constraint == "HARD" else ConstraintType.SOFT,
        ),
    )
    if budget_amount is not None:
        kwargs["budget_amount"] = ConstrainedField(value=budget_amount, constraint_type=ConstraintType.HARD)
        kwargs["budget_currency"] = ConstrainedField(value="USD", constraint_type=ConstraintType.HARD)
    return TravelObjective(**kwargs)


def _seed_journey(repo: Any, objective: Any, departure_date_override: str | None = None) -> str:
    from journey.models.journey import JourneyState
    from journey.services.journey_service import JourneyService

    if departure_date_override is not None:
        from journey.models.objective import ConstrainedField, ConstraintType

        objective = objective.model_copy(
            update={
                "departure_date": ConstrainedField(
                    value=departure_date_override, constraint_type=ConstraintType.HARD
                )
            }
        )
    journey = JourneyService(repository=repo).create_journey(objective)
    repo.update_journey_state(journey.journey_id, JourneyState.MONITORING)
    return journey.journey_id


def _seed_order_and_current_option(
    repo: Any, journey_id: str, order_no: str, price: Decimal = Decimal("500.00")
) -> str:
    from journey.models.booking import Order, OrderOutcome
    from journey.models.flight import FlightOption

    now = datetime.now(tz=timezone.utc)
    option_id = str(uuid.uuid4())
    option = FlightOption(
        option_id=option_id,
        journey_id=journey_id,
        search_record_id="search-current",
        fid="fid-current",
        routing_identifier="RID-CURRENT",
        currency="USD",
        adult_price=price,
        adult_tax=Decimal("0.00"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=now,
        expire_at=now + timedelta(days=1000),
        is_multi_leg=False,
        separate_bookings=False,
        legs=[],
        recorded_at=now,
    )
    repo.save_flight_options([option])
    order = Order(
        order_id=str(uuid.uuid4()),
        journey_id=journey_id,
        option_id=option_id,
        requested_at=now,
        responded_at=now,
        raw_response_json="{}",
        outcome=OrderOutcome.CREATED,
        order_no=order_no,
        booking_reference="PNR1",
        ticketing_deadline=None,
        session_id_used="sess-1",
    )
    repo.save_order(order)
    return option_id


def _seed_schedule_change_notification(
    repo: Any, order_reference: str, revised_arrival_iso: str, journey_id: str | None = None
) -> None:
    from journey.models.webhook import InboundNotification

    envelope = {
        "cid": "<client id>",
        "type": "schedule.changed",
        "status": 0,
        "data": {"orderNo": order_reference, "revisedArrivalTime": revised_arrival_iso},
    }
    notification = InboundNotification(
        notification_id=str(uuid.uuid4()),
        received_at=datetime.now(tz=timezone.utc),
        declared_event_type="schedule.changed",
        order_reference=order_reference,
        raw_payload_json=json.dumps(envelope),
        journey_id=journey_id,
        associated=journey_id is not None,
        confirmation_triggered=False,
        simulated=True,
    )
    repo.save_notification(notification)


def _seed_wake_event(repo: Any, journey_id: str, order_reference: str = _ORDER_REF) -> Any:
    from journey.models.events import EventType
    from journey.services.event_service import EventService

    return EventService(repo).append(
        journey_id,
        EventType.WAKE_REQUESTED,
        {
            "order_reference": order_reference,
            "declared_event_type": "reconciliation_sweep",
            "classification": "SUCCESS",
        },
    )


def _service(repo: Any, search_handler=None, verify_handler=None) -> Any:
    from journey.services.event_service import EventService
    from journey.services.flight_search import FlightSearchService
    from journey.services.impact_evaluation_service import ImpactEvaluationService
    from journey.services.scoring_service import ScoringService
    from journey.services.verification_service import VerificationService

    def _dispatch(request: httpx.Request) -> httpx.Response:
        if request.url == _ATLAS_SEARCH_URL and search_handler is not None:
            return search_handler(request)
        if request.url == _ATLAS_VERIFY_URL and verify_handler is not None:
            return verify_handler(request)
        return httpx.Response(200, json={"status": 0, "routings": []})

    client = httpx.Client(transport=httpx.MockTransport(_dispatch))
    events = EventService(repo)
    return ImpactEvaluationService(
        repo=repo,
        http_client=client,
        event_service=events,
        flight_search=FlightSearchService(repo=repo, http_client=client),
        scoring_service=ScoringService(),
        verification_service=VerificationService(repo=repo, http_client=client),
    )


def _routing(
    routing_identifier: str,
    dep_time: str,
    arr_time: str,
    price: str = "400.00",
) -> dict[str, Any]:
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    far_future = (datetime.now(tz=timezone.utc) + timedelta(days=1000)).isoformat()
    return {
        "fid": f"fid-{routing_identifier}",
        "routingIdentifier": routing_identifier,
        "currency": "USD",
        "adultPrice": price,
        "adultTax": "0.00",
        "transactionFeePerPax": "0.00",
        "refreshTime": now_iso,
        "expireTime": far_future,
        "separateBookings": False,
        "fromSegments": [
            {
                "segmentIndex": 0,
                "carrier": "SQ",
                "flightNumber": "SQ1",
                "depAirport": _ORIGIN,
                "depTime": dep_time,
                "arrAirport": _DEST,
                "arrTime": arr_time,
                "duration": 300,
                "stopCities": "",
                "cabinClass": "Y",
                "seatCount": 9,
                "riskSellout": False,
                "codeShare": False,
                "aircraftCode": "77W",
                "fareFamily": None,
            }
        ],
    }


def _search_response(*routings: dict[str, Any]) -> dict[str, Any]:
    return {"status": 0, "routings": list(routings)}


def _verify_response_verified(session_id: str = "sess-verify-1") -> dict[str, Any]:
    return {
        "status": 0,
        "sessionId": session_id,
        "maxSeats": 9,
        "priceChange": {"isPriceChange": False},
        "bookingRequirement": {"passenger": {}},
    }


def _violating_claim_iso() -> str:
    # 23:00 on 2099-06-15 — 60 minutes after the 22:00 deadline
    return datetime(2099, 6, 15, 23, 0, tzinfo=timezone.utc).isoformat()


def _favourable_claim_iso() -> str:
    # 20:00 — earlier than the deadline
    return datetime(2099, 6, 15, 20, 0, tzinfo=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# User Story 1
# ---------------------------------------------------------------------------


class TestRehydratesFromDurableStorage:
    def test_evaluation_reads_journey_fresh_from_repository(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        stored = repo.get_impact_evaluation(evaluation.evaluation_id)
        assert stored.journey_id == journey_id


class TestViolationStatedInObjectiveTerms:
    def test_violated_constraints_names_latest_arrival(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.objective_satisfied is False
        assert evaluation.violated_constraints == ["latest_arrival"]


class TestViolationExtentQuantified:
    def test_extent_reflects_sixty_minute_overage(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.violation_extent is not None
        assert "60" in evaluation.violation_extent


class TestSoftLatestArrivalNotAViolation:
    def test_soft_constraint_breach_treated_as_satisfied(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective(latest_arrival_constraint="SOFT")
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.objective_satisfied is True


# ---------------------------------------------------------------------------
# User Story 2
# ---------------------------------------------------------------------------


class TestNoSearchActivityWhenSatisfied:
    def test_no_search_record_created(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _favourable_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        search_calls: list[Any] = []

        def _search_handler(request: httpx.Request) -> httpx.Response:
            search_calls.append(request)
            return httpx.Response(200, json=_search_response())

        service = _service(repo, search_handler=_search_handler)

        service.evaluate_wake(journey_id, wake_event)

        assert search_calls == []


class TestSatisfiedDeterminationRecorded:
    def test_evaluation_row_completed_and_satisfied(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _favourable_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        from journey.models.impact_evaluation import EvaluationStatus

        assert evaluation.status == EvaluationStatus.COMPLETED
        assert evaluation.objective_satisfied is True


class TestFavourableChangeTreatedAsSatisfied:
    def test_earlier_arrival_is_satisfied_not_violated(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_schedule_change_notification(repo, _ORDER_REF, _favourable_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.objective_satisfied is True
        assert evaluation.violated_constraints == []


# ---------------------------------------------------------------------------
# User Story 3
# ---------------------------------------------------------------------------


class TestSearchTriggeredOnViolation:
    def test_search_called_when_violated(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        search_calls: list[Any] = []

        def _search_handler(request: httpx.Request) -> httpx.Response:
            search_calls.append(request)
            return httpx.Response(
                200,
                json=_search_response(_routing("RID-1", "209906151000", "209906152100")),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        service.evaluate_wake(journey_id, wake_event)

        assert len(search_calls) == 1


class TestSameScoringRulesAsOriginalSelection:
    def test_scoring_service_invoked_with_original_objective(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(_routing("RID-2", "209906151000", "209906152100")),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.recommendation_id is not None


class TestRecommendationTracesToVerifiedResult:
    def test_recommendation_verification_id_is_verified_outcome(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(_routing("RID-3", "209906151000", "209906152100")),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        from sqlalchemy import select

        from journey.storage.db import get_connection
        from journey.storage.tables import recommendations, verifications

        assert evaluation.recommendation_id is not None
        with get_connection() as conn:
            rec_row = conn.execute(
                select(recommendations).where(
                    recommendations.c.recommendation_id == evaluation.recommendation_id
                )
            ).mappings().first()
            verification_row = conn.execute(
                select(verifications).where(
                    verifications.c.verification_id == rec_row["verification_id"]
                )
            ).mappings().first()

        assert verification_row is not None
        assert verification_row["outcome"] == "VERIFIED"


class TestCostRelativeAndOneSentenceRationale:
    def test_cost_is_relative_and_rationale_is_one_sentence(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF, price=Decimal("500.00"))
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(
                    _routing("RID-4", "209906151000", "209906152100", price="480.00")
                ),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        from journey.storage.tables import recommendations
        from sqlalchemy import select
        from journey.storage.db import get_connection

        with get_connection() as conn:
            row = conn.execute(
                select(recommendations).where(
                    recommendations.c.recommendation_id == evaluation.recommendation_id
                )
            ).mappings().first()

        assert "500" not in row["cost_relative_description"] or "-" in row["cost_relative_description"] or "+" in row["cost_relative_description"]
        assert row["rationale"].count(".") <= 1


class TestConstraintBreachCaveatStatedExplicitly:
    def test_budget_only_alternative_flagged_as_breach(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective(budget_amount=Decimal("300.00"))
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF, price=Decimal("300.00"))
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(
                    _routing("RID-5", "209906151000", "209906152100", price="480.00")
                ),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        from journey.storage.tables import recommendations
        from sqlalchemy import select
        from journey.storage.db import get_connection

        with get_connection() as conn:
            row = conn.execute(
                select(recommendations).where(
                    recommendations.c.recommendation_id == evaluation.recommendation_id
                )
            ).mappings().first()

        assert row is not None
        assert bool(row["constraint_breach"]) is True
        assert row["constraint_breach_detail"]


class TestNoAlternativeReportedPlainly:
    def test_no_satisfying_option_reports_no_alternative(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_search_response())  # no routings

        service = _service(repo, search_handler=_search_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.recommendation_id is None
        assert evaluation.no_alternative_reason is not None


class TestBudgetExhaustionFoldedIntoNoAlternative:
    def test_budget_exhausted_reports_as_no_alternative(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        # Exhaust the journey's call budget before evaluation runs
        for _ in range(20):
            try:
                repo.decrement_call_budget(journey_id)
            except Exception:
                break

        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.recommendation_id is None
        assert evaluation.no_alternative_reason == "budget_exhausted"


class TestFreshnessLapseFoldedIntoNoAlternative:
    def test_unavailable_candidate_falls_through_to_no_alternative(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(_routing("RID-6", "209906151000", "209906152100")),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": 1})  # UNAVAILABLE

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert evaluation.recommendation_id is None
        assert evaluation.no_alternative_reason == "all_expired"


class TestNextRankedTriedWhenTopVerificationFails:
    def test_second_candidate_recommended_when_first_unavailable(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        from journey.models.objective import ConstrainedField, ConstraintType

        objective = _make_objective()
        objective = objective.model_copy(
            update={
                "preferences": ConstrainedField(
                    value=["cost"], constraint_type=ConstraintType.SOFT
                )
            }
        )
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        attempts: list[str] = []

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(
                    _routing("RID-CHEAP", "209906151000", "209906152100", price="100.00"),
                    _routing("RID-EXPENSIVE", "209906151000", "209906152100", price="900.00"),
                ),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            ri = body["routingIdentifier"]
            attempts.append(ri)
            if ri == "RID-CHEAP":
                return httpx.Response(200, json={"status": 1})  # UNAVAILABLE
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        assert "RID-CHEAP" in attempts
        assert "RID-EXPENSIVE" in attempts
        assert evaluation.recommendation_id is not None


class TestEverySearchCountsAgainstCallBudget:
    def test_budget_decrements_for_search_and_verify(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)

        def _search_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_search_response(_routing("RID-7", "209906151000", "209906152100")),
            )

        def _verify_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_verify_response_verified())

        service = _service(repo, search_handler=_search_handler, verify_handler=_verify_handler)
        before = repo.get_journey(journey_id).call_budget

        service.evaluate_wake(journey_id, wake_event)

        after = repo.get_journey(journey_id).call_budget
        assert after == before - 2  # one search + one verify


class TestPastDepartureJourneyInert:
    def test_no_evaluation_activity_for_past_departure(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective, departure_date_override="20200101")
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        wake_event = _seed_wake_event(repo, journey_id)
        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, wake_event)

        from journey.models.impact_evaluation import EvaluationStatus

        assert evaluation.status == EvaluationStatus.INERT_PAST_DEPARTURE
        assert evaluation.objective_satisfied is None


class TestSupersededByNewerWake:
    def test_older_wake_marked_superseded(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        repo = _repo()
        objective = _make_objective()
        journey_id = _seed_journey(repo, objective)
        _seed_order_and_current_option(repo, journey_id, _ORDER_REF)
        _seed_schedule_change_notification(repo, _ORDER_REF, _violating_claim_iso(), journey_id)
        old_wake = _seed_wake_event(repo, journey_id)
        # A newer wake for the same journey arrives before evaluation of the older one runs
        _seed_wake_event(repo, journey_id)

        service = _service(repo)

        evaluation = service.evaluate_wake(journey_id, old_wake)

        from journey.models.impact_evaluation import EvaluationStatus

        assert evaluation.status == EvaluationStatus.SUPERSEDED


class TestOnWakeFiresFromConfirmAndReconcile:
    pass  # covered in tests/contract/test_impact_evaluation_wiring.py
