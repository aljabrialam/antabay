from __future__ import annotations

import uuid
from datetime import datetime, timezone

from journey.models.journey import AuditEntry, JourneyDisplay, JourneyRecord, JourneyState
from journey.models.objective import TravelObjective
from journey.storage.repository import JourneyRepository


class JourneyService:
    def __init__(self, repository: JourneyRepository | None = None) -> None:
        self._repo = repository if repository is not None else JourneyRepository()

    def create_journey(self, confirmed_objective: TravelObjective) -> JourneyRecord:
        now = datetime.now(tz=timezone.utc)
        journey_id = str(uuid.uuid4())
        entry = AuditEntry(
            entry_id=str(uuid.uuid4()),
            journey_id=journey_id,
            entry_type="DECISION",
            content="Journey created with confirmed objective",
            recorded_at=now,
            sequence=1,
        )
        record = JourneyRecord(
            journey_id=journey_id,
            state=JourneyState.OBJECTIVE_CONFIRMED,
            objective=confirmed_objective,
            schema_version=1,
            created_at=now,
            updated_at=now,
            audit_entries=[entry],
        )
        self._repo.insert_journey(record)
        return record

    def get_journey(self, journey_id: str) -> JourneyRecord:
        return self._repo.get_journey(journey_id)

    def get_display(self, journey_id: str) -> JourneyDisplay:
        record = self._repo.get_journey(journey_id)
        return JourneyDisplay(
            journey_id=record.journey_id,
            state=record.state,
            objective=record.objective,
            audit_trail=record.audit_entries,
        )

