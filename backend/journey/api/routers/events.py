from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from journey.models.events import JourneyEvent
from journey.services.event_service import EventService

router = APIRouter(prefix="/journeys", tags=["journey-events"])


def _sse_envelope(event: JourneyEvent) -> dict[str, object]:
    """Wrap a JourneyEvent so the wire carries simulated/recorded_at (FR-010, FR-013)."""
    return {
        "event_id": event.event_id,
        "payload": event.payload,
        "simulated": event.simulated,
        "recorded_at": event.recorded_at.isoformat(),
    }


def _verify_journey_exists(journey_id: str) -> str:
    """404 before the SSE stream opens when the journey is unknown (contract)."""
    service = EventService()
    if not service.journey_exists(journey_id):
        raise HTTPException(status_code=404, detail="Journey not found")
    return journey_id


@router.get("/{journey_id}/events", response_class=EventSourceResponse)
async def stream_events(
    journey_id: str = Depends(_verify_journey_exists),
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID"),
) -> AsyncGenerator[ServerSentEvent, None]:
    """Live SSE stream of journey events. Resumes after Last-Event-ID on reconnect."""
    service = EventService()
    from_sequence = last_event_id if last_event_id is not None else 0
    async for event in service.stream_events(journey_id, from_sequence):
        yield ServerSentEvent(
            id=str(event.sequence),
            event=event.event_type.value,
            data=_sse_envelope(event),
        )


@router.get("/{journey_id}/events/replay")
async def replay_events(journey_id: str, speed: float = 1.0) -> dict[str, str]:
    """Replay a recorded event stream at a controllable pace (FR-012). Stub until US3."""
    raise HTTPException(status_code=501, detail="Replay not yet implemented")


@router.post("/{journey_id}/authorisation/{request_id}")
async def respond_authorisation(journey_id: str, request_id: str) -> dict[str, str]:
    """Record an observer's approve/refuse decision. Stub until US2."""
    raise HTTPException(status_code=501, detail="Authorisation response not yet implemented")
