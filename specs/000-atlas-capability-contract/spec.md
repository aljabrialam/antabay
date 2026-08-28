# Feature Specification: Atlas Capability Contract

**Feature Branch**: `000-atlas-capability-contract`

**Created**: 2026-08-28

**Status**: Superseded (2026-08-29)

**Superseded rationale**: This feature proposed a standalone contract-
enforcement library (`backend/atlas/`) — typed models, an endpoint
allowlist, canonical pricing, error classification, call-budget tracking —
sitting in front of every feature that calls the travel API. In practice,
features 001 through 012 each achieved this specification's actual safety
guarantees (opaque identifiers preserved byte-for-byte, `Decimal` for every
monetary value, every field traced to a verified capability-map entry, no
call to an undocumented endpoint) directly in their own
`journey/models/*.py` and `journey/services/*.py`, with no dependency on
`backend/atlas/`. That package was never imported by any of them. Building
out the remaining 38 tasks (Pydantic models per endpoint, pricing,
error/budget/telemetry modules, a dedicated CI workflow) would add a
second, parallel implementation of guarantees the working system already
enforces inline, with nothing left to consume it — the "no premature
abstraction" and "no building for a hypothetical future requirement"
principles this project otherwise follows argue against it. The 17 tasks
already completed (`OpaqueId`, the endpoint allowlist, `OrderStatus`
normalisation) remain in the tree as real, tested, working code — just
unused by the rest of the system. Phases 4 onward (T018–T055) are marked
accordingly in tasks.md, not completed.

**Input**: External contract definition sourced from `.antabay/atlas-capability-map.md`
(verified against the Atlas API sandbox on 2026-08-15).

---

## Business Context

**Business Goal**: Give the system a single, enforced definition of what the
travel API can do, so no other feature can call an endpoint or read a field
that has not been verified to exist.

**Business Value**: The primary failure mode of AI-assisted integration work
is confidently invented endpoints and field names. This feature makes that
failure impossible to commit.

**Business Actors**:
- Developer — writes features that call the travel API
- Continuous integration pipeline — validates that every change respects the
  contract

**Business Capability**: External Contract Governance

**Reference**: `.antabay/atlas-capability-map.md` records the verified
contract and is the input to this feature. This specification governs how
that contract is enforced.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Enforce the Endpoint Allowlist (Priority: P1)

A developer writes code that calls an external travel endpoint. The contract
enforcement layer checks, at build time, whether the endpoint is in the
verified allowlist. If it is not, the build fails with an actionable message
before the code can be committed or deployed.

**Why this priority**: This is the primary safety guarantee of the feature.
Without it, invented endpoints can reach production silently. All other
stories depend on having a trustworthy boundary.

**Independent Test**: Submit a change that calls a non-existent endpoint and
confirm the build rejects it. Submit a change that calls a verified endpoint
and confirm the build accepts it.

**Acceptance Scenarios**:

1. **Given** a developer writes a call to `search.do`, **When** the build
   runs, **Then** the build passes and no contract violation is reported.
2. **Given** a developer writes a call to `suggestFlight.do` (not in the
   verified contract), **When** the build runs, **Then** the build fails and
   the error message identifies the unrecognised endpoint by name.
3. **Given** the allowlist is updated to add a newly verified endpoint,
   **When** the build runs against code that calls that endpoint, **Then** the
   build passes.

---

### User Story 2 — Typed Request and Response Shapes (Priority: P2)

A developer consumes the output of a travel API call. The contract provides
a typed representation of each verified request and response shape, so
accessing a field that does not exist in the verified schema is detected
before the code runs.

**Why this priority**: Typed shapes prevent the second class of silent
failure — reading an invented field. They also document the verified API
surface in a form that tooling can check.

**Independent Test**: Write a type-safe accessor for a field that exists in
the schema and confirm no error. Write an accessor for a non-existent field
and confirm a build-time or static-analysis failure.

