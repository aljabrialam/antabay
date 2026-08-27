"""Unit tests for FlightOption model — T012 (TDD: must FAIL before flight.py exists)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_leg(**kwargs):
    from journey.models.flight import Leg
    defaults = dict(
        leg_id="leg-001",
        option_id="opt-001",
        segment_index=0,
        carrier="SQ",
        flight_number="SQ321",
        dep_airport="SIN",
        dep_time="202609051000",
        arr_airport="LHR",
        arr_time="202609051600",
        duration_minutes=740,
        stop_cities="",
        cabin_class="Y",
        seat_count=9,
        risk_sellout=False,
        code_share=False,
        aircraft_code="773",
        fare_family=None,
    )
    defaults.update(kwargs)
    return Leg(**defaults)


def _make_option(**kwargs):
    from journey.models.flight import FlightOption
    expire = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
    refreshed = datetime(2026, 9, 5, 10, 45, 0, tzinfo=timezone.utc)
    defaults = dict(
        option_id="opt-001",
        journey_id="journey-1",
        search_record_id="search-1",
        fid="ABC|SIN|LHR|20260905|SQ321",
        routing_identifier="RI::SIN::LHR::20260905::SQ::321",
        currency="USD",
        adult_price=Decimal("450.00"),
        adult_tax=Decimal("85.50"),
        transaction_fee=Decimal("0.00"),
        refreshed_at=refreshed,
        expire_at=expire,
        is_multi_leg=False,
        separate_bookings=False,
        legs=[_make_leg()],
        recorded_at=datetime(2026, 9, 5, 10, 46, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return FlightOption(**defaults)


# ---------------------------------------------------------------------------
# T012: FlightOption model tests
# ---------------------------------------------------------------------------

class TestIdentifiersPreservedVerbatim:
    """FR-003: fid and routing_identifier stored byte-for-byte."""

    def test_fid_preserved_verbatim(self) -> None:
        raw_fid = "ABC|SIN|LHR|20260905|SQ321\x00"  # includes unusual chars
        opt = _make_option(fid=raw_fid)
        assert opt.fid == raw_fid

    def test_routing_identifier_preserved_verbatim(self) -> None:
        raw_ri = "RI::SIN::LHR::20260905::SQ::321  "  # trailing spaces preserved
        opt = _make_option(routing_identifier=raw_ri)
        assert opt.routing_identifier == raw_ri

    def test_identifiers_preserved_verbatim(self) -> None:
        fid = "fid-exact-value"
        ri = "ri-exact-value"
        opt = _make_option(fid=fid, routing_identifier=ri)
        assert opt.fid is fid
        assert opt.routing_identifier is ri


class TestFreshnessTimestampsRecorded:
    """FR-004: refreshed_at and expire_at mapped from provider timestamps."""

    def test_freshness_timestamps_recorded(self) -> None:
        refreshed = datetime(2026, 9, 5, 10, 45, 0, tzinfo=timezone.utc)
        expire = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
        opt = _make_option(refreshed_at=refreshed, expire_at=expire)
        assert opt.refreshed_at == refreshed
        assert opt.expire_at == expire

    def test_refreshed_at_nullable(self) -> None:
        opt = _make_option(refreshed_at=None)
        assert opt.refreshed_at is None

    def test_expire_at_nullable(self) -> None:
        opt = _make_option(expire_at=None)
        assert opt.expire_at is None


class TestRemainingSecondsUsesNowNotReceipt:
    """FR-005: remaining_seconds uses injected now, not internal clock."""

    def test_remaining_seconds_uses_now_not_receipt(self) -> None:
        expire = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
        opt = _make_option(expire_at=expire)
        # 15 minutes before expiry
        now = datetime(2026, 9, 5, 10, 45, 0, tzinfo=timezone.utc)
        assert opt.remaining_seconds(now) == pytest.approx(900.0)

    def test_remaining_seconds_negative_when_expired(self) -> None:
        expire = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
        opt = _make_option(expire_at=expire)
        now = datetime(2026, 9, 5, 10, 5, 0, tzinfo=timezone.utc)
        assert opt.remaining_seconds(now) == pytest.approx(-300.0)

    def test_remaining_seconds_takes_now_parameter(self) -> None:
        import inspect
        opt = _make_option()
        sig = inspect.signature(opt.remaining_seconds)
        assert "now" in sig.parameters


class TestRemainingSecondsRaisesIfExpireAtNone:
    """F5: remaining_seconds raises ValueError when expire_at is None."""

    def test_remaining_seconds_raises_if_expire_at_none(self) -> None:
        opt = _make_option(expire_at=None)
        now = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            opt.remaining_seconds(now)


class TestIsExpiredUsesInjectedNow:
    """F6: is_expired returns True when now >= expire_at; never reads clock."""

    def test_is_expired_uses_injected_now(self) -> None:
        expire = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
        opt = _make_option(expire_at=expire)
        before = datetime(2026, 9, 5, 10, 59, 59, tzinfo=timezone.utc)
        after = datetime(2026, 9, 5, 11, 0, 1, tzinfo=timezone.utc)
        assert opt.is_expired(before) is False
        assert opt.is_expired(after) is True

    def test_is_expired_at_exact_boundary(self) -> None:
        expire = datetime(2026, 9, 5, 11, 0, 0, tzinfo=timezone.utc)
        opt = _make_option(expire_at=expire)
        assert opt.is_expired(expire) is True  # remaining_seconds == 0 → expired

    def test_is_expired_takes_now_parameter(self) -> None:
        import inspect
        opt = _make_option()
        sig = inspect.signature(opt.is_expired)
        assert "now" in sig.parameters


class TestMultiLegDetection:
    """FR-007: is_multi_leg = len(legs) > 1."""

    def test_multi_leg_detection_single(self) -> None:
        opt = _make_option(legs=[_make_leg(segment_index=0)], is_multi_leg=False)
        assert opt.is_multi_leg is False

    def test_multi_leg_detection_multi(self) -> None:
        leg1 = _make_leg(leg_id="l1", segment_index=0, arr_airport="FRA")
        leg2 = _make_leg(leg_id="l2", segment_index=1, dep_airport="FRA")
        opt = _make_option(legs=[leg1, leg2], is_multi_leg=True)
        assert opt.is_multi_leg is True

    def test_multi_leg_detection(self) -> None:
        """Traceability matrix name — is_multi_leg reflects len(legs) > 1."""
        single = _make_option(legs=[_make_leg()], is_multi_leg=False)
        leg1 = _make_leg(leg_id="l1", segment_index=0)
        leg2 = _make_leg(leg_id="l2", segment_index=1)
        multi = _make_option(legs=[leg1, leg2], is_multi_leg=True)
        assert single.is_multi_leg is False
        assert multi.is_multi_leg is True


class TestScarcityFieldsRecorded:
    """FR-008: seat_count and risk_sellout per leg."""

    def test_scarcity_fields_recorded(self) -> None:
        leg = _make_leg(seat_count=3, risk_sellout=True)
        opt = _make_option(legs=[leg])
        assert opt.legs[0].seat_count == 3
        assert opt.legs[0].risk_sellout is True

    def test_scarcity_fields_false_when_no_risk(self) -> None:
        leg = _make_leg(seat_count=50, risk_sellout=False)
        opt = _make_option(legs=[leg])
        assert opt.legs[0].risk_sellout is False


class TestNoFieldEnrichment:
    """FR-011: all values trace to provided data; nothing authored by system."""

    def test_no_field_enrichment(self) -> None:
        raw_data = dict(
            option_id="opt-enrichment",
            journey_id="journey-enrichment",
            search_record_id="search-enrichment",
            fid="raw-fid",
            routing_identifier="raw-ri",
            currency="USD",
            adult_price=Decimal("100.00"),
            adult_tax=Decimal("10.00"),
            transaction_fee=Decimal("0.00"),
            refreshed_at=datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc),
            expire_at=datetime(2026, 9, 5, 11, 0, tzinfo=timezone.utc),
            is_multi_leg=False,
            separate_bookings=False,
            legs=[_make_leg()],
            recorded_at=datetime(2026, 9, 5, 10, 1, tzinfo=timezone.utc),
        )
        from journey.models.flight import FlightOption
        opt = FlightOption(**raw_data)
        # Every stored field matches what was passed in; no value was authored
        assert opt.fid == raw_data["fid"]
        assert opt.routing_identifier == raw_data["routing_identifier"]
        assert opt.currency == raw_data["currency"]
        assert opt.adult_price == raw_data["adult_price"]
        assert opt.adult_tax == raw_data["adult_tax"]
        assert opt.transaction_fee == raw_data["transaction_fee"]
        assert opt.refreshed_at == raw_data["refreshed_at"]
        assert opt.expire_at == raw_data["expire_at"]
        assert opt.is_multi_leg == raw_data["is_multi_leg"]
        assert opt.recorded_at == raw_data["recorded_at"]
