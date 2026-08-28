# Contract: Booking Service (internal, exposed)

**Feature**: 005-booking-path
**Type**: Internal service interface — consumed by whatever orchestrates
the journey (the agent loop), not by an external caller
**Consumed by**: The agent loop, after a `VerificationResult` with
`outcome` in `{VERIFIED, PRICE_CHANGED}` exists for the journey's selected
option (spec 004's output — this feature's precondition)

---

## Operation: CreateOrder

**Preconditions**: A verified session exists for the journey (spec 004's
`VerificationResult`), with its session `held_identifiers` freshness
window not yet expired.

**Inputs**: `journey_id`, `option_id`.

**Behaviour**:
1. Checks the session's freshness window (FR-014). If already expired,
   refuses to attempt order creation and raises a distinct expired-session
   condition — no `Order` row is created, no HTTP call is made.
2. Builds the request from the session's `sessionId` (unmodified, FR-001)
   and the passenger/contact fields per the requirements recorded at
   verification (FR-002).
3. Persists an `Order` row regardless of outcome (NFR-002).
4. On `CREATED`: begins the ticketing-deadline freshness window
   (research.md R2).
5. On `DUPLICATE_REJECTED`: reads `duplicateOrders` (raising an anomaly if
   it contains more than one entry, research.md R8), queries the
   referenced order via `queryOrderDetails.do`, and returns the resulting
   real state rather than reporting failure (FR-006).
6. On `UNCERTAIN` (no response, or unparseable response): re-attempts
   order creation once (research.md R3). The retry's own outcome is
   handled recursively by this same behaviour list — including the
   possibility that *it* is also uncertain, in which case the caller
   receives an `UNCERTAIN` `Order` and must decide whether to invoke
   `CreateOrder` again.

**Outputs**: The persisted `Order` (see data-model.md).

**Error conditions**:

| Condition | Behaviour |
|---|---|
| Session freshness window already expired | Raises an expired-session error before any HTTP call is made (FR-014) |
| No verified session exists at all for the journey | Raises before any HTTP call — a caller error, not an Atlas condition |
| `duplicateOrders` contains more than one entry | Raises an anomaly condition rather than resolving automatically (research.md R8) |

## Operation: SubmitPayment

**Preconditions**: An `Order` with `outcome = CREATED` (or a
`DUPLICATE_REJECTED` order already resolved to a real `CREATED`-equivalent
state via `CreateOrder`'s own handling) exists for the journey.

**Inputs**: `journey_id`, `order_no`.

**Behaviour**:
1. Refuses to proceed if no qualifying order exists (FR-008).
2. Submits `pay.do` for `order_no`.
3. Persists a `PaymentAttempt` row regardless of outcome (NFR-002).
4. On `SUCCESS`: records the outcome only — does not itself confirm
   ticketing or change `JourneyState` (FR-009).
5. On `DECLINED`: records the outcome; this feature does not attempt
   payment again for this `order_no` under any circumstance (FR-013). The
   caller must obtain a new order (via a separate feature) before trying
   again.
6. On `UNCERTAIN`: does **not** resubmit payment. The caller is expected
   to invoke `ConfirmTicketing` (or a lighter one-shot order query) to
   establish whether payment actually went through before deciding on any
   next step (FR-007).

**Outputs**: The persisted `PaymentAttempt`.

**Error conditions**:

| Condition | Behaviour |
|---|---|
| No qualifying `Order` exists for the journey | Raises before any HTTP call (FR-008) |
| A `DECLINED` `PaymentAttempt` already exists for `order_no` | Raises — this operation refuses to be called again for the same order (FR-013) |

## Operation: ConfirmTicketing

**Inputs**: `journey_id`, `order_no`, `now` (for deadline evaluation).

**Behaviour**: Queries `queryOrderDetails.do` for `order_no`, persists a
`TicketingQuery` row (NFR-002, extended per plan.md to cover queries),
and:
- If every passenger's `ticketNos[]` is non-empty: sets `confirmed = True`
  and transitions the journey `VERIFIED → MONITORING` (FR-012). Returns.
- If the response carries a non-null `errorCode`: sets
  `is_terminal_error = True`. Returns without transitioning the journey.
- If `now` has passed the order's ticketing-deadline freshness window:
  stops (does not query again) and returns the last `TicketingQuery`
  without transitioning the journey (FR-011).
- Otherwise: this single call returns a not-yet-confirmed
  `TicketingQuery`; the caller is expected to call `ConfirmTicketing`
  again later (the polling cadence itself is an orchestration concern,
  out of scope for this operation's contract).

**Outputs**: The persisted `TicketingQuery` for this call.

**Error conditions**:

| Condition | Behaviour |
|---|---|
| No `Order` with `outcome = CREATED` exists for `order_no` | Raises — nothing to confirm |

---

## Relationship to FR-011's "continue querying"

`ConfirmTicketing` is a single query-and-evaluate operation, not the loop
itself — mirroring `VerificationService.needs_reverification()`'s
single-check contract from spec 004. The orchestrator (the agent loop) is
expected to call it repeatedly until it returns a `confirmed` or
`is_terminal_error` result, or until it independently observes the
ticketing-deadline window has elapsed and stops calling at all.
