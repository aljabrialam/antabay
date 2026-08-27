from __future__ import annotations

from enum import IntEnum
from typing import Union


class OrderStatus(IntEnum):
    """Normalised order status (FR-006).

    Atlas returns orderStatus as a string from queryOrderDetails.do
    and as an integer from webhook events. Both surfaces are normalised
    to this IntEnum on ingest so downstream code never branches on raw type.

    Partial enum — only values observed in sandbox captured to date.
    Unknown values are preserved via _missing_ to avoid crashing on
    future Atlas enum additions.
    """

    PAID_NOT_TICKETED = 1
    TICKETED = 2

    @classmethod
    def _missing_(cls, value: object) -> "OrderStatus":
        if not isinstance(value, (int, str)):
            raise ValueError(f"Cannot create OrderStatus from {value!r}")
        int_value = int(value)
        obj = int.__new__(cls, int_value)
        obj._value_ = int_value
        obj._name_ = f"UNKNOWN_{int_value}"
        return obj

