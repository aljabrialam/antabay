"""Unit tests for FlightSearchService — T013 (TDD: must FAIL before flight_search.py exists)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import httpx
import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

BASE_NOW = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)

ATLAS_SUCCESS_RESPONSE = {
    "status": 0,
    "msg": "success",
    "routings": [
        {
            "fid": "fid-001",
            "routingIdentifier": "ri-001",
            "currency": "USD",
            "adultPrice": 450.00,
            "adultTax": 85.50,
            "transactionFeePerPax": 0.00,
            "refreshTime": "2026-09-05T10:45:00Z",
            "expireTime": "2026-09-05T11:00:00Z",
            "separateBookings": False,
            "fromSegments": [
                {
                    "segmentIndex": 0,
                    "carrier": "SQ",
                    "flightNumber": "SQ321",
                    "depAirport": "SIN",
                    "depTime": "202609051000",
                    "arrAirport": "LHR",
                    "arrTime": "202609051600",
                    "duration": 740,
                    "stopCities": "",
                    "cabinClass": "Y",
                    "seatCount": 9,
                    "riskSellout": False,
                    "codeShare": False,
                    "aircraftCode": "773",
                    "fareFamily": None,
                }
            ],
        },
        {
            "fid": "fid-002",
            "routingIdentifier": "ri-002",
            "currency": "USD",
            "adultPrice": 520.00,
            "adultTax": 90.00,
            "transactionFeePerPax": 0.00,
            "refreshTime": "2026-09-05T10:45:00Z",
            "expireTime": "2026-09-05T11:00:00Z",
            "separateBookings": False,
            "fromSegments": [
                {
                    "segmentIndex": 0,
                    "carrier": "EK",
                    "flightNumber": "EK432",
                    "depAirport": "SIN",
                    "depTime": "202609050800",
                    "arrAirport": "DXB",
                    "arrTime": "202609051100",
                    "duration": 420,
                    "stopCities": "DXB",
                    "cabinClass": "Y",
                    "seatCount": 4,
                    "riskSellout": True,
                    "codeShare": False,
                    "aircraftCode": "77W",
                    "fareFamily": None,
                },
                {
                    "segmentIndex": 1,
                    "carrier": "EK",
                    "flightNumber": "EK001",
                    "depAirport": "DXB",
                    "depTime": "202609051400",
                    "arrAirport": "LHR",
                    "arrTime": "202609051800",
                    "duration": 420,
                    "stopCities": "",
                    "cabinClass": "Y",
                    "seatCount": 4,
                    "riskSellout": True,
                    "codeShare": False,
                    "aircraftCode": "77W",
                    "fareFamily": None,
                },
            ],
        },
    ],
}

ATLAS_EMPTY_RESPONSE = {
    "status": 0,
    "msg": "success",
    "routings": [],
}

ATLAS_NONZERO_STATUS_RESPONSE = {
    "status": 1,
    "msg": "Invalid request parameters",
    "data": {},
}

ATLAS_RATE_LIMIT_RESPONSE = {
    "status": 2,
    "msg": "Rate limit exceeded",
    "retryAfter": 5,
}


def _make_journey(call_budget: int = 10):
    """Build a minimal JourneyRecord-like mock with a confirmed objective."""
    from journey.models.objective import (
        ConstrainedField,
        ConstraintType,
        TravelObjective,
    )

    objective = TravelObjective(
        origin=ConstrainedField(value="ICN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.HARD),
        pax_count=ConstrainedField(value=1, constraint_type=ConstraintType.HARD),
        budget_amount=ConstrainedField(value=Decimal("1000"), constraint_type=ConstraintType.SOFT),
        budget_currency=ConstrainedField(value="USD", constraint_type=ConstraintType.SOFT),
    )
    # departure_date added by Feature 002 — set directly for now
    objective.departure_date = ConstrainedField(
        value="20260905", constraint_type=ConstraintType.HARD
    )

    journey = MagicMock()
    journey.journey_id = "journey-001"
    journey.call_budget = call_budget
    journey.confirmed_objective = objective
    journey.state = "OBJECTIVE_CONFIRMED"
    return journey


def _make_service(journey=None, http_response=None):
    """Build a FlightSearchService with mocked repo and http_client."""
    from journey.services.flight_search import FlightSearchService

    if journey is None:
        journey = _make_journey()

    repo = MagicMock()
    repo.get_journey.return_value = journey
    repo.decrement_call_budget.return_value = (journey.call_budget, journey.call_budget - 1)

    http_client = MagicMock(spec=httpx.Client)
    if http_response is None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_SUCCESS_RESPONSE
        http_response = mock_resp
    http_client.post.return_value = http_response

    svc = FlightSearchService(repo=repo, http_client=http_client)
    return svc, repo, http_client


# ---------------------------------------------------------------------------
# T013: FlightSearchService unit tests
# ---------------------------------------------------------------------------

class TestSearchParamsFromObjective:
    """FR-001: request body contains correct fromCity, toCity, fromDate, adultNum, currency."""

    def test_search_params_from_objective(self) -> None:
        svc, repo, http_client = _make_service()
        svc.search(journey_id="journey-001", now=BASE_NOW)

        http_client.post.assert_called_once()
        _, kwargs = http_client.post.call_args
        body = kwargs.get("json") or http_client.post.call_args[0][1]
        # Accept either positional or keyword json arg
        call_kwargs = http_client.post.call_args
        request_body = call_kwargs.kwargs.get("json") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert request_body is not None
        assert request_body["fromCity"] == "ICN"
        assert request_body["toCity"] == "NRT"
        assert request_body["fromDate"] == "20260905"
        assert request_body["adultNum"] == 1
        assert request_body["currency"] == "USD"

    def test_trip_type_is_one_way(self) -> None:
        svc, _, http_client = _make_service()
        svc.search(journey_id="journey-001", now=BASE_NOW)
        call_kwargs = http_client.post.call_args
        request_body = call_kwargs.kwargs.get("json") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert request_body["tripType"] == "1"


class TestCurrencyFromObjective:
    """FR-002: currency taken from budget_currency.value."""

    def test_currency_from_objective(self) -> None:
        svc, _, http_client = _make_service()
        svc.search(journey_id="journey-001", now=BASE_NOW)
        call_kwargs = http_client.post.call_args
        request_body = call_kwargs.kwargs.get("json") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert request_body["currency"] == "USD"

    def test_currency_defaults_to_usd_when_budget_currency_none(self) -> None:
        journey = _make_journey()
        journey.confirmed_objective.budget_currency = None
        svc, _, http_client = _make_service(journey=journey)
        svc.search(journey_id="journey-001", now=BASE_NOW)
        call_kwargs = http_client.post.call_args
        request_body = call_kwargs.kwargs.get("json") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert request_body["currency"] == "USD"


class TestAtlasStatusNonzeroRaisesError:
    """F3: HTTP 200 with atlas status != 0 raises AtlasSearchError."""

    def test_atlas_status_nonzero_raises_error(self) -> None:
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_NONZERO_STATUS_RESPONSE
        svc, _, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

    def test_atlas_status_nonzero_records_error_outcome(self) -> None:
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_NONZERO_STATUS_RESPONSE
        svc, repo, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.outcome.value == "ERROR"


class TestResultSummaryFields:
    """FR-006: SearchResult.option_count and carriers populated correctly."""

    def test_result_summary_fields(self) -> None:
        svc, _, _ = _make_service()
        result = svc.search(journey_id="journey-001", now=BASE_NOW)
        assert result.option_count == 2
        assert set(result.carriers) == {"SQ", "EK"}

    def test_no_options_false_when_options_present(self) -> None:
        svc, _, _ = _make_service()
        result = svc.search(journey_id="journey-001", now=BASE_NOW)
        assert result.no_options is False


class TestBudgetDecremented:
    """FR-009: call_budget decremented by 1 after successful search."""

    def test_budget_decremented(self) -> None:
        svc, repo, _ = _make_service()
        svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.decrement_call_budget.assert_called_once_with("journey-001")

    def test_search_record_records_budget_before_after(self) -> None:
        journey = _make_journey(call_budget=10)
        svc, repo, _ = _make_service(journey=journey)
        repo.decrement_call_budget.return_value = (10, 9)
        svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.budget_before == 10
        assert saved.budget_after == 9


class TestRateLimitNoRetry:
    """NFR-002: HTTP 429 raises RateLimitError; no retry before retryAfter."""

    def test_rate_limit_no_retry(self) -> None:
        from journey.errors import RateLimitError

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = ATLAS_RATE_LIMIT_RESPONSE
        svc, _, http_client = _make_service(http_response=mock_resp)

        with pytest.raises(RateLimitError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        # Must not retry — exactly one HTTP call
        assert http_client.post.call_count == 1


class TestEmptyResultNoException:
    """FR-010: zero routings returns SearchResult with no_options=True; no exception."""

    def test_empty_result_no_exception(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_EMPTY_RESPONSE
        svc, _, _ = _make_service(http_response=mock_resp)

        result = svc.search(journey_id="journey-001", now=BASE_NOW)
        assert result.option_count == 0
        assert result.no_options is True
        assert result.options == []


# ---------------------------------------------------------------------------
# T022: User Story 2 — Empty result handling
# ---------------------------------------------------------------------------

class TestEmptyRoutingsNoOptionTrue:
    """FR-010: zero routings → no_options=True, no exception."""

    def test_empty_routings_returns_no_options_true(self) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_EMPTY_RESPONSE
        svc, _, _ = _make_service(http_response=mock_resp)
        result = svc.search(journey_id="journey-001", now=BASE_NOW)
        assert result.no_options is True
        assert result.option_count == 0

    def test_empty_result_budget_still_decremented(self) -> None:
        """Budget decremented even when routings is empty (FR-009)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_EMPTY_RESPONSE
        svc, repo, _ = _make_service(http_response=mock_resp)
        svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.decrement_call_budget.assert_called_once_with("journey-001")

    def test_empty_result_search_record_outcome(self) -> None:
        """SearchRecord.outcome == EMPTY for zero-routing response."""
        from journey.models.flight import SearchOutcome
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = ATLAS_EMPTY_RESPONSE
        svc, repo, _ = _make_service(http_response=mock_resp)
        svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.outcome == SearchOutcome.EMPTY


