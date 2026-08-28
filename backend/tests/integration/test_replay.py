"""Integration tests for replay (T055).

Loads the canonical fixture (backend/tests/fixtures/journey_events_001.json),
replays it at high speed via the HTTP endpoint, and asserts (FR-012):
- all events are received in recorded order
- inter-event timing is scaled by the speed multiplier
- replay_started.speed_multiplier matches the requested speed
- no rows are written to journey_events during replay
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from journey.api.main import app

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "journey_events_001.json"
STREAM_TIMEOUT_SECONDS = 10.0


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'replay.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _load_fixture_journey() -> str:
    """Create a journey and load the fixture events into its event log.

    Preserves each row's original `recorded_at` so inter-event delays match
    the recording exactly — passing `recorded_at=None` here would collapse
    every delay to ~0 (all rows inserted within the same event loop tick).
    """
    from datetime import datetime

    from journey.models.events import EventType
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.event_service import EventService
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    journey = JourneyService().create_journey(objective)
    service = EventService()
    fixture = json.loads(FIXTURE_PATH.read_text())
    for row in fixture:
        service.append(
            journey.journey_id,
            EventType(row["event_type"]),
            row["payload"],
            simulated=row["simulated"],
            recorded_at=datetime.fromisoformat(row["recorded_at"]),
        )
    return journey.journey_id


async def _collect_replay(journey_id: str, speed: float) -> list[dict[str, str]]:
    transport = ASGITransport(app=app)
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}

    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        async with client.stream(
            "GET", f"/journeys/{journey_id}/events/replay?speed={speed}"
        ) as response:
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
    return events


class TestReplayFixture:
    @pytest.mark.asyncio
    async def test_all_events_received_in_order(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _load_fixture_journey()
        fixture = json.loads(FIXTURE_PATH.read_text())

        events = await asyncio.wait_for(
            _collect_replay(journey_id, speed=1000.0), timeout=STREAM_TIMEOUT_SECONDS
        )

        assert events[0]["event"] == "replay_started"
        assert events[-1]["event"] == "replay_ended"
        middle = events[1:-1]
        assert [e["event"] for e in middle] == [row["event_type"] for row in fixture]

    @pytest.mark.asyncio
    async def test_replay_started_reports_requested_speed(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _load_fixture_journey()

        # High speed so the ~90s of recorded deltas collapse to well under
        # STREAM_TIMEOUT_SECONDS; only the reported multiplier is under test.
        events = await asyncio.wait_for(
            _collect_replay(journey_id, speed=1000.0), timeout=STREAM_TIMEOUT_SECONDS
        )

        started = json.loads(events[0]["data"])
        assert started["payload"]["speed_multiplier"] == 1000.0
        assert started["payload"]["source_journey_id"] == journey_id

    @pytest.mark.asyncio
    async def test_inter_event_timing_is_scaled_by_speed(self, tmp_path: Any) -> None:
        """A 2s recorded gap replayed at speed=10 takes ~0.2s wall-clock.

        Uses its own short two-event sequence (not the ~90s fixture) so the
        assertion is tight enough to actually prove scaling, rather than a
        loose upper bound that would pass even if delays were ignored.
        """
        from datetime import datetime, timedelta, timezone

        from journey.models.events import EventType
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
        from journey.services.event_service import EventService
        from journey.services.journey_service import JourneyService

        _file_db(tmp_path)
        objective = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )
        journey = JourneyService().create_journey(objective)
        service = EventService()
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        service.append(
            journey.journey_id,
            EventType.DECISION,
            {"description": "d1", "reason": "r1"},
            recorded_at=t0,
        )
        service.append(
            journey.journey_id,
            EventType.DECISION,
            {"description": "d2", "reason": "r2"},
            recorded_at=t0 + timedelta(seconds=2),
        )

        start = time.monotonic()
        await asyncio.wait_for(
            _collect_replay(journey.journey_id, speed=10.0),
            timeout=STREAM_TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - start
        assert 0.1 <= elapsed <= 1.0

    @pytest.mark.asyncio
    async def test_no_rows_written_during_replay(self, tmp_path: Any) -> None:
        from journey.storage.db import get_connection
        from journey.storage.tables import journey_events
        import sqlalchemy as sa

        _file_db(tmp_path)
        journey_id = _load_fixture_journey()

        def _count() -> int:
            with get_connection() as conn:
                return conn.execute(
                    sa.select(sa.func.count()).select_from(journey_events).where(
                        journey_events.c.journey_id == journey_id
                    )
                ).scalar()

        before = _count()
        await asyncio.wait_for(
            _collect_replay(journey_id, speed=1000.0), timeout=STREAM_TIMEOUT_SECONDS
        )
        after = _count()
        assert before == after
