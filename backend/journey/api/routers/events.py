from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from typing import Literal

from journey.models.events import JourneyEvent
from journey.services.event_service import (
    AuthorisationAlreadyResolvedError,
    AuthorisationRequestNotFoundError,
    EventService,
)

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


@router.get("/{journey_id}/events/replay", response_class=EventSourceResponse)
async def replay_events(
    journey_id: str = Depends(_verify_journey_exists),
    speed: float = Query(default=1.0, gt=0),
) -> AsyncGenerator[ServerSentEvent, None]:
    """Replay a recorded event stream at a controllable pace (FR-012)."""
    service = EventService()
    yield ServerSentEvent(
        id="0",
        event="replay_started",
        data={
            "event_id": f"{journey_id}-replay-started",
            "payload": {"source_journey_id": journey_id, "speed_multiplier": speed},
            "simulated": False,
            "recorded_at": EventService.now_iso(),
        },
    )
    last_sequence = 0
    async for event in service.replay_events(journey_id, speed):
        last_sequence = event.sequence
        yield ServerSentEvent(
            id=str(event.sequence),
            event=event.event_type.value,
            data=_sse_envelope(event),
        )
    yield ServerSentEvent(
        id=str(last_sequence + 1),
        event="replay_ended",
        data={
            "event_id": f"{journey_id}-replay-ended",
            "payload": {},
            "simulated": False,
            "recorded_at": EventService.now_iso(),
        },
    )


class AuthorisationOutcomeRequest(BaseModel):
    outcome: Literal["approved", "refused"]


@router.post("/{journey_id}/authorisation/{request_id}")
async def respond_authorisation(
    journey_id: str,
    request_id: str,
    body: AuthorisationOutcomeRequest,
    journey: str = Depends(_verify_journey_exists),
) -> dict[str, str]:
    """Record an observer's approve/refuse decision (FR-009)."""
    service = EventService()
    try:
        service.record_auth_outcome(journey_id, request_id, body.outcome)
    except AuthorisationRequestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthorisationAlreadyResolvedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "recorded"}
