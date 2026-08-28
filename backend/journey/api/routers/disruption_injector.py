from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from journey.errors import InjectorDisabledError, JourneyHasNoOrderError, JourneyNotFoundError
from journey.services.disruption_injector_service import DisruptionInjectorService

router = APIRouter(prefix="/operator", tags=["disruption-injector"])

_TOKEN_ENV_VAR = "DISRUPTION_INJECTOR_TOKEN"


def get_disruption_injector_service() -> DisruptionInjectorService:
    return DisruptionInjectorService()


class DisruptionRequest(BaseModel):
    journey_id: str
    revised_arrival_time: datetime


def _verify_operator_token(x_operator_token: str | None = Header(default=None)) -> None:
    """Fail closed: an unset or empty configured token means every request
    is treated as unauthorised, never as open (research.md R5, NFR-002)."""
    expected = os.environ.get(_TOKEN_ENV_VAR, "")
    if not expected or x_operator_token != expected:
        raise HTTPException(status_code=401, detail="Not authorised")


@router.post("/disruptions")
async def inject_disruption(
    body: DisruptionRequest,
    _: None = Depends(_verify_operator_token),
    service: DisruptionInjectorService = Depends(get_disruption_injector_service),
) -> dict[str, str]:
    try:
        service.inject(body.journey_id, body.revised_arrival_time, datetime.now(tz=timezone.utc))
    except InjectorDisabledError as exc:
        raise HTTPException(status_code=401, detail="Not authorised") from exc
    except JourneyNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except JourneyHasNoOrderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "injected"}
