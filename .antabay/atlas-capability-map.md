# Atlas Capability Map — Verified

**Status:** verified against sandbox on 15 August 2026
**Source of truth for:** specs 000, 002, 003, 004, 005, 007, 009, 011, 012

Everything in this file was observed in a real sandbox response or read from
the Atlas API Reference. Nothing here is inferred. If a field is not in this
file, it has not been verified — do not use it.

---

## 1. Environment

| Item | Value |
|---|---|
| Sandbox base URL | `https://sandbox.atriptech.com/` |
| Auth | headers `x-atlas-client-id`, `x-atlas-client-secret` |
| Encoding | `Accept-Encoding: gzip` required |
| Currency | must send `"currency": "USD"` explicitly in sandbox |
| Extra field observed | `cid` (client id) included in working request body |

Sandbox and production credentials are separate and only work in their own
environment.

## 2. Verified endpoints

Proven end-to-end via the Sandbox Validation Test Kit (5 requests, 13
assertions, all passing):

`search.do` → `verify.do` → `order.do` → `pay.do` → `queryOrderDetails.do`

Documented but not yet exercised: `getOffers.do`, `getOfferPrice.do`,
`seatAvailability.do`, `getLuggage.do`, refunds, void, webhook
registration, incident query, balance.

**No flight-change endpoint exists in the API Reference.** Change is an
ATRIP service-request workflow. Recovery must therefore be rebook plus
void/refund of the original.

## 3. Search request schema

```json
{
  "cid": "<client id>",
  "tripType": "1",
  "adultNum": 1,
  "childNum": 0,
  "infantNum": 0,
  "fromCity": "SEL",
  "toCity": "TYO",
  "fromDate": "20260905",
  "currency": "USD",
  "requestSource": "antabay"
}
```

`tripType` `"1"` one-way, `"2"` return (requires `retDate`). Dates are
`YYYYMMDD`. Optional: `fromAirport`, `toAirport`, `airlines` (array of
carrier codes; omit for all carriers), `includeMultipleFareFamily`.

## 4. Search response envelope

```
{ routings: [...], status: 0, msg: null, requestId: null, clientRequestId: null }
```

`status === 0` means success. Assert on this, not only on HTTP 200.

### Fields per routing that Antabay uses

| Field | Type | Use |
|---|---|---|
| `fid` | opaque string | routing identity — preserve exactly |
| `routingIdentifier` | opaque string | required by verify — preserve exactly |
| `currency` | string | always `USD` when requested |
| `adultPrice` | number | base fare |
| `adultTax` | number | tax |
| `transactionFeePerPax` | number | fee (0.00 observed) |
| `fromSegments[]` | array | itinerary legs — **length > 1 means a connection** |
| `retSegments[]` | array | empty for one-way |
| `seatCount` | int (on segment) | remaining seats — scarcity signal |
| `riskSellout` | boolean | Atlas's own sellout risk flag |
| `refreshTime` | ISO8601 | when this offer was priced |
| `expireTime` | ISO8601 | **when this offer dies** |
| `separateBookings` | boolean | true means legs are not protected together |
| `rule.hasBaggage` / `rule.baggageElements[]` | | included allowance |
| `rule.refundRules[]` / `rule.changesRules[]` | | time-banded fees |
| `ancillarySupported[]` | array | e.g. `["luggage"]` |
| `supportCreditTransPayment` | `"0"` / `"1"` | `"0"` observed — balance/VCC only |

### Segment fields

`segmentIndex`, `carrier`, `flightNumber`, `depAirport`, `depTime`,
`arrAirport`, `arrTime`, `stopCities`, `duration` (minutes), `codeShare`,
`cabinClass`, `seatCount`, `aircraftCode`, `fareFamily`.

Times are `YYYYMMDDHHMM` strings in **local airport time**.

## 5. Total price formula

```
total_per_adult = adultPrice + adultTax + transactionFeePerPax
```

Confirmed by Atlas documentation.

## 6. Critical constraints

