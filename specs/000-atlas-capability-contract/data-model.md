# Data Model: Atlas Capability Contract

**Feature**: 000-atlas-capability-contract
**Date**: 2026-08-28
**Source of truth**: `.antabay/atlas-capability-map.md` (verified 2026-08-15)

All entities below are derived from observed sandbox responses. No field
is invented. Fields not present in the capability map are excluded.

---

## Entity Map

```
EndpointAllowlist
  └─ contains ──→ AllowedEndpoint

AllowedEndpoint
  └─ has request ──→ [typed model per endpoint]
  └─ has response ──→ [typed model per endpoint]

OpaqueId  (wraps: routingIdentifier, sessionId, orderNo, fid, pnrCode)

SearchRequest ──→ SearchResponse
  └─ contains ──→ Routing[]
       └─ contains ──→ Segment[]
       └─ contains ──→ Rule
       └─ has ──→ FreshnessWindow (offer clock)

VerifyRequest ──→ VerifyResponse
  └─ contains ──→ Routing (same shape)
  └─ contains ──→ PriceChange
  └─ contains ──→ BookingRequirement
  └─ has ──→ FreshnessWindow (session clock)

OrderRequest ──→ OrderResponse
  └─ has ──→ FreshnessWindow (ticket clock — tktLimitTime)

PayRequest ──→ PayResponse

QueryOrderRequest ──→ QueryOrderResponse
  └─ has normalised ──→ OrderStatus (IntEnum)

WebhookEvent
  └─ has normalised ──→ OrderStatus (IntEnum)

CanonicalPrice  (value object — output of canonical_total_price())

ErrorCode  (enum)
  └─ mapped to ──→ ErrorDisposition (retryable | reconcilable | terminal)

ReconcilableOutcome
  └─ carries ──→ duplicate_orders: list[OpaqueId]

CallRecord  (append-only telemetry)

CallBudget
  └─ tracks per journey per endpoint ──→ call count vs declared limit

RateLimitHold
  └─ carries ──→ retry_after: datetime | None

FreshnessWindow
  └─ clock_type: offer | session | ticket
  └─ issued_at: datetime
  └─ expires_at: datetime | None
```

---

## Entities

### EndpointAllowlist

The complete set of endpoints the system is permitted to call.
Checked at import time via Mypy; any symbol not in this list cannot be
imported from `backend/atlas/allowlist.py`.

| Field | Type | Notes |
|-------|------|-------|
| `endpoints` | `frozenset[AllowedEndpoint]` | Immutable at runtime |

### AllowedEndpoint

One permitted endpoint entry.

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | e.g. `"search.do"` |
| `path` | `str` | relative path on sandbox base URL |
| `verification_status` | `Literal["verified", "unverified"]` | Unverified endpoints must not be called by production paths |

**Verified endpoints** (exercised end-to-end):
`search.do`, `verify.do`, `order.do`, `pay.do`, `queryOrderDetails.do`,
`updateWebhookURL.do`

**Listed but unverified** (in allowlist; schemas pending):
`getOffers.do`, `getOfferPrice.do`, `seatAvailability.do`, `getLuggage.do`,
`createRefundRecord.do`, `queryRefund.do`, `void.do`, `queryIncident.do`,
`queryBalance.do`

---

### OpaqueId

A wrapper for any externally issued identifier. Provides equality comparison
and passthrough; provides no string-manipulation, parsing, or construction API.

Covers: `routingIdentifier`, `sessionId`, `orderNo`, `fid`, `pnrCode`,
`ticketNo`, `airlinePNR`.

| Field | Type | Notes |
|-------|------|-------|
| `_value` | `str` | Private; not accessible via attribute access outside the wrapper |

**Operations permitted**: `==`, `!=`, pass to HTTP client.
**Operations prohibited**: substring, split, join, format, regex match,
len, construction from components.

---

### SearchRequest

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `cid` | `str` | yes | Client ID from credentials |
| `trip_type` | `Literal["1", "2"]` | yes | `"1"` one-way, `"2"` return |
| `adult_num` | `int` | yes | ≥ 1 |
| `child_num` | `int` | yes | ≥ 0 |
| `infant_num` | `int` | yes | ≥ 0 |
| `from_city` | `str` | yes | IATA city code |
| `to_city` | `str` | yes | IATA city code |
| `from_date` | `str` | yes | `YYYYMMDD` |
| `currency` | `Literal["USD"]` | yes | Must be `"USD"` in sandbox |
| `request_source` | `Literal["antabay"]` | yes | Fixed string |
| `ret_date` | `str \| None` | conditional | Required when `trip_type == "2"` |
| `from_airport` | `str \| None` | no | IATA airport code |
| `to_airport` | `str \| None` | no | IATA airport code |
| `airlines` | `list[str] \| None` | no | Carrier codes; omit for all |
| `include_multiple_fare_family` | `bool \| None` | no | |

