"""
Failing tests for ConstraintType, ConstrainedField[T], and TravelObjective.
Written before implementation — all tests must fail first (Constitution IX).
"""
from decimal import Decimal

import pytest
from pydantic import ValidationError

# These imports will fail until implementation exists — that is the expected
# failing state before T012/T014.
from journey.models.objective import (
    ConstrainedField,
    ConstraintType,
    TravelObjective,
)


class TestConstraintType:
    def test_hard_value(self) -> None:
        assert ConstraintType.HARD == ConstraintType.HARD

    def test_soft_value(self) -> None:
        assert ConstraintType.SOFT == ConstraintType.SOFT

    def test_hard_and_soft_are_distinct(self) -> None:
        assert ConstraintType.HARD != ConstraintType.SOFT


class TestConstrainedField:
    def test_stores_string_value_and_constraint_type(self) -> None:
        field: ConstrainedField[str] = ConstrainedField(
            value="LHR", constraint_type=ConstraintType.HARD
        )
        assert field.value == "LHR"
        assert field.constraint_type == ConstraintType.HARD

    def test_stores_decimal_value(self) -> None:
        field: ConstrainedField[Decimal] = ConstrainedField(
            value=Decimal("2000.00"), constraint_type=ConstraintType.HARD
        )
        assert field.value == Decimal("2000.00")

    def test_stores_int_value(self) -> None:
        field: ConstrainedField[int] = ConstrainedField(
            value=2, constraint_type=ConstraintType.SOFT
        )
        assert field.value == 2

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            ConstrainedField(value="X", constraint_type=ConstraintType.HARD, extra_field="bad")  # type: ignore[call-arg]

    def test_constraint_type_required(self) -> None:
        with pytest.raises(ValidationError):
            ConstrainedField(value="X")  # type: ignore[call-arg]

    def test_model_json_schema_contains_constraint_type(self) -> None:
        schema = ConstrainedField[str].model_json_schema()
        assert "constraint_type" in str(schema)


class TestTravelObjective:
    def test_all_fields_nullable(self) -> None:
        obj = TravelObjective()
        assert obj.origin is None
        assert obj.destination is None
        assert obj.latest_arrival is None
        assert obj.budget_amount is None
        assert obj.budget_currency is None
        assert obj.pax_count is None
        assert obj.preferences is None

    def test_accepts_constrained_fields(self) -> None:
        obj = TravelObjective(
            origin=ConstrainedField(value="LHR", constraint_type=ConstraintType.HARD),
            destination=ConstrainedField(value="SIN", constraint_type=ConstraintType.HARD),
            pax_count=ConstrainedField(value=2, constraint_type=ConstraintType.HARD),
        )
        assert obj.origin is not None
        assert obj.origin.value == "LHR"
        assert obj.pax_count is not None
        assert obj.pax_count.value == 2

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            TravelObjective(invented_field="bad")  # type: ignore[call-arg]

    def test_budget_co_presence_both_set_ok(self) -> None:
        obj = TravelObjective(
            budget_amount=ConstrainedField(value=Decimal("2000"), constraint_type=ConstraintType.HARD),
            budget_currency=ConstrainedField(value="GBP", constraint_type=ConstraintType.HARD),
        )
        assert obj.budget_amount is not None
        assert obj.budget_currency is not None

    def test_budget_co_presence_amount_without_currency_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TravelObjective(
                budget_amount=ConstrainedField(value=Decimal("2000"), constraint_type=ConstraintType.HARD),
            )

    def test_budget_co_presence_currency_without_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TravelObjective(
                budget_currency=ConstrainedField(value="GBP", constraint_type=ConstraintType.HARD),
            )

    def test_model_json_schema_round_trip(self) -> None:
        schema = TravelObjective.model_json_schema()
        assert "origin" in str(schema)
        assert "destination" in str(schema)
        assert "pax_count" in str(schema)
