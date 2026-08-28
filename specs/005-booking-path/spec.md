# Feature Specification: Order Creation and Payment

**Feature Branch**: `005-booking-path`

**Created**: 2026-08-28

**Status**: Draft

**Input**: External contract definition sourced from
`.antabay/atlas-capability-map.md` section 7b (order.do, pay.do,
queryOrderDetails.do; verified against the Atlas API sandbox on
2026-08-15).

---

## Business Context

**Business Goal**: Convert a verified option into a booked and ticketed
journey, without ever assuming an outcome that has not been independently
confirmed.

**Business Value**: This is where money moves and where mistakes are
irreversible. Duplicate orders and false confirmations are the two
failures that matter.

**Business Actors**:
- Traveller — the person whose money is spent and whose ticket is issued
- Agent — creates the order, submits payment, and confirms ticketing on
  the traveller's behalf

**Business Capability**: Transaction Execution

**Reference**: `.antabay/atlas-capability-map.md` section 7b records the
verified order.do / pay.do / queryOrderDetails.do contract and is the
input to this feature. This specification governs how that contract is
used to move from a verified option to a confirmed ticket without
assuming any unconfirmed outcome.

---

## Clarifications

### Session 2026-08-28

- Q: When order creation times out with no response, FR-007 says not to repeat it "whose outcome is uncertain," but there's no order reference yet to query directly. How should the outcome be established? → A: Re-attempt order creation; if Atlas rejects it as a duplicate (FR-006's mechanism), that rejection is the independent confirmation that the first attempt succeeded — read the referenced order and resume from it. If it succeeds outright, no prior order existed.
- Q: Payment is declined (a certain, known outcome, not an uncertain one). Is retrying payment against the same order permitted? → A: Never retry payment against an order once declined — the journey must return to an earlier state (e.g. re-verification) before any further payment attempt.
- Q: Should the system check the session hasn't already expired before attempting order creation, or just attempt it and let Atlas's response reveal the problem? → A: Check the session's freshness window before attempting order creation; if already expired, refuse to attempt and surface it as a distinct "session expired" condition rather than sending a doomed request.
- Q: For a multi-passenger booking, is ticketing confirmed when ALL passengers have non-empty ticket numbers, or when ANY do? → A: ALL passengers must have non-empty ticket numbers before ticketing is confirmed and the journey moves to monitoring.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Create Order From a Verified Session (Priority: P1)

The agent creates an order using the session identifier obtained from
verification, forwarded exactly as received. Passenger and contact
details are populated according to the field requirements returned at
verification time — not a fixed form. The resulting order reference and
any booking reference are recorded, but a booking reference alone is
never treated as proof that a ticket has been issued. The order's
ticketing deadline is recorded as its own, distinct expiry.

**Why this priority**: Nothing downstream — payment, ticketing
confirmation — can happen without a created order. This is the entry
point to the entire booking path.

**Independent Test**: Create an order from a verified session and confirm
the order reference, booking reference, and ticketing deadline are all
recorded, and that no part of the system treats the booking reference as
ticketing evidence.

**Acceptance Scenarios**:

1. **Given** a verified session with `sessionId` held from verification,
   **When** the agent creates an order, **Then** that `sessionId` is sent
   byte-for-byte, with no construction, parsing, or alteration.

2. **Given** the passenger requirements recorded at verification time,
   **When** the order request is built, **Then** it populates exactly
   those fields — not a fixed or previously used form.

3. **Given** an order is created successfully, **When** the response is
   read, **Then** the order reference (`orderNo`) and booking reference
   (`pnrCode`) are both recorded, and the ticketing deadline
   (`tktLimitTime`) is recorded as a freshness window distinct from the
   session window it followed.

4. **Given** an order has just been created, **When** any part of the
   system checks whether a ticket exists, **Then** the presence of a
   booking reference alone is never treated as sufficient evidence.

