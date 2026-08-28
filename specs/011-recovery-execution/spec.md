# Feature Specification: Recovery Execution

**Feature Branch**: `011-recovery-execution`

**Created**: 2026-08-28

**Status**: Draft

**Input**: The point at which the product delivers on its promise. The
provider offers no facility to change an existing booking, so recovery is
the creation of a replacement booking, followed by cancellation of the
superseded one — a two-outcome sequence where ordering is itself a safety
property.

---

## Business Context

**Business Goal**: Carry out an authorised recovery, confirm independently
that it succeeded, and return the journey to monitoring with its objective
intact.

**Business Value**: This is the point at which the product delivers on its
promise. Everything upstream — detection, evaluation, authorisation — is
preparation; this feature is where the traveller's objective is actually
restored, or where it is not, and that outcome is made unambiguous.

**Business Actors**:
- Agent — executes the authorised recovery, independently verifies each
  outcome, and returns the journey to monitoring
- Traveller — receives the final position stated in terms of the objective

**Business Capability**: Outcome Restoration

**Reference**: The provider offers no facility to change an existing
booking. Recovery is therefore the creation of a replacement booking,
followed by cancellation of the superseded one — not an atomic operation,
but two independently-verified steps whose order is itself a safety
property (Constitution Principle V — Honest Simulation / independent
verification; Principle XIV — Auditability).

---

## Clarifications

### Session 2026-08-28

- Q: When execution is abandoned (price changed, sold out) or a step fails, what state does the journey return to? → A: The journey returns to monitoring immediately, so a fresh evaluation/authorisation cycle can pick it up on the next relevant trigger — consistent with this feature's own "no step repeated on an uncertain outcome" discipline; an abandoned or failed execution does not leave the journey stuck in a recovery-pending limbo state.
- Q: Does recovery execution's provider-facing activity (pre-execution verification, booking creation, ticketing confirmation, cancellation) count against the journey's call budget? → A: Yes — consistent with feature 009's existing precedent that every provider-facing search or verification call is tracked against the journey's call budget, this feature's calls are tracked the same way rather than being treated as exempt.
- Q: If the same authorisation is presented for execution a second time (duplicate trigger, retry, or re-delivery), should a second execution attempt proceed? → A: No — an authorisation can only ever produce one execution attempt; a second trigger against an already-consumed or in-progress authorisation is refused rather than re-executed, mirroring feature 007's established "tolerate duplicates without duplicating any resulting action" precedent.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Execute Only What Was Authorised (Priority: P1)

The agent executes a recovery action only when authorisation has been
granted for that specific action. Immediately before executing, it
re-verifies the alternative; if its price has changed since authorisation,
the agent abandons execution rather than proceeding on stale terms.

**Why this priority**: Executing an action beyond its authorised scope, or
on since-invalidated terms, is the exact failure this feature exists to
prevent — everything else in the feature only matters once this boundary
holds.

**Independent Test**: Attempt execution without a matching authorisation
and confirm it is refused. Separately, authorise an alternative, alter its
price before execution begins, and confirm execution is abandoned rather
than proceeding.

**Acceptance Scenarios**:

1. **Given** a recovery action with no matching authorisation, **When**
   execution is attempted, **Then** it is refused.

2. **Given** an authorised alternative, **When** execution is about to
   begin, **Then** the alternative is verified immediately beforehand.

3. **Given** the alternative's price has changed since authorisation was
   granted, **When** this is discovered during pre-execution verification,
   **Then** execution is abandoned rather than proceeding on the changed
   terms.

---

### User Story 2 — Secure the Replacement Before Releasing the Original (Priority: P1)

The agent creates and pays for the replacement booking, then confirms its
ticketing by an independent query before treating it as successful. Only
once the replacement is confirmed does the agent initiate cancellation of
the superseded booking. The journey's current booking is updated only
after the replacement is confirmed, and the journey never ends a recovery
attempt without a confirmed booking of some kind.

