from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from journey.models.journey import (
    AuditEntry,
    AuthorisationOutcome,
    HeldIdentifier,
    JourneyRecord,
    JourneyState,
)
from journey.models.objective import (
    ConstrainedField,
    ConstraintType,
    TravelObjective,
)
from journey.storage.db import get_connection
from journey.storage.tables import (
    audit_entries,
    authorisation_outcomes,
    held_identifiers,
    journeys,
)


class JourneyRepository:
    def insert_journey(self, record: JourneyRecord) -> None:
        with get_connection() as conn:
            conn.execute(
                insert(journeys).values(
                    journey_id=record.journey_id,
                    state=record.state.value,
                    objective_json=record.objective.model_dump_json(),
                    schema_version=record.schema_version,
                    created_at=record.created_at.isoformat(),
                    updated_at=record.updated_at.isoformat(),
                )
            )
            for entry in record.audit_entries:
                conn.execute(
                    insert(audit_entries).values(
                        entry_id=entry.entry_id,
                        journey_id=entry.journey_id,
                        entry_type=entry.entry_type,
                        content=entry.content,
                        recorded_at=entry.recorded_at.isoformat(),
                        sequence=entry.sequence,
                    )
                )
            conn.commit()

    def get_journey(self, journey_id: str) -> JourneyRecord:
        with get_connection() as conn:
            row = conn.execute(
                select(journeys).where(journeys.c.journey_id == journey_id)
            ).mappings().one()

            entries = [
                AuditEntry(
                    entry_id=r["entry_id"],
                    journey_id=r["journey_id"],
                    entry_type=r["entry_type"],
                    content=r["content"],
                    recorded_at=datetime.fromisoformat(r["recorded_at"]),
                    sequence=r["sequence"],
                )
                for r in conn.execute(
                    select(audit_entries)
                    .where(audit_entries.c.journey_id == journey_id)
                    .order_by(audit_entries.c.sequence)
                ).mappings()
            ]

            held = [
                HeldIdentifier(
                    identifier_id=r["identifier_id"],
                    journey_id=r["journey_id"],
                    value=r["value"],
                    issued_at=datetime.fromisoformat(r["issued_at"]),
                    stale_after_seconds=r["stale_after_seconds"],
                    stale_at=datetime.fromisoformat(r["stale_at"]),
                )
                for r in conn.execute(
                    select(held_identifiers).where(
                        held_identifiers.c.journey_id == journey_id
                    )
                ).mappings()
            ]

            outcomes = [
                AuthorisationOutcome(
                    outcome_id=r["outcome_id"],
                    journey_id=r["journey_id"],
                    request_desc=r["request_desc"],
                    outcome=r["outcome"],
                    recorded_by=r["recorded_by"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                )
                for r in conn.execute(
                    select(authorisation_outcomes).where(
                        authorisation_outcomes.c.journey_id == journey_id
                    )
                ).mappings()
            ]

            objective = TravelObjective.model_validate_json(row["objective_json"])
            return JourneyRecord(
                journey_id=row["journey_id"],
                state=JourneyState(row["state"]),
                objective=objective,
                schema_version=row["schema_version"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                audit_entries=entries,
                held_identifiers=held,
                authorisation_outcomes=outcomes,
            )

    def append_audit_entry(
        self,
        journey_id: str,
        entry_type: str,
        content: str,
        recorded_at: datetime | None = None,
    ) -> AuditEntry:
        ts = recorded_at if recorded_at is not None else datetime.now(tz=timezone.utc)
        with get_connection() as conn:
            row = conn.execute(
                select(func.max(audit_entries.c.sequence)).where(
                    audit_entries.c.journey_id == journey_id
                )
            ).scalar()
            next_seq = (row or 0) + 1
            entry_id = str(uuid.uuid4())
            conn.execute(
                insert(audit_entries).values(
                    entry_id=entry_id,
                    journey_id=journey_id,
                    entry_type=entry_type,
                    content=content,
                    recorded_at=ts.isoformat(),
                    sequence=next_seq,
                )
            )
            conn.commit()
        return AuditEntry(
            entry_id=entry_id,
            journey_id=journey_id,
            entry_type=entry_type,
            content=content,
            recorded_at=ts,
            sequence=next_seq,
        )

    def get_audit_trail(self, journey_id: str) -> list[AuditEntry]:
        with get_connection() as conn:
            return [
                AuditEntry(
                    entry_id=r["entry_id"],
                    journey_id=r["journey_id"],
                    entry_type=r["entry_type"],
                    content=r["content"],
                    recorded_at=datetime.fromisoformat(r["recorded_at"]),
                    sequence=r["sequence"],
                )
                for r in conn.execute(
                    select(audit_entries)
                    .where(audit_entries.c.journey_id == journey_id)
                    .order_by(audit_entries.c.sequence)
                ).mappings()
            ]

    def update_journey_state(
        self,
        journey_id: str,
        new_state: JourneyState,
        updated_at: datetime | None = None,
    ) -> None:
        ts = updated_at if updated_at is not None else datetime.now(tz=timezone.utc)
        with get_connection() as conn:
            conn.execute(
                update(journeys)
                .where(journeys.c.journey_id == journey_id)
                .values(state=new_state.value, updated_at=ts.isoformat())
            )
            conn.commit()

    def add_held_identifier(
        self,
        journey_id: str,
        value: str,
        issued_at: datetime,
        stale_after_seconds: int,
    ) -> HeldIdentifier:
        stale_at = datetime.fromtimestamp(
            issued_at.timestamp() + stale_after_seconds,
            tz=issued_at.tzinfo,
        )
        identifier_id = str(uuid.uuid4())
        with get_connection() as conn:
            conn.execute(
                insert(held_identifiers).values(
                    identifier_id=identifier_id,
                    journey_id=journey_id,
                    value=value,
                    issued_at=issued_at.isoformat(),
                    stale_after_seconds=stale_after_seconds,
                    stale_at=stale_at.isoformat(),
                )
            )
            conn.commit()
        return HeldIdentifier(
            identifier_id=identifier_id,
            journey_id=journey_id,
            value=value,
            issued_at=issued_at,
            stale_after_seconds=stale_after_seconds,
            stale_at=stale_at,
        )