5. **Given** the session's freshness window has already expired, **When**
   order creation is attempted, **Then** the attempt is refused before any
   call is made and the condition is surfaced as an expired session, not
   as an order-creation failure (FR-014).

---

### User Story 2 — Payment Only After Order Exists (Priority: P1)

Payment is submitted only once an order has been successfully created,
and never before. A successful payment response is read for what it is —
confirmation that the payment request was accepted — and is never treated
as evidence that a ticket has been issued.

**Why this priority**: Submitting payment against a nonexistent or
unconfirmed order is a direct path to spending money incorrectly. This
ordering constraint is as fundamental as order creation itself.

**Independent Test**: Attempt payment without a prior successful order
creation and confirm it is refused. Submit payment against a valid order
and confirm the response is recorded without advancing the journey to a
ticketed state.

**Acceptance Scenarios**:

1. **Given** no order has yet been successfully created for the journey,
   **When** a payment is attempted, **Then** the attempt does not
   proceed.

2. **Given** an order was created successfully, **When** payment is
   submitted, **Then** it is submitted for that specific order reference.

3. **Given** payment returns a successful response, **When** the response
   is read, **Then** it is recorded as a successful payment submission
   only — it does not by itself change the journey's ticketing status.

4. **Given** payment is declined, **When** the decline is recorded,
   **Then** no further payment attempt is made against that order; the
   journey does not advance past the decline within this feature (FR-013).

---

### User Story 3 — Independent Ticketing Confirmation and Monitoring Handoff (Priority: P1)

After payment, the agent independently queries the order rather than
trusting the payment response. The presence of issued ticket numbers in
that query is the only evidence accepted as proof of ticketing. Querying
continues until ticketing is confirmed, the ticketing deadline passes, or
a terminal error is returned. The journey moves to a monitoring state only
once ticketing is confirmed this way.

**Why this priority**: This is the second of the two named failure modes
this feature exists to prevent: assuming a ticket exists because payment
succeeded. The independent read is the only thing standing between a
traveller and a false confirmation.

**Independent Test**: Submit payment, then simulate a query response
where ticket numbers are still empty, and confirm the journey does not
advance to monitoring. Simulate a later query where ticket numbers are
populated and confirm the journey then — and only then — moves to
monitoring.

**Acceptance Scenarios**:

1. **Given** payment has succeeded, **When** the order is queried and its
   ticket numbers are empty, **Then** the journey remains exactly where it
   was — not advanced, not marked as ticketed.

2. **Given** repeated queries, **When** a query eventually returns
   non-empty ticket numbers, **Then** that — and only that — is accepted
   as evidence of ticketing.

3. **Given** a multi-passenger booking, **When** a query shows ticket
   numbers for some passengers but not all, **Then** ticketing is not yet
   confirmed and the journey does not advance; querying continues as
   though no passenger were ticketed yet.

4. **Given** ticketing has been confirmed this way, **When** the journey
   state is next read, **Then** it reflects the monitoring state.

5. **Given** the ticketing deadline passes before any query returns
   ticket numbers, **When** the deadline is reached, **Then** querying
   stops and the journey is left in an explicit unconfirmed-ticketing
   condition rather than continuing to poll indefinitely or being assumed
   ticketed.

6. **Given** a query itself returns a terminal error, **When** that error
   is read, **Then** querying stops and the condition is recorded rather
   than retried indefinitely.

---

### User Story 4 — Duplicate Order Reconciliation (Priority: P2)

If order creation is rejected as a duplicate, the agent reads the existing
order reference Atlas returns with that rejection, queries that order
independently, and resumes the journey from whatever state that query
actually shows — rather than treating the rejection as a failure to retry
or the duplicate as a new order to create again. More generally, an order
creation or payment attempt whose outcome is uncertain is never repeated;
its actual outcome is established by an independent read first.

