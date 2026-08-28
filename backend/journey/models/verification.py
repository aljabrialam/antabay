from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class VerificationOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    PRICE_CHANGED = "PRICE_CHANGED"
    UNAVAILABLE = "UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"


@dataclass
class PriceChange:
    """Mirrors verify.do's priceChange object exactly — no derived fields (FR-003)."""

    is_price_change: bool
    original_adult_price: Decimal
    new_adult_price: Decimal
    original_adult_tax: Decimal
    new_adult_tax: Decimal
    original_child_price: Decimal | None = None
    new_child_price: Decimal | None = None
    original_infant_price: Decimal | None = None
    new_infant_price: Decimal | None = None


@dataclass
class PassengerRequirementField:
    """One entry from bookingRequirement.passenger (FR-007)."""

    field_name: str
    type: str
    required: bool
    description: str
    max_length: int | None


@dataclass
class VerificationResult:
    verification_id: str
    journey_id: str
    option_id: str
    requested_at: datetime
    responded_at: datetime
    raw_response_json: str
    status_code: int
    atlas_status: int | None
    outcome: VerificationOutcome
    budget_before: int
    budget_after: int
    session_id: str | None = None
    max_seats: int | None = None
    price_change: PriceChange | None = None
    passenger_requirements: list[PassengerRequirementField] = field(default_factory=list)
    invalidates_authorisation: bool = False