---

### SearchResponse

| Field | Type | Notes |
|-------|------|-------|
| `routings` | `list[Routing]` | May be empty |
| `status` | `int` | `0` = success; assert on this, not only HTTP 200 |
| `msg` | `str \| None` | |
| `request_id` | `str \| None` | |
| `client_request_id` | `str \| None` | |

---

### Routing

Represents one flight option. Used in both search and verify responses
(same shape; `refresh_time` and `expire_time` are `null` in verify).

| Field | Type | Notes |
|-------|------|-------|
| `fid` | `OpaqueId` | Routing identity — preserve exactly |
| `routing_identifier` | `OpaqueId` | Required by verify — preserve exactly |
| `currency` | `Literal["USD"]` | |
| `adult_price` | `Decimal` | Base fare |
| `adult_tax` | `Decimal` | Tax component |
| `transaction_fee_per_pax` | `Decimal` | Fee (0.00 observed) |
| `from_segments` | `list[Segment]` | Length > 1 means connection |
| `ret_segments` | `list[Segment]` | Empty for one-way |
| `seat_count` | `int \| None` | Per-segment; scarcity signal |
| `risk_sellout` | `bool` | Atlas's own sellout risk flag |
| `refresh_time` | `datetime \| None` | `null` in verify response |
| `expire_time` | `datetime \| None` | `null` in verify response |
| `separate_bookings` | `bool` | `true` = legs not protected together |
| `rule` | `Rule` | Baggage and fare rules |
| `ancillary_supported` | `list[str]` | e.g. `["seat", "luggage"]` |
| `support_credit_trans_payment` | `Literal["0", "1"]` | `"0"` = balance/VCC only |

**Note**: `Decimal` is used (not `float`) for monetary fields to avoid
floating-point representation errors in price comparisons.

---

### Segment

| Field | Type | Notes |
|-------|------|-------|
| `segment_index` | `int` | |
| `carrier` | `str` | IATA carrier code |
| `flight_number` | `str` | |
| `dep_airport` | `str` | IATA |
| `dep_time` | `str` | `YYYYMMDDHHMM` local airport time |
| `arr_airport` | `str` | IATA |
| `arr_time` | `str` | `YYYYMMDDHHMM` local airport time |
| `stop_cities` | `str \| None` | |
| `duration` | `int` | Minutes |
| `code_share` | `bool` | |
| `cabin_class` | `str` | |
| `seat_count` | `int` | Remaining seats |
| `aircraft_code` | `str \| None` | |
| `fare_family` | `str \| None` | |

---

### Rule

| Field | Type | Notes |
|-------|------|-------|
| `has_baggage` | `bool` | |
| `baggage_elements` | `list[BaggageElement]` | Included allowance |
| `refund_rules` | `list[FareRule]` | Time-banded refund fees |
| `changes_rules` | `list[FareRule]` | Time-banded change fees |

**Currency warning**: `refund_rules` and `changes_rules` amounts may be in
IDR (observed on JKT→SUB route) even when the fare is in USD. These amounts
must never be combined with fare amounts without explicit conversion.
Currency normalisation is out of scope for this feature.

---

### VerifyRequest

| Field | Type | Notes |
|-------|------|-------|
| `routing_identifier` | `OpaqueId` | Byte-for-byte from search |
| `max_response_time` | `int \| None` | `null` in observed requests |
| `request_source` | `Literal["antabay"]` | |

---

### VerifyResponse

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | `OpaqueId` | Required for order; preserve exactly |
| `max_seats` | `int` | Max bookable (7 observed) |
| `routing` | `Routing` | Same shape; `refresh_time` and `expire_time` are `null` |
| `booking_requirement` | `BookingRequirement` | Passenger field schema |
| `price_change` | `PriceChange` | |
| `status` | `int` | |
| `msg` | `str \| None` | |

### PriceChange

| Field | Type | Notes |
|-------|------|-------|
| `is_price_change` | `bool` | When `true`, prior authorisation is void |
| `original_adult_price` | `Decimal` | |
| `new_adult_price` | `Decimal` | |
| `original_adult_tax` | `Decimal` | |
| `new_adult_tax` | `Decimal` | |

---

### OrderRequest

| Field | Type | Notes |
|-------|------|-------|
| `cid` | `str` | |
| `session_id` | `OpaqueId` | From verify — preserve exactly |
| `passengers` | `list[Passenger]` | |
| `contact` | `Contact` | |
| `request_source` | `Literal["antabay"]` | |

### Passenger

Fields derived from `bookingRequirement.passenger` (runtime schema):

| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | yes |
| `birthday` | `str` | yes (`YYYYMMDD`) |
| `gender` | `Literal["M", "F"]` | yes |
| `nationality` | `str` | yes (ISO 3166-1 alpha-2) |
| `passenger_type` | `int` | yes (`0` adult) |
| `card_num` | `str \| None` | no |
| `card_type` | `str \| None` | no |
| `card_issue_place` | `str \| None` | no |
| `card_expired` | `str \| None` | no |

### OrderResponse

| Field | Type | Notes |
|-------|------|-------|
| `order_no` | `OpaqueId` | Primary order identifier |
| `pnr_code` | `OpaqueId` | PNR — not a ticket |
| `total_price` | `Decimal` | |
| `total_transaction_fee` | `Decimal` | |
| `currency` | `str` | |
| `tkt_limit_time` | `datetime` | Ticket deadline clock — 30 min observed |
| `duplicate_orders` | `list[OpaqueId]` | Non-empty on error 318 |
| `status` | `int` | |
| `msg` | `str \| None` | |

---

### PayRequest / PayResponse

**PayRequest**:

| Field | Type | Notes |
|-------|------|-------|
| `cid` | `str` | |
| `order_no` | `OpaqueId` | From order response |
| `request_source` | `Literal["antabay"]` | |

No card details. Payment is from Atlas balance.

**PayResponse**:

| Field | Type | Notes |
|-------|------|-------|
| `order_no` | `OpaqueId` | |
| `pnr_code` | `OpaqueId` | |
| `payment_method` | `int` | `1` = balance |
| `airlines` | `list[str]` | |
| `status` | `int` | `0` = accepted; NOT proof of ticketing |
| `msg` | `str \| None` | |

---

### QueryOrderRequest / QueryOrderResponse

**QueryOrderRequest**:

| Field | Type | Notes |
|-------|------|-------|
| `cid` | `str` | |
| `order_no` | `OpaqueId` | |
| `request_source` | `Literal["antabay"]` | |

**QueryOrderResponse** (key fields):

| Field | Type | Notes |
|-------|------|-------|
| `order_status` | `OrderStatus` | Normalised from string on ingest |
| `ticket_status` | `str` | `"0"` unticket, observed after payment |
| `pax_ticket_infos` | `list[PaxTicketInfo]` | |
| `pay_time` | `datetime \| None` | |
| `tkt_limit_time` | `datetime \| None` | |
| `error_code` | `str \| None` | |
| `error_message` | `str \| None` | |
| `status` | `int` | |
| `msg` | `str \| None` | |

### PaxTicketInfo

| Field | Type | Notes |
|-------|------|-------|
| `name` | `str` | |
| `ticket_nos` | `list[OpaqueId]` | Non-empty = proof of ticketing |
| `airline_pnrs` | `list[OpaqueId]` | |

**Rule**: `ticketNos` non-empty is the only accepted proof of ticketing.
`ticketStatus "0"` with empty `ticketNos` was observed after a successful
`pay.do` call. Downstream code MUST NOT treat payment as ticketing.

---

### WebhookEvent

Inbound push notification from Atlas. Unauthenticated — treat as an
untrusted hint; confirm all claims against `queryOrderDetails.do`.

| Field | Type | Notes |
|-------|------|-------|
| `cid` | `str` | Client ID (not a secret) |
| `type` | `str` | Dotted event name e.g. `"order.ticketed"` |
| `status` | `int` | `-1` observed on a SUCCESSFUL ticketing event — do NOT gate on `== 0` |
| `data` | `WebhookData` | |

### WebhookData

| Field | Type | Notes |
|-------|------|-------|
| `order_no` | `OpaqueId` | |
| `order_status` | `OrderStatus` | Normalised from integer on ingest |
| `pax_ticket_infos` | `list[PaxTicketInfo]` | |

---

### OrderStatus (IntEnum)

Normalised order status. Ingest converts both the string form (REST) and
the integer form (webhook) to this enum.

| Value | Name | Source of truth |
|-------|------|----------------|
| `1` | `PAID_NOT_TICKETED` | Observed; REST returns `"1"`, webhook returns `1` |
| `2` | `TICKETED` | Observed; webhook only in captured data |

Unknown integer values are preserved as their integer representation via
`_missing_` fallback. The full enum is not yet verified.

---

### CanonicalPrice

Value object returned by `canonical_total_price()`.

| Field | Type | Notes |
|-------|------|-------|
| `amount` | `Decimal` | `adult_price + adult_tax + transaction_fee_per_pax` |
| `currency` | `Literal["USD"]` | Always USD in sandbox |

**Invariant**: This is the only object in the codebase that carries a
computed price total. No other code path may sum these three fields.

---

### ErrorCode / ErrorDisposition