**Why this priority**: Named explicitly as one of the two failures that
matter for this feature. It is a P2 because it is a resilience path
triggered by a specific rejection condition, not something every booking
attempt exercises — but its correctness is non-negotiable when it does
trigger.

**Independent Test**: Attempt to create an order that Atlas rejects as a
duplicate of an existing one, and confirm the system reads the referenced
order, queries it, and continues from its real state rather than
reporting failure or attempting to create a second order.

**Acceptance Scenarios**:

1. **Given** an order creation attempt is rejected as a duplicate,
   **When** the rejection is read, **Then** the existing order reference
   it carries is extracted and that order is queried.

2. **Given** the queried duplicate order's actual state, **When** the
   journey resumes, **Then** it resumes from that real state — not from
   an assumption that the duplicate attempt failed or succeeded.

3. **Given** a payment call whose outcome could not be determined (for
   example, no response was received), **When** deciding what to do next,
   **Then** the system does not repeat that call; it independently queries
   the order first to establish what actually happened.

4. **Given** an order-creation call whose outcome could not be determined,
   **When** deciding what to do next, **Then** the system re-attempts
   order creation rather than querying (no order reference yet exists to
   query by); if that retry is rejected as a duplicate, the referenced
   order is read as the confirmation that the original attempt succeeded,
   per FR-007.

---

### Edge Cases

- A duplicate-order rejection carries more than one existing order
  reference. The verified case observed exactly one; this condition is
  itself anomalous and must be surfaced rather than silently resolved by
  picking one.
- Order creation itself times out or otherwise returns no response. Per
  FR-007, the system re-attempts order creation rather than treating the
  attempt as failed; a resulting duplicate-order rejection (FR-006) is
  read as confirmation the original attempt succeeded, and the referenced
  order is resumed from. This is the only case in which "repeating" a
  state-changing call is correct, precisely because Atlas's own
  duplicate-detection is what makes the retry a safe reconciliation
  mechanism rather than a blind one.
- The ticketing deadline passes while a query is in flight. The
  in-flight query's result is still read; the deadline check applies to
  whether another query is initiated afterward, not to abandoning a
  response already being received.
- A multi-passenger booking's ticket numbers arrive for some passengers
  before others. Ticketing is not confirmed, and the journey does not
  advance, until every passenger on the order has a non-empty ticket
  number; a partial result is treated identically to no ticketing yet.
- `queryOrderDetails.do`'s `orderStatus` and `ticketStatus` fields
  disagree with the ticket-numbers evidence in ways not yet fully
  understood — their full enum values are not yet mapped. Only the
  presence of non-empty ticket numbers is treated as ticketing evidence;
  `orderStatus` and `ticketStatus` are recorded for audit but are never
  the basis for confirming a ticket.
- A query call itself fails (network error, malformed response). Because
  a query is a read with no state-changing effect, it may be retried
  without violating FR-007 — the "never repeat an uncertain outcome"
  constraint governs the order-creation and payment calls themselves, not
  the queries used to reconcile them.
- Payment is attempted a second time after a first payment attempt whose
  outcome is uncertain. The system queries the order first to determine
  whether payment was already accepted before deciding whether submitting
  again is even meaningful.
- Payment is declined (a certain outcome, distinct from an uncertain one).
  The decline is recorded and no retry against that order is made — this
  is different from the uncertain-outcome case above, which resolves via
  a query rather than a permanent stop (FR-013).
- The passenger requirements recorded at verification no longer match
  what the traveller's held data provides (a required field is missing).
  Order creation is not attempted with an incomplete request; this is
  surfaced rather than submitted with a placeholder value.
- The session's freshness window expires before order creation is
  attempted (for example, authorisation or another prior step took long
  enough). The system checks this before attempting order creation and
  refuses to attempt it, surfacing an expired-session condition distinct
  from any Atlas-returned rejection (FR-014).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create an order using the session
  identifier obtained from verification, preserved unmodified.

