# Feature Specification: Price Verification and Offer Staleness

**Feature Branch**: `004-price-verification`

**Created**: 2026-08-28

**Status**: Draft

**Input**: External contract definition sourced from
`.antabay/atlas-capability-map.md` section 7a (verify.do, verified against
the Atlas API sandbox on 2026-08-15).

---

## Business Context

**Business Goal**: Confirm that a selected option is still available at
the stated price before any commitment is made, and manage the shifting
freshness windows that govern how long a held position remains usable.

**Business Value**: Offers age faster than they appear to. Committing on a
stale offer means booking something the traveller did not agree to, at a
price they did not approve.

**Business Actors**:
- Agent — selects an option from search results and must confirm it is
  still valid before any order is created

**Business Capability**: Commitment Safety

**Reference**: `.antabay/atlas-capability-map.md` section 7a records the
verified verify.do request/response contract and is the input to this
feature. This specification governs how that contract is used to gate
commitment.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Verify Before Commitment (Priority: P1)

Before any order is created for a selected option, the agent verifies that
option with the provider. The option's identifier is forwarded exactly as
received — never reconstructed or altered. The agent reads the provider's
own price-change indicator to learn whether the price has moved; it does
not compare prices itself. If the provider reports a price change, any
authorisation a human previously granted for that option is treated as no
longer valid.

**Why this priority**: This is the core commitment-safety gate. Every
other capability in this feature exists to support a trustworthy verify
step. Without it, the system could commit to an order at a price, or for
an option, the traveller never actually agreed to.

**Independent Test**: Select an option from a prior search, verify it, and
confirm the identifier reaches the provider unmodified. Simulate a
provider response with a price-change indicator set and confirm any
existing authorisation for that option is discarded rather than reused.

**Acceptance Scenarios**:

1. **Given** an option with `routingIdentifier` held from search, **When**
   the agent verifies the option, **Then** the identifier is sent
   byte-for-byte and no construction, parsing, or substring operation is
   performed on it.

2. **Given** a verify response with `priceChange.isPriceChange: false`,
   **When** the agent reads the response, **Then** it treats the price as
   unchanged and does not perform its own comparison of the old and new
   fare fields.

3. **Given** a verify response with `priceChange.isPriceChange: true`,
   **When** the agent reads the response, **Then** any authorisation
   previously granted for that option is invalidated and a fresh
   authorisation is required before proceeding.

4. **Given** a verify call is made, **When** the call completes, **Then**
   it is counted against the journey's call budget for the shared
   verify/getOffers allowance.

---

### User Story 2 — Freshness Window Handoff (Priority: P2)

Once verification succeeds, the short pre-verify offer window no longer
applies. A new, longer session-level window takes over, bounded by the
session identifier returned at verify time. The agent tracks the two
windows as distinct phases rather than as one continuous clock, and
re-verifies before the held position is close enough to expiry that
inventory or price could plausibly have moved.

**Why this priority**: The offer clock and the session clock have
different scopes, different durations, and different consequences on
expiry. Treating them as one clock — or trusting the session clock all the
way to its documented limit — creates a window where the agent commits
against a position that has quietly gone stale.

**Independent Test**: Verify an option and confirm the pre-verify expiry
tracking is replaced by session-level tracking. Advance a held session to
within the declared safety margin of its documented limit and confirm the
agent re-verifies rather than proceeding directly to order creation.

**Acceptance Scenarios**:

1. **Given** an offer held with an `expireTime` from search, **When**
   verification succeeds, **Then** the offer-level freshness window is
   retired and a session-level freshness window, bounded by the returned
   `sessionId`, begins being tracked in its place.

2. **Given** a verified session and its declared safety margin, **When**
   the time remaining on the session falls inside that margin, **Then**
   the agent re-verifies before taking any further action on that option.

3. **Given** a session identifier returned at verification, **When** it is
   stored and later read, **Then** its value is identical, byte-for-byte,
   to what was returned.

---

### User Story 3 — Runtime Requirements Capture (Priority: P2)

