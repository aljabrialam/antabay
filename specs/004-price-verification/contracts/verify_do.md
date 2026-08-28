# Contract: Atlas `verify.do` (external, consumed)

**Feature**: 004-price-verification
**Type**: External HTTP endpoint contract (already verified — see
`.antabay/atlas-capability-map.md` §7a)
**Status**: `verified` in `backend/atlas/allowlist.py` — no allowlist change needed

This document restates the parts of the verified contract this feature
depends on. It is not the source of truth — the capability map is. This
exists so this feature's tests and data model can be checked against a
stable reference without re-reading the map on every change.

---

## Request

```json
{
  "routingIdentifier": "<byte-for-byte from search>",
  "maxResponseTime": null,
  "requestSource": "antabay"
}
```

`routingIdentifier` MUST be forwarded exactly as held from the search
result for the selected option (FR-002). No other request field is
computed from data this feature owns.

## Response envelope

```json
{
  "sessionId": "string (UUID)",
  "maxSeats": "int",
  "routing": { "...": "same shape as a search routing" },
  "bookingRequirement": { "passenger": { "...": "see below" } },
  "priceChange": { "...": "see below" },
  "status": "int",
  "msg": "string",
  "requestId": null,
  "clientRequestId": null
}
```

`status: 0`, `msg: "success"` on success (both a plain `VERIFIED` outcome
and a `PRICE_CHANGED` one — see below).

| Field | Used for |
|---|---|
| `sessionId` | FR-005 — recorded, preserved unmodified |
| `maxSeats` | FR-008 — recorded as the bookable quantity ceiling |
| `routing.expireTime`, `routing.refreshTime` | Both `null` on this response — see research.md R2; the offer window they used to carry does not transfer |
| `bookingRequirement.passenger` | FR-007 — recorded as-is |
| `priceChange` | FR-003/FR-004 — read directly, not recomputed |
| `status` | Distinguishes `VERIFIED`/`PRICE_CHANGED` (0) from `UNAVAILABLE` (non-zero, per research.md R3) |

## `priceChange` shape

```json
{
  "isPriceChange": false,
  "originalAdultPrice": 66.43, "newAdultPrice": 66.43,
  "originalAdultTax": 23.96,   "newAdultTax": 23.96,
  "originalChildPrice": null, "newChildPrice": null,
  "originalInfantPrice": null, "newInfantPrice": null
}
```

`isPriceChange` is the single field this feature reads to decide whether
the price moved (FR-003). The `original*`/`new*` pairs are persisted for
audit (NFR-002) alongside it, never compared by this feature to derive
`isPriceChange` itself.

## `bookingRequirement.passenger` shape

A map of field name → `{ type, required, description, maxLength }`.
Observed fields on the ZE605 capture: `name`, `birthday`, `gender`,
`nationality`, `passengerType`, `cardNum`, `cardType`, `cardIssuePlace`,
`cardExpired` — but per the capability map, this is "returned per offer,"
not a fixed set (FR-007). Do not assume any field is always present.

## Known, verified example (ZE605, captured 2026-08-15)

- `sessionId`: a UUID string
- `maxSeats`: `7`
- `priceChange.isPriceChange`: `false`
- Total price unchanged from search: `adultPrice 66.43 + adultTax 23.96 +
  transactionFeePerPax 0.00 = 90.39`

This is the basis for the Tier 1 VCR cassette
(`fixtures/atlas/cassettes/verification/verify_ze605.yaml`).

## Rate limiting

`verify.do` shares its 60 QPM allowance with `getOffers.do` (capability
map §6). A 429 response carries `retryAfter`; this feature's call-budget
accounting (FR-011) and retry discipline reuse the same pattern already
implemented for `search.do`.

## Not yet verified (do not build against)

- The exact `status` code or `msg` Atlas returns when the selected option
  is no longer available. This feature's `UNAVAILABLE` outcome is
  currently "any non-zero status that isn't a price-change response" —
  see research.md R3. Narrow this once a real sandbox capture of that
  condition exists.