- **FR-002**: The system MUST populate passenger and contact details
  according to the field requirements returned at verification time, not
  a fixed or assumed set.

- **FR-003**: The system MUST record the order reference (`orderNo`) and
  any booking reference (`pnrCode`) returned by order creation.

- **FR-004**: The system MUST NOT treat a booking reference
  (`pnrCode`) as evidence that a ticket has been issued.

- **FR-005**: The system MUST record the ticketing deadline
  (`tktLimitTime`) returned with the order and MUST track it as a
  freshness window distinct from the session window that preceded it.

- **FR-006**: The system MUST detect a duplicate-order rejection, read the
  existing order reference returned with it (`duplicateOrders`), query
  that order, and resume the journey from its actual queried state. This
  rejection also serves as the reconciliation mechanism for FR-007 when an
  earlier order-creation attempt's outcome was uncertain (see FR-007).

- **FR-007**: The system MUST NOT treat the outcome of an order-creation or
  payment attempt as failed or successful merely because no response was
  received; an uncertain outcome MUST be resolved before any further
  action is decided. For payment, resolution MUST be via an independent
  order query (an order reference already exists to query by that point).
  For order creation specifically, no order reference yet exists to query
  directly when its own outcome is uncertain — in that case, re-attempting
  order creation is the sanctioned resolution path: if Atlas rejects the
  retry as a duplicate (FR-006), that rejection is itself the independent
  confirmation that the earlier attempt already succeeded, and MUST be
  treated as such rather than as a failure to retry from scratch. If the
  retry succeeds outright, no prior order existed.

- **FR-008**: The system MUST submit payment only after an order has been
  successfully created for the journey.

- **FR-009**: The system MUST NOT treat a successful payment response as
  evidence that a ticket has been issued.

- **FR-010**: The system MUST query the order independently after payment
  and MUST treat the presence of non-empty issued ticket numbers as the
  only accepted evidence of ticketing. For a booking with more than one
  passenger, ticketing is confirmed only when every passenger on the
  order has non-empty ticket numbers — a partial result (some passengers
  ticketed, others not) is not sufficient.

- **FR-011**: The system MUST continue querying the order until one of:
  ticketing is confirmed, the ticketing deadline passes, or a terminal
  error is returned. It MUST NOT continue querying indefinitely past any
  of those three outcomes.

- **FR-012**: The system MUST transition the journey to the monitoring
  state only once ticketing has been confirmed via FR-010.

- **FR-013**: The system MUST NOT retry payment against the same order
  once it has been declined. A decline is a certain, known outcome — not
  the uncertain-outcome condition FR-007 governs — and this feature's
  responsibility for that order ends at recording it; any further payment
  attempt requires the journey to return to an earlier state first (out
  of scope for this feature to define).

- **FR-014**: The system MUST check that the session's freshness window
  has not already expired before attempting order creation. If it has,
  the system MUST refuse to attempt order creation and MUST surface this
  as a distinct expired-session condition rather than submitting a
  request expected to fail.

### Non-Functional Requirements

- **NFR-001**: Every state-changing call (order creation, payment) MUST be
  followed by an independent read before the journey's state is updated
  on the basis of that call.

- **NFR-002**: Order and payment responses MUST be persisted in full for
  audit, regardless of outcome.

### Key Entities

- **Order**: The result of a successful order-creation call. Carries the
  order reference (`orderNo`), booking reference (`pnrCode`), and the
  ticketing deadline (`tktLimitTime`). A booking reference existing on an
  Order does not imply a ticket exists.

- **Ticketing Deadline**: The time interval, bounded by `tktLimitTime`,
  during which payment and ticketing confirmation must complete.
  Chronologically follows the session freshness window established at
  verification and is tracked as its own, separate window (a third,
  distinct freshness phase alongside the offer and session windows).

- **Payment Attempt**: The record of a submission to pay for a specific
  order reference. Its success indicates the payment request was
  accepted — nothing about ticketing.

