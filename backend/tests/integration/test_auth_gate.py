"""Integration tests for the authorisation gate (T044).

Seeds an authorisation_requested event, POSTs an outcome, and asserts the
resulting authorisation_outcome event appears on the SSE stream with the
matching rule_id (FR-008, FR-009, SC-003).
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


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'auth_gate.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _seed_journey_with_auth_request() -> str:
    from journey.models.events import EventType
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.event_service import EventService
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService().create_journey(objective)
    EventService().append(
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
    return journey.journey_id


async def _collect_until_terminal(journey_id: str, expect_events: int) -> list[dict[str, str]]:
    from journey.models.events import EventType
    from journey.services.event_service import EventService

    transport = ASGITransport(app=app)
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}

    async def _read() -> None:
        nonlocal current
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            async with client.stream(
                "GET", f"/journeys/{journey_id}/events"
            ) as response:
                async for line in response.aiter_lines():
                    if line == "":
                        if current:
                            events.append(current)
                            current = {}
                        if len(events) >= expect_events:
                            return
                        continue
                    field, _, value = line.partition(":")
                    if field in ("id", "event", "data"):
                        current[field] = value.lstrip(" ")

    read_task = asyncio.create_task(_read())
    await asyncio.sleep(0.1)
    EventService().append(
        journey_id,
        EventType.STATE_CHANGE,
        {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "CANCELLED"},
    )
    await asyncio.wait_for(read_task, timeout=STREAM_TIMEOUT_SECONDS)
    return events


class TestAuthGate:
    @pytest.mark.asyncio
    async def test_approval_appears_on_stream_with_rule_id(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_auth_request()

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                f"/journeys/{journey_id}/authorisation/req-1",
                json={"outcome": "approved"},
            )
        assert response.status_code == 200

        # 2 events expected: authorisation_requested, authorisation_outcome,
        # plus the terminal state_change appended by the collector.
        events = await _collect_until_terminal(journey_id, expect_events=3)
        assert [e["event"] for e in events] == [
            "authorisation_requested",
            "authorisation_outcome",
            "state_change",
        ]
        outcome_data = json.loads(events[1]["data"])
        assert outcome_data["payload"]["outcome"] == "approved"
        assert outcome_data["payload"]["rule_id"] == "AUTH-01"

    @pytest.mark.asyncio
    async def test_refusal_appears_on_stream_with_rule_id(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _seed_journey_with_auth_request()

        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            response = await client.post(
                f"/journeys/{journey_id}/authorisation/req-1",
                json={"outcome": "refused"},
            )
        assert response.status_code == 200

        events = await _collect_until_terminal(journey_id, expect_events=3)
        outcome_data = json.loads(events[1]["data"])
        assert outcome_data["payload"]["outcome"] == "refused"
        assert outcome_data["payload"]["rule_id"] == "AUTH-01"