**Why this priority**: This is the safety property the entire feature is
built around — replacement secured before original released, never the
reverse. Getting the ordering wrong is the one failure mode that can leave
a traveller with no confirmed booking at all.

**Independent Test**: Execute a recovery and confirm the replacement is
created, paid for, and its ticketing confirmed by independent query before
any cancellation of the original is initiated. Confirm the journey's
current booking only changes after that independent confirmation.
Separately, force replacement failure and confirm the original booking is
left untouched.

**Acceptance Scenarios**:

1. **Given** authorisation and a verified alternative, **When** recovery
   executes, **Then** a replacement booking is created and paid for.

2. **Given** a replacement booking has been created and paid for, **When**
   its success is being determined, **Then** this is established by an
   independent query confirming ticketing — not by the outcome of the
   creation or payment call alone.

3. **Given** the replacement is not yet independently confirmed, **When**
   this state holds, **Then** cancellation of the superseded booking has
   not been initiated and the journey's current booking has not been
   updated.

4. **Given** the replacement is independently confirmed, **When** this is
   established, **Then** cancellation of the superseded booking is
   initiated and the journey's current booking is updated to the
   replacement.

5. **Given** a recovery attempt of any outcome, **When** it concludes,
   **Then** the traveller is never left without a confirmed booking as a
   result of that attempt.

---

### User Story 3 — Treat Replacement and Cancellation as Separate, Independently Verified Outcomes (Priority: P2)

Replacement and cancellation are not treated as a single combined result.
Each is independently verified, and if the replacement succeeds but
cancellation does not, that partial state is recorded and surfaced rather
than concealed or silently retried into an uncertain outcome. Once
recovery is complete, the journey returns to monitoring, and the final
position is reported to the traveller in terms of the objective. The full
sequence — including the authorisation that permitted it — is recorded in
the audit trail.

**Why this priority**: This is what makes a partial outcome trustworthy
rather than either hidden or repeatedly retried into an unknown state — a
necessary refinement once User Story 2's core ordering guarantee is in
place, but not itself the safety-critical ordering.

**Independent Test**: Force a cancellation failure after a successful,
confirmed replacement, and confirm the resulting state is recorded and
surfaced explicitly — not concealed, and not silently retried. Confirm a
fully successful recovery returns the journey to monitoring and reports
the final position in objective terms, with the full sequence and its
authorising decision present in the audit trail.

**Acceptance Scenarios**:

1. **Given** a replacement has been independently confirmed, **When**
   cancellation of the superseded booking subsequently fails, **Then**
   this exact state — replacement succeeded, cancellation did not — is
   recorded and surfaced, not concealed.

2. **Given** an outcome of uncertain state, **When** the agent considers
   whether to repeat a step, **Then** it does not repeat any step on an
   uncertain outcome — it reconciles that outcome by an independent query
   first.

3. **Given** recovery has completed successfully, **When** this is
   established, **Then** the journey returns to monitoring.

4. **Given** recovery has completed (in any final outcome), **When** the
   traveller is informed, **Then** the final position is reported in terms
   of the objective.

5. **Given** any recovery attempt, **When** it is recorded, **Then** the
   full sequence of steps is present in the audit trail, including the
   specific authorisation that permitted the attempt.

---

### Edge Cases

- The replacement booking fails outright after authorisation was granted
  (for example, payment is declined). The superseded booking is left
  untouched — cancellation is never initiated before a replacement is
  confirmed — and the traveller retains their original, still-valid
  booking.
- The replacement succeeds and is independently confirmed, but
  cancellation of the superseded booking then fails. This partial outcome
  is recorded and surfaced explicitly (User Story 3), and is not treated
  as a reason to retry cancellation blindly — any retry is preceded by an
  independent query establishing the superseded booking's actual current
  state.
- The alternative's price changes between authorisation and the start of
  execution. Pre-execution verification catches this, and execution is
  abandoned (User Story 1) — the agent does not proceed on the
  authorised-but-now-stale price, and does not silently re-authorise
  itself on the new price.