**Acceptance Scenarios**:

1. **Given** a developer accesses `routing.fid` (a verified field), **When**
   the code is checked, **Then** no type error is raised.
2. **Given** a developer accesses `routing.fareCode` (not in the verified
   schema), **When** the code is checked, **Then** a type error is raised
   before the code is executed.
3. **Given** the `verify.do` response includes `sessionId`, **When** a
   developer reads `sessionId` from the typed response, **Then** the value is
   returned as an opaque, unmodifiable string.

---

### User Story 3 — Identifier Integrity (Priority: P2)

A developer needs to pass an externally issued identifier (such as
`routingIdentifier`, `sessionId`, or `orderNo`) to a downstream call. The
contract ensures the identifier is treated as an opaque token: it can be
stored and passed through, but it cannot be constructed from parts, parsed
into sub-fields, or altered in any way.

**Why this priority**: Atlas identifiers are opaque by design. Any code that
constructs or parses them will break silently when the format changes. The
contract must make this failure mode structurally impossible.

**Independent Test**: Attempt to construct a `routingIdentifier` from its
apparent parts and confirm the build rejects the attempt. Pass an unmodified
`routingIdentifier` through storage and retrieval and confirm it arrives at
the downstream call unchanged.

**Acceptance Scenarios**:

1. **Given** a `routingIdentifier` is received from a search response,
   **When** it is passed byte-for-byte to a verify request, **Then** it is
   accepted without modification.
2. **Given** a developer attempts to substring, concatenate, or otherwise
   construct an identifier value, **When** the code is checked, **Then** no
   construction path is available through the contract types.
3. **Given** an identifier is stored and later retrieved, **When** it is used
   in a subsequent call, **Then** its byte sequence is identical to what was
   originally received.

---

### User Story 4 — Canonical Price Calculation (Priority: P3)

Any part of the system that needs to display or compare a total price calls
the single canonical price function defined by the contract. No other code
path computes a price total.

**Why this priority**: The Atlas total-price formula is documented and
verified. Allowing ad-hoc price arithmetic elsewhere introduces drift, which
can produce incorrect totals shown to travellers.

**Independent Test**: Call the canonical price function with known inputs and
confirm the result. Verify that no other callable path in the codebase
produces a price total.

**Acceptance Scenarios**:

1. **Given** `adultPrice = 66.43`, `adultTax = 23.96`,
   `transactionFeePerPax = 0.00`, **When** the canonical price function is
   called, **Then** it returns `90.39`.
2. **Given** a developer writes a price total calculation outside the
   canonical function, **When** the build runs, **Then** the build fails or
   the linter raises a violation.
3. **Given** a price total is needed in two separate features, **When** each
   feature calls the canonical function with the same inputs, **Then** both
   return the same result.

---

### User Story 5 — Error Classification and Rate-Limit Discipline (Priority: P3)

A developer handling an API error looks up the error code in the contract's
classification table. The contract tells them whether to retry, reconcile, or
treat the error as terminal — and for rate-limit responses, it enforces that
no retry occurs before the instructed wait elapses.

**Why this priority**: Incorrect retry behaviour on Atlas errors causes
duplicate bookings (code 318) and account bans (rate-limit loops). The
contract must make the correct handling the only available path.

**Independent Test**: Trigger error code 318 (duplicate booking) and confirm
the system reads `duplicateOrders` and surfaces the existing order reference
rather than retrying. Trigger a rate-limit response and confirm no retry is
attempted before the `retryAfter` interval.

**Acceptance Scenarios**:

1. **Given** an API call returns error code `318`, **When** the error is
   handled, **Then** the system classifies it as reconcilable, reads the
   existing order reference from `duplicateOrders`, and does not retry.
2. **Given** an API call returns a rate-limit rejection with a `retryAfter`
   value, **When** the error is handled, **Then** no retry is initiated before
   that interval elapses.
