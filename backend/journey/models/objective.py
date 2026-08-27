from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, model_validator

T = TypeVar("T")


class ConstraintType(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"


class ConstrainedField(BaseModel, Generic[T]):
    value: T
    constraint_type: ConstraintType

    model_config = {"extra": "forbid"}


class TravelObjective(BaseModel):
    origin: ConstrainedField[str] | None = None
    destination: ConstrainedField[str] | None = None
    latest_arrival: ConstrainedField[str] | None = None
    departure_date: ConstrainedField[str] | None = None
    budget_amount: ConstrainedField[Decimal] | None = None
    budget_currency: ConstrainedField[str] | None = None
    pax_count: ConstrainedField[int] | None = None
    preferences: ConstrainedField[list[str]] | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def budget_co_presence(self) -> "TravelObjective":
        has_amount = self.budget_amount is not None
        has_currency = self.budget_currency is not None
        if has_amount != has_currency:
            raise ValueError(
                "budget_amount and budget_currency must both be present or both be absent"
            )
        return self


@dataclass
class ParseResult:
    objective: TravelObjective
    absent_fields: list[str] = field(default_factory=list)
    ambiguous_fields: list[str] = field(default_factory=list)
