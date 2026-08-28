from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from journey.models.flight import FlightOption, Leg, SearchOutcome, SearchRecord
from journey.models.events import EventType, JourneyEvent
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
from journey.models.scoring import (
    ConnectionEvaluation,
    EliminationRecord,
    NoSatisfyingOptionReport,
    Rationale,
    RejectionReason,
    ScoredOption,
    ScoringOutcome,
    ScoringRun,
)
from journey.storage.db import get_connection
from journey.storage.tables import (
    audit_entries,
    authorisation_outcomes,
    flight_options,
    held_identifiers,
    journey_events,
    journeys,
    legs,
    orders,
    payments,
    scoring_runs,
    search_records,
    ticketing_queries,
    verifications,
)

if TYPE_CHECKING:
    from journey.models.booking import Order, PaymentAttempt, TicketingQuery
    from journey.models.verification import VerificationResult


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

    def get_flight_option(self, option_id: str) -> FlightOption | None:
        """Return a single FlightOption (with legs) by option_id, or None if unknown."""
        with get_connection() as conn:
            row = conn.execute(
                select(flight_options).where(flight_options.c.option_id == option_id)
            ).mappings().first()
            if row is None:
                return None

            leg_rows = conn.execute(
                select(legs)
                .where(legs.c.option_id == option_id)
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

        return FlightOption(
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

    # ------------------------------------------------------------------
    # Verification persistence methods (004-price-verification)
    # ------------------------------------------------------------------

    def save_verification(self, result: VerificationResult) -> None:
        from journey.models.verification import PriceChange, PassengerRequirementField

        price_change_json = None
        if result.price_change is not None:
            pc = result.price_change
            price_change_json = json.dumps(
                {
                    "is_price_change": pc.is_price_change,
                    "original_adult_price": str(pc.original_adult_price),
                    "new_adult_price": str(pc.new_adult_price),
                    "original_adult_tax": str(pc.original_adult_tax),
                    "new_adult_tax": str(pc.new_adult_tax),
                    "original_child_price": str(pc.original_child_price) if pc.original_child_price is not None else None,
                    "new_child_price": str(pc.new_child_price) if pc.new_child_price is not None else None,
                    "original_infant_price": str(pc.original_infant_price) if pc.original_infant_price is not None else None,
                    "new_infant_price": str(pc.new_infant_price) if pc.new_infant_price is not None else None,
                }
            )
        passenger_requirements_json = json.dumps(
            [
                {
                    "field_name": f.field_name,
                    "type": f.type,
                    "required": f.required,
                    "description": f.description,
                    "max_length": f.max_length,
                }
                for f in result.passenger_requirements
            ]
        )
        with get_connection() as conn:
            conn.execute(
                insert(verifications).values(
                    verification_id=result.verification_id,
                    journey_id=result.journey_id,
                    option_id=result.option_id,
                    requested_at=result.requested_at.isoformat(),
                    responded_at=result.responded_at.isoformat(),
                    raw_response_json=result.raw_response_json,
                    status_code=result.status_code,
                    atlas_status=result.atlas_status,
                    outcome=result.outcome.value,
                    session_id=result.session_id,
                    max_seats=result.max_seats,
                    price_change_json=price_change_json,
                    passenger_requirements_json=passenger_requirements_json,
                    budget_before=result.budget_before,
                    budget_after=result.budget_after,
                )
            )
            conn.commit()

    def get_latest_verification(self, journey_id: str, option_id: str) -> VerificationResult | None:
        from journey.models.verification import (
            PassengerRequirementField,
            PriceChange,
            VerificationOutcome,
            VerificationResult,
        )

        with get_connection() as conn:
            row = (
                conn.execute(
                    select(verifications)
                    .where(
                        verifications.c.journey_id == journey_id,
                        verifications.c.option_id == option_id,
                    )
                    .order_by(verifications.c.responded_at.desc())
                )
                .mappings()
                .first()
            )
        if row is None:
            return None

        price_change = None
        if row["price_change_json"] is not None:
            pc = json.loads(row["price_change_json"])
            price_change = PriceChange(
                is_price_change=pc["is_price_change"],
                original_adult_price=Decimal(pc["original_adult_price"]),
                new_adult_price=Decimal(pc["new_adult_price"]),
                original_adult_tax=Decimal(pc["original_adult_tax"]),
                new_adult_tax=Decimal(pc["new_adult_tax"]),
                original_child_price=Decimal(pc["original_child_price"]) if pc["original_child_price"] is not None else None,
                new_child_price=Decimal(pc["new_child_price"]) if pc["new_child_price"] is not None else None,
                original_infant_price=Decimal(pc["original_infant_price"]) if pc["original_infant_price"] is not None else None,
                new_infant_price=Decimal(pc["new_infant_price"]) if pc["new_infant_price"] is not None else None,
            )
        passenger_requirements = [
            PassengerRequirementField(
                field_name=f["field_name"],
                type=f["type"],
                required=f["required"],
                description=f["description"],
                max_length=f["max_length"],
            )
            for f in json.loads(row["passenger_requirements_json"])
        ]

        return VerificationResult(
            verification_id=row["verification_id"],
            journey_id=row["journey_id"],
            option_id=row["option_id"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            responded_at=datetime.fromisoformat(row["responded_at"]),
            raw_response_json=row["raw_response_json"],
            status_code=row["status_code"],
            atlas_status=row["atlas_status"],
            outcome=VerificationOutcome(row["outcome"]),
            session_id=row["session_id"],
            max_seats=row["max_seats"],
            price_change=price_change,
            passenger_requirements=passenger_requirements,
            budget_before=row["budget_before"],
            budget_after=row["budget_after"],
        )

    def save_order(self, order: "Order") -> None:
        with get_connection() as conn:
            conn.execute(
                insert(orders).values(
                    order_id=order.order_id,
                    journey_id=order.journey_id,
                    option_id=order.option_id,
                    requested_at=order.requested_at.isoformat(),
                    responded_at=order.responded_at.isoformat() if order.responded_at else None,
                    raw_response_json=order.raw_response_json,
                    outcome=order.outcome.value,
                    order_no=order.order_no,
                    booking_reference=order.booking_reference,
                    ticketing_deadline=order.ticketing_deadline.isoformat() if order.ticketing_deadline else None,
                    session_id_used=order.session_id_used,
                )
            )
            conn.commit()

    def _row_to_order(self, row: Any) -> "Order":
        from journey.models.booking import Order, OrderOutcome

        return Order(
            order_id=row["order_id"],
            journey_id=row["journey_id"],
            option_id=row["option_id"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            responded_at=datetime.fromisoformat(row["responded_at"]) if row["responded_at"] else None,
            raw_response_json=row["raw_response_json"],
            outcome=OrderOutcome(row["outcome"]),
            order_no=row["order_no"],
            booking_reference=row["booking_reference"],
            ticketing_deadline=datetime.fromisoformat(row["ticketing_deadline"]) if row["ticketing_deadline"] else None,
            session_id_used=row["session_id_used"],
        )

    def get_order_by_order_no(self, order_no: str) -> "Order | None":
        with get_connection() as conn:
            row = (
                conn.execute(select(orders).where(orders.c.order_no == order_no))
                .mappings()
                .first()
            )
        return self._row_to_order(row) if row is not None else None

    def get_latest_order(self, journey_id: str, option_id: str) -> "Order | None":
        with get_connection() as conn:
            row = (
                conn.execute(
                    select(orders)
                    .where(orders.c.journey_id == journey_id, orders.c.option_id == option_id)
                    .order_by(orders.c.requested_at.desc())
                )
                .mappings()
                .first()
            )
        return self._row_to_order(row) if row is not None else None

    def save_payment(self, payment: "PaymentAttempt") -> None:
        with get_connection() as conn:
            conn.execute(
                insert(payments).values(
                    payment_id=payment.payment_id,
                    journey_id=payment.journey_id,
                    order_no=payment.order_no,
                    requested_at=payment.requested_at.isoformat(),
                    responded_at=payment.responded_at.isoformat() if payment.responded_at else None,
                    raw_response_json=payment.raw_response_json,
                    outcome=payment.outcome.value,
                )
            )
            conn.commit()

    def get_declined_payment(self, order_no: str) -> "PaymentAttempt | None":
        from journey.models.booking import PaymentAttempt, PaymentOutcome

        with get_connection() as conn:
            row = (
                conn.execute(
                    select(payments).where(
                        payments.c.order_no == order_no,
                        payments.c.outcome == PaymentOutcome.DECLINED.value,
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return PaymentAttempt(
            payment_id=row["payment_id"],
            journey_id=row["journey_id"],
            order_no=row["order_no"],
            requested_at=datetime.fromisoformat(row["requested_at"]),
            responded_at=datetime.fromisoformat(row["responded_at"]) if row["responded_at"] else None,
            raw_response_json=row["raw_response_json"],
            outcome=PaymentOutcome(row["outcome"]),
        )

    def save_ticketing_query(self, query: "TicketingQuery") -> None:
        with get_connection() as conn:
            conn.execute(
                insert(ticketing_queries).values(
                    query_id=query.query_id,
                    journey_id=query.journey_id,
                    order_no=query.order_no,
                    queried_at=query.queried_at.isoformat(),
                    raw_response_json=query.raw_response_json,
                    order_status=query.order_status,
                    ticket_status=query.ticket_status,
                    passenger_ticket_numbers_json=json.dumps(query.passenger_ticket_numbers),
                    confirmed=1 if query.confirmed else 0,
                    is_terminal_error=1 if query.is_terminal_error else 0,
                )
            )
            conn.commit()

    def get_ticketing_queries(self, order_no: str) -> list["TicketingQuery"]:
        from journey.models.booking import TicketingQuery

        with get_connection() as conn:
            rows = (
                conn.execute(
                    select(ticketing_queries)
                    .where(ticketing_queries.c.order_no == order_no)
                    .order_by(ticketing_queries.c.queried_at)
                )
                .mappings()
                .all()
            )
        return [
            TicketingQuery(
                query_id=r["query_id"],
                journey_id=r["journey_id"],
                order_no=r["order_no"],
                queried_at=datetime.fromisoformat(r["queried_at"]),
                raw_response_json=r["raw_response_json"],
                order_status=r["order_status"],
                ticket_status=r["ticket_status"],
                passenger_ticket_numbers=json.loads(r["passenger_ticket_numbers_json"]),
                confirmed=bool(r["confirmed"]),
                is_terminal_error=bool(r["is_terminal_error"]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Scoring persistence methods (003-option-scoring)
    # ------------------------------------------------------------------

    def save_scoring_run(self, run: ScoringRun, journey_id: str) -> None:
        eliminated_count = sum(
            1 for so in run.scored_options
            if so.outcome == ScoringOutcome.ELIMINATED
        )
        result_json = _scoring_run_to_json(run)
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        with get_connection() as conn:
            conn.execute(
                insert(scoring_runs).values(
                    run_id=run.run_id,
                    journey_id=journey_id,
                    evaluated_at=run.evaluated_at.isoformat(),
                    objective_json=run.objective.model_dump_json(),
                    result_json=result_json,
                    selected_option_id=(
                        run.selected_option.option.option_id
                        if run.selected_option else None
                    ),
                    option_count=len(run.scored_options),
                    eliminated_count=eliminated_count,
                    created_at=now_iso,
                )
            )
            conn.commit()

    def get_scoring_run(self, run_id: str) -> ScoringRun:
        from journey.errors import ScoringRunNotFoundError

        with get_connection() as conn:
            row = conn.execute(
                select(scoring_runs).where(scoring_runs.c.run_id == run_id)
            ).mappings().first()
        if row is None:
            raise ScoringRunNotFoundError(run_id)
        return _scoring_run_from_json(row["result_json"])

    # ------------------------------------------------------------------
    # Journey event stream methods (006-agent-trace-console)
    # ------------------------------------------------------------------

    def append_event(
        self,
        journey_id: str,
        event_type: EventType,
        payload: dict[str, object],
        simulated: bool = False,
        recorded_at: datetime | None = None,
    ) -> JourneyEvent:
        """Append an event; sequence = MAX(sequence)+1 within the transaction."""
        ts = recorded_at if recorded_at is not None else datetime.now(tz=timezone.utc)
        event_id = str(uuid.uuid4())
        with get_connection() as conn:
            exists = conn.execute(
                select(journeys.c.journey_id).where(journeys.c.journey_id == journey_id)
            ).scalar()
            if exists is None:
                raise ValueError(f"Journey not found: {journey_id}")
            last = conn.execute(
                select(func.max(journey_events.c.sequence)).where(
                    journey_events.c.journey_id == journey_id
                )
            ).scalar()
            next_seq = (last or 0) + 1
            conn.execute(
                insert(journey_events).values(
                    event_id=event_id,
                    journey_id=journey_id,
                    sequence=next_seq,
                    event_type=event_type.value,
                    payload_json=json.dumps(payload),
                    simulated=1 if simulated else 0,
                    recorded_at=ts.isoformat(),
                )
            )
            conn.commit()
        return JourneyEvent(
            event_id=event_id,
            journey_id=journey_id,
            sequence=next_seq,
            event_type=event_type,
            payload=payload,
            simulated=simulated,
            recorded_at=ts,
        )

    def get_events_from_sequence(
        self, journey_id: str, from_sequence: int = 0
    ) -> list[JourneyEvent]:
        """Return events with sequence > from_sequence, ordered ASC."""
        with get_connection() as conn:
            rows = conn.execute(
                select(journey_events)
                .where(
                    journey_events.c.journey_id == journey_id,
                    journey_events.c.sequence > from_sequence,
                )
                .order_by(journey_events.c.sequence)
            ).mappings().all()
        return [
            JourneyEvent(
                event_id=r["event_id"],
                journey_id=r["journey_id"],
                sequence=r["sequence"],
                event_type=EventType(r["event_type"]),
                payload=json.loads(r["payload_json"]),
                simulated=bool(r["simulated"]),
                recorded_at=datetime.fromisoformat(r["recorded_at"]),
            )
            for r in rows
        ]

    def journey_exists(self, journey_id: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                select(journeys.c.journey_id).where(journeys.c.journey_id == journey_id)
            ).scalar()
        return row is not None


# ---------------------------------------------------------------------------
# ScoringRun JSON serialization helpers
# ---------------------------------------------------------------------------

def _leg_to_dict(leg: Leg) -> dict:
    return {
        "leg_id": leg.leg_id, "option_id": leg.option_id,
        "segment_index": leg.segment_index, "carrier": leg.carrier,
        "flight_number": leg.flight_number, "dep_airport": leg.dep_airport,
        "dep_time": leg.dep_time, "arr_airport": leg.arr_airport,
        "arr_time": leg.arr_time, "duration_minutes": leg.duration_minutes,
        "stop_cities": leg.stop_cities, "cabin_class": leg.cabin_class,
        "seat_count": leg.seat_count, "risk_sellout": leg.risk_sellout,
        "code_share": leg.code_share, "aircraft_code": leg.aircraft_code,
        "fare_family": leg.fare_family,
    }


def _option_to_dict(opt: FlightOption) -> dict:
    return {
        "option_id": opt.option_id, "journey_id": opt.journey_id,
        "search_record_id": opt.search_record_id, "fid": opt.fid,
        "routing_identifier": opt.routing_identifier, "currency": opt.currency,
        "adult_price": str(opt.adult_price), "adult_tax": str(opt.adult_tax),
        "transaction_fee": str(opt.transaction_fee),
        "refreshed_at": opt.refreshed_at.isoformat() if opt.refreshed_at else None,
        "expire_at": opt.expire_at.isoformat() if opt.expire_at else None,
        "is_multi_leg": opt.is_multi_leg, "separate_bookings": opt.separate_bookings,
        "legs": [_leg_to_dict(l) for l in opt.legs],
        "recorded_at": opt.recorded_at.isoformat(),
    }


def _option_from_dict(d: dict) -> FlightOption:
    return FlightOption(
        option_id=d["option_id"], journey_id=d["journey_id"],
        search_record_id=d["search_record_id"], fid=d["fid"],
        routing_identifier=d["routing_identifier"], currency=d["currency"],
        adult_price=Decimal(d["adult_price"]), adult_tax=Decimal(d["adult_tax"]),
        transaction_fee=Decimal(d["transaction_fee"]),
        refreshed_at=datetime.fromisoformat(d["refreshed_at"]) if d["refreshed_at"] else None,
        expire_at=datetime.fromisoformat(d["expire_at"]) if d["expire_at"] else None,
        is_multi_leg=d["is_multi_leg"], separate_bookings=d["separate_bookings"],
        legs=[Leg(**{k: v for k, v in ld.items()}) for ld in d["legs"]],
        recorded_at=datetime.fromisoformat(d["recorded_at"]),
    )


def _elim_to_dict(e: EliminationRecord | None) -> dict | None:
    if e is None:
        return None
    return {"option_id": e.option_id, "reason_code": e.reason_code,
            "reason_detail": e.reason_detail, "constraint_id": e.constraint_id}


def _rationale_to_dict(r: Rationale | None) -> dict | None:
    if r is None:
        return None
    return {"option_id": r.option_id, "objective_elements": r.objective_elements,
            "summary": r.summary, "arrival_margin_minutes": r.arrival_margin_minutes,
            "total_cost": str(r.total_cost) if r.total_cost is not None else None}


def _rejection_to_dict(r: RejectionReason | None) -> dict | None:
    if r is None:
        return None
    return {"option_id": r.option_id, "reason_code": r.reason_code,
            "reason_detail": r.reason_detail}


def _conn_eval_to_dict(c: ConnectionEvaluation | None) -> dict | None:
    if c is None:
        return None
    return {"option_id": c.option_id, "connection_times": c.connection_times,
            "connection_excluded": c.connection_excluded,
            "exclusion_rule": c.exclusion_rule,
            "impossible_connections": c.impossible_connections}


def _scored_option_to_dict(so: ScoredOption) -> dict:
    return {
        "option": _option_to_dict(so.option),
        "outcome": so.outcome.value,
        "rank": so.rank,
        "rationale": _rationale_to_dict(so.rationale),
        "elimination": _elim_to_dict(so.elimination),
        "rejection_reason": _rejection_to_dict(so.rejection_reason),
        "connection_eval": _conn_eval_to_dict(so.connection_eval),
    }


def _scored_option_from_dict(d: dict) -> ScoredOption:
    elim_d = d["elimination"]
    rat_d = d["rationale"]
    rej_d = d["rejection_reason"]
    ce_d = d["connection_eval"]
    return ScoredOption(
        option=_option_from_dict(d["option"]),
        outcome=ScoringOutcome(d["outcome"]),
        rank=d["rank"],
        rationale=Rationale(
            option_id=rat_d["option_id"],
            objective_elements=rat_d["objective_elements"],
            summary=rat_d["summary"],
            arrival_margin_minutes=rat_d["arrival_margin_minutes"],
            total_cost=Decimal(rat_d["total_cost"]) if rat_d["total_cost"] is not None else None,
        ) if rat_d else None,
        elimination=EliminationRecord(**elim_d) if elim_d else None,
        rejection_reason=RejectionReason(**rej_d) if rej_d else None,
        connection_eval=ConnectionEvaluation(**ce_d) if ce_d else None,
    )


def _no_sat_to_dict(n: NoSatisfyingOptionReport | None) -> dict | None:
    if n is None:
        return None
    return {"unsatisfied_constraints": n.unsatisfied_constraints,
            "eliminated_count": n.eliminated_count, "summary": n.summary}


def _scoring_run_to_json(run: ScoringRun) -> str:
    selected_idx: int | None = None
    scored_dicts = [_scored_option_to_dict(so) for so in run.scored_options]
    if run.selected_option is not None:
        for i, so in enumerate(run.scored_options):
            if so is run.selected_option:
                selected_idx = i
                break

    return json.dumps({
        "run_id": run.run_id,
        "objective": run.objective.model_dump(mode="json"),
        "evaluated_at": run.evaluated_at.isoformat(),
        "scored_options": scored_dicts,
        "selected_option_index": selected_idx,
        "no_satisfying_option": _no_sat_to_dict(run.no_satisfying_option),
    })


def _scoring_run_from_json(raw: str) -> ScoringRun:
    d = json.loads(raw)
    scored = [_scored_option_from_dict(sd) for sd in d["scored_options"]]
    idx = d["selected_option_index"]
    selected = scored[idx] if idx is not None else None
    no_sat_d = d["no_satisfying_option"]
    return ScoringRun(
        run_id=d["run_id"],
        objective=TravelObjective.model_validate(d["objective"]),
        evaluated_at=datetime.fromisoformat(d["evaluated_at"]),
        scored_options=scored,
        selected_option=selected,
        no_satisfying_option=NoSatisfyingOptionReport(**no_sat_d) if no_sat_d else None,
    )