3. **Given** an API call returns error code `900` (auth failure), **When** the
   error is handled, **Then** the system classifies it as terminal and does not
   retry.
4. **Given** an API call returns error code `800` (order not found), **When**
   the error is handled, **Then** the system classifies it as terminal (a
   local state bug) and does not retry.

---

### Edge Cases

- A search response returns an offer whose `expireTime` is already in the
  past at the time it is received. The contract must surface this condition
  so the offer is rejected before any action is taken on it.
- A webhook delivers `orderStatus` as an integer. The canonical REST response
  delivers `orderStatus` as a string. The normalisation layer must produce
  one consistent type before either value reaches business logic.
- A rate-limit response carries no `retryAfter` value. The contract must
  treat this as an indefinite hold, not as permission to retry immediately.
- An identifier field (e.g. `routingIdentifier`) is `null` in a response. The
  contract must surface this as an error rather than passing a null downstream.
- A call budget for a rate-limited endpoint is exhausted mid-journey. The
  contract must record the condition and prevent further calls to that endpoint
  for the journey without crashing.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a machine-readable declaration of every
  external travel endpoint it is permitted to call.

- **FR-002**: The system MUST reject, at build time, any attempt to call an
  endpoint not present in that declaration. A runtime-only rejection is
  insufficient.

- **FR-003**: The system MUST define a typed representation of each verified
  request and response shape, such that accessing an unverified field is
  detected before the code is executed.

- **FR-004**: The system MUST preserve every externally issued identifier
  without modification. It MUST provide no means of constructing, parsing, or
  altering an externally issued identifier.

- **FR-005**: The system MUST define a single canonical total-price calculation
  (`adultPrice + adultTax + transactionFeePerPax`) and MUST NOT permit price
  totals to be computed by any other code path.

- **FR-006**: The system MUST normalise fields whose type differs between the
  REST API and its webhook notifications, so that downstream code sees one
  consistent type. Specifically, `orderStatus` MUST be normalised to a single
  type on ingest, because the REST surface returns it as a string and the
  webhook returns it as an integer.

- **FR-007**: The system MUST classify every known external error code as one
  of: retryable, reconcilable, or terminal, and MUST expose that classification
  to callers. Unknown error codes MUST default to terminal.

- **FR-008**: The system MUST treat error code `318` (duplicate booking) as
  reconcilable, and MUST surface the existing order reference contained in
  `duplicateOrders` to the caller. It MUST NOT retry on this error.

- **FR-009**: The system MUST record, for every external call, the endpoint
  name, the outcome (success or error code), and the elapsed time.

- **FR-010**: The system MUST enforce a declared per-journey call budget for
  rate-limited endpoints. Once the budget is exhausted, further calls to that
  endpoint for the same journey MUST be refused and the condition MUST be
  recorded.

- **FR-011**: The system MUST honour a wait instruction (`retryAfter`) returned
  with a rate-limit rejection and MUST NOT initiate a retry before that
  interval elapses. Absence of a `retryAfter` value MUST be treated as an
  indefinite hold.

- **FR-012**: The system MUST track, for each held offer or session, the time
  it was issued and the time it becomes unusable:
  - Pre-verify offers are bounded by `expireTime` (observed as short as 7
    minutes 43 seconds, sometimes already partly elapsed on receipt).
  - Post-verify sessions are bounded by `sessionId` TTL (documented up to
    2 hours).
  - Post-order tickets are bounded by `tktLimitTime` (observed 30 minutes).

### Non-Functional Requirements

- **NFR-001**: Any endpoint or field not present in the verified contract MUST
  cause a build failure, not a runtime error.

- **NFR-002**: Contract tests MUST run in continuous integration on every
  change to the codebase.

- **NFR-003**: Recorded fixtures used by contract tests MUST be captured from
  live sandbox runs. Handwritten fixtures are prohibited.

### Key Entities

