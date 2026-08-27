from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpaqueId:
    """Opaque externally-issued identifier (FR-004).

    Stores a raw string value received from the Atlas API.
    Supports equality comparison and str() passthrough only.
    No subscript, concatenation, format, len, or construction-from-parts
    is available — those operations are structurally absent.
    """

    _value: str

    def __init__(self, value: str) -> None:
        object.__setattr__(self, "_value", value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, OpaqueId):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"OpaqueId({self._value!r})"
