"""Unit tests for EventService append and stream semantics (T023).

TDD NOTE (T027): EventService.append and stream_events were delivered fully
in Phase 2 (T015), so this suite passes immediately and serves as the
FR-011 regression suite. The US1 frontend tests (T024-T026) fail as
expected and gate the Phase 3 implementation work.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import aclosing
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from journey.models.events import EventType
from journey.services.event_service import EventService


def _file_db(tmp_path: Any) -> None:
    db_url = f"sqlite:///{tmp_path / 'event_service.db'}"
    os.environ["JOURNEY_DB_URL"] = db_url
    from journey.storage.db import get_engine, reset_engine
    from journey.storage.tables import metadata

    reset_engine()
    metadata.create_all(get_engine())


def _create_journey() -> str:
    from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective
    from journey.services.journey_service import JourneyService

    objective = TravelObjective(
        origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
    )
    return JourneyService().create_journey(objective).journey_id


def _service() -> EventService:
    return EventService()


class TestAppendEvent:
    def test_sequence_starts_at_one(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        event = _service().append(
            journey_id,
            EventType.EXTERNAL_CALL,
            {"endpoint": "/p", "outcome": "success", "elapsed_ms": 10},
        )
        assert event.sequence == 1
        assert event.journey_id == journey_id
        assert event.event_type is EventType.EXTERNAL_CALL
        assert event.simulated is False

    def test_sequence_increments_monotonically(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        service = _service()
        sequences = [
            service.append(
                journey_id, EventType.DECISION, {"description": "d", "reason": "r"}
            ).sequence
            for _ in range(3)
        ]
        assert sequences == [1, 2, 3]

    def test_append_raises_on_unknown_journey(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        with pytest.raises(ValueError):
            _service().append(
                "00000000-0000-0000-0000-000000000000",
                EventType.DECISION,
                {"description": "d", "reason": "r"},
            )

    def test_duplicate_sequence_rejected_by_unique_constraint(
        self, tmp_path: Any
    ) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        service = _service()
        first = service.append(
            journey_id,
            EventType.EXTERNAL_CALL,
            {"endpoint": "/p", "outcome": "success", "elapsed_ms": 10},
        )

        from journey.storage.db import get_connection
        from journey.storage.tables import journey_events

        # A raw insert replaying an existing sequence must violate the
        # (journey_id, sequence) unique constraint.
        with pytest.raises(IntegrityError):
            with get_connection() as conn:
                conn.execute(
                    insert(journey_events).values(
                        event_id="dup-event",
                        journey_id=journey_id,
                        sequence=first.sequence,
                        event_type=EventType.DECISION.value,
                        payload_json='{"description": "d", "reason": "r"}',
                        simulated=0,
                        recorded_at=first.recorded_at.isoformat(),
                    )
                )
                conn.commit()

    def test_append_rejects_invalid_payload(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        with pytest.raises(Exception):
            _service().append(
                journey_id,
                EventType.EXTERNAL_CALL,
                {"endpoint": "/p"},  # missing outcome and elapsed_ms
            )


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_yields_only_rows_after_last_sequence(self, tmp_path: Any) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        service = _service()
        for i in range(3):
            service.append(
                journey_id,
                EventType.DECISION,
                {"description": f"d{i}", "reason": "r"},
            )

        collected: list[int] = []

        async def _consume() -> None:
            gen = service.stream_events(journey_id, last_sequence=1)
            async with aclosing(gen):
                async for event in gen:
                    collected.append(event.sequence)
                    # Stop after the batch: without a terminal event the
                    # stream polls forever by design.
                    if collected and collected[-1] == 3:
                        return

        await asyncio.wait_for(_consume(), timeout=3.0)
        assert collected == [2, 3]

    @pytest.mark.asyncio
    async def test_stream_terminates_on_terminal_state_change(
        self, tmp_path: Any
    ) -> None:
        _file_db(tmp_path)
        journey_id = _create_journey()
        service = _service()
        service.append(
            journey_id,
            EventType.DECISION,
            {"description": "d", "reason": "r"},
        )
        service.append(
            journey_id,
            EventType.STATE_CHANGE,
            {"from_state": "OBJECTIVE_CONFIRMED", "to_state": "ABANDONED"},
        )

        collected = [e.sequence async for e in service.stream_events(journey_id)]
        assert collected == [1, 2]


class TestObjectiveSetPayloadFrom:
    """T031: TravelObjective -> ObjectiveSetPayload dict conversion (FR-001)."""

    def test_buckets_fields_by_their_own_constraint_type(self) -> None:
        from decimal import Decimal

        from journey.models.events import objective_set_payload_from
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        objective = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
            destination=ConstrainedField(value="NRT", constraint_type=ConstraintType.SOFT),
            budget_amount=ConstrainedField(
                value=Decimal("120.00"), constraint_type=ConstraintType.HARD
            ),
            budget_currency=ConstrainedField(value="USD", constraint_type=ConstraintType.HARD),
            preferences=ConstrainedField(
                value=["window seat"], constraint_type=ConstraintType.SOFT
            ),
        )

        payload = objective_set_payload_from(objective)

        assert {"field": "origin", "value": "SIN"} in payload["hard_constraints"]
        assert {"field": "budget", "value": "USD 120.00"} in payload["hard_constraints"]
        assert {"field": "destination", "value": "NRT"} in payload["preferences"]
        assert {"field": "preference", "value": "window seat"} in payload["preferences"]

    def test_omits_absent_fields(self) -> None:
        from journey.models.events import objective_set_payload_from
        from journey.models.objective import ConstrainedField, ConstraintType, TravelObjective

        objective = TravelObjective(
            origin=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
        )

        payload = objective_set_payload_from(objective)

        assert payload == {
            "hard_constraints": [{"field": "origin", "value": "SIN"}],
            "preferences": [],
        }