**Offer expiry is short and variable.** Observed windows: 7 min 43 s
(SEL→TYO) and 31 min (JKT→SUB). Offers can also arrive already partially
aged, because results are served from cache — one observed offer had 14
minutes left at the moment it was returned. Freshness must be checked
before every decision, not treated as an edge case.

**Currency mixing hazard.** Fares are returned in USD. `refundRules` and
`changesRules` amounts are in **IDR** on the JKT→SUB route. Never combine
them without an explicit conversion, and never invent a rate.

**Rate limits.** `search.do` 10 QPS. `verify.do` + `getOffers.do` share
60 QPM. `seatAvailability.do` + `getLuggage.do` share 60 QPM. Over-limit
returns `429` with `retryAfter`. No retry loops.

**Identifier TTLs.** `routingIdentifier` documented up to 6 h, `sessionId`
up to 2 h — but the per-offer `expireTime` is authoritative and much
shorter. Trust `expireTime`.

**Payment failure simulation.** Cardholder first name `Reject` → error
`604` (declined). Cardholder first name `Three DS` → error `616` (3DS).
Any card number and last name. Deterministic — use for the failure path.

## 7. Verified route data — SEL → TYO, 2026-09-05

30 routings returned. 28 single-segment, 2 connecting.

Carriers: `7C` Jeju (11), `TW` T'way (6), `ZE` Eastar (5), `LJ` Jin Air
(4), `RS` Air Seoul (3), `BX` Air Busan (1), `ZG` ZipAir (1), `MM` Peach
(1).

Airports: departures `ICN` and `GMP`; arrivals `NRT` and `HND`.

Arrival feasibility: **0 options arrive before 09:00**, 3 before 10:00,
7 before 11:00.

The two connecting options are both `7C907` GMP→PUS, connecting at Busan
with layovers of **625 and 835 minutes** (10.4 h and 13.9 h), departing
the previous evening, total journey 13.6 h and 17.1 h.

One of them arrives NRT at 09:30 — meaning a naive arrival-time-only
filter would select a 13.6-hour overnight itinerary. Antabay must reject
it and explain why. This is a required behaviour, not a nice-to-have.

## 7a. Verify response schema — VERIFIED

Verified against ZE605 on 15 August 2026.

### Request

```json
{
  "routingIdentifier": "<byte-for-byte from search>",
  "maxResponseTime": null,
  "requestSource": "antabay"
}
```

### Response envelope

```
{ sessionId, maxSeats, routing, bookingRequirement, priceChange,
  status, msg, requestId, clientRequestId }
```

`status: 0`, `msg: "success"` on success.

| Field | Type | Notes |
|---|---|---|
| `sessionId` | UUID string | required for order — preserve exactly |
| `maxSeats` | int | max bookable on this offer (7 observed) |
| `routing` | object | same shape as a search routing |
| `bookingRequirement` | object | passenger field schema, see below |
| `priceChange` | object | see below |

### `priceChange` — use this for P-08

```json
{
  "isPriceChange": false,
  "originalAdultPrice": 66.43, "newAdultPrice": 66.43,
  "originalAdultTax": 23.96,   "newAdultTax": 23.96,
  "originalChildPrice": ..., "newChildPrice": ...,
  "originalInfantPrice": ..., "newInfantPrice": ...
}
```

Atlas computes the delta. Antabay reads `isPriceChange` rather than
comparing prices itself. When true, prior human approval is void.

### `bookingRequirement.passenger` — runtime schema for spec 005

Each field is `{ type, required, description, maxLength }`.

| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `birthday` | string | yes |
| `gender` | string | yes |
| `nationality` | string | yes |
| `passengerType` | int | yes |
| `cardNum` | string | no |
| `cardType` | string | no |
| `cardIssuePlace` | string | no |
| `cardExpired` | string | no |

This is returned per offer. Read it at runtime — do not hardcode a
passenger form.

### Freshness changes shape after verify

`routing.refreshTime` and `routing.expireTime` are **null** in the verify
response. The short offer window is replaced by the `sessionId` window
(documented up to 2 h).

The journey state machine therefore has two distinct freshness phases:

