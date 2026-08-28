"""Contract tests for POST /journeys/{id}/authorisation/{request_id} (T043).

Verifies against contracts/sse_stream.md: 200 on approval, 409 on duplicate
resolution, 404 for unknown journey/request, 422 for an invalid outcome.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi.testclient import TestClient

from journey.api.main import app


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'auth_contract.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_auth_request() -> tuple[str, str]:
    from journey.models.events import EventType
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.event_service import EventService
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService().create_journey(objective)
    service = EventService()
    service.append(
        journey.journey_id,
        EventType.AUTHORISATION_REQUESTED,
        {
            "request_id": "req-1",
            "action": "Rebook LJ201",
            "cost": "+USD 6.24",
            "objective_effect": "Preserved",
            "rule_id": "AUTH-01",
        },
    )
    return journey.journey_id, "req-1"


class TestAuthContract:
    def test_approve_returns_200(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id, request_id = _seed_journey_with_auth_request()
        client = TestClient(app)
        response = client.post(
            f"/journeys/{journey_id}/authorisation/{request_id}",
            json={"outcome": "approved"},
        )
        assert response.status_code == 200

    def test_duplicate_resolution_returns_409(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id, request_id = _seed_journey_with_auth_request()
        client = TestClient(app)
        client.post(
            f"/journeys/{journey_id}/authorisation/{request_id}",
            json={"outcome": "approved"},
        )
        response = client.post(
            f"/journeys/{journey_id}/authorisation/{request_id}",
            json={"outcome": "refused"},
        )
        assert response.status_code == 409

    def test_unknown_journey_returns_404(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        client = TestClient(app)
        response = client.post(
            "/journeys/00000000-0000-0000-0000-000000000000/authorisation/req-1",
            json={"outcome": "approved"},
        )
        assert response.status_code == 404

    def test_unknown_request_id_returns_404(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id, _ = _seed_journey_with_auth_request()
        client = TestClient(app)
        response = client.post(
            f"/journeys/{journey_id}/authorisation/does-not-exist",
            json={"outcome": "approved"},
        )
        assert response.status_code == 404

    def test_invalid_outcome_returns_422(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id, request_id = _seed_journey_with_auth_request()
        client = TestClient(app)
        response = client.post(
            f"/journeys/{journey_id}/authorisation/{request_id}",
            json={"outcome": "maybe"},
        )
        assert response.status_code == 422