At verification time, the provider returns the exact passenger fields it
requires for this offer, and the maximum quantity of this offer that may
be booked. The agent records both and uses them as the source of truth for
any later booking step, rather than assuming a fixed passenger form or an
assumed quantity ceiling.

**Why this priority**: Passenger requirements and bookable quantity are
returned per offer and can differ between them. Hardcoding either
produces a booking step that silently rejects valid attempts or accepts
invalid ones.

**Independent Test**: Verify two different options and confirm each
produces its own recorded passenger field set and its own maximum bookable
quantity, without either being backfilled from a fixed default.

**Acceptance Scenarios**:

1. **Given** a verify response whose `bookingRequirement.passenger`
   declares `name`, `birthday`, `gender`, `nationality`, and
   `passengerType` as required fields, **When** the response is recorded,
   **Then** exactly that field set — not a fixed or previously seen set —
   is what later booking steps read.

2. **Given** a verify response with `maxSeats: 7`, **When** the response is
   recorded, **Then** 7 is stored as the maximum bookable quantity for
   that verified option.

---

### User Story 4 — Unavailable Option Recovery (Priority: P3)

If verification reports that the selected option is no longer available,
the agent does not attempt to proceed. It returns the journey to the
search state so a new option can be selected.

**Why this priority**: Inventory changes between search and verify.
Recovering cleanly back to search is lower priority than the safety gate
itself, but still necessary — without it, an unavailable option leaves the
journey stuck rather than progressing.

**Independent Test**: Verify an option that the provider reports as no
longer available and confirm the journey state transitions back to
search rather than remaining on, or advancing past, the verify step.

**Acceptance Scenarios**:

1. **Given** a verify response indicating the option is no longer
   available, **When** the agent reads the response, **Then** the journey
   returns to the search state and the unavailable option is not retried.

---

### Edge Cases

- A verify response arrives with `priceChange` absent or malformed. The
  agent must not infer "no change" from its absence; the condition must be
  surfaced rather than silently treated as safe.
- A verify response has `sessionId` as `null` or empty. This must be
  surfaced as an error rather than a session window being tracked with no
  bound.
- The declared safety margin is larger than the session's total documented
  duration, making every session immediately due for re-verification. This
  is a valid, if conservative, configuration and must not cause an error.
- Two verify calls for the same option are made in close succession
  (e.g., after a re-verify triggered by the safety margin). Each is
  independently counted against the call budget.
- A verify call itself fails (network error, non-success status other than
  "no longer available") — this is distinct from a reported price change
  or unavailability and must be distinguishable from both.
- `bookingRequirement.passenger` is returned with zero required fields.
  The agent records this as-is rather than substituting a non-empty
  default.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST verify the selected option with the provider
  before creating any order for it.

- **FR-002**: The system MUST pass the option's identifier
  (`routingIdentifier`) to verification unmodified. It MUST NOT construct,
  parse, or otherwise alter the identifier.

- **FR-003**: The system MUST read the provider's own price-change
  indicator (`priceChange.isPriceChange`) to determine whether the price
  has changed. It MUST NOT compute or infer a price change by comparing
  fare fields itself.

- **FR-004**: The system MUST treat a reported price change
  (`priceChange.isPriceChange: true`) as invalidating any authorisation
  previously granted for that option. A fresh authorisation MUST be
  obtained before the option can proceed to order creation.

- **FR-005**: The system MUST record the session identifier (`sessionId`)
  returned by verification and MUST preserve it unmodified for use in
  subsequent calls that require it.

- **FR-006**: The system MUST recognise that the offer-level freshness
  window (bounded by `expireTime`) is retired once verification succeeds,
  and that a session-level freshness window (bounded by `sessionId`'s
  documented duration) begins in its place. The two windows MUST be
  tracked as distinct phases, not merged into one.

- **FR-007**: The system MUST record the passenger field requirements
  returned in `bookingRequirement.passenger` at verification time and MUST
  use that recorded set — not a fixed or assumed set — for any later
  booking step.

- **FR-008**: The system MUST record the maximum bookable quantity
  (`maxSeats`) returned at verification time and MUST use it as the
  ceiling for that verified option.

- **FR-009**: The system MUST return the journey to the search state when
  verification reports that the selected option is no longer available.

