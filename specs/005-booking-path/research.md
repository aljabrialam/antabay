# Research: Order Creation and Payment

## R1 — JourneyState additions

**Decision**: Add a single new `JourneyState.MONITORING` value. Add one new
transition: `VERIFIED → MONITORING`, triggered only by FR-012 (ticketing
confirmed). No intermediate transient states ("ordering", "paying",
"awaiting ticketing") are added.

**Rationale**: This mirrors spec 004's own R5 decision exactly: `order.do`
and `pay.do` are synchronous calls in this codebase's established pattern
(`FlightSearchService.search()`, `VerificationService.verify()`) — there
is no observable interval during which the journey is meaningfully
"ordering" as opposed to "about to call" or "just called." The one
genuinely observable interval this feature introduces — the ticketing
query loop (FR-011), which can run for up to the `tktLimitTime` window —
is tracked by the *persisted `ticketing_queries` rows and the
ticketing-deadline freshness window*, not by `JourneyState`. This keeps
`JourneyState` answering "what phase is the journey in" while the
lower-level "has this specific thing happened yet" questions are answered
by querying the relevant table, exactly as `VERIFIED` doesn't distinguish
"has a `held_identifiers` session row" from "hasn't" — a caller checks the
table for that.

**Alternatives considered**:
- *Add `ORDERED` and `PAID` intermediate states*: rejected — nothing in
  the spec's acceptance scenarios needs to observe the journey mid-order
  or mid-payment as a distinct *state machine* fact; FR-003/FR-008's
  requirements are satisfied by the persisted `Order`/`PaymentAttempt`
  rows existing, not by a state transition.
- *Transition back to `SEARCHING` on an expired-session refusal (FR-014)
  or a payment decline (FR-013)*: rejected — both FRs explicitly describe
  only *refusing the attempt* and *surfacing a distinct condition*; FR-013
  goes further and explicitly states that returning to an earlier state
  is "out of scope for this feature to define." Inventing either
  transition here would exceed what the spec asked for and encroach on a
  future recovery feature's territory (Constitution Principle XVI, Single
  Capability).

## R2 — Ticketing deadline as a third freshness window

**Decision**: Reuse `held_identifiers` again (as 004's R1 already did for
the session window) for the ticketing deadline (`tktLimitTime`). A new row
is added when an order is created successfully, with `value` set to the
order's `orderNo` and `stale_after_seconds` computed as
`(tktLimitTime - now).total_seconds()` at the moment the order response is
read.

**Rationale**: `tktLimitTime` is Atlas's own absolute deadline, observed
as a 30-minute window (17:22:46 → 17:52:46) in the capability map — the
same shape of fact as the offer's `expireTime` and the session's
documented ~2h ceiling. `held_identifiers` already generically models
"an identifier with a known expiry"; this is the third and, per the
capability map's own "three clocks, not one" framing, final phase in the
chain (offer → session → ticketing deadline). Reusing it means 006's
console — which already renders `held_identifiers` as expiry clocks —
picks up the ticketing-deadline clock for free, the same benefit 004's R1
called out for the session clock.

**Alternatives considered**:
- *Store `tktLimitTime` only as a column on the `orders` row*: rejected —
  would require a second, parallel freshness-checking code path alongside
  `held_identifiers`' existing `is_stale(now)` / `check_identifier_freshness`
  machinery, duplicating logic for no benefit.

## R3 — Order-creation timeout reconciliation (spec Clarifications, Q1)

**Decision**: Confirmed by the spec's own clarification — implemented as:
on an uncertain order-creation outcome, re-attempt `order.do` with the
same request. If Atlas returns a duplicate rejection (`duplicateOrders`
non-empty), read the referenced order and resume from its queried state.
If the retry succeeds outright, no prior order existed.

**Rationale**: The capability map states plainly that "Atlas enforces
idempotency server-side and returns the existing order number in
`duplicateOrders`" — this is what makes retrying order creation specifically
(and only order creation, not payment) a safe reconciliation mechanism
rather than a blind repeat forbidden by FR-007/NFR-001.

**Alternatives considered**: None beyond what the spec's clarification
already ruled out (see spec.md Clarifications, Q1) — this section exists
to record the source-grounded reasoning of *why* the answer is safe, not
to re-litigate the choice.

## R4 — Payment outcome model, including the uncertain/timeout case

**Decision**: `PaymentAttempt.outcome` is one of `SUCCESS`, `DECLINED`,
`UNCERTAIN` (no response received, or an unparseable/unexpected response),
or `ERROR` (a recognisable non-success response). A `DECLINED` outcome is
terminal for that order per FR-013 — no retry. An `UNCERTAIN` outcome is
resolved exclusively by querying the order via `queryOrderDetails.do`
(never by resubmitting `pay.do`), per FR-007.

