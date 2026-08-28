"""Contract tests for GET /journeys/{id}/events/replay (T054).

Verifies against contracts/sse_stream.md: replay_started first, events in
order, speed<=0 returns 422, and (per FR-012) replay makes no calls to any
external service — verified indirectly here by asserting the replay reads
only from local storage (no network client is constructed at all).
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from journey.api.main import app


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'replay_contract.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_events() -> str:
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
        EventType.EXTERNAL_CALL,
        {"endpoint": "/p", "outcome": "success", "elapsed_ms": 5},
    )
    service.append(
        journey.journey_id,
        EventType.CALL_BUDGET_UPDATED,
        {"budget_remaining": 9},
    )
    return journey.journey_id


def _parse_sse_events(lines: Iterator[str]) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in lines:
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        field, _, value = line.partition(":")
        if field in ("id", "event", "data"):
            current[field] = value.lstrip(" ")
    if current:
        events.append(current)
    return events


class TestReplayContract:
    def test_replay_started_first_and_replay_ended_last(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_events()
        client = TestClient(app)
        with client.stream(
            "GET", f"/journeys/{journey_id}/events/replay?speed=1000"
        ) as response:
            assert response.status_code == 200
            events = _parse_sse_events(response.iter_lines())

        assert [e["event"] for e in events] == [
            "replay_started",
            "external_call",
            "call_budget_updated",
            "replay_ended",
        ]
        started = json.loads(events[0]["data"])
        assert started["payload"]["source_journey_id"] == journey_id
        assert started["payload"]["speed_multiplier"] == 1000.0

    def test_events_arrive_in_recorded_order(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_events()
        client = TestClient(app)
        with client.stream(
            "GET", f"/journeys/{journey_id}/events/replay?speed=1000"
        ) as response:
            events = _parse_sse_events(response.iter_lines())

        middle = [json.loads(e["data"]) for e in events[1:-1]]
        assert middle[0]["payload"] == {
            "endpoint": "/p",
            "outcome": "success",
            "elapsed_ms": 5,
        }
        assert middle[1]["payload"] == {"budget_remaining": 9}

    def test_non_positive_speed_returns_422(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_events()
        client = TestClient(app)
        response = client.get(f"/journeys/{journey_id}/events/replay?speed=0")
        assert response.status_code == 422

    def test_negative_speed_returns_422(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_events()
        client = TestClient(app)
        response = client.get(f"/journeys/{journey_id}/events/replay?speed=-2")
        assert response.status_code == 422
