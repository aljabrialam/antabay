# Contract: Atlas `order.do` / `pay.do` / `queryOrderDetails.do` (external, consumed)

**Feature**: 005-booking-path
**Type**: External HTTP endpoint contracts (already verified — see
`.antabay/atlas-capability-map.md` §7b)
**Status**: All three `verified` in `backend/atlas/allowlist.py` — no
allowlist change needed

This document restates the parts of the verified contract this feature
depends on. It is not the source of truth — the capability map is.

---

## `order.do`

### Request

```json
{
  "cid": "<client id>",
  "sessionId": "<from verify, byte-for-byte>",
  "passengers": [{
    "name": "string", "passengerType": "int", "birthday": "string",
    "gender": "string", "nationality": "string",
    "cardNum": "string", "cardType": "string", "cardExpired": "string"
  }],
  "contact": { "name": "string", "email": "string", "mobile": "string" },
  "requestSource": "antabay"
}
```

`sessionId` MUST be forwarded exactly as held from verification (FR-001).
Each entry in `passengers[]` MUST populate exactly the fields
`bookingRequirement.passenger` declared at verification time for this
option (FR-002) — not a fixed template.

### Response

| Field | Used for |
|---|---|
| `orderNo` | FR-003 — the order reference |
| `pnrCode` | FR-003 — the booking reference; FR-004 — never ticketing evidence |
| `tktLimitTime` | FR-005 — the ticketing-deadline freshness window |
| `sessionId` | Echoed back; not re-read as a new value (the request's copy is authoritative) |
| `duplicateOrders` | FR-006 — Atlas's own duplicate signal; non-empty means read and query the referenced order |
| `status`, `msg` | `status: 0` = created successfully |

**Observed** (JKT→SUB, 2026-08-15): `orderNo TESTA20260815172246746`,
`pnrCode TZKZYA`.

**A PNR is issued at order time, before payment.** Per the capability map:
"A PNR is not proof of a ticket" (FR-004).

## `pay.do`

### Request

```json
{ "cid": "<client id>", "orderNo": "<from order>", "requestSource": "antabay" }
```

No card details are submitted (`paymentMethod: 1` — payment is taken from
the Atlas account balance). `orderNo` MUST be the reference from a
successfully created order (FR-008).

### Response

Key fields: `orderNo`, `pnrCode`, `paymentMethod`, `airlines[]`, `status`,
`msg`.

`status: 0` indicates the payment request was accepted — per FR-009, this
is not evidence of ticketing. No specific decline response shape has been
captured yet for this payment path; the documented `Reject`/`Three DS`
cardholder-name simulations apply to a separate, unused VCC path (§6) and
are not applicable here (research.md R4).

## `queryOrderDetails.do`

### Request

```json
{ "cid": "<client id>", "orderNo": "<order reference>", "requestSource": "antabay" }
```

A read with no state-changing effect — may be called repeatedly without
restriction from FR-007/NFR-001 (those govern `order.do`/`pay.do` only).

### Response

Key fields used by this feature:

| Field | Used for |
|---|---|
| `orderStatus` | Recorded for audit only — enum not yet fully mapped, never used to confirm ticketing |
| `ticketStatus` | Same caveat |
| `paxTicketInfos[].ticketNos[]` | FR-010 — the *only* accepted evidence of ticketing, required non-empty for every passenger (research.md R5) |
| `paxTicketInfos[].airlinePNRs[]` | Recorded for audit |
| `errorCode`, `errorMessage` | research.md R6 — a non-null `errorCode` is treated as the terminal-error stop condition for the polling loop (FR-011) |
| `payTime`, `createdTime`, `updatedTime` | Recorded for audit |

**Observed** (immediately after successful payment): `orderStatus: "1"`,
`ticketStatus: "0"`, `ticketNos: []`, `payTime` set. **Paid is not
ticketed** — this is the exact condition FR-009/FR-010 exist to prevent
being mistaken for confirmation.

## Error codes relevant to this feature (capability map §9)

| Code | Meaning | This feature's behaviour |
|---|---|---|
| `0` | success | proceed |
| `318` | duplicate booking, same passenger + flight | FR-006 — read `duplicateOrders`, query, resume from real state; never retry blindly |
| `800` | order not exists | Treated as a bug in this feature's own state tracking, not a retryable condition — surfaced, not retried |
| `900` | auth failed | Terminal; not retried |

## Three clocks (capability map §7b, "Three clocks, not one")

| Clock | Scope | Observed |
|---|---|---|
| `expireTime` | offer, pre-verify | 7 min 43 s to 31 min (spec 002/004) |
| `sessionId` | post-verify, pre-order | documented up to 2 h (spec 004) |
| `tktLimitTime` | post-order, pre-ticket | **30 min** (17:22:46 → 17:52:46) — this feature |

## Not yet verified (do not build against)

- The exact `errorCode` values `queryOrderDetails.do` returns for a
  terminal error — this feature treats any non-null `errorCode` as
  terminal (research.md R6) pending a real capture.
- The response shape of a declined `pay.do` call on the verified
  balance-payment path — this feature detects "declined" as any
  recognisable non-success response, not against a specific documented
  code (research.md R4).
- Whether `duplicateOrders` can legitimately carry more than one entry —
  the verified capture shows exactly one; more than one is treated as an
  anomaly (research.md R8).
