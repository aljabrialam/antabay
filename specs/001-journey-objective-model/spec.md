# Feature Specification: Journey and Objective Model

**Feature Branch**: `001-journey-objective-model`

**Created**: 2026-08-28

**Status**: Draft

**Input**: FR-001–FR-012 from the Journey and Objective Model feature brief.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Objective Capture and Confirmation (Priority: P1)

A traveller describes their trip in plain language. The system extracts a
structured objective from that description, flags any missing or ambiguous
elements, asks the traveller to supply them, presents the complete parsed
objective for confirmation, and only then creates a persisted journey record.

**Why this priority**: Every downstream capability — search, scoring,
disruption detection, recovery — depends on a confirmed, structured
objective existing in durable storage. Nothing else can proceed without it.

**Independent Test**: Can be fully tested by submitting a natural-language
goal, responding to any clarifying questions, confirming the parsed
objective, and asserting that a journey record is created in storage with
the correct fields and initial state.

**Acceptance Scenarios**:

1. **Given** a traveller submits "I need to get from London to Singapore
   by Friday evening, budget £2,000, two adults, window seats preferred",
   **When** the system parses the goal,
   **Then** the structured objective contains origin = LHR/London, destination
   = SIN/Singapore, latest acceptable arrival = Friday 23:59 local, budget =
   £2,000 GBP (hard), travellers = 2, preference = window seats (soft), and
   each element is classified as hard or soft.

2. **Given** a traveller's goal omits the number of travellers,
   **When** the system identifies the gap,
   **Then** the system asks the traveller for the missing value before
   presenting a parsed objective; it does not default to 1.

3. **Given** the system presents a parsed objective,
   **When** the traveller confirms it,
   **Then** a journey record is created in durable storage with a unique
   identifier, the confirmed objective, and state = OBJECTIVE_CONFIRMED;
   no flight search is initiated.

4. **Given** the system presents a parsed objective,
   **When** the traveller rejects it or requests a correction,
   **Then** the system re-prompts for the corrected information and does not
   create a journey record until confirmation is received.

---

### User Story 2 — Hard Constraint vs. Soft Preference Classification (Priority: P2)

The traveller's stated goal contains a mix of non-negotiable constraints
and preferences. The system classifies each element and records that
classification so that downstream scoring and disruption assessment can
distinguish between them.

**Why this priority**: Without this classification, the system cannot tell
whether missing a connection violates the objective or merely falls short
of a preference. The distinction determines whether recovery is mandatory.

**Independent Test**: Can be fully tested by submitting goals with explicit
and implicit constraints, then asserting the classification of each extracted
element against expected hard/soft values.

**Acceptance Scenarios**:

1. **Given** a stated budget with the word "maximum" or a definite ceiling,
   **When** the objective is parsed,
   **Then** the budget is classified as a hard constraint.

2. **Given** a stated preference for a window seat,
   **When** the objective is parsed,
   **Then** the seat preference is classified as a soft preference.

3. **Given** a stated latest acceptable arrival time ("must arrive by"),
   **When** the objective is parsed,
   **Then** the arrival time is classified as a hard constraint.

4. **Given** the objective contains any ambiguity in constraint vs. preference
   classification,
   **When** the system identifies the ambiguity,
   **Then** the system asks the traveller to confirm the classification rather
   than defaulting.

---

### User Story 3 — Journey State and Audit Trail (Priority: P2)

Once a journey record exists, the system maintains its state through defined
transitions and records every observation, decision, external call, and
authorisation outcome in an append-only audit trail with timestamps.

**Why this priority**: The audit trail and state machine are the backbone
of trust and recoverability. Without them, the system cannot demonstrate
what happened or why.

**Independent Test**: Can be fully tested by advancing a journey through
state transitions, asserting only permitted transitions are accepted, and
verifying the audit trail grows append-only with correct entries.

**Acceptance Scenarios**:

1. **Given** a journey in state OBJECTIVE_CONFIRMED,
   **When** a permitted downstream event triggers a state transition,
   **Then** the journey state updates to the next defined state and the
   transition is recorded in the audit trail with a timestamp.

