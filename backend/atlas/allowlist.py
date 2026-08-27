from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class AllowedEndpoint:
    """One permitted Atlas API endpoint entry (FR-001).

    Fields:
        name: The endpoint name as used in the URL path (e.g. "search.do").
        path: Relative path on the sandbox base URL.
        verification_status: "verified" if exercised end-to-end in sandbox;
            "unverified" if listed in the API reference but not yet exercised.
            Unverified endpoints MUST NOT be called by production code paths.
    """

    name: str
    path: str
    verification_status: Literal["verified", "unverified"]


# Sandbox base URL: https://sandbox.atriptech.com/
# Production base URL: https://[production-host]/ (separate credentials)

ENDPOINT_ALLOWLIST: frozenset[AllowedEndpoint] = frozenset(
    {
        # ── Verified endpoints (exercised end-to-end, 2026-08-15) ──────────
        AllowedEndpoint(
            name="search.do",
            path="search.do",
            verification_status="verified",
        ),
        AllowedEndpoint(
            name="verify.do",
            path="verify.do",
            verification_status="verified",
        ),
        AllowedEndpoint(
            name="order.do",
            path="order.do",
            verification_status="verified",
        ),
        AllowedEndpoint(
            name="pay.do",
            path="pay.do",
            verification_status="verified",
        ),
        AllowedEndpoint(
            name="queryOrderDetails.do",
            path="queryOrderDetails.do",
            verification_status="verified",
        ),
        AllowedEndpoint(
            name="updateWebhookURL.do",
            path="updateWebhookURL.do",
            verification_status="verified",
        ),
        # ── Listed but unverified (API reference only; schemas are stubs) ──
        AllowedEndpoint(
            name="getOffers.do",
            path="getOffers.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="getOfferPrice.do",
            path="getOfferPrice.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="seatAvailability.do",
            path="seatAvailability.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="getLuggage.do",
            path="getLuggage.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="createRefundRecord.do",
            path="createRefundRecord.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="queryRefund.do",
            path="queryRefund.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="void.do",
            path="void.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="queryIncident.do",
            path="queryIncident.do",
            verification_status="unverified",
        ),
        AllowedEndpoint(
            name="queryBalance.do",
            path="queryBalance.do",
            verification_status="unverified",
        ),
    }
)