- The alternative sells out between authorisation and execution.
  Pre-execution verification surfaces this the same way a price change
  does — execution is abandoned before any booking or payment attempt is
  made, and the superseded booking is left untouched.
- Cancellation of the superseded booking is attempted outside a window the
  provider permits. This is treated as a failed cancellation outcome under
  User Story 3 — recorded and surfaced, not concealed — since the
  provider's own constraint, not the agent's action, is what caused it.
- Both the replacement and the superseded booking end up active
  simultaneously (cancellation not yet initiated, or itself failed). This
  state is recorded and surfaced explicitly rather than treated as
  success; it is not, on its own, a violation of FR-008 (never leaving the
  traveller without a confirmed booking) since the traveller in this state
  has strictly more confirmed bookings than intended, not fewer.
- Execution is interrupted partway (for example, the agent restarts) after
  the replacement was created but before its ticketing was independently
  confirmed. On resumption, the agent reconciles by an independent query
  before taking any further step — it does not assume the interrupted
  step's outcome and does not repeat payment on an uncertain result.
- A further disruption is confirmed for the journey while a recovery
  execution is already in progress. The in-progress execution is not
  abandoned mid-sequence on the strength of the new disruption alone — the
  safety ordering (replacement before release) still governs whatever step
  is currently in progress; the new disruption is handled once the current
  recovery attempt reaches a recorded, independently-verified outcome.
- Execution is abandoned (price changed, sold out) or a step fails outright
  with no partial outcome to reconcile. The journey returns to monitoring
  immediately rather than being left in a recovery-pending state — the
  same "no step repeated on an uncertain outcome" discipline that governs
  execution itself also governs what happens once execution ends.
- The same authorisation is presented for execution a second time — for
  example, a duplicate trigger or a re-delivered message. The second
  attempt is refused rather than re-executed, whether the first attempt is
  still in progress or has already concluded; an authorisation is consumed
  by, at most, one execution attempt.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST execute a recovery action only when
  authorisation has been granted for that specific action.

- **FR-002**: The system MUST verify the alternative immediately before
  executing, and MUST abandon execution if the alternative's price has
  changed since authorisation.

- **FR-003**: The system MUST create and pay for the replacement booking.

- **FR-004**: The system MUST confirm the replacement's ticketing by an
  independent query before considering the replacement successful.

- **FR-005**: The system MUST initiate cancellation of the superseded
  booking only after the replacement has been confirmed.

- **FR-006**: The system MUST treat replacement and cancellation as
  separate outcomes, each independently verified.

- **FR-007**: The system MUST record a state where the replacement
  succeeded but cancellation did not, and MUST surface that state rather
  than conceal it.

- **FR-008**: The system MUST never leave the traveller without a
  confirmed booking as a result of a recovery attempt.

- **FR-009**: The system MUST update the journey's current booking only
  after the replacement is confirmed.

- **FR-010**: The system MUST return the journey to monitoring once
  recovery is complete, whether that completion is a full success, a
  recorded partial outcome (FR-007), or an abandonment of execution
  (FR-002) — the journey MUST NOT be left in a recovery-pending state
  awaiting further action from this feature.

- **FR-011**: The system MUST record the full sequence of a recovery
  attempt in the audit trail, including the authorisation that permitted
  it.

- **FR-012**: The system MUST report the final position to the traveller
  in terms of the objective.

- **FR-013**: The system MUST count every provider-facing call made during
  recovery execution (pre-execution verification, booking creation,
  ticketing confirmation, cancellation) against the journey's call
  budget.

- **FR-014**: The system MUST refuse a second execution attempt against an
  authorisation that has already been consumed by, or is already in
  progress for, an execution attempt.

### Non-Functional Requirements

- **NFR-001**: Ordering is a safety property — the replacement MUST be
  secured before the superseded booking is released, never the reverse.

- **NFR-002**: No step MUST be repeated on an uncertain outcome; every
  uncertain outcome MUST be reconciled by an independent query before any
  further step is taken.

