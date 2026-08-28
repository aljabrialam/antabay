from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderOutcome(str, Enum):
    CREATED = "CREATED"
    DUPLICATE_REJECTED = "DUPLICATE_REJECTED"
    UNCERTAIN = "UNCERTAIN"
    ERROR = "ERROR"


class PaymentOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    DECLINED = "DECLINED"
    UNCERTAIN = "UNCERTAIN"
    ERROR = "ERROR"


@dataclass
class Order:
    order_id: str
    journey_id: str
    option_id: str
    requested_at: datetime
    outcome: OrderOutcome
    session_id_used: str
    responded_at: datetime | None = None
    raw_response_json: str | None = None
    order_no: str | None = None
    booking_reference: str | None = None
    ticketing_deadline: datetime | None = None


@dataclass
class PaymentAttempt:
    payment_id: str
    journey_id: str
    order_no: str
    requested_at: datetime
    outcome: PaymentOutcome
    responded_at: datetime | None = None
    raw_response_json: str | None = None


@dataclass
class TicketingQuery:
    query_id: str
    journey_id: str
    order_no: str
    queried_at: datetime
    raw_response_json: str
    confirmed: bool
    is_terminal_error: bool
    order_status: str | None = None
    ticket_status: str | None = None
    passenger_ticket_numbers: list[list[str]] = field(default_factory=list)
