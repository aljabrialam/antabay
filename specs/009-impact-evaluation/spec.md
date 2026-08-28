# Feature Specification: Objective Impact Evaluation and Alternative Discovery

**Feature Branch**: `009-impact-evaluation`

**Created**: 2026-08-28

**Status**: Draft

**Input**: This is what a wake exists for. Feature 007 (Event Reception
and Reconciliation) and feature 008 (Disruption Injector) both explicitly
exclude "evaluating impact" from their own scope and defer it here — this
feature is what a wake actually does once the agent resumes. It reuses
feature 002 (Flight Search) to search, feature 003 (Option Scoring) to
evaluate against the objective, and feature 004 (Price Verification) to
verify before recommending — the same disciplines already proven for the
traveller's original selection, applied again to whatever would replace
it.

---

## Business Context

**Business Goal**: Determine whether the traveller's objective is still
achievable after a change, and if not, find and price the options that
would restore it.

**Business Value**: This is the difference between reporting a delay and
protecting an outcome. The question is never "is the flight late" but "is
the objective still reachable, and what would it cost to keep it".

**Business Actors**:
- Agent — wakes, reconstructs the journey, evaluates impact, and (when
  needed) searches for and recommends a restoring alternative
- Traveller — receives the evaluation and, when the objective is
  violated, the recommendation

**Business Capability**: Objective Protection