1. **Pre-verify** — governed by the offer's `expireTime`, observed as
   short as 7 min 43 s and sometimes already partly elapsed on arrival.
2. **Post-verify** — governed by `sessionId`, longer but still bounded.

### Observed values, ZE605

Search total and verify total both 90.39 USD
(`adultPrice` 66.43 + `adultTax` 23.96 + `transactionFeePerPax` 0.00).
`ancillarySupported` `["seat", "luggage"]`. `maxSeats` 7.
`separateBookings` false. `supportCreditTransPayment` `"0"`.

## 7b. Order / Pay / Order Query — VERIFIED

Verified via the Sandbox Validation Test Kit, 15 August 2026 (JKT→SUB).

### `order.do`

Request:
```json
{
  "cid": "<client id>",
  "sessionId": "<from verify, byte-for-byte>",
  "passengers": [{
    "name": "TEST/ONE", "passengerType": 0, "birthday": "19900101",
    "gender": "M", "nationality": "ID",
    "cardNum": "A12345678", "cardType": "PP", "cardExpired": "20301231"
  }],
  "contact": { "name": "...", "email": "...", "mobile": "0062-8123456789" },
  "requestSource": "antabay"
}
```

Response keys: `orderNo`, `pnrCode`, `totalPrice`, `totalTransactionFee`,
`currency`, `vendorTotalPrice`, `vendorCurrency`, `tktLimitTime`,
`paxTicketInfos[]`, `routing`, `sessionId`, `offerId`, `originalOrderNo`,
`ticketOrderNo`, `includeExtraBaggage`, `paymentOptions`,
**`duplicateOrders`**, `status`, `msg`.

Observed: `orderNo` `TESTA20260815172246746`, `pnrCode` `TZKZYA`.

**`duplicateOrders` is Atlas's own duplicate signal.** Read it. It is the
mechanism behind P-06 — reconcile, never retry.

**A PNR is issued at order time, before payment.** A PNR is not proof of
a ticket.

### `pay.do`

Request:
```json
{ "cid": "<client id>", "orderNo": "<from order>", "requestSource": "antabay" }
```

**No card details.** `paymentMethod: 1` — payment is taken from the Atlas
balance. The documented `Reject` / `Three DS` cardholder simulations apply
to VCC flows, not this path.

Response: `orderNo`, `pnrCode`, `paymentMethod`, `airlines[]`, `status`,
`msg`.

### `queryOrderDetails.do`

Request: `{ cid, orderNo, requestSource }`

Key response fields: `orderStatus` (string), `ticketStatus` (string),
`paxTicketInfos[].ticketNos[]`, `paxTicketInfos[].airlinePNRs[]`,
`payTime`, `createdTime`, `updatedTime`, `tktLimitTime`, `vccStatus`,
`paymentAttempted`, `errorCode`, `errorMessage`, `ifSeatOccupied`,
`itineraryDownload`, `refundRules`, `airlineBookings`, `airlineMessage`.

Observed immediately after successful payment:
`orderStatus: "1"`, `ticketStatus: "0"`, `ticketNos: []`, `payTime` set.

**Paid is not ticketed.** `ticketStatus` was still `"0"` with empty
`ticketNos` after `pay.do` returned success. Ticketing confirmation means
polling until `ticketNos` is populated. The full enum values for
`orderStatus` and `ticketStatus` are still unmapped — treat only
"`ticketNos` non-empty" as proof of ticketing until they are.

### Three clocks, not one

| Clock | Scope | Observed |
|---|---|---|
| `expireTime` | offer, pre-verify | 7 min 43 s to 31 min, sometimes partly elapsed on arrival |
| `sessionId` | post-verify, pre-order | documented up to 2 h |
| `tktLimitTime` | post-order, pre-ticket | **30 min** (17:22:46 → 17:52:46) |

The journey state machine must track all three. Each has a different
expiry consequence.

## 7c. Webhook — VERIFIED BY CAPTURE

Registration and a real `order.ticketed` event captured 15 August 2026 via
a Cloudflare quick tunnel.

