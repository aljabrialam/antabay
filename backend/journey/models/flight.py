from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


@dataclass
class Leg:
    leg_id: str
    option_id: str
    segment_index: int
    carrier: str
    flight_number: str
    dep_airport: str
    dep_time: str
    arr_airport: str
    arr_time: str
    duration_minutes: int
    stop_cities: str
    cabin_class: str
    seat_count: int
    risk_sellout: bool
    code_share: bool
    aircraft_code: str
    fare_family: str | None


@dataclass
class FlightOption:
    option_id: str
    journey_id: str
    search_record_id: str
    fid: str
    routing_identifier: str
    currency: str
    adult_price: Decimal
    adult_tax: Decimal
    transaction_fee: Decimal
    refreshed_at: datetime | None
    expire_at: datetime | None
    is_multi_leg: bool
    separate_bookings: bool
    legs: list[Leg]
    recorded_at: datetime

    def remaining_seconds(self, now: datetime) -> float:
        if self.expire_at is None:
            raise ValueError("expire_at is None; cannot compute remaining_seconds")
        return (self.expire_at - now).total_seconds()

    def is_expired(self, now: datetime) -> bool:
        return self.remaining_seconds(now) <= 0


@dataclass
class SearchResult:
    search_id: str
    option_count: int
    no_options: bool
    carriers: list[str]
    options: list[FlightOption]


class SearchOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    EMPTY = "EMPTY"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"


@dataclass
class SearchRecord:
    search_id: str
    journey_id: str
    requested_at: datetime
    responded_at: datetime
    raw_response_json: str
    status_code: int
    atlas_status: int
    option_count: int
    budget_before: int
    budget_after: int
    outcome: SearchOutcome
