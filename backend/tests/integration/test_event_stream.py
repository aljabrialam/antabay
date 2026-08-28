"""Integration tests for the live SSE event stream (T022).

Seeds a journey and events via EventService.append, opens the stream with
httpx.AsyncClient(stream=True) against the ASGI app, and asserts:
- events arrive in sequence order (FR-006)
- Last-Event-ID reconnection skips already-delivered events (FR-006)
- events appended after the stream opens arrive on the open stream

TDD NOTE (T027): EventService.stream_events and the SSE endpoint were
delivered fully in Phase 2 (T015/T016), so this suite passes immediately
and serves as the FR-006/FR-011 regression suite. The US1 frontend tests
(T024-T026) fail as expected and gate the Phase 3 implementation work.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from journey.api.main import app

STREAM_TIMEOUT_SECONDS = 5.0


def _file_db(tmp_path: Any) -> str:
    db_url = f"sqlite:///{tmp_path / 'event_stream.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())
    return db_url


def _create_journey() -> str:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        destination=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
    )
    return JourneyService().create_journey(objective).journey_id


def _append(journey_id: str, event_type: str, payload: dict[str, object]) -> None:
    from journey.models.events import EventType
    from journey.services.event_service import EventService

    EventService().append(journey_id, EventType(event_type), payload)


async def _collect_events(
    journey_id: str, last_event_id: str | None = None
) -> list[dict[str, str]]:
    """Open the SSE stream and collect every event until it closes."""
    headers = {"Last-Event-ID": last_event_id} if last_event_id else {}
    transport = ASGITransport(app=app)
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}

    async def _read() -> None:
        nonlocal current
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            async with client.stream(
                "GET", f"/journeys/{journey_id}/events", headers=headers
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")
                async for line in response.aiter_lines():
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

    await asyncio.wait_for(_read(), timeout=STREAM_TIMEOUT_SECONDS)
    return events


class TestLiveStream:
    @pytest.mark.asyncio
    async def test_events_arrive_in_sequence_order(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        _append(journey_id, "objective_set", {"hard_constraints": [], "preferences": []})
        _append(
            journey_id,
            "external_call",
            {"endpoint": "/shopping/flightoffices", "outcome": "success", "elapsed_ms": 500},
        )
        _append(journey_id, "call_budget_updated", {"budget_remaining": 19})
        # Terminal event closes the stream after yielding.
        _append(
            journey_id,
            "state_change",
            {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "CANCELLED"},
        )

        events = await _collect_events(journey_id)

        assert [e["id"] for e in events] == ["1", "2", "3", "4"]
        assert [e["event"] for e in events] == [
            "objective_set",
            "external_call",
            "call_budget_updated",
            "state_change",
        ]

    @pytest.mark.asyncio
    async def test_last_event_id_reconnection_skips_delivered_events(
        self, tmp_path: Any
    ) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        _append(journey_id, "objective_set", {"hard_constraints": [], "preferences": []})
        _append(journey_id, "decision", {"description": "d1", "reason": "r1"})
        _append(journey_id, "decision", {"description": "d2", "reason": "r2"})
        _append(
            journey_id,
            "state_change",
            {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "CANCELLED"},
        )

        # Client already saw sequences 1 and 2 before disconnecting.
        events = await _collect_events(journey_id, last_event_id="2")

        assert [e["id"] for e in events] == ["3", "4"]
        data = json.loads(events[0]["data"])
        assert data["payload"] == {"description": "d2", "reason": "r2"}

    @pytest.mark.asyncio
    async def test_event_appended_after_open_arrives_on_open_stream(
        self, tmp_path: Any
    ) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        _append(journey_id, "objective_set", {"hard_constraints": [], "preferences": []})

        async def _append_terminal_later() -> None:
            await asyncio.sleep(0.2)
            _append(
                journey_id,
                "state_change",
                {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "CANCELLED"},
            )

        append_task = asyncio.create_task(_append_terminal_later())
        events = await _collect_events(journey_id)
        await append_task

        # Sequence 1 was already stored; sequence 2 arrives via the 0.5 s
        # poll after the stream opened (FR-006: pushed, not polled by the client).
        assert [e["id"] for e in events] == ["1", "2"]
        assert events[-1]["event"] == "state_change"
