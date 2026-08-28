"""Contract tests for POST /operator/disruptions (T029-T032).

TDD gate: these tests must fail (ImportError against the not-yet-existing
router module) before implementation.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

_TOKEN_ENV = "DISRUPTION_INJECTOR_TOKEN"
_ENABLED_ENV = "DISRUPTION_INJECTOR_ENABLED"


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'disruption_injector_contract.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_order(order_no: str = "TESTA20260815180326173") -> str:
    from journey.models.booking import Order, OrderOutcome
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService
    from journey.storage.repository import JourneyRepository

    repo = JourneyRepository()
    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey_id = JourneyService(repository=repo).create_journey(objective).journey_id
    repo.save_order(
        Order(
            order_id="order-1",
            journey_id=journey_id,
            option_id="option-1",
            requested_at=datetime.now(tz=timezone.utc),
            responded_at=datetime.now(tz=timezone.utc),
            raw_response_json="{}",
            outcome=OrderOutcome.CREATED,
            order_no=order_no,
            booking_reference="PNR123",
            ticketing_deadline=None,
            session_id_used="session-1",
        )
    )
    return journey_id


def _reset_env() -> None:
    os.environ.pop(_TOKEN_ENV, None)
    os.environ.pop(_ENABLED_ENV, None)


class TestEndpointRejectsMissingOrWrongToken:
    def test_missing_token_returns_401(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "true"
        journey_id = _seed_journey_with_order()
        from journey.api.main import app

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            json={"journey_id": journey_id, "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 401

    def test_wrong_token_returns_401(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "true"
        journey_id = _seed_journey_with_order()
        from journey.api.main import app

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            headers={"X-Operator-Token": "wrong"},
            json={"journey_id": journey_id, "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 401


class TestEndpointRejectsWhenDisabled:
    def test_correct_token_but_disabled_returns_401(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "false"
        journey_id = _seed_journey_with_order()
        from journey.api.main import app

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            headers={"X-Operator-Token": "secret123"},
            json={"journey_id": journey_id, "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 401


class TestEndpointAcceptsValidTokenWhenEnabled:
    def test_200_and_notification_persisted(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "true"
        journey_id = _seed_journey_with_order()
        from journey.api.main import app
        from journey.storage.repository import JourneyRepository

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            headers={"X-Operator-Token": "secret123"},
            json={"journey_id": journey_id, "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 200
        notifications = JourneyRepository().get_notifications_for_order("TESTA20260815180326173")
        assert len(notifications) == 1
        assert notifications[0].simulated is True


class TestEndpointTranslatesTargetErrors:
    def test_nonexistent_journey_returns_404(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "true"
        from journey.api.main import app

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            headers={"X-Operator-Token": "secret123"},
            json={"journey_id": "does-not-exist", "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 404

    def test_journey_with_no_order_returns_409(self, tmp_path: Any) -> None:
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
        from journey.services.journey_service import JourneyService
        from journey.storage.repository import JourneyRepository

        _file_db(tmp_path)
        _reset_env()
        os.environ[_TOKEN_ENV] = "secret123"
        os.environ[_ENABLED_ENV] = "true"
        objective = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        journey_id = JourneyService(repository=JourneyRepository()).create_journey(objective).journey_id
        from journey.api.main import app

        client = TestClient(app)
        response = client.post(
            "/operator/disruptions",
            headers={"X-Operator-Token": "secret123"},
            json={"journey_id": journey_id, "revised_arrival_time": "2026-09-01T00:00:00+00:00"},
        )

        assert response.status_code == 409
