"""Shared construction of ImpactEvaluationService for WebhookService's
on_wake hook (research.md R1). Both `journey/api/main.py`'s reconciliation
loop and `journey/api/routers/webhooks.py`'s request-scoped WebhookService
use this factory so they wire the same evaluation logic without either one
importing the other.
"""
from __future__ import annotations

import httpx

from journey.services.event_service import EventService
from journey.services.flight_search import FlightSearchService
from journey.services.impact_evaluation_service import ImpactEvaluationService
from journey.services.scoring_service import ScoringService
from journey.services.verification_service import VerificationService
from journey.storage.repository import JourneyRepository


def build_impact_evaluation_service() -> ImpactEvaluationService:
    repo = JourneyRepository()
    http_client = httpx.Client()
    return ImpactEvaluationService(
        repo=repo,
        http_client=http_client,
        event_service=EventService(repo),
        flight_search=FlightSearchService(repo=repo, http_client=http_client),
        scoring_service=ScoringService(),
        verification_service=VerificationService(repo=repo, http_client=http_client),
    )
