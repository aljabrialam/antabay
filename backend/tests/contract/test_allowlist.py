"""
Contract tests for the endpoint allowlist (FR-001, FR-002, SC-001, SC-002).

These tests MUST fail before backend/atlas/allowlist.py is implemented.
Run: pytest tests/contract/test_allowlist.py -v
"""
import pytest
from atlas.allowlist import ENDPOINT_ALLOWLIST, AllowedEndpoint


VERIFIED_ENDPOINTS = {
    "search.do",
    "verify.do",
    "order.do",
    "pay.do",
    "queryOrderDetails.do",
    "updateWebhookURL.do",
}

UNVERIFIED_ENDPOINTS = {
    "getOffers.do",
    "getOfferPrice.do",
    "seatAvailability.do",
    "getLuggage.do",
    "createRefundRecord.do",
    "queryRefund.do",
    "void.do",
    "queryIncident.do",
    "queryBalance.do",
}


class TestAllowlistCompleteness:
    def test_allowlist_is_frozenset_of_allowed_endpoints(self):
        assert isinstance(ENDPOINT_ALLOWLIST, frozenset)
        for entry in ENDPOINT_ALLOWLIST:
            assert isinstance(entry, AllowedEndpoint)

    def test_all_verified_endpoints_present(self):
        names = {e.name for e in ENDPOINT_ALLOWLIST}
        for endpoint in VERIFIED_ENDPOINTS:
            assert endpoint in names, f"{endpoint} missing from allowlist"

    def test_all_unverified_endpoints_present(self):
        names = {e.name for e in ENDPOINT_ALLOWLIST}
        for endpoint in UNVERIFIED_ENDPOINTS:
            assert endpoint in names, f"{endpoint} missing from allowlist"

    def test_no_extra_endpoints(self):
        names = {e.name for e in ENDPOINT_ALLOWLIST}
        expected = VERIFIED_ENDPOINTS | UNVERIFIED_ENDPOINTS
        assert names == expected, f"Unexpected endpoints: {names - expected}"


class TestVerificationStatus:
    def test_verified_endpoints_have_verified_status(self):
        for entry in ENDPOINT_ALLOWLIST:
            if entry.name in VERIFIED_ENDPOINTS:
                assert entry.verification_status == "verified", (
                    f"{entry.name} should be 'verified'"
                )

    def test_unverified_endpoints_have_unverified_status(self):
        for entry in ENDPOINT_ALLOWLIST:
            if entry.name in UNVERIFIED_ENDPOINTS:
                assert entry.verification_status == "unverified", (
                    f"{entry.name} should be 'unverified'"
                )


class TestAllowedEndpointShape:
    def test_each_entry_has_name_path_status(self):
        for entry in ENDPOINT_ALLOWLIST:
            assert entry.name, "name must be non-empty"
            assert entry.path, "path must be non-empty"
            assert entry.verification_status in ("verified", "unverified")

    def test_suggestflight_does_not_exist(self):
        names = {e.name for e in ENDPOINT_ALLOWLIST}
        assert "suggestFlight.do" not in names, (
            "suggestFlight.do must not exist in the allowlist"
        )

    def test_arbitrary_invented_endpoint_does_not_exist(self):
        names = {e.name for e in ENDPOINT_ALLOWLIST}
        assert "bookFlight.do" not in names
        assert "cancelOrder.do" not in names
