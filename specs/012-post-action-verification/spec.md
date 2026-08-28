# Feature Specification: Post-Action Verification

**Feature Branch**: `012-post-action-verification`

**Created**: 2026-08-28

**Status**: Draft

**Input**: Cross-cutting policy definition. Not tied to one external
endpoint section — grounded in verified instances scattered across
`.antabay/atlas-capability-map.md` §7b–7c (verified against the Atlas API
sandbox on 2026-08-15): a booking reference is issued before payment and
is not proof of a ticket; a successful payment response left
`ticketStatus` at `"0"` with empty `ticketNos`; the `order.ticketed`
webhook is unauthenticated and must be treated as "an untrusted hint," not
a fact, until confirmed against `queryOrderDetails.do`; and that same
webhook reports `orderStatus` as an integer while the REST query reports
it as a string.

---

## Business Context

**Business Goal**: Establish independently, after every state-changing
action, what actually happened, and update journey state only from that.

**Business Value**: Confirmed twice in live testing: a successful payment
response does not mean a ticket exists. An agent that trusts its own
writes will report success that did not occur.

**Business Actors**:
- Agent — performs state-changing actions and is the sole consumer of
  this feature's verification gate before updating journey state

**Business Capability**: Truth Reconciliation

**Reference**: `.antabay/atlas-capability-map.md` — no single section owns
this feature; it generalises a pattern already observed in multiple
places in that document (see Input above). Feature 005 (Order Creation
and Payment) already implements one instance of this pattern for
`order.do`/`pay.do`/`queryOrderDetails.do`; this specification defines
the general rule that instance is an example of, so that every future
state-changing action (refunds, void, rebooking, and others not yet
built) is held to the same discipline rather than reinventing it
ad hoc.

---

## Clarifications

### Session 2026-08-28