- **Ticketing Confirmation**: The state established only when an
  independent order query returns non-empty issued ticket numbers for
  every passenger on the order. Nothing else — not a booking reference,
  not a successful payment response, not a partial result covering some
  but not all passengers — constitutes this confirmation.

- **Duplicate Order Reference**: The existing order reference Atlas
  returns alongside a duplicate-order rejection. Read and queried, never
  discarded or treated as a reason to create a second order.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No payment is ever submitted without a preceding successful
  order creation for the same journey — confirmed by an automated
  contract test on every push.

- **SC-002**: In no automated test or recorded scenario does the system
  treat a booking reference or a successful payment response as proof of
  ticketing — only non-empty ticket numbers from an independent query do
  so, confirmed on every push.

- **SC-003**: A duplicate-order rejection is followed by a query of the
  referenced existing order and a resumption from its real state 100% of
  the time in test scenarios that trigger it — never by a reported
  failure or a second order-creation attempt.

- **SC-004**: A payment call whose outcome is uncertain is never followed
  by a repeat of that same call in any recorded test scenario — it is
  always followed by an independent order query first. An order-creation
  call whose outcome is uncertain is followed only by a retry whose
  resulting duplicate rejection (if any) is read as confirmation, never by
  the system reporting the original attempt as a plain failure.

- **SC-005**: Ticketing confirmation, when it occurs, is always preceded
  by at least one order query showing non-empty ticket numbers for every
  passenger on the order — confirmed by a contract test using a recorded
  fixture, on every push. Zero instances of confirmation on a partial
  (some-but-not-all-passengers) result appear in the test suite.

- **SC-006**: Querying for ticketing confirmation always terminates —
  either by confirmation, by the ticketing deadline passing, or by a
  terminal error — with zero instances of indefinite polling in the test
  suite.

- **SC-007**: A declined payment is followed by zero further payment
  attempts against that order in any recorded test scenario.

- **SC-008**: An order-creation attempt against an already-expired session
  never reaches Atlas in any recorded test scenario — the expired
  condition is caught locally 100% of the time.

---

## Out of Scope

- Searching for and scoring options (separate, prior capabilities)
- Verification of the selected option (a separate, prior capability whose
  output — the session identifier, passenger requirements, ticketing
  eligibility — this feature consumes)
- Authorisation policy (whether human approval is required before order
  creation or payment; this feature assumes any required authorisation
  has already been granted before it acts)
- Monitoring (what happens after the journey enters the monitoring state)
- Recovery (rebooking, voiding, or refunding when ticketing fails or a
  schedule change occurs)

---

## Assumptions

- The verified contract recorded in `.antabay/atlas-capability-map.md`
  section 7b (verified 2026-08-15) is the authoritative source of truth
  for the order.do, pay.do, and queryOrderDetails.do request and response
  shapes used by this feature.
- Payment in the verified flow is taken from an Atlas account balance
  (`paymentMethod: 1`); no card details are submitted by this feature.
  The documented card-decline simulations (`Reject` / `Three DS`
  cardholder names) apply to a separate VCC payment path and are not
  applicable here.
- No declared per-journey call-budget interaction is specified for
  order.do, pay.do, or queryOrderDetails.do in the capability map, unlike
  the explicit shared allowance documented for search.do/verify.do/
  getOffers.do. If one exists, it is outside this specification's
  knowledge and therefore outside its scope.
- The full enum values for `orderStatus` and `ticketStatus` are not yet
  mapped (per the capability map's own "not yet verified" section); this
  specification depends only on the presence of non-empty ticket numbers,
  which is already established as reliable.
- Querying an order is a read with no state-changing effect and may
  therefore be retried freely; the "never repeat an uncertain outcome"
  discipline in FR-007 and NFR-001 applies specifically to order-creation
  and payment calls, not to queries.
- A single order is created per verified option per journey under normal
  operation; this specification does not address booking multiple options
  within one journey.
