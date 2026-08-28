"""Contract tests for the SSE event stream endpoint (T021).

Verifies GET /journeys/{journey_id}/events against contracts/sse_stream.md:
Content-Type, per-event {id, event, data} shape with valid JSON data, and
HTTP 404 for an unknown journey before the stream opens.

TDD NOTE (T027): the SSE endpoint was delivered fully in Phase 2 (T016
implemented the live endpoint rather than a stub), so this suite passes
immediately and serves as the contract regression suite for FR-006.
The US1 frontend tests (T024-T026) fail as expected and gate the
Phase 3 implementation work.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

from fastapi.testclient import TestClient

from journey.api.main import app


def _file_db(tmp_path: Any) -> str:
    db_url = f"sqlite:///{tmp_path / 'sse_contract.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())
    return db_url


def _seed_journey_with_terminal_event() -> str:
    """Create a journey with a short event sequence ending in CANCELLED.

    The terminal state_change closes the stream so tests can read it to
    completion synchronously.
    """
    from journey.models.events import EventType
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.event_service import EventService
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
    )
    created = JourneyService().create_journey(objective)
    service = EventService()
    service.append(
        created.journey_id,
        EventType.OBJECTIVE_SET,
        {
            "hard_constraints": [{"field": "origin", "value": "SIN"}],
            "preferences": [{"field": "cabin", "value": "economy"}],
        },
    )
    service.append(
        created.journey_id,
        EventType.EXTERNAL_CALL,
        {"endpoint": "/shopping/flightoffices", "outcome": "success", "elapsed_ms": 843},
    )
    service.append(
        created.journey_id,
        EventType.CALL_BUDGET_UPDATED,
        {"budget_remaining": 19},
        simulated=True,
    )
    service.append(
        created.journey_id,
        EventType.STATE_CHANGE,
        {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "CANCELLED"},
    )
    return created.journey_id


def _parse_sse_events(lines: Iterator[str]) -> list[dict[str, str]]:
    """Parse SSE wire lines into {id, event, data} dicts per event block."""
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


class TestSSEContract:
    def test_unknown_journey_returns_404(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        client = TestClient(app)
        response = client.get("/journeys/00000000-0000-0000-0000-000000000000/events")
        assert response.status_code == 404

    def test_content_type_is_text_event_stream(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_terminal_event()
        client = TestClient(app)
        with client.stream("GET", f"/journeys/{journey_id}/events") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            list(response.iter_lines())  # drain: terminal event closes the stream

    def test_cache_control_and_buffering_headers(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_terminal_event()
        client = TestClient(app)
        with client.stream("GET", f"/journeys/{journey_id}/events") as response:
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-accel-buffering"] == "no"
            list(response.iter_lines())  # drain: terminal event closes the stream

    def test_each_event_has_id_event_and_valid_json_data(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_terminal_event()
        client = TestClient(app)
        with client.stream("GET", f"/journeys/{journey_id}/events") as response:
            events = _parse_sse_events(response.iter_lines())

        assert len(events) == 4
        assert [e["id"] for e in events] == ["1", "2", "3", "4"]
        assert [e["event"] for e in events] == [
            "objective_set",
            "external_call",
            "call_budget_updated",
            "state_change",
        ]
        for event in events:
            data = json.loads(event["data"])
            assert isinstance(data, dict)
            # FR-010: the simulated flag travels on the wire so the
            # stateless interface can distinguish simulated events.
            assert isinstance(data["simulated"], bool)
            assert isinstance(data["payload"], dict)

    def test_payload_fields_reach_the_wire(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_terminal_event()
        client = TestClient(app)
        with client.stream("GET", f"/journeys/{journey_id}/events") as response:
            events = _parse_sse_events(response.iter_lines())

        external_call = json.loads(events[1]["data"])
        assert external_call["payload"] == {
            "endpoint": "/shopping/flightoffices",
            "outcome": "success",
            "elapsed_ms": 843,
        }
        simulated_budget_event = json.loads(events[2]["data"])
        assert simulated_budget_event["simulated"] is True
        state_change = json.loads(events[3]["data"])
        assert state_change["payload"]["to_state"] == "CANCELLED"