2. **Given** a request to transition a journey to a state not reachable from
   its current state,
   **When** the transition is attempted,
   **Then** the system rejects it and the journey state is unchanged.

3. **Given** any observation, decision, or external call occurs,
   **When** it is recorded in the audit trail,
   **Then** the entry is appended with a timestamp; no prior entry is modified
   or deleted.

4. **Given** an authorisation request is made and the traveller refuses,
   **When** the refusal is recorded,
   **Then** the audit trail contains an entry for the authorisation request
   and a separate entry for the refusal, each with a timestamp.

---

### User Story 4 — Journey State Persistence and Reconstruction (Priority: P3)

The journey record is stored in durable storage outside any running process.
If the process handling a journey terminates, the complete journey can be
fully reconstructed and resumed from storage.

**Why this priority**: Durability is essential for a travel guardian operating
across long time horizons (hours to days), but can be delivered independently
of the capture and classification stories.

**Independent Test**: Can be fully tested by creating a journey, terminating
the handling process, re-loading the journey from storage, and asserting
that state, objective, and audit trail are identical to their pre-termination
values.

**Acceptance Scenarios**:

1. **Given** a journey record has been created and populated,
   **When** the process handling it is terminated and restarted,
   **Then** the journey can be fully reconstructed from storage with no
   loss of state, objective, audit entries, or held identifiers.

2. **Given** the journey record is the single source of truth,
   **When** any journey state is queried,
   **Then** the response is derived exclusively from the persisted record,
   not from any in-process cache or language model context.

---

### User Story 5 — Held Identifier Staleness Tracking (Priority: P3)

For every externally issued identifier the journey holds, the system records
when it was issued and when it becomes stale, so that downstream steps can
verify freshness before use.

**Why this priority**: Dependent on journey creation (US3) but does not
block the primary capture flow. Stale-identifier detection is essential
before booking or payment but can be proven in isolation.

**Independent Test**: Can be fully tested by recording a held identifier with
issue and staleness times, then asserting that a query before the staleness
time returns "fresh" and a query after it returns "stale".

**Acceptance Scenarios**:

1. **Given** an externally issued identifier is added to the journey,
   **When** the identifier is recorded,
   **Then** the record contains both the issue time and the staleness
   threshold.

2. **Given** a held identifier whose staleness threshold has passed,
   **When** the identifier's freshness is queried,
   **Then** the system returns stale; it does not silently treat the
   identifier as valid.

---

### Edge Cases

- What happens when the traveller's natural-language goal contains
  contradictory constraints (e.g., budget below realistic minimum for the
  route)?
- What happens when the same goal is submitted twice — does the system
  create two journey records or detect the duplicate?
- What happens when the confirmed objective is modified after the journey
  record is created?
- How does the system handle a goal that specifies no destination?
- What happens when the storage layer is unavailable at the moment the
  journey record should be persisted?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a travel goal stated in natural language.
- **FR-002**: The system MUST extract from the stated goal a structured
  objective containing: origin, destination, latest acceptable arrival time,
  budget with currency, number of travellers, and stated preferences.
- **FR-003**: The system MUST classify each extracted objective element as
  either a hard constraint or a soft preference, and MUST record that
  classification alongside the element.
- **FR-004**: The system MUST present the fully parsed objective to the
  traveller for confirmation before any downstream action is taken.
- **FR-005**: The system MUST identify elements that were absent or ambiguous
  in the stated goal and MUST ask the traveller to supply them; it MUST NOT
  infer, default, or assume a value for any absent travel fact.
- **FR-006**: The system MUST create a journey record containing a unique
  journey identifier, the confirmed objective, and an initial journey state
  upon traveller confirmation.
- **FR-007**: The system MUST maintain a defined set of journey states and
  MUST permit only documented transitions between them; any attempt to
  perform an undocumented transition MUST be rejected.
- **FR-008**: The system MUST persist the full journey record in durable
  storage external to any running process, such that the journey can be
  completely reconstructed after process termination.
- **FR-009**: The system MUST record, for each externally issued identifier
  it holds, the time the identifier was issued and the time at which it
  should be considered stale.