### Registration

`POST /updateWebhookURL.do` with `{ "cid": "...", "url": "https://..." }`
→ `{"status":0,"msg":"Operation succeeded"}`.

Account-wide, not per-order. Re-register whenever the public URL changes.

### Captured envelope

```json
{
  "cid": "<client id>",
  "type": "order.ticketed",
  "status": -1,
  "data": {
    "orderNo": "TESTA20260815180326173",
    "orderStatus": 2,
    "paxTicketInfos": [{
      "name": "TEST/ONE", "passengerType": 0, "birthday": "...",
      "gender": "M", "nationality": "ID",
      "cardNum": "...", "cardType": "PP", "cardExpired": "...",
      "cardIssuePlace": "",
      "airlinePNRs": ["S46659"],
      "ticketNos": ["S46659"],
      "ancillaries": []
    }]
  }
}
```

Delivered as `POST`, `Content-Type: application/json;charset=UTF-8`,
`User-Agent: ... Hutool`, source IP in Singapore.

### Four things this proves

**1. Event type is a dotted string in `type`.** `order.ticketed` observed.
Route on `type`. The Schedule Change event name is not yet observed but
will follow this convention.

**2. `status: -1` on a SUCCESSFUL event.** Webhook `status` does **not**
carry the API's `status: 0 == success` semantics. Do not gate webhook
handling on `status == 0` — a correct ticketing notification arrived with
`-1`.

**3. `orderStatus` type differs between surfaces.** The webhook sends
integer `2`. `queryOrderDetails.do` returns string `"1"`. Normalise on
ingest or comparisons will silently fail.

Partial enum, inferred from observation:
`orderStatus 1` = paid, not ticketed. `orderStatus 2` = ticketed.

**4. The webhook is UNAUTHENTICATED.** No signature header, no HMAC, no
shared secret — only `cid` in the body, which is not a secret. Anyone who
learns the URL can post a forged event.

This makes P-05 a security requirement, not only a correctness one.
Antabay MUST treat every inbound webhook as an untrusted hint and confirm
the claim against `queryOrderDetails.do` before changing journey state.
The event says *look again*; the API says *what is true*.

### Timing

Paid 10:03:36 UTC, `order.ticketed` received 10:04:11 UTC — about
**35 seconds**. Ticketing completed after the newman run had finished, so
the in-run retrieve step still showed `ticketStatus "0"` and empty
`ticketNos`, in both runs. Confirmed twice: **paid is not ticketed.**

### Implication for the injector (spec 008)

The injector emits an envelope of exactly this shape with a schedule-change
`type`, into the same receiver. Structure is observed, not invented. It
remains labelled as simulated per P-13, and all flight data stays real.

## 8. Fixtures

The raw verified response is committed at `fixtures/atlas/sel_tyo_search.json`
(credentials and opaque identifiers redacted). This is the seed for Tier 1
recorded end-to-end tests. Per the constitution, fixtures are captured from
live sandbox runs and never handwritten.

## 9. Error codes — VERIFIED

| Code | Meaning | Antabay behaviour |
|---|---|---|
| `0` | success | proceed |
| `318` | duplicate booking, same passenger + flight | **read `duplicateOrders[]`, query that order, resume from its real state — never retry** |
| `800` | order not exists | treat as a bug in our own state, not a retryable condition |
| `900` | auth failed | credentials or account problem, do not retry |

`318` is the important one. Atlas enforces idempotency server-side and
returns the existing order number in `duplicateOrders`. P-06 is therefore
implementable directly: on `318`, reconcile against the returned order.

Observed: a repeat of the same passenger and flight returned
`status 318`, `duplicateOrders: ["TESTA20260815172246746"]`, and every
other field null.

## 10. Not yet verified — do not build against

- The Schedule Change event's `type` string and `data` shape
- Full enum values for `orderStatus` and `ticketStatus`
- Whether void/refund are enabled on hackathon credentials
- Sandbox balance level and how it is topped up
- Whether schedule-change events can be triggered in sandbox at all