**Rationale**: Payment, unlike order creation, always has an order
reference to query by the time it is attempted (FR-008 guarantees an
order already exists) — so unlike R3, there is no structural reason
payment ever needs a "retry as reconciliation" path. The capability map
gives no observed decline-response shape for the verified balance-payment
path (`paymentMethod: 1`); the documented `Reject`/`Three DS` cardholder
simulations are explicitly for a different, unused VCC path (§6). A
decline is therefore detected generically — a recognisable non-success
`pay.do` response — rather than against any specific undocumented error
code.

**Alternatives considered**:
- *Treat "declined" and "uncertain" as the same case*: rejected — a
  decline is a certain, known outcome (the spec's own Clarification Q2
  distinguishes this explicitly); collapsing them would make FR-013's "no
  retry, ever" and FR-007's "resolve via query first" indistinguishable in
  behaviour, when the spec requires them to differ.

## R5 — Multi-passenger ticketing confirmation (spec Clarifications, Q4)

**Decision**: `TicketingQuery.confirmed` is `True` only when every
`paxTicketInfos[]` entry in the response has a non-empty `ticketNos`
array. `BookingService.confirm_ticketing()`'s polling loop keeps going as
long as `confirmed` is `False`, subject to the deadline/terminal-error
stop conditions (FR-011).

**Rationale**: Directly from the spec's own clarification. No further
reasoning needed beyond what's recorded there — this section exists so
`data-model.md`'s validation rule for `TicketingQuery` has a research
citation.

## R6 — Terminal error definition for the ticketing query loop

**Decision**: A `queryOrderDetails.do` response is treated as a terminal
error, stopping the polling loop (FR-011), specifically when it carries a
non-null `errorCode`. Any other response — regardless of what
`orderStatus`/`ticketStatus` say, per spec.md's own edge case on their
unmapped enums — is treated as "not yet ticketed" and polling continues
until the deadline.

**Rationale**: `errorCode` and `errorMessage` are explicitly documented,
verified response fields on `queryOrderDetails.do` (capability map §7b) —
this is the one concrete, source-grounded signal available, in contrast
to the unmapped `orderStatus`/`ticketStatus` enums the spec explicitly
says not to rely on. No specific `errorCode` values have been captured
yet (capability map §10, "not yet verified"), so this decision treats
*any* non-null value as terminal rather than trying to distinguish
recoverable from unrecoverable codes prematurely — the conservative
direction, consistent with how 004's R3 handled an equally undocumented
"unavailable" condition for `verify.do`.

**Alternatives considered**:
- *Treat only specific known `errorCode` values as terminal, and retry-poll
  through unknown ones*: rejected — no `errorCode` values are captured
  yet at all; there is nothing to build an allowlist from without
  guessing, which Constitution Principle I forbids.

## R7 — No call-budget interaction for this feature's endpoints

**Decision**: `BookingService` does not call
`JourneyRepository.decrement_call_budget()` for `order.do`, `pay.do`, or
`queryOrderDetails.do`, and does not persist `budget_before`/`budget_after`
on `Order`/`PaymentAttempt`/`TicketingQuery` rows.

**Rationale**: The capability map's rate-limit section (§6) documents a
shared QPM/QPS allowance only for `search.do`, `verify.do`, and
`getOffers.do`/`seatAvailability.do`/`getLuggage.do`. It says nothing
about `order.do`/`pay.do`/`queryOrderDetails.do`. Inventing a budget
interaction for endpoints the source material is silent on would violate
Principle I (Truth Over Fluency) — this is a case where the *absence* of
a documented constraint is itself the fact to preserve, not a gap to fill
with an assumed default.

**Alternatives considered**:
- *Apply the same budget mechanism defensively, in case one exists*:
  rejected — would silently decrement a budget for calls the capability
  map gives no basis to believe are constrained by it, and could produce
  a `BudgetExhaustedError` on a code path that should never raise one.

## R8 — Multiple duplicate-order references

**Decision**: If `duplicateOrders` contains more than one entry (the
verified capture shows exactly one), `BookingService` raises an anomaly
condition rather than selecting the first entry or attempting to
reconcile against all of them.

**Rationale**: Directly from spec.md's own edge case: "this condition is
itself anomalous and must be surfaced rather than silently resolved by
picking one." Silently picking `duplicateOrders[0]` would violate Truth
Over Fluency by acting on an assumption the source data has never
demonstrated is correct.
