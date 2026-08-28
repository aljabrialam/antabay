from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from anyio import to_thread

from journey.models.events import EventType, JourneyEvent, payload_model_for
from journey.models.journey import JourneyState
from journey.storage.repository import JourneyRepository

POLL_INTERVAL_SECONDS = 0.5

_TERMINAL_STATES = {JourneyState.CANCELLED, JourneyState.ABANDONED}


class AuthorisationRequestNotFoundError(Exception):
    """No `authorisation_requested` event exists for this request_id."""


class AuthorisationAlreadyResolvedError(Exception):
    """An `authorisation_outcome` event already exists for this request_id."""


class EventService:
    def __init__(self, repository: JourneyRepository | None = None) -> None:
        self._repo = repository if repository is not None else JourneyRepository()

    def append(
        self,
        journey_id: str,
        event_type: EventType,
        payload: dict[str, object],
        simulated: bool = False,
        recorded_at: datetime | None = None,
    ) -> JourneyEvent:
        """Validate payload against its Pydantic schema, then persist."""
        model = payload_model_for(event_type)
        model.model_validate(payload)
        return self._repo.append_event(
            journey_id, event_type, payload, simulated, recorded_at
        )

    async def stream_events(
        self, journey_id: str, last_sequence: int = 0
    ) -> AsyncGenerator[JourneyEvent, None]:
        """Yield events with sequence > last_sequence, then poll for new rows.

        Terminates when the journey reaches a terminal state.
        """
        cursor = last_sequence
        while True:
            events = await to_thread.run_sync(
                self._repo.get_events_from_sequence, journey_id, cursor
            )
            for event in events:
                yield event
                cursor = event.sequence
            if events and self._is_terminal(events[-1]):
                return
            if not events and await self._journey_terminal(journey_id):
                return
            import asyncio

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def replay_events(
        self, journey_id: str, speed: float = 1.0
    ) -> AsyncGenerator[JourneyEvent, None]:
        """Replay the full recorded sequence with inter-event delays scaled by 1/speed.

        Makes no calls to any external service (FR-012). The replay_started and
        replay_ended events are synthesised in the router, not persisted here.
        """
        if speed <= 0:
            raise ValueError("speed must be > 0")
        import asyncio

        events = await to_thread.run_sync(
            self._repo.get_events_from_sequence, journey_id, 0
        )
        previous: JourneyEvent | None = None
        for event in events:
            if previous is not None:
                delay = (event.recorded_at - previous.recorded_at).total_seconds()
                scaled = max(delay / speed, 0.0)
                if scaled > 0:
                    await asyncio.sleep(scaled)
            yield event
            previous = event

    def record_auth_outcome(
        self, journey_id: str, request_id: str, outcome: str
    ) -> JourneyEvent:
        """Resolve an outstanding authorisation request (FR-009).

        Looks up the matching `authorisation_requested` event to recover its
        `rule_id`, refuses to resolve twice, then appends the outcome event.
        """
        events = self._repo.get_events_from_sequence(journey_id, 0)
        requested = next(
            (
                e
                for e in events
                if e.event_type is EventType.AUTHORISATION_REQUESTED
                and e.payload.get("request_id") == request_id
            ),
            None,
        )
        if requested is None:
            raise AuthorisationRequestNotFoundError(
                f"No authorisation request {request_id} for journey {journey_id}"
            )
        already_resolved = any(
            e.event_type is EventType.AUTHORISATION_OUTCOME
            and e.payload.get("request_id") == request_id
            for e in events
        )
        if already_resolved:
            raise AuthorisationAlreadyResolvedError(
                f"Authorisation request {request_id} is already resolved"
            )
        return self.append(
            journey_id,
            EventType.AUTHORISATION_OUTCOME,
            {
                "request_id": request_id,
                "outcome": outcome,
                "rule_id": requested.payload["rule_id"],
            },
        )

    def journey_exists(self, journey_id: str) -> bool:
        return self._repo.journey_exists(journey_id)

    def _is_terminal(self, event: JourneyEvent) -> bool:
        if event.event_type is not EventType.STATE_CHANGE:
            return False
        to_state = event.payload.get("to_state")
        return isinstance(to_state, str) and to_state in {
            s.value for s in _TERMINAL_STATES
        }

    async def _journey_terminal(self, journey_id: str) -> bool:
        def _check() -> bool:
            import sqlalchemy as sa

            from journey.storage.db import get_connection
            from journey.storage.tables import journeys

            with get_connection() as conn:
                row = conn.execute(
                    sa.select(journeys.c.state).where(
                        journeys.c.journey_id == journey_id
                    )
                ).scalar()
            return row in {s.value for s in _TERMINAL_STATES}

        return await to_thread.run_sync(_check)

    @staticmethod
    def payload_json(event: JourneyEvent) -> str:
        """Serialise a payload dict to JSON for the SSE data field."""
        return json.dumps(event.payload)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()