- **FR-010**: The system MUST maintain an append-only audit trail for each
  journey, recording every observation, decision, external call, and
  authorisation event with a timestamp; no entry may be modified or deleted
  after it is written.
- **FR-011**: The system MUST expose the current journey state, confirmed
  objective, and full audit trail for display on demand.
- **FR-012**: The system MUST record the outcome of every authorisation
  request, including refusals, in the journey audit trail.

### Non-Functional Requirements

- **NFR-001**: The journey record in durable storage is the single source of
  truth for journey state. No journey state required for correctness may
  reside only in a language model context window or in process memory.
- **NFR-002**: The audit trail is append-only. No entry may be modified or
  deleted after it is written.
- **NFR-003**: The system MUST NOT author, infer, or default any travel fact.
  Absent information MUST be requested from the traveller.
- **NFR-004**: Objective parsing MUST be reproducible: the same stated goal,
  submitted under the same conditions, MUST produce the same structured
  objective.

### Key Entities

- **TravelObjective**: The structured representation of the traveller's goal.
  Contains origin, destination, latest acceptable arrival time, budget
  (amount + currency), number of travellers, stated preferences, and a
  hard/soft classification for each element.

- **JourneyRecord**: The root entity persisted in durable storage. Contains
  a unique journey identifier, the confirmed TravelObjective, current
  JourneyState, held external identifiers (each with issue time and staleness
  threshold), audit trail, and authorisation history.

- **JourneyState**: An enumerated set of states a journey may occupy, with
  documented permitted transitions between them. Initial state is
  OBJECTIVE_CONFIRMED upon creation.

- **AuditEntry**: An immutable record appended to the journey audit trail.
  Contains a timestamp, entry type (observation, decision, external call,
  authorisation), and the recorded content.

- **HeldIdentifier**: A reference to an externally issued identifier stored
  within the journey record. Contains the identifier value, the time it was
  issued, and the staleness threshold.

- **AuthorisationOutcome**: A record of an authorisation request and its
  result (approved or refused), linked to the relevant AuditEntry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A traveller can state a complete travel goal and receive a
  confirmed journey record in under two minutes from first input to
  confirmation.
- **SC-002**: Every absent or ambiguous element in a stated goal is surfaced
  as a question to the traveller; zero travel facts are defaulted or inferred
  silently.
- **SC-003**: The audit trail for any journey contains a complete, ordered
  record of all events from objective capture to the present moment, with
  no gaps.
- **SC-004**: A journey terminated mid-session is fully reconstructable from
  durable storage with no loss of state, objective, or audit history.
- **SC-005**: The same natural-language goal submitted in two separate
  sessions produces identical structured objectives (same fields, same
  classifications), confirming reproducibility.
- **SC-006**: Every hard-constraint element in a confirmed objective is
  correctly classified in 100% of test cases covering the defined constraint
  vocabulary.

## Assumptions

- The traveller interacts with the system through a single session at a time;
  concurrent multi-session editing of the same journey is out of scope.
- "Durable storage" means storage that survives process restart; the specific
  storage technology is a planning-phase decision.
- Journey states and permitted transitions are defined during the planning
  phase; this specification establishes the requirement for a state machine
  but does not enumerate all states.
- The authorisation policy engine (which produces authorisation outcomes
  recorded by FR-012) is implemented by a separate feature; this feature
  treats it as a black-box producer of outcomes.
- The language model used for natural-language parsing is treated as an
  implementation detail; this specification requires only that parsing be
  reproducible (NFR-004).
- Currency codes follow ISO 4217; the system records the currency as stated
  by the traveller and does not perform conversion.
- "Latest acceptable arrival time" is interpreted as a hard constraint unless
  the traveller explicitly states it is a preference.
- Duplicate journey detection (two submissions of the same goal) is out of
  scope for this feature.

## Out of Scope

- Flight search, option scoring, and price verification.
- Booking, ticketing, and payment.
- Disruption monitoring and recovery.
- The authorisation policy engine (referenced here only as a producer of
  authorisation outcomes).
- Multi-traveller profile management.
- Modification of a confirmed objective after the journey record is created.
