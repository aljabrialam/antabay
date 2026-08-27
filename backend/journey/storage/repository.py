from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from journey.models.flight import FlightOption, Leg, SearchOutcome, SearchRecord
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
    flight_options,
    held_identifiers,
    journeys,
    legs,
    search_records,
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
                    call_budget=record.call_budget,
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
                call_budget=row["call_budget"] if row["call_budget"] is not None else 20,
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

    # ------------------------------------------------------------------
    # Flight search methods
    # ------------------------------------------------------------------

    def decrement_call_budget(self, journey_id: str) -> tuple[int, int]:
        """Atomically decrement call_budget; return (budget_before, budget_after).

        Raises BudgetExhaustedError if budget is already 0.
        """
        from journey.errors import BudgetExhaustedError

        with get_connection() as conn:
            row = conn.execute(
                select(journeys.c.call_budget).where(journeys.c.journey_id == journey_id)
            ).scalar()
            if row is None:
                raise ValueError(f"Journey not found: {journey_id}")
            budget_before: int = row
            if budget_before <= 0:
                raise BudgetExhaustedError(f"call_budget exhausted for journey {journey_id}")
            budget_after = budget_before - 1
            conn.execute(
                update(journeys)
                .where(journeys.c.journey_id == journey_id)
                .values(call_budget=budget_after)
            )
            conn.commit()
        return budget_before, budget_after

    def save_search_record(self, record: SearchRecord) -> None:
        with get_connection() as conn:
            conn.execute(
                insert(search_records).values(
                    search_id=record.search_id,
                    journey_id=record.journey_id,
                    requested_at=record.requested_at.isoformat(),
                    responded_at=record.responded_at.isoformat(),
                    raw_response_json=record.raw_response_json,
                    status_code=record.status_code,
                    atlas_status=record.atlas_status,
                    option_count=record.option_count,
                    budget_before=record.budget_before,
                    budget_after=record.budget_after,
                    outcome=record.outcome.value,
                )
            )
            conn.commit()

    def get_search_record(self, search_id: str) -> SearchRecord | None:
        with get_connection() as conn:
            row = conn.execute(
                select(search_records).where(search_records.c.search_id == search_id)
            ).mappings().first()
        if row is None:
            return None
        return SearchRecord(
            search_id=row["search_id"],
            journey_id=row["journey_id"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            responded_at=datetime.fromisoformat(row["responded_at"]),
            raw_response_json=row["raw_response_json"],
            status_code=row["status_code"],
            atlas_status=row["atlas_status"],
            option_count=row["option_count"],
            budget_before=row["budget_before"],
            budget_after=row["budget_after"],
            outcome=SearchOutcome(row["outcome"]),
        )

    def save_flight_options(self, options: list[FlightOption]) -> None:
        """Persist FlightOption and their Legs rows in a single transaction (Tx2)."""
        with get_connection() as conn:
            for opt in options:
                conn.execute(
                    insert(flight_options).values(
                        option_id=opt.option_id,
                        journey_id=opt.journey_id,
                        search_record_id=opt.search_record_id,
                        fid=opt.fid,
                        routing_identifier=opt.routing_identifier,
                        currency=opt.currency,
                        adult_price=str(opt.adult_price),
                        adult_tax=str(opt.adult_tax),
                        transaction_fee=str(opt.transaction_fee),
                        refreshed_at=opt.refreshed_at.isoformat() if opt.refreshed_at else None,
                        expire_at=opt.expire_at.isoformat() if opt.expire_at else None,
                        is_multi_leg=1 if opt.is_multi_leg else 0,
                        separate_bookings=1 if opt.separate_bookings else 0,
                        recorded_at=opt.recorded_at.isoformat(),
                    )
                )
                for leg in opt.legs:
                    conn.execute(
                        insert(legs).values(
                            leg_id=leg.leg_id,
                            option_id=leg.option_id,
                            segment_index=leg.segment_index,
                            carrier=leg.carrier,
                            flight_number=leg.flight_number,
                            dep_airport=leg.dep_airport,
                            dep_time=leg.dep_time,
                            arr_airport=leg.arr_airport,
                            arr_time=leg.arr_time,
                            duration_minutes=leg.duration_minutes,
                            stop_cities=leg.stop_cities,
                            cabin_class=leg.cabin_class,
                            seat_count=leg.seat_count,
                            risk_sellout=1 if leg.risk_sellout else 0,
                            code_share=1 if leg.code_share else 0,
                            aircraft_code=leg.aircraft_code,
                            fare_family=leg.fare_family,
                        )
                    )
            conn.commit()

    def get_options(self, search_id: str) -> list[FlightOption]:
        """Return FlightOption list for search_id; raises SearchRecordNotFoundError if unknown."""
        from journey.errors import SearchRecordNotFoundError

        with get_connection() as conn:
            exists = conn.execute(
                select(search_records.c.search_id).where(search_records.c.search_id == search_id)
            ).scalar()
            if exists is None:
                raise SearchRecordNotFoundError(search_id)

            opt_rows = conn.execute(
                select(flight_options).where(flight_options.c.search_record_id == search_id)
            ).mappings().all()

            result = []
            for row in opt_rows:
                leg_rows = conn.execute(
                    select(legs)
                    .where(legs.c.option_id == row["option_id"])
                    .order_by(legs.c.segment_index)
                ).mappings().all()

                leg_list = [
                    Leg(
                        leg_id=lr["leg_id"],
                        option_id=lr["option_id"],
                        segment_index=lr["segment_index"],
                        carrier=lr["carrier"],
                        flight_number=lr["flight_number"],
                        dep_airport=lr["dep_airport"],
                        dep_time=lr["dep_time"],
                        arr_airport=lr["arr_airport"],
                        arr_time=lr["arr_time"],
                        duration_minutes=lr["duration_minutes"],
                        stop_cities=lr["stop_cities"],
                        cabin_class=lr["cabin_class"],
                        seat_count=lr["seat_count"],
                        risk_sellout=bool(lr["risk_sellout"]),
                        code_share=bool(lr["code_share"]),
                        aircraft_code=lr["aircraft_code"],
                        fare_family=lr["fare_family"],
                    )
                    for lr in leg_rows
                ]

                result.append(
                    FlightOption(
                        option_id=row["option_id"],
                        journey_id=row["journey_id"],
                        search_record_id=row["search_record_id"],
                        fid=row["fid"],
                        routing_identifier=row["routing_identifier"],
                        currency=row["currency"],
                        adult_price=Decimal(row["adult_price"]),
                        adult_tax=Decimal(row["adult_tax"]),
                        transaction_fee=Decimal(row["transaction_fee"]),
                        refreshed_at=datetime.fromisoformat(row["refreshed_at"]) if row["refreshed_at"] else None,
                        expire_at=datetime.fromisoformat(row["expire_at"]) if row["expire_at"] else None,
                        is_multi_leg=bool(row["is_multi_leg"]),
                        separate_bookings=bool(row["separate_bookings"]),
                        legs=leg_list,
                        recorded_at=datetime.fromisoformat(row["recorded_at"]),
                    )
                )
        return result