# ---------------------------------------------------------------------------
# T026: User Story 3 — Rate limits and call budget
# ---------------------------------------------------------------------------

class TestRateLimitAndBudget:
    """NFR-002 / FR-009: rate limits and budget exhaustion."""

    def test_rate_limit_raises_error_with_retry_after(self) -> None:
        """HTTP 429 with retryAfter: 5 → RateLimitError(retry_after_seconds=5)."""
        from journey.errors import RateLimitError
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {"status": 2, "msg": "Rate limit", "retryAfter": 5}
        svc, _, _ = _make_service(http_response=mock_resp)
        with pytest.raises(RateLimitError) as exc_info:
            svc.search(journey_id="journey-001", now=BASE_NOW)
        assert exc_info.value.retry_after_seconds == 5.0

    def test_rate_limit_no_internal_retry(self) -> None:
        """After 429, no second HTTP request is made."""
        from journey.errors import RateLimitError
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = ATLAS_RATE_LIMIT_RESPONSE
        svc, _, http_client = _make_service(http_response=mock_resp)
        with pytest.raises(RateLimitError):
            svc.search(journey_id="journey-001", now=BASE_NOW)
        assert http_client.post.call_count == 1

    def test_rate_limit_budget_decremented(self) -> None:
        """429 still decrements call_budget and records budget_before/after."""
        from journey.errors import RateLimitError
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = ATLAS_RATE_LIMIT_RESPONSE
        journey = _make_journey(call_budget=10)
        svc, repo, _ = _make_service(journey=journey, http_response=mock_resp)
        repo.decrement_call_budget.return_value = (10, 9)
        with pytest.raises(RateLimitError):
            svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.decrement_call_budget.assert_called_once_with("journey-001")
        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.budget_before == 10
        assert saved.budget_after == 9

    def test_rate_limit_audit_trail_entry(self) -> None:
        """429 outcome recorded in SearchRecord as RATE_LIMITED."""
        from journey.errors import RateLimitError
        from journey.models.flight import SearchOutcome
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = ATLAS_RATE_LIMIT_RESPONSE
        svc, repo, _ = _make_service(http_response=mock_resp)
        with pytest.raises(RateLimitError):
            svc.search(journey_id="journey-001", now=BASE_NOW)
        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.outcome == SearchOutcome.RATE_LIMITED

    def test_budget_zero_raises_before_http_call(self) -> None:
        """call_budget=0 → BudgetExhaustedError raised; no HTTP call made."""
        from journey.errors import BudgetExhaustedError
        journey = _make_journey(call_budget=0)
        svc, repo, http_client = _make_service(journey=journey)
        repo.decrement_call_budget.side_effect = BudgetExhaustedError("exhausted")
        with pytest.raises(BudgetExhaustedError):
            svc.search(journey_id="journey-001", now=BASE_NOW)
        http_client.post.assert_not_called()

    def test_rate_gate_enforces_100ms_gap(self) -> None:
        """If _last_call_at < 100ms ago, RateLimitError is raised before HTTP."""
        from datetime import timedelta
        from journey.errors import RateLimitError
        svc, _, http_client = _make_service()
        # Simulate a recent call 50ms ago
        svc._last_call_at = BASE_NOW - timedelta(milliseconds=50)
        with pytest.raises(RateLimitError):
            svc.search(journey_id="journey-001", now=BASE_NOW)
        http_client.post.assert_not_called()


