"""
Tests for OrderStatus IntEnum normalisation (FR-006).

These tests MUST fail before backend/atlas/models/_base.py is implemented.
Run: pytest tests/unit/test_models_base.py -v
"""
from atlas.models._base import OrderStatus


class TestOrderStatusNormalisation:
    def test_string_one_maps_to_paid_not_ticketed(self):
        # REST surface returns orderStatus as string "1"
        result = OrderStatus(int("1"))
        assert result == OrderStatus.PAID_NOT_TICKETED

    def test_integer_two_maps_to_ticketed(self):
        # Webhook surface returns orderStatus as integer 2
        result = OrderStatus(2)
        assert result == OrderStatus.TICKETED

    def test_paid_not_ticketed_value_is_one(self):
        assert OrderStatus.PAID_NOT_TICKETED == 1

    def test_ticketed_value_is_two(self):
        assert OrderStatus.TICKETED == 2

    def test_unknown_integer_preserved(self):
        # Unknown values must be preserved, not raise KeyError
        result = OrderStatus(999)
        assert int(result) == 999

    def test_comparison_with_int_member(self):
        assert OrderStatus.PAID_NOT_TICKETED == 1
        assert OrderStatus.TICKETED == 2

    def test_is_int(self):
        assert isinstance(OrderStatus.TICKETED, int)