- Q: FR-007 says an unresolved outcome is reconciled "by querying again," but doesn't say when to stop. Should this feature impose a universal retry/duration cap, or leave that to each action type? → A: Leave the reconciliation bound to each action type's own FR-003 definition (e.g., 005's ticketing deadline) — this feature only requires that *some* bound exists and is respected, not what it is.
- Q: When the independent query reports the affected record doesn't exist at all (not-found) right after a state-changing action was attempted, how should that be classified? → A: Treat not-found as potentially transient (e.g. provider-side propagation delay) — reconcile as unresolved by querying again up to the action type's declared bound (FR-003); only classify as failure if the bound is reached with the record still missing.
- Q: Two verification attempts for the same record run concurrently and would derive different journey states — which one wins? → A: The query with the most recent observed timestamp wins, regardless of which verification attempt started or finished first locally.
- Q: When verification is still unresolved and something asks for the reportable outcome, should this feature expose a distinct "pending" status, or simply have nothing available? → A: Nothing available — querying for a reportable outcome before verification concludes returns absence; this feature defines no pending/in-progress status of its own.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Independent Confirmation Gate (Priority: P1)

After any state-changing action completes, the agent does not update
journey state from that action's own response. It instead issues an
independent query of the affected record and updates state only from
what that query shows. For each type of action, a specific, observable
condition is defined in advance as the only thing that counts as success
for that action — and for ticketing specifically, that condition is the
presence of issued ticket numbers, nothing else.

**Why this priority**: This is the mechanism itself. Every other story in
this feature exists to support, audit, or handle the edge cases of this
one gate. Without it, nothing else here has anything to attach to.

**Independent Test**: Perform a state-changing action, confirm no journey
state changes until an independent query has run, and confirm the query's
result — not the action's response — is what state is derived from.
Confirm that for a ticketing action specifically, a response with issued
ticket numbers is the only condition accepted as success.

**Acceptance Scenarios**:

1. **Given** a state-changing action has just returned a response,
   **When** journey state is about to be updated, **Then** an independent
   query of the affected record has already been made, and the update is
   derived from that query's result, not from the action's response.

2. **Given** a new type of state-changing action is introduced, **When**
   this feature is applied to it, **Then** a specific, observable success
   condition has been defined for that action type before any journey
   state is derived from it — there is no default or inherited condition.

3. **Given** a ticketing action, **When** the affected record is queried,
   **Then** the presence of non-empty issued ticket numbers is the only
   condition treated as evidence that a ticket exists — a booking
   reference or a successful payment response is not.

---

### User Story 2 — Discrepancy Detection and Audit Trail (Priority: P1)

Every time an action's own response and the subsequent independent query
disagree about what happened, that disagreement is recorded — not
silently resolved in favour of either one. Every verification attempt,
and its result, is written to the journey's audit trail, whether or not a
discrepancy was found.

**Why this priority**: A verification step that only records outcomes
when they're clean has no value in the case that matters — when the
action's own response and reality differ. This is also the trail that
makes the business value ("confirmed twice in live testing") auditable
after the fact rather than anecdotal.

**Independent Test**: Perform an action whose own response claims one
outcome while the subsequent query shows another, and confirm the
discrepancy is recorded. Perform an action where both agree, and confirm
the verification attempt is still recorded in the audit trail.

**Acceptance Scenarios**:

1. **Given** an action's response indicates success, **When** the
   independent query shows a different actual state, **Then** the
   discrepancy between the two is recorded, not discarded.

2. **Given** any independent query is performed as part of this
   verification gate, **When** it completes, **Then** the attempt and its
   result are written to the journey audit trail, regardless of whether a
   discrepancy was found.

---

### User Story 3 — Unresolved Outcome Handling (Priority: P1)

When the independent query itself cannot establish what happened — its
own call fails, times out, or returns something inconclusive — the
outcome is recorded as unresolved. It is not treated as either a success
or a failure. An unresolved outcome is reconciled by querying again, never
by repeating the original action.

**Why this priority**: Guessing in either direction on an inconclusive
result is exactly the failure mode this feature exists to prevent — an
optimistic guess produces a false success report; a pessimistic guess can
trigger a needless and possibly harmful repeat of a state-changing action.

**Independent Test**: Simulate a verification query that itself fails to
return a usable result, and confirm the outcome is recorded as unresolved
rather than success or failure. Confirm that resolving it triggers another
query, never a repeat of the original action.

**Acceptance Scenarios**:

1. **Given** an independent query cannot establish the affected record's
   state, **When** the verification attempt concludes, **Then** the
   outcome is recorded as unresolved — not success, not failure.

2. **Given** an unresolved outcome exists, **When** it is later
   reconciled, **Then** reconciliation happens by querying again, and the
   original state-changing action is never repeated as a way of resolving
   it.

3. **Given** an action type's declared reconciliation bound (FR-003) is
   reached and every query attempt was inconclusive (not a clean
   not-found), **When** that bound is hit, **Then** the outcome remains
   recorded as unresolved — it is not assumed to be a success or a
   failure just because reconciliation has stopped.

4. **Given** an action type's declared reconciliation bound (FR-003) is
   reached and every query attempt cleanly reported the record as
   not-found, **When** that bound is hit, **Then** the outcome is
   classified as failure — the not-found result is trusted once the
   transient-propagation grace period this bound represents has elapsed.

---

### User Story 4 — Cross-Surface Type Normalisation (Priority: P2)

When the same status is reported with a different data type by the query
interface and by an event notification about the same record, the two are
normalised to a common type before being compared to each other or used
to detect a discrepancy.

**Why this priority**: Without this, a type mismatch that carries no real
meaning (the same status, reported as a string in one place and an
integer in another) would be misread as a substantive discrepancy —
undermining User Story 2's audit trail with false positives, or worse,
masking a real one underneath the noise.

**Independent Test**: Feed the verification gate a query result and an
event notification reporting the same underlying status in two different
data types, and confirm they are treated as equal, not as a discrepancy.

**Acceptance Scenarios**:

1. **Given** a query interface reports a status as one type and an event
   notification about the same record reports the equivalent status as a
   different type, **When** the two are compared, **Then** they are
   normalised to a common type first, and are treated as equal.

---

### User Story 5 — Verified-Only Reporting (Priority: P2)

Whatever ultimately reports outcomes to the traveller may only report
outcomes that this feature has independently verified. An outcome that is
still unresolved, or that has only been claimed by an action's own
response, is not available to be reported as fact.

**Why this priority**: This is the payoff of the whole feature from the
traveller's side — but it is a gate on what data is *available* to
reporting, not the reporting mechanism itself, which is explicitly out of
scope here.

**Independent Test**: Attempt to read a reportable outcome for an action
that has not yet been independently verified, and confirm none is
available. Confirm a verified outcome becomes available once verification
completes.

**Acceptance Scenarios**:

1. **Given** an action has completed but its independent verification has
   not, **When** something attempts to read a reportable outcome for it,
   **Then** no verified outcome is available — not a placeholder
   "pending" value, just absence.

2. **Given** independent verification has completed for an action,
   **When** the same is attempted, **Then** the verified outcome — and
   only that — is available to be reported.

---

### Edge Cases

- An action type is unusual in that the provider's own duplicate-handling
  makes *repeating the action* the only practical way to discover an
  unresolved outcome (as established for order creation in spec 005 —
  a timed-out `order.do` call is reconciled by retrying it, because no
  record exists yet to query directly, and the provider's own duplicate
  rejection on retry *is* the independent signal). This is a structural
  exception to FR-007's general rule, not a violation of it: the retry in
  that case functions as the query, because the provider's duplicate
  check is itself the independent confirmation mechanism. Whether an
  action type has this property MUST be established explicitly per type
  (see FR-003), never assumed as a general escape hatch from FR-007.
- An event notification arrives claiming an outcome before any
  corresponding action was ever performed by this agent (an unsolicited
  or out-of-band event). It is still treated as an unverified hint,
  reconciled the same way as any other unresolved outcome — not acted on
  directly regardless of its origin.
- An action type's declared reconciliation bound (FR-003) is reached with
  every query attempt genuinely inconclusive (not a clean not-found). The
  outcome stays unresolved rather than defaulting to success or failure;
  whatever consumes an unresolved outcome past its bound (e.g.,
  escalation, operator attention) is a concern of the action-type-specific
  feature that owns that bound, not of this general policy.
- The same bound is reached, but every query attempt cleanly reported the
  record as not-found the whole time. Unlike the case above, this
  resolves to failure, not unresolved — a consistent not-found result is
  treated as definite once the transient-propagation grace period has
  run out (FR-006, FR-007).
- The independent query itself returns a response that is inconsistent
  with all previously defined success/failure conditions for that action
  type (an unrecognised status). This is treated as unresolved, not as an
  implicit success or failure.
- Two verification attempts for the same action run close together (for
  example, one triggered by the agent's own follow-up and one triggered
  by an incoming event notification about the same record). Both are
  recorded independently in the audit trail; neither is discarded as
  redundant. If they would derive different journey states, the one whose
  query observed the record more recently governs, even if the other
  finishes being processed first (FR-011).
- A verification attempt that observed the record earlier finishes being
  processed *after* one that observed it later (e.g. it was queued behind
  a slower query call). The later-observing attempt's result still
  governs state, because ordering is by observed timestamp, not by local
  processing order.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST follow every state-changing external action
  with an independent query of the affected record before that action's
  outcome is treated as known.

- **FR-002**: The system MUST update journey state only from the result of
  that independent query, never from the response returned by the action
  itself. When more than one query result for the same record is being
  processed concurrently, the one with the most recent observed timestamp
  MUST govern the resulting state, regardless of which verification
  attempt started or finished being processed first (FR-011).

- **FR-003**: The system MUST define, for each type of state-changing
  action, the specific observable condition — checked via the independent
  query — that constitutes success for that action type. No action type
  may rely on a default or borrowed condition. This definition MUST
  include a bound on how long or how many times reconciliation may
  continue for an unresolved outcome of that action type (for example,
  005's ticketing deadline) — this feature does not impose one universal
  bound across all action types, but every action type MUST have one.

- **FR-004**: The system MUST treat the presence of non-empty issued
  ticket numbers as the only evidence that a ticket exists. A booking
  reference and a successful payment response are explicitly insufficient
  (this is the canonical, previously-confirmed instance of FR-003).

- **FR-005**: The system MUST record any discrepancy between an action's
  own response and the state subsequently observed by the independent
  query, rather than silently preferring one over the other.

- **FR-006**: The system MUST treat an outcome that its independent query
  cannot establish as unresolved — neither success nor failure. This
  includes both a query that fails to execute or return usable data, and
  a query that cleanly reports the affected record does not exist at all
  immediately after the action — the latter MUST be treated as
  potentially transient (e.g. provider-side propagation delay) rather
  than immediately conclusive, subject to FR-007's bound.

- **FR-007**: The system MUST reconcile an unresolved outcome by querying
  again, up to the bound that action type's FR-003 definition declares.
  It MUST NOT resolve an unresolved outcome by repeating the original
  action (see Edge Cases for the one structural exception this applies
  to, and how it differs from a general escape hatch). Once that bound is
  reached: if the record was never found by any query, the outcome MUST
  be classified as failure (a not-found result is definite enough to
  trust once the transient-propagation grace period has elapsed); for
  every other kind of inconclusive query result, the outcome remains
  unresolved rather than being assumed as either success or failure.

- **FR-008**: The system MUST normalise status values to a common type
  before comparing a value reported by the query interface with the
  equivalent value reported by an event notification, whenever the two
  surfaces report that status using different data types.

- **FR-009**: The system MUST record every verification attempt and its
  result in the journey's audit trail, whether or not a discrepancy was
  found and whether the outcome was success, failure, or unresolved.

- **FR-010**: The system MUST make available for reporting to the
  traveller only those outcomes that have been independently verified by
  this feature. An outcome pending verification, or known only from an
  action's own response, MUST NOT be available to be reported as fact.
  This feature defines no distinct "pending" or "in progress" reportable
  status of its own — absence of a Reportable Outcome is itself the
  signal that verification has not yet concluded; anything that presents
  status to the traveller (out of scope here) is free to render that
  absence however it chooses.

- **FR-011**: Every Verification Attempt MUST carry the timestamp at which
  its query observed the affected record's state. When two or more
  verification attempts for the same record are processed concurrently
  and would derive conflicting journey states, the attempt whose observed
  timestamp is most recent MUST be the one that governs — a verification
  attempt that happens to finish local processing first, but observed the
  record earlier, MUST NOT override a later observation processed after
  it. Every attempt is still recorded in full (FR-009) regardless of
  whether it governed the resulting state.

### Non-Functional Requirements

- **NFR-001**: Verification MUST be expressed in terms of externally
  observable state (what an independent query of the provider reports),
  never in terms of the system's own return values, internal flags, or
  the response object the action itself produced.

### Key Entities

- **Verification Attempt**: One independent query performed to establish
  the actual outcome of a state-changing action. Carries which action it
  verifies, the query's result, the timestamp at which that result was
  observed (FR-011 — distinct from when the attempt finished local
  processing), the resulting classification (success / failure /
  unresolved per FR-003's definition for that action type), and whether a
  discrepancy against the action's own response was found. Always
  recorded in the audit trail (FR-009), regardless of outcome.

- **Success Condition**: The per-action-type, observable, query-derived
  definition of what counts as success (FR-003). Ticketing's success
  condition (FR-004) is the reference example every other action type's
  definition is held to the same standard as.

- **Discrepancy**: The recorded fact that an action's own response and
  the independently observed state disagreed. Not a resolution of which
  one was "right" — the independently observed state always governs
  (FR-002) — but a preserved record that the disagreement happened.

- **Unresolved Outcome**: The state of an action whose independent
  verification could not establish success or failure. Distinct from
  both; reconciled only by further querying (FR-007), never by repeating
  the action (except the structural exception in Edge Cases), up to that
  action type's declared reconciliation bound (FR-003). If every query
  attempt was a clean not-found for the affected record, reaching the
  bound resolves the outcome to failure; for every other kind of
  inconclusive result, reaching the bound leaves it unresolved rather
  than reclassifying it as success or failure.

- **Reportable Outcome**: The subset of verified outcomes exposed for
  traveller-facing reporting (FR-010). Does not exist for an action until
  its Verification Attempt has concluded with success or failure —
  unresolved outcomes are never reportable as fact. Has no "pending"
  variant: its absence, not a placeholder value, is what signals that
  verification has not yet concluded.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No journey state update is ever derived directly from a
  state-changing action's own response in any recorded test scenario — an
  independent query always precedes it, confirmed on every push.

- **SC-002**: Zero instances, across the test suite, of a booking
  reference or a payment-success response being treated as ticketing
  evidence — only non-empty issued ticket numbers ever are.

- **SC-003**: Every discrepancy between an action's response and its
  independently observed state is present in the audit trail in 100% of
  test scenarios that create one — none are silently dropped.

- **SC-004**: An unresolved outcome is never reported to the traveller as
  either a success or a failure in any recorded test scenario, and is
  never followed by a repeat of the original action (structural
  exception aside) — only by a further query.

- **SC-005**: A status reported in two different data types by the query
  interface and an event notification for the same underlying value
  produces zero false-positive discrepancies in the test suite.

- **SC-006**: Every verification attempt performed in a test scenario has
  a corresponding audit trail entry — 100%, including attempts that found
  no discrepancy.

- **SC-007**: Every action type exercised in the test suite has a declared
  reconciliation bound (FR-003). Reaching that bound with a genuinely
  inconclusive query result produces a persisted unresolved outcome 100%
  of the time; reaching it with a consistently not-found result produces
  a persisted failure outcome 100% of the time — never the reverse of
  either.

- **SC-008**: When two concurrent verification attempts for the same
  record would derive different journey states in a test scenario, the
  resulting state always matches the query with the more recent observed
  timestamp, 100% of the time — including scenarios where that query's
  attempt finishes local processing after the other one.

---

## Out of Scope

- The state-changing actions themselves (order creation, payment,
  refunds, void, rebooking, and any other action this gate is applied
  to) — this feature defines and enforces the verification discipline
  that wraps them, not the actions' own request/response handling
- Authorisation policy (whether an action was permitted to run in the
  first place)
- Presentation (how a verified or reportable outcome is displayed to the
  traveller or an operator) — FR-010 governs only what is *available* to
  be reported, not how

---

## Assumptions

- Feature 005's `BookingService.confirm_ticketing()` (and its handling of
  the `order.do` uncertain-outcome retry) is treated as the first
  concrete instance of this feature's general pattern, not as a
  competing implementation — see the Edge Cases entry reconciling
  FR-007's "never repeat the action" rule with 005's documented
  exception for order creation specifically.
- "Independent query" means a read against the provider that carries no
  state-changing effect of its own — consistent with how spec 005
  already treats `queryOrderDetails.do` as freely repeatable.
- This feature defines the verification *discipline* as a set of rules
  every action type must satisfy; it does not mandate a single shared
  code path that all current and future actions must call through,
  since some actions may have structurally different query mechanisms
  (as the order-creation exception already shows).
- The cross-surface type-normalisation rule (FR-008) is grounded in the
  one verified instance currently known — `orderStatus` reported as a
  string by `queryOrderDetails.do` and as an integer by the
  `order.ticketed` webhook (`.antabay/atlas-capability-map.md` §7c) — and
  generalises to any future surface pair exhibiting the same pattern.
- An inbound webhook or other event notification is never, by itself, a
  Verification Attempt's query — per the capability map's own framing,
  it is an unverified hint that *triggers* one.