# ---------------------------------------------------------------------------
# FR-012: Malformed response body handling (SC-007)
# ---------------------------------------------------------------------------

class TestMalformedResponseBody:
    """FR-012: unparseable body or missing 'routings' key → ERROR outcome, not EMPTY."""

    def test_unparseable_json_raises_atlas_search_error(self) -> None:
        """Body that cannot be parsed as JSON raises AtlasSearchError."""
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("not valid json")
        mock_resp.text = "not valid json"
        svc, _, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

    def test_unparseable_json_persists_search_record(self) -> None:
        """SearchRecord with outcome ERROR is saved even when body cannot be parsed."""
        from journey.errors import AtlasSearchError
        from journey.models.flight import SearchOutcome

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("not valid json")
        mock_resp.text = "not valid json"
        svc, repo, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.outcome == SearchOutcome.ERROR
        assert saved.raw_response_json == "not valid json"

    def test_unparseable_json_budget_decremented(self) -> None:
        """Call budget is decremented even when body cannot be parsed (FR-009)."""
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("not valid json")
        mock_resp.text = "not valid json"
        svc, repo, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        repo.decrement_call_budget.assert_called_once_with("journey-001")

    def test_missing_routings_key_raises_atlas_search_error(self) -> None:
        """Valid JSON body lacking 'routings' key raises AtlasSearchError, not silent EMPTY."""
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0, "msg": "ok"}
        svc, _, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

    def test_missing_routings_key_persists_error_outcome(self) -> None:
        """SearchRecord with outcome ERROR is saved when 'routings' key is absent."""
        from journey.errors import AtlasSearchError
        from journey.models.flight import SearchOutcome

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0, "msg": "ok"}
        svc, repo, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        repo.save_search_record.assert_called_once()
        saved = repo.save_search_record.call_args[0][0]
        assert saved.outcome == SearchOutcome.ERROR

    def test_missing_routings_key_not_treated_as_empty(self) -> None:
        """Missing 'routings' key must NOT produce a SearchResult with option_count=0."""
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0, "msg": "ok"}
        svc, _, _ = _make_service(http_response=mock_resp)

        # Must raise — must never return a SearchResult
        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

    def test_missing_routings_key_budget_decremented(self) -> None:
        """Call budget is decremented when 'routings' key is absent (FR-009)."""
        from journey.errors import AtlasSearchError

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": 0, "msg": "ok"}
        svc, repo, _ = _make_service(http_response=mock_resp)

        with pytest.raises(AtlasSearchError):
            svc.search(journey_id="journey-001", now=BASE_NOW)

        repo.decrement_call_budget.assert_called_once_with("journey-001")
