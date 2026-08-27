"""Integration tests for FlightSearchService persistence (T014).

Tests MUST fail before production code is written (TDD gate T016).
NFR-001: Transaction 1 (SearchRecord + budget) is committed before Transaction 2
(FlightOption/Leg). A Transaction 2 failure must NOT roll back Transaction 1.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

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


ATLAS_SUCCESS_RESPONSE = {
    "status": 0,
    "routings": [
        {
            "fid": "TEST_FID_001",
            "routingIdentifier": "RI::ICN::NRT::20260905::ZE::609",
            "currency": "USD",
            "adultPrice": 62.43,
            "adultTax": 29.35,
            "transactionFee": 0.0,
            "separateBookings": False,
            "refreshTime": "2026-09-05T02:30:00Z",
            "expireTime": "2026-09-05T02:36:47Z",
            "riskSellout": False,
            "fromSegments": [
                {
                    "segmentIndex": 1,
                    "carrier": "ZE",
                    "flightNumber": "ZE609",
                    "depAirport": "ICN",
                    "depTime": "202609051030",
                    "arrAirport": "NRT",
                    "arrTime": "202609051300",
                    "stopCities": "",
                    "duration": 150,
                    "codeShare": False,
                    "cabin": "S",
                    "cabinClass": 1,
                    "seatCount": 9,
                    "aircraftCode": "738",
                    "fareFamily": "Discount Fare",
                }
            ],
            "retSegments": [],
        }
    ],
}


class TestRawResponsePersisted:
    def setup_method(self) -> None:
        _fresh_db()

    def test_raw_response_persisted(self) -> None:
        """NFR-001: full raw JSON written to search_records before option mapping."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService

        repo = JourneyRepository()
        record = _make_journey(repo)
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ATLAS_SUCCESS_RESPONSE

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        result = svc.search(journey_id=record.journey_id, now=now)

        search_rec = repo.get_search_record(result.search_id)
        assert search_rec is not None
        raw = json.loads(search_rec.raw_response_json)
        assert raw["status"] == 0
        assert "routings" in raw


class TestTransaction2FailureDoesNotRollbackTransaction1:
    def setup_method(self) -> None:
        _fresh_db()

    def test_transaction2_failure_does_not_rollback_transaction1(self) -> None:
        """NFR-001: Transaction 2 failure leaves Transaction 1 data intact in DB."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService

        repo = JourneyRepository()
        record = _make_journey(repo)
        budget_before = record.call_budget
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        # Malformed: missing required fields to trigger mapping failure in Tx2
        bad_response = {
            "status": 0,
            "routings": [
                {
                    "fid": "BAD_FID",
                    "routingIdentifier": "RI::BAD",
                    "currency": "USD",
                    "adultPrice": 100.0,
                    "adultTax": 10.0,
                    "transactionFee": 0.0,
                    "separateBookings": False,
                    "refreshTime": None,
                    "expireTime": None,
                    "riskSellout": False,
                    "fromSegments": [
                        # Missing all required fields — should fail mapping
                        {"INVALID_KEY": "INVALID_VALUE"}
                    ],
                    "retSegments": [],
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = bad_response

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        # Search may succeed (mapping failure is logged; partial results allowed)
        # or raise — what matters is Transaction 1 committed regardless
        try:
            svc.search(journey_id=record.journey_id, now=now)
        except Exception:
            pass

        # Transaction 1 must be committed: SearchRecord row must exist
        from journey.storage.db import get_engine
        from sqlalchemy import text

        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) FROM search_records WHERE journey_id = :jid"),
                {"jid": record.journey_id},
            ).scalar()
        assert row == 1, "SearchRecord from Transaction 1 must persist even if Transaction 2 fails"

        # Budget must be decremented (also Transaction 1)
        reloaded = repo.get_journey(record.journey_id)
        assert reloaded.call_budget == budget_before - 1


class TestSearchRecordAndOptionsRoundTrip:
    def setup_method(self) -> None:
        _fresh_db()

    def test_search_record_and_options_round_trip(self) -> None:
        """All SearchRecord and FlightOption fields survive a persist-and-reload cycle."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService

        repo = JourneyRepository()
        record = _make_journey(repo)
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ATLAS_SUCCESS_RESPONSE

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        result = svc.search(journey_id=record.journey_id, now=now)

        assert result.option_count == 1
        options = repo.get_options(search_id=result.search_id)
        assert len(options) == 1
        opt = options[0]
        assert opt.fid == "TEST_FID_001"
        assert opt.routing_identifier == "RI::ICN::NRT::20260905::ZE::609"
        assert opt.currency == "USD"
        assert opt.adult_price == Decimal("62.43")
        assert len(opt.legs) == 1
        assert opt.legs[0].carrier == "ZE"
        assert opt.legs[0].flight_number == "ZE609"