### Key Entities

- **Recovery Execution**: The bounded attempt to carry out one authorised
  recovery action — beginning with pre-execution verification (FR-002) and
  ending in a recorded outcome (FR-007, FR-011), whether fully successful,
  partially successful, or abandoned.

- **Replacement Booking**: The newly created booking that supersedes the
  original — created and paid for (FR-003), and not treated as successful
  until confirmed by independent query (FR-004).

- **Superseded Booking**: The original booking, cancelled only once the
  replacement is confirmed (FR-005) — never released before the
  replacement is secured (NFR-001).

- **Recovery Outcome**: The recorded, independently-verified result of a
  recovery attempt — distinguishing full success, replacement-succeeded-
  cancellation-failed (FR-007), and abandonment (FR-002), each surfaced
  rather than concealed.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of recovery executions in the test suite are preceded
  by a check confirming authorisation exists for that specific action;
  zero executions proceed without one.

- **SC-002**: 100% of recovery executions in the test suite re-verify the
  alternative immediately before executing, and 100% of executions where
  the price has changed are abandoned rather than proceeding.

- **SC-003**: 100% of replacement bookings in the test suite are confirmed
  by an independent query before being treated as successful.

- **SC-004**: Zero cancellations of a superseded booking are initiated in
  the test suite before the replacement is independently confirmed.

- **SC-005**: 100% of recovery attempts in the test suite conclude with
  the traveller holding at least one confirmed booking.

- **SC-006**: 100% of replacement-succeeded-cancellation-failed outcomes
  produced in the test suite are recorded and surfaced, with zero silently
  concealed or silently retried without an intervening reconciliation
  query.

- **SC-007**: 100% of successfully completed recovery attempts in the test
  suite return the journey to monitoring.

- **SC-008**: 100% of recovery attempts in the test suite have their full
  sequence, including the authorising decision, present in the audit
  trail.

- **SC-009**: 100% of final positions reported to the traveller in the
  test suite are stated in terms of the objective.

- **SC-010**: 100% of provider-facing calls made during recovery
  execution in the test suite are reflected in the journey's call budget
  accounting.

- **SC-011**: 100% of duplicate or repeated execution triggers against an
  already-consumed or in-progress authorisation in the test suite are
  refused, with zero resulting in a second execution attempt.

---

## Out of Scope

- Detecting disruption — this feature begins from an already-authorised
  recovery action (features 007/008's concern)
- Evaluating impact — determining that a recovery is needed at all is
  Impact Evaluation's concern (feature 009), not this feature's
- Scoring alternatives — the alternative arrives already selected and
  recommended (feature 009's concern)
- Obtaining authorisation — this feature consumes an authorisation
  decision already granted (feature 010's concern); it does not request,
  evaluate, or grant one itself

---

## Assumptions

- "That specific action" (FR-001) means the authorisation matches the
  exact alternative and action being executed — an authorisation granted
  for a different alternative, or for the same alternative at a different
  price, does not satisfy FR-001; this is what FR-002's pre-execution
  verification exists to catch when the price itself has drifted.
- "Verify the alternative" (FR-002) reuses feature 004's existing
  verification mechanism rather than a parallel one built for this
  feature specifically — the same discipline already proven for the
  traveller's original selection.
- "Independent query" (FR-004, NFR-002) reuses feature 012's existing
  post-action verification mechanism — confirming an outcome by querying
  the provider directly, not by trusting the response of the action that
  produced it.
- A recovery attempt is a single, bounded sequence triggered by one
  authorisation; a further disruption arriving mid-sequence does not
  interrupt the in-progress attempt (see Edge Cases) but is handled by
  upstream capabilities once the current attempt reaches a recorded
  outcome.
- "Outside the permitted window" cancellation failures are treated as an
  ordinary failed-cancellation outcome (FR-007) rather than a distinct
  error category, since the traveller-facing handling — record, surface,
  do not conceal — is the same regardless of the specific reason
  cancellation failed.
