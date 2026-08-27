# Contract: Atlas Endpoint Allowlist

**Feature**: 000-atlas-capability-contract
**Date**: 2026-08-28
**Source**: `.antabay/atlas-capability-map.md` §2

This contract defines the complete set of Atlas API endpoints the system
is permitted to reference. Any symbol not on this list MUST NOT be imported
from `backend/atlas/allowlist.py`. Mypy enforces this at build time.

---

## Verified Endpoints (exercised end-to-end)

These endpoints have been exercised against the sandbox. Typed request/response
models exist and are production-safe.

| Endpoint | Method | Purpose | Verified |
|----------|--------|---------|---------|
| `search.do` | POST | Search for flight options | 2026-08-15 |
| `verify.do` | POST | Re-price and lock a routing | 2026-08-15 |
| `order.do` | POST | Create an order (issues PNR) | 2026-08-15 |
| `pay.do` | POST | Trigger payment from Atlas balance | 2026-08-15 |
| `queryOrderDetails.do` | POST | Query current order/ticket status | 2026-08-15 |
| `updateWebhookURL.do` | POST | Register webhook receiver URL | 2026-08-15 |

## Listed but Unverified Endpoints

These endpoints appear in the Atlas API Reference but have not been exercised
in the sandbox. They are included in the allowlist but MUST NOT be called by
production code paths. Their Pydantic models are stubs, marked
`verification_status = "unverified"`.

| Endpoint | Purpose |
|----------|---------|
| `getOffers.do` | Retrieve ancillary offers |
| `getOfferPrice.do` | Price an ancillary offer |
| `seatAvailability.do` | Query seat map |
| `getLuggage.do` | Query luggage options |
| `createRefundRecord.do` | Initiate refund |
| `queryRefund.do` | Query refund status |
| `void.do` | Void an order |
| `queryIncident.do` | Query schedule incident |
| `queryBalance.do` | Query Atlas account balance |

## Prohibited Patterns

The following are not endpoints and MUST NOT appear in call code:

- `suggestFlight.do` — does not exist in the API reference
- Any URL constructed by string interpolation or concatenation
- Any endpoint not present in either table above

## Rate Limit Declarations

| Endpoint(s) | Limit | Window |
|------------|-------|--------|
| `search.do` | 10 | per second |
| `verify.do`, `getOffers.do` | 60 | per minute (shared pool) |
| `seatAvailability.do`, `getLuggage.do` | 60 | per minute (shared pool) |

Over-limit returns HTTP 429 with `retryAfter`. No retry loop is permitted.
