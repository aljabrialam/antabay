"""
Tests for OpaqueId (FR-004).

These tests MUST fail before backend/atlas/identifiers.py is implemented.
Run: pytest tests/unit/test_identifiers.py -v
"""
import pytest
from atlas.identifiers import OpaqueId


class TestOpaqueIdEquality:
    def test_equal_same_value(self):
        a = OpaqueId("ABC123")
        b = OpaqueId("ABC123")
        assert a == b

    def test_not_equal_different_value(self):
        a = OpaqueId("ABC123")
        b = OpaqueId("XYZ999")
        assert a != b

    def test_hashable(self):
        a = OpaqueId("ABC123")
        s = {a}
        assert OpaqueId("ABC123") in s


class TestOpaqueIdPassthrough:
    def test_str_returns_raw_value(self):
        raw = "routingIdentifier-opaque-blob=="
        oid = OpaqueId(raw)
        assert str(oid) == raw

    def test_round_trip_byte_identity(self):
        raw = "TESTA20260815172246746"
        oid = OpaqueId(raw)
        assert str(oid) == raw


class TestOpaqueIdNoManipulation:
    def test_no_getitem(self):
        oid = OpaqueId("ABC123")
        assert not hasattr(oid, "__getitem__"), "OpaqueId must not support subscript"

    def test_no_add(self):
        oid = OpaqueId("ABC123")
        assert not hasattr(oid, "__add__"), "OpaqueId must not support concatenation"

    def test_no_mod(self):
        oid = OpaqueId("ABC123")
        assert not hasattr(oid, "__mod__"), "OpaqueId must not support % formatting"

    def test_no_len(self):
        oid = OpaqueId("ABC123")
        assert not hasattr(oid, "__len__"), "OpaqueId must not expose length"

    def test_value_not_directly_accessible(self):
        oid = OpaqueId("secret-value")
        # _value must be private — no public attribute named 'value' or 'raw'
        assert not hasattr(oid, "value"), "OpaqueId must not expose a public .value"
        assert not hasattr(oid, "raw"), "OpaqueId must not expose a public .raw"