| Code | Name | Disposition | Behaviour |
|------|------|-------------|-----------|
| `0` | `SUCCESS` | — | Proceed |
| `318` | `DUPLICATE_BOOKING` | `reconcilable` | Read `duplicate_orders`; do not retry |
| `800` | `ORDER_NOT_EXISTS` | `terminal` | Local state bug; do not retry |
| `900` | `AUTH_FAILED` | `terminal` | Credentials problem; do not retry |
| `_unknown_` | — | `terminal` | Default; do not retry |

### ReconcilableOutcome

Returned when `ErrorCode.DUPLICATE_BOOKING` is classified.

| Field | Type | Notes |
|-------|------|-------|
| `error_code` | `ErrorCode` | Always `DUPLICATE_BOOKING` |
| `duplicate_orders` | `list[OpaqueId]` | Existing order references from Atlas |

---

### CallRecord

Append-only telemetry record for every external call (FR-009).

| Field | Type | Notes |
|-------|------|-------|
| `endpoint` | `str` | e.g. `"search.do"` |
| `outcome` | `int` | Atlas status code or HTTP error code |
| `elapsed_ms` | `int` | Wall-clock milliseconds |
| `journey_id` | `str` | Correlation key |
| `recorded_at` | `datetime` | UTC |

---

### CallBudget

Per-journey, per-endpoint call counter enforcing declared rate limits (FR-010).

| Field | Type | Notes |
|-------|------|-------|
| `journey_id` | `str` | |
| `endpoint` | `str` | |
| `limit` | `int` | Declared maximum for this endpoint/journey |
| `used` | `int` | Incremented on each call |

**Declared limits** (from capability map):

| Endpoint(s) | Limit | Window |
|------------|-------|--------|
| `search.do` | 10 | per second |
| `verify.do`, `getOffers.do` | 60 | per minute (shared) |
| `seatAvailability.do`, `getLuggage.do` | 60 | per minute (shared) |

### RateLimitHold

Produced when a rate-limit rejection is received.

| Field | Type | Notes |
|-------|------|-------|
| `endpoint` | `str` | |
| `retry_after` | `datetime \| None` | `None` = indefinite hold |

**Invariant**: No call may be initiated while a `RateLimitHold` is active
for the same endpoint and `retry_after` is in the future (or `None`).

---

### FreshnessWindow

Tracks the usable lifetime of a held offer or session (FR-012).

| Field | Type | Notes |
|-------|------|-------|
| `clock_type` | `Literal["offer", "session", "ticket"]` | |
| `issued_at` | `datetime` | When the offer/session/order was received |
| `expires_at` | `datetime \| None` | `None` = expiry unknown (session clock when no explicit field) |

**Three clock instances per journey**:

| Clock | Field | Observed range |
|-------|-------|---------------|
| `offer` | `routing.expire_time` | 7 min 43 s to 31 min; may arrive pre-aged |
| `session` | `sessionId` TTL | Documented up to 2 h; no explicit timestamp in response |
| `ticket` | `tkt_limit_time` | 30 min (observed) |

**Invariant**: Any business action on a held identifier MUST check
`FreshnessWindow.is_usable(now)` before proceeding.

---

## State Transitions (Freshness)

```
search.do response received
  └─→ FreshnessWindow(clock_type="offer", expires_at=routing.expire_time)
        └─→ if expires_at < now: REJECT offer before any action
        └─→ verify.do called before expiry
              └─→ FreshnessWindow(clock_type="session", expires_at=None)
                    └─→ order.do called within session window
                          └─→ FreshnessWindow(clock_type="ticket",
                                              expires_at=tkt_limit_time)
                                └─→ pay.do + queryOrderDetails.do before tkt_limit_time
```

---

## Traceability Matrix

| Requirement | Entity / Function | Test file |
|-------------|------------------|-----------|
| FR-001 | `EndpointAllowlist` | `test_allowlist.py` |
| FR-002 | `AllowedEndpoint`, Mypy gate | `test_allowlist.py` |
| FR-003 | All Pydantic models | `test_models.py` |
| FR-004 | `OpaqueId` | `test_identifiers.py` |
| FR-005 | `canonical_total_price()`, `CanonicalPrice` | `test_pricing.py` |
| FR-006 | `OrderStatus` (IntEnum), webhook/query normalisation | `test_models.py` |
| FR-007 | `ErrorCode`, `ErrorDisposition` | `test_errors.py` |
| FR-008 | `ReconcilableOutcome` | `test_errors.py` |
| FR-009 | `CallRecord` | `test_telemetry.py` |
| FR-010 | `CallBudget` | `test_budget.py` |
| FR-011 | `RateLimitHold` | `test_budget.py` |
| FR-012 | `FreshnessWindow` | `test_freshness.py` |
| NFR-001 | Mypy strict gate in CI | `test_allowlist.py` (build check) |
| NFR-002 | CI workflow definition | CI config |
| NFR-003 | pytest-recording, no handwritten fixtures | `conftest.py` |