- **FR-010**: The system MUST re-verify, rather than proceed to order
  creation, when the held session's time remaining is closer to its
  documented expiry than a declared safety margin.

- **FR-011**: The system MUST count every verification call against the
  journey's call budget for the endpoint group verification shares with
  offer retrieval.

### Non-Functional Requirements

- **NFR-001**: The system SHOULD prefer re-verifying earlier than the
  documented expiry of a held position rather than waiting until it
  elapses, because inventory and price can change before the documented
  limit is reached.

- **NFR-002**: Verification responses MUST be persisted in full for audit,
  independent of which fields the agent acts on at the time.

### Key Entities

- **Verified Option**: The result of a successful verification — carries
  the same routing detail as the original search offer, plus the fields
  only verification returns: `sessionId`, `maxSeats`,
  `bookingRequirement`, and `priceChange`.

- **Session Freshness Window**: The time interval, bounded by `sessionId`,
  during which a verified option remains usable. Distinct from — and
  chronologically follows — the offer freshness window it replaces.

- **Price Change Signal**: The provider-reported determination
  (`isPriceChange`) of whether the price has moved since the option was
  first offered, together with the original and new per-passenger-type
  price components it carries.

- **Passenger Requirement Set**: The per-offer, per-field declaration
  (type, required, description, maximum length) of what a booking for this
  verified option requires. Read fresh from each verification; never
  assumed.

- **Bookable Quantity**: The maximum number of passengers of this offer
  that may be booked, as declared by the provider at verification time.

- **Safety Margin**: A declared buffer, expressed as a duration, that
  triggers re-verification when the time remaining on a held session
  falls inside it.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No order is ever created for an option that has not been
  independently verified in the same journey — confirmed by an automated
  contract test on every push.

- **SC-002**: Every price-change determination made by the system matches
  the provider's own `isPriceChange` value; zero instances of the system
  computing its own price comparison — confirmed by a contract test using
  a recorded fixture with `isPriceChange: true` and one with `false`.

- **SC-003**: A `routingIdentifier` and a `sessionId` each arrive at their
  next respective use byte-for-byte identical to how they were received —
  confirmed by an automated test on every push.

- **SC-004**: When a held session's remaining time crosses the declared
  safety margin, a re-verification occurs before any order-creation
  attempt on that session — confirmed by a contract test using a recorded
  fixture, on every push.

- **SC-005**: Passenger field requirements and maximum bookable quantity
  used in a later step always match what the most recent verification for
  that option returned — zero instances of a fixed or stale value being
  used instead.

- **SC-006**: An option reported as no longer available at verification
  results in the journey being back in the search state 100% of the time,
  with no retry of the same unavailable option.

---

## Out of Scope

- Searching for options (a separate, prior capability)
- Scoring or ranking options
- Order creation and payment
- Authorisation policy (what qualifies as high-impact, who may approve) —
  this feature only defines what invalidates an existing authorisation,
  not how authorisation itself is granted

---

## Assumptions

- The verified contract recorded in `.antabay/atlas-capability-map.md`
  section 7a (verified 2026-08-15) is the authoritative source of truth
  for the verify.do request and response shapes used by this feature.
- The session-level freshness window is documented as up to 2 hours, but
  the offer-level `expireTime` observed before it is authoritative for
  when it was superseded; this feature does not need to reconcile the two
  durations, only to stop tracking one and start tracking the other at the
  moment verification succeeds.
- The declared safety margin is a configuration value owned by operational
  policy, not defined by this feature; this feature only specifies that
  crossing it triggers re-verification.
- `verify.do` shares its per-journey call budget allowance with
  `getOffers.do` (60 QPM combined, per the capability map); this feature
  only requires that verification calls are counted, not that it owns the
  shared budget's configuration.
- "No longer available" is inferred from a non-success verification
  outcome that is distinct from a reported price change; the exact status
  code or message the provider uses for this condition is not yet
  documented in the capability map and is treated as an integration detail
  for the implementing feature, not a specification concern here.
- Passenger field requirements may legitimately be an empty set for some
  offers; this feature does not impose a minimum.