**Reference**: Constitution Principle VI (State Outside the Agent —
"Every agent wake-up MUST rehydrate fully from storage before taking any
action"). Feature 007's `WAKE_REQUESTED` event is what triggers this
feature's evaluation; feature 002/003/004 are reused, not reimplemented,
for search/scoring/verification.

---

## Clarifications

### Session 2026-08-28

- Q: A second confirmed change arrives for the same journey while alternatives from the first are still being searched/scored/verified — does the new change interrupt and restart evaluation, or does the in-progress search finish first? → A: The new change interrupts and restarts evaluation from scratch against the new confirmed state, mirroring features 007/012's "most recent observed wins" precedent for concurrent confirmations.
- Q: Does an alternative exceeding a traveller-stated budget count as breaching a stated constraint (FR-011), or does it need its own distinct treatment? → A: It is treated as a constraint breach like any other, if the budget was stated as a hard constraint — reusing FR-011's existing mechanism rather than inventing a parallel one for cost specifically.
- Q: Does evaluation still run for a journey whose departure has already passed by the time a confirmed change arrives? → A: No — a journey already past departure is treated the same way feature 007 already treats a terminal journey: the change is still recorded upstream, but no evaluation, search, or recommendation activity is triggered here, since there is no longer a forward-looking objective to protect.
- Q: If every alternative found expires (its verification freshness lapses) before a decision is made, and none can be re-verified in time, is this reported differently from "no alternative preserves the objective"? → A: No — it is reported identically to FR-012's no-alternative outcome; from the traveller's perspective the result is the same regardless of whether the cause was absence of a suitable alternative or its freshness lapsing before it could be presented.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Evaluate the Confirmed Change Against the Objective (Priority: P1)

On waking, the agent reconstructs the journey and its objective entirely
from durable storage, then evaluates the confirmed change against every
element of that objective. The result is stated in terms of the
objective itself — not in terms of the flight fact that triggered the
wake — and if the objective is now violated, the extent of that
violation is quantified.

**Why this priority**: This is the translation step the entire feature
exists to perform — the business value's central claim ("is the objective
still reachable") is only meaningful if this evaluation happens
correctly, on fully rehydrated state, every single time.

**Independent Test**: Wake the agent for a journey with a known objective
and a confirmed change, and verify the evaluation is performed against
state read fresh from storage (not any cached or in-memory value), that
its result names a specific objective element rather than a raw flight
fact, and that a violation carries a quantified extent.

**Acceptance Scenarios**:

1. **Given** a wake occurs for a journey, **When** the agent begins
   evaluating, **Then** the journey and its objective have been fully
   reconstructed from durable storage first — nothing about the
   evaluation depends on state carried over from before the wake.

2. **Given** a confirmed change, **When** it is evaluated, **Then** every
   element of the traveller's stated objective is checked against it, not
   only the element the change most obviously touches.

3. **Given** an evaluation result, **When** it is stated, **Then** it is
   expressed in terms of the objective (for example, which element is
   affected and how) rather than in terms of the flight fact itself.

4. **Given** the objective is found to be violated, **When** this is
   recorded, **Then** the extent of the violation is quantified, not
   merely flagged as present.

---

### User Story 2 — No Action, Recorded, When the Objective Still Holds (Priority: P1)

When evaluation shows the objective remains satisfied — including when
the change is neutral or actually favourable — the agent takes no further
action. That determination is itself recorded, not left implicit.

**Why this priority**: A system that only speaks up when something is
wrong, and stays silently correct the rest of the time, has no
auditable record of having checked at all. This is the other half of User
Story 1's evaluation — equally necessary for the feature to be trusted.

**Independent Test**: Evaluate a confirmed change that does not violate
the objective (including one that improves the traveller's position), and
confirm no search or recommendation activity occurs, while the
satisfied-objective determination is still recorded.

**Acceptance Scenarios**:

1. **Given** evaluation shows the objective remains satisfied, **When**
   this is determined, **Then** no alternative search, scoring, or
   recommendation activity is triggered.

2. **Given** the objective remains satisfied, **When** the evaluation
   concludes, **Then** that determination is recorded, exactly as a
   violation determination would be.

3. **Given** a confirmed change that improves the traveller's position
   (for example, an earlier arrival) rather than worsening it, **When** it
   is evaluated, **Then** it is treated the same as a neutral change — the
   objective is satisfied, and nothing further is triggered.

---

### User Story 3 — Search, Score, Verify, and Recommend Alternatives When the Objective Is Violated (Priority: P2)

When the objective is violated, the agent searches for alternatives,
evaluates each against the original objective using the same scoring
rules already used for the original selection, and independently verifies
an alternative before ever recommending it. Exactly one alternative is
recommended, with its cost stated relative to the traveller's current
position and a one-sentence reason a traveller could evaluate. If the
only alternative that would restore the objective breaches a stated
constraint, that fact is stated explicitly rather than concealed. If
nothing restores the objective, that is reported plainly. Every search
counts against the journey's call budget.

**Why this priority**: This is the "protect the outcome" half of the
business value — but it is explicitly a P2 because it is the second half
of a two-part capability: nothing here can be demonstrated meaningfully
until User Story 1's evaluation has correctly identified that a violation
exists in the first place.

**Independent Test**: Trigger a violated-objective evaluation and confirm
alternatives are searched for, scored with the same rules as the original
selection, and independently verified before any is recommended. Confirm
the recommendation states cost relative to the traveller's position and a
one-sentence reason. Separately, confirm a constraint-breaching-only
scenario states that fact explicitly, and a no-alternative scenario is
reported rather than silently dropped. Confirm every search performed is
counted against the call budget.

**Acceptance Scenarios**:

1. **Given** the objective is violated, **When** the agent responds,
   **Then** it searches for alternatives rather than stopping at the
   violation report.

2. **Given** a set of candidate alternatives, **When** they are evaluated,
   **Then** they are scored using the same rules already used for the
   traveller's original selection — not a different or relaxed standard.

3. **Given** a candidate alternative, **When** it is being considered for
   recommendation, **Then** it has been independently verified first — no
   alternative is ever recommended on the strength of a search result
   alone.

4. **Given** a verified alternative is recommended, **When** it is
   presented, **Then** its cost is stated relative to the traveller's
   current position, not as a bare absolute price, and the recommendation
   is accompanied by a one-sentence reason the traveller can evaluate.

5. **Given** the only alternative that would restore the objective also
   breaches a constraint the traveller has stated, **When** it is
   presented, **Then** that breach is stated explicitly, not silently
   accepted or silently hidden.

6. **Given** no alternative restores the objective, **When** the search
   concludes, **Then** this is reported plainly — not left as silence
   that could be mistaken for the objective still being satisfied.

7. **Given** any alternative search is performed, **When** it completes,
   **Then** it has been counted against the journey's call budget.

---

### Edge Cases

- A confirmed change affects one element of the objective favourably and
  another unfavourably at the same time (for example, an earlier arrival
  that also removes a stated preferred connection). Each element is
  evaluated on its own terms; an improvement in one does not offset or
  hide a violation in another.
- The alternative search exhausts the journey's remaining call budget
  before a verified alternative is found. This is reported the same way
  as no alternative restoring the objective being found (User Story 3,
  Acceptance Scenario 6) — from the traveller's perspective the outcome is
  identical (no recoverable alternative was surfaced), even though the
  specific reason is available internally for audit.
- Multiple alternatives score equally well against the objective. The
  same ranking and tie-breaking behaviour already used for the original
  selection applies — this feature does not introduce a separate
  tie-breaking rule of its own.
- An alternative that would restore the objective is found and verified,
  but by the time it would be recommended, the freshness window
  established at verification has already elapsed. It is treated as no
  longer verified, and either re-verified or excluded — never recommended
  on stale verification.
- Every alternative found for a violation expires before a recommendation
  decision can be made, and none can be re-verified in time. This is
  reported identically to no alternative preserving the objective at all
  (FR-012) — the traveller-facing outcome is the same either way.
- A second confirmed change arrives for the same journey while
  alternatives from an earlier evaluation are still being searched,
  scored, or verified. The in-progress evaluation is abandoned and
  restarted from scratch against the newly confirmed state — work already
  underway against the superseded state is not carried forward or
  presented.
- A confirmed change arrives for a journey whose departure has already
  passed. No evaluation, search, or recommendation activity is triggered
  — there is no longer a forward-looking objective for this feature to
  protect, consistent with how a terminal journey is already handled
  upstream (feature 007).
- The only alternative that preserves the objective exceeds a budget the
  traveller stated as a hard constraint. This is treated as a constraint
  breach exactly like any other (FR-011) — exceeding a stated budget is
  not a separate category from breaching any other stated constraint.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST reconstruct the journey and its objective
  from durable storage on waking, before any evaluation begins. If the
  journey's departure has already passed by the time a confirmed change
  arrives, no evaluation, search, or recommendation activity MUST be
  triggered — there is no longer a forward-looking objective to protect.

- **FR-002**: The system MUST evaluate the confirmed change against every
  element of the objective, not only the element most directly affected.
  If a second confirmed change arrives for the same journey while an
  earlier evaluation is still in progress (searching, scoring, or
  verifying alternatives), that in-progress evaluation MUST be abandoned
  and restarted from scratch against the newly confirmed state.

- **FR-003**: The system MUST state the result of evaluation in terms of
  the objective — which element, and how — rather than in terms of the
  flight fact that triggered the wake.

- **FR-004**: The system MUST quantify the extent of any violation it
  identifies, not merely record that one exists.

- **FR-005**: The system MUST take no further action when the objective
  remains satisfied — including when the change is neutral or favourable
  — and MUST record that determination.

- **FR-006**: The system MUST search for alternatives when the objective
  is violated.

- **FR-007**: The system MUST evaluate alternatives against the original
  objective using the same scoring rules used for the original selection.

- **FR-008**: The system MUST verify an alternative before recommending
  it.

- **FR-009**: The system MUST express the cost of each alternative
  relative to the traveller's current position, never as an absolute
  price alone.

- **FR-010**: The system MUST recommend exactly one alternative and state
  why.

- **FR-011**: The system MUST state explicitly when the only alternative
  that preserves the objective breaches a stated constraint.

- **FR-012**: The system MUST report when no alternative preserves the
  objective. This report is identical whether the cause is that no
  suitable alternative was ever found, the call budget was exhausted
  first, or every candidate's verification freshness lapsed before a
  decision could be made — the traveller-facing outcome does not
  distinguish between these causes.

- **FR-013**: The system MUST count every alternative search against the
  journey's call budget.

### Non-Functional Requirements

- **NFR-001**: Every alternative presented MUST come from a verified
  provider response — no alternative is ever presented on the strength of
  an unverified search result.

- **NFR-002**: The recommendation MUST be explainable in one sentence a
  traveller can evaluate.

### Key Entities

- **Impact Evaluation**: The determination of whether the objective
  remains satisfied after a confirmed change (FR-002), stated in
  objective terms (FR-003), carrying a quantified violation extent when
  one exists (FR-004).

- **Objective Element**: One hard constraint or preference from the
  traveller's stated objective — the unit each evaluation checks
  individually (FR-002).

- **Alternative**: A candidate replacement option — searched (FR-006),
  scored against the original objective using the existing scoring rules
  (FR-007), and independently verified (FR-008) before it can ever be
  recommended.

- **Recommendation**: The single alternative selected (FR-010), carrying
  its cost relative to the traveller's current position (FR-009) and a
  one-sentence rationale (NFR-002).

- **No-Alternative Report**: The explicit, recorded outcome when no
  alternative restores the objective (FR-012) — never a silent absence.

- **Constraint-Breach Caveat**: The explicit statement accompanying a
  recommendation when the only objective-preserving alternative also
  breaches a stated constraint (FR-011) — distinct from, and more
  specific than, a plain recommendation.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every evaluation in the test suite reconstructs the journey
  and objective from durable storage before proceeding — 100%, with zero
  evaluations observed to depend on carried-over in-memory state.

- **SC-002**: Every evaluation result in the test suite names a specific
  objective element, never only the triggering flight fact — 100%.

- **SC-003**: Every violation recorded in the test suite carries a
  quantified extent — 100%.

- **SC-004**: Zero alternative-search activity occurs in the test suite
  when the objective remains satisfied, and 100% of satisfied-objective
  determinations are recorded regardless.

- **SC-005**: 100% of alternatives presented in the test suite trace to
  an independently verified provider response — zero presented on search
  results alone.

- **SC-006**: 100% of recommendations in the test suite state cost
  relative to the traveller's current position, never as a bare absolute
  price.

- **SC-007**: 100% of recommendations in the test suite carry a
  one-sentence rationale.

- **SC-008**: 100% of test scenarios where the only objective-preserving
  alternative breaches a stated constraint produce an explicit statement
  of that breach.

- **SC-009**: 100% of test scenarios where no alternative preserves the
  objective produce an explicit no-alternative report.

- **SC-010**: 100% of alternative searches performed in the test suite
  are reflected in the journey's call budget accounting.

---

## Out of Scope

- Detecting the change itself — this feature begins from an
  already-confirmed change (features 007/008's concern)
- Authorisation policy — whether a recommended alternative may be acted
  on autonomously or requires the traveller's explicit consent is a
  separate capability's concern
- Executing recovery — creating, paying for, or cancelling any booking as
  a result of a recommendation is not this feature's concern
- Verification of the executed action — once a recovery action is taken
  (elsewhere), confirming it succeeded is Post-Action Verification's
  concern, not this feature's

---

## Assumptions

- "Objective violated" (FR-002, FR-006) means a hard constraint the
  traveller stated is no longer satisfied by the current booking.
  Preferences are ranked, not binary, so a change that only affects
  preference ranking — without breaching a hard constraint — does not on
  its own constitute a violation; it is treated as the objective
  remaining satisfied (User Story 2).
- This feature is invoked only once a change has already been established
  as genuinely confirmed by whatever upstream capability owns detection
  and confirmation (features 007/008); it does not itself interpret or
  re-derive whether a claimed change actually happened.
- "The same scoring rules used for the original selection" (FR-007) means
  feature 003's existing scoring mechanism, invoked the same way — including
  its existing ranking and tie-breaking behaviour — not a parallel or
  relaxed rule set built for this feature specifically.
- Cost expressed relative to the traveller's current position (FR-009) is
  informational only at this feature's boundary; whether that cost is
  acceptable to spend autonomously or requires the traveller's
  authorisation is decided by a separate capability (Authorisation
  Policy), not by this feature.
- If the journey's call budget is exhausted before a verified alternative
  can be found, this is reported identically to no alternative preserving
  the objective (FR-012) — the specific reason is available internally
  for audit, but the traveller-facing outcome is the same: no recoverable
  alternative was surfaced.