class TestBudgetBeforeAfterRecorded:
    def setup_method(self) -> None:
        _fresh_db()

    def test_budget_before_after_recorded(self) -> None:
        """SearchRecord.budget_before and budget_after reflect the decrement."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService

        repo = JourneyRepository()
        record = _make_journey(repo)
        budget_before = record.call_budget
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ATLAS_SUCCESS_RESPONSE

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        result = svc.search(journey_id=record.journey_id, now=now)

        search_rec = repo.get_search_record(result.search_id)
        assert search_rec.budget_before == budget_before
        assert search_rec.budget_after == budget_before - 1


class TestGetOptionsRaisesIfSearchRecordNotFound:
    def setup_method(self) -> None:
        _fresh_db()

    def test_get_options_raises_if_search_record_not_found(self) -> None:
        """get_options(unknown_search_id) raises SearchRecordNotFoundError (contract F4)."""
        from journey.storage.repository import JourneyRepository
        from journey.errors import SearchRecordNotFoundError

        repo = JourneyRepository()
        with pytest.raises(SearchRecordNotFoundError):
            repo.get_options(search_id="does-not-exist")


class TestMalformedResponsePersistence:
    """FR-012 / SC-007: malformed body still persists SearchRecord with ERROR outcome."""

    def setup_method(self) -> None:
        _fresh_db()

    def test_unparseable_json_persists_error_search_record(self) -> None:
        """Unparseable body → SearchRecord with ERROR outcome and raw text in DB."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService
        from journey.models.flight import SearchOutcome
        from journey.errors import AtlasSearchError

        repo = JourneyRepository()
        record = _make_journey(repo)
        budget_before = record.call_budget
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("not valid json")
        mock_response.text = "not valid json"

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        with pytest.raises(AtlasSearchError):
            svc.search(journey_id=record.journey_id, now=now)

        from journey.storage.db import get_engine
        from sqlalchemy import text

        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT outcome, raw_response_json FROM search_records WHERE journey_id = :jid"),
                {"jid": record.journey_id},
            ).fetchone()

        assert row is not None, "SearchRecord must be persisted even when body is unparseable"
        assert row[0] == SearchOutcome.ERROR
        assert row[1] == "not valid json"

        reloaded = repo.get_journey(record.journey_id)
        assert reloaded.call_budget == budget_before - 1

    def test_missing_routings_key_persists_error_search_record(self) -> None:
        """Missing 'routings' key → SearchRecord with ERROR outcome in DB; not EMPTY."""
        from journey.storage.repository import JourneyRepository
        from journey.services.flight_search import FlightSearchService
        from journey.models.flight import SearchOutcome
        from journey.errors import AtlasSearchError

        repo = JourneyRepository()
        record = _make_journey(repo)
        budget_before = record.call_budget
        now = datetime(2026, 9, 5, 2, 31, 0, tzinfo=timezone.utc)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": 0, "msg": "ok"}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response

        svc = FlightSearchService(repo=repo, http_client=mock_client)
        with pytest.raises(AtlasSearchError):
            svc.search(journey_id=record.journey_id, now=now)

        from journey.storage.db import get_engine
        from sqlalchemy import text

        with get_engine().connect() as conn:
            row = conn.execute(
                text("SELECT outcome, raw_response_json FROM search_records WHERE journey_id = :jid"),
                {"jid": record.journey_id},
            ).fetchone()

        assert row is not None, "SearchRecord must be persisted when 'routings' key is absent"
        assert row[0] == SearchOutcome.ERROR
        raw = json.loads(row[1])
        assert "routings" not in raw

        reloaded = repo.get_journey(record.journey_id)
        assert reloaded.call_budget == budget_before - 1
