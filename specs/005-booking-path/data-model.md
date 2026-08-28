# Data Model: Order Creation and Payment

## Entities

### Order

The persisted record of one `order.do` attempt. One row per attempt —
including the retry that reconciles an uncertain outcome (research.md R3)
— so the audit trail (NFR-002) shows every attempt, not just the one that
stuck.

| Field | Type | Notes |
|---|---|---|
| `order_id` | string (UUID) | Primary key (internal, not Atlas's) |
| `journey_id` | string | FK → `journeys.journey_id` |
| `option_id` | string | FK → `flight_options.option_id` — the verified option being booked |
| `requested_at` | datetime (ISO-8601 UTC) | |
| `responded_at` | datetime \| null | Null only if no response was ever received (the uncertain-outcome case, R3) |
| `raw_response_json` | text \| null | Full, unmodified `order.do` response body; null only alongside `responded_at` being null (NFR-002) |
| `outcome` | enum | `CREATED` \| `DUPLICATE_REJECTED` \| `UNCERTAIN` \| `ERROR` |
| `order_no` | string \| null | Atlas's `orderNo`; set on `CREATED`, or on `DUPLICATE_REJECTED` after the referenced order is read (FR-001, FR-003) |
| `booking_reference` | string \| null | Atlas's `pnrCode`; set only on `CREATED` (FR-003, FR-004 — never treated as ticketing evidence) |
| `ticketing_deadline` | datetime \| null | Atlas's `tktLimitTime`, parsed; set only on `CREATED` (FR-005) |
| `session_id_used` | string | The verified session's `sessionId`, exactly as sent (FR-001) — recorded for audit even though it is also held elsewhere |

**`outcome` values**:

| Value | Meaning | Triggers |
|---|---|---|
| `CREATED` | Order created successfully | `booking_reference`, `ticketing_deadline` recorded; ticketing-deadline freshness window begins (R2) |
| `DUPLICATE_REJECTED` | Atlas rejected as a duplicate, `duplicateOrders` non-empty | The referenced order is queried (via `queryOrderDetails.do`) and the journey resumes from its real state (FR-006) |
| `UNCERTAIN` | No response received, or response unparseable | Triggers the R3 reconciliation path: retry order creation |
| `ERROR` | A recognisable non-success response that is not a duplicate rejection | Recorded; not retried blindly (FR-007 still applies — an `ERROR` is not automatically "uncertain") |

**Validation rules**:
- `booking_reference` and `ticketing_deadline` MUST be `null` unless
  `outcome` is `CREATED`.
- `sessionId` in the request that produced this row MUST equal,
  byte-for-byte, the session identifier held from the option's most recent
  successful verification (FR-001).
- If `outcome` is `DUPLICATE_REJECTED` and `duplicateOrders` contains more
  than one entry, this MUST be treated as an anomaly (research.md R8), not
  silently resolved by choosing the first.

### PaymentAttempt

The persisted record of one `pay.do` attempt.

| Field | Type | Notes |
|---|---|---|
| `payment_id` | string (UUID) | Primary key |
| `journey_id` | string | FK → `journeys.journey_id` |
| `order_no` | string | The order this payment was submitted for (FR-008 — never submitted without one) |
| `requested_at` | datetime (ISO-8601 UTC) | |
| `responded_at` | datetime \| null | Null only on `UNCERTAIN` |
| `raw_response_json` | text \| null | Full response body; null only alongside `responded_at` (NFR-002) |
| `outcome` | enum | `SUCCESS` \| `DECLINED` \| `UNCERTAIN` \| `ERROR` |

**Validation rules**:
- A `PaymentAttempt` row MUST NOT be created for a journey unless an
  `Order` row with `outcome = CREATED` (or a `DUPLICATE_REJECTED` order
  resolved to a real, queried state) already exists for it (FR-008).
- `outcome = SUCCESS` MUST NOT, by itself, cause any `JourneyState`
  transition or set any ticketing-confirmed flag (FR-009).
- `outcome = DECLINED` MUST NOT be followed by another `PaymentAttempt`
  row for the same `order_no` (FR-013).
- `outcome = UNCERTAIN` MUST be resolved via a `TicketingQuery` (reading
  the order's actual state), never by a repeated `PaymentAttempt` for the
  same `order_no` (FR-007).

### TicketingQuery

The persisted record of one `queryOrderDetails.do` call made while
confirming ticketing. One row per call in the polling loop (FR-011),
enabling audit of exactly when ticket numbers appeared for which
passengers (relevant to the partial-ticketing edge case).

| Field | Type | Notes |
|---|---|---|
| `query_id` | string (UUID) | Primary key |
| `journey_id` | string | FK → `journeys.journey_id` |
| `order_no` | string | The order being queried |
| `queried_at` | datetime (ISO-8601 UTC) | |
| `raw_response_json` | text | Full response body (NFR-002 extended to queries, per plan.md) |
| `order_status` | string \| null | Recorded for audit only — never used to confirm ticketing (unmapped enum, spec.md edge case) |
| `ticket_status` | string \| null | Same caveat as `order_status` |
| `passenger_ticket_numbers` | list[list[string]] | One list per passenger, from each `paxTicketInfos[].ticketNos[]` |
| `confirmed` | bool | `True` only if every passenger's ticket-numbers list is non-empty (FR-010, research.md R5) |
| `is_terminal_error` | bool | `True` if the response carried a non-null `errorCode` (research.md R6) |

**Validation rules**:
- `confirmed` MUST be computed as declared above — never `True` on a
  partial result (some but not all passengers ticketed).
- The polling loop that produces these rows (FR-011) MUST stop after the
  first row with `confirmed = True` or `is_terminal_error = True`, or once
  `now` has passed the order's ticketing-deadline freshness window —
  whichever comes first.

### JourneyState (extends spec 004's enum — one addition)

| Value | New? | Meaning |
|---|---|---|
| `MONITORING` | **Yes** | Ticketing has been confirmed (FR-012); the journey is now in its post-ticketing phase |

**New allowed transition**:

| From | To | Trigger |
|---|---|---|
| `VERIFIED` | `MONITORING` | A `TicketingQuery` row with `confirmed = True` exists for the journey's current order |

No other new transitions are added by this feature — see research.md R1
for why an expired-session refusal (FR-014) and a payment decline
(FR-013) do not themselves cause a `JourneyState` transition here.

### Freshness Windows (reuses `HeldIdentifier`, spec 001/004 — no schema change)

Three rows now exist across a journey's lifecycle, all in the same table:

| Row | `identifier_id` scope | Begins | Ends / retired |
|---|---|---|---|
| Offer window | `routingIdentifier` | at search | superseded at verify (spec 004) |
| Session window | `sessionId` | at successful verify | superseded at order creation (this feature) |
| Ticketing-deadline window | `orderNo` | at successful order creation | ends when ticketing is confirmed or the deadline passes |

**Validation rule**: The ticketing-deadline row is created only on
`Order.outcome = CREATED` (research.md R2); the session-window row from
verification is left as-is (not deleted), preserving the audit trail of
when each phase held, consistent with spec 004's own rule for the
offer→session handoff.

## Relationships

```text
journeys (1) ──< orders (many)              -- retries on uncertain outcome = multiple rows
orders (1) ──< payments (many)              -- normally one, but a payment can be attempted at most once per outcome path
orders (1) ──< ticketing_queries (many)     -- the polling loop
flight_options (1) ──< orders (many)
journeys (1) ──< held_identifiers (many)    -- existing relationship, reused for the third window
```

## Safety Properties Enforced By This Model (traceability to FR/NFR)

- FR-001, FR-002: `Order.session_id_used` and the request that produced it
  are exact copies of held, verified data — no field is constructed here.
- FR-003, FR-004: `booking_reference` exists on the model but no code path
  in this feature reads it as ticketing evidence — only `TicketingQuery.confirmed`
  does.
- FR-005: `ticketing_deadline` is a `held_identifiers` row, not a bare
  column consulted ad hoc — it goes through the same freshness machinery
  as the other two windows.
- FR-006, FR-007: `Order.outcome = DUPLICATE_REJECTED` and `UNCERTAIN` are
  distinct values specifically so the reconciliation logic can be tested
  against each independently.
- FR-008, FR-009, FR-013: enforced as `PaymentAttempt` validation rules
  above.
- FR-010, FR-011, FR-012: enforced as `TicketingQuery` validation rules
  and the `JourneyState` transition table above.
- FR-014: not a persisted fact in this model — evaluated directly against
  the session `held_identifiers` row's freshness at the moment order
  creation is attempted, before any `Order` row is created at all.