- **Endpoint allowlist**: The machine-readable set of permitted external
  endpoints. Each entry records the endpoint name, the direction (request or
  response), and the verification status.

- **Typed schema**: The verified shape of each request and response for each
  allowed endpoint. Fields not present in the schema are inaccessible.

- **Opaque identifier**: An externally issued string token (e.g.
  `routingIdentifier`, `sessionId`, `orderNo`) that MUST be stored and
  forwarded without inspection or mutation.

- **Canonical price**: The single authoritative total-price value for a per-
  adult fare, computed as `adultPrice + adultTax + transactionFeePerPax`.

- **Error classification**: The mapping of each known Atlas error code to one
  of three dispositions: retryable, reconcilable, or terminal.

- **Call budget**: The declared maximum number of calls to a rate-limited
  endpoint that may be made within a single journey.

- **Freshness window**: The time interval during which a held offer or session
  is still usable. Represented as an issued-at timestamp and an expires-at
  timestamp. Three distinct windows exist: offer (`expireTime`), session
  (`sessionId` TTL), and ticketing deadline (`tktLimitTime`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every call to an unverified endpoint is rejected before the
  change can be committed — zero unverified endpoint calls reach the
  integration branch.

- **SC-002**: Every access to an unverified response field is rejected before
  the code is executed — zero unverified field accesses reach the integration
  branch.

- **SC-003**: The canonical price function, when called with inputs from the
  verified SEL→TYO fixture (`adultPrice 66.43`, `adultTax 23.96`,
  `transactionFeePerPax 0.00`), returns `90.39` — confirmed by an automated
  contract test on every push.

- **SC-004**: On receipt of error code `318`, the system surfaces the existing
  order reference and records a reconcilable outcome — confirmed by a contract
  test using a recorded fixture, on every push.

- **SC-005**: On receipt of a rate-limit rejection, no retry is initiated
  before the instructed wait interval — confirmed by a contract test using a
  recorded fixture, on every push.

- **SC-006**: The `orderStatus` field, regardless of whether it arrives from
  the REST API (string) or a webhook (integer), produces the same type in the
  normalised output — confirmed by a contract test covering both surfaces.

- **SC-007**: Contract tests complete and report pass/fail on every CI run,
  without requiring a live sandbox connection.

---

## Out of Scope

- Agent reasoning and decision logic
- Journey state storage and retrieval
- Any specific booking, recovery, or rescheduling workflow
- User interface or operator display
- Webhook receiver infrastructure (the contract defines the shape; a separate
  feature owns the receiver)

---

## Assumptions

- The verified contract recorded in `.antabay/atlas-capability-map.md`
  (verified 2026-08-15) is the authoritative source of truth for this feature.
  Any field or endpoint not present in that file is treated as unverified.
- The five endpoints exercised end-to-end (`search.do`, `verify.do`,
  `order.do`, `pay.do`, `queryOrderDetails.do`) are the primary scope of the
  typed schema. Documented-but-unexercised endpoints
  (`getOffers.do`, `getOfferPrice.do`, `seatAvailability.do`, `getLuggage.do`,
  refunds, void, webhook registration, incident query, balance) are included
  in the allowlist but their schemas are marked as unverified pending exercise.
- The `webhook.do` shape is defined from the captured `order.ticketed` event.
  The Schedule Change event shape is not yet verified and is excluded from the
  typed schema until captured.
- Currency normalisation (USD fares vs. IDR penalty amounts in `refundRules`)
  is a data concern, not a type normalisation concern. It is out of scope for
  FR-006, which covers only the `orderStatus` integer/string divergence.
- The per-journey call budget values (QPM/QPS limits) are taken from the
  capability map: `search.do` 10 QPS; `verify.do` and `getOffers.do` share
  60 QPM; `seatAvailability.do` and `getLuggage.do` share 60 QPM.
- Fixture capture is performed against the Atlas sandbox. Production
  credentials are separate and are not used in any test.
