# Feature Specification: End-to-End Demonstration Capture

**Feature Branch**: `014-demonstration-capture`

**Created**: 2026-08-29

**Status**: Draft

**Input**: Produce a repeatable, unattended run of the complete journey
that both verifies the system works and records usable footage of it
working. The product is assessed entirely from a three-minute recording;
a scripted capture can be re-run after any change, at any hour, without a
steady hand or a second take, and is the only end-to-end test that
exercises every feature together.

---

## Business Context

**Business Goal**: Produce a repeatable, unattended run of the complete
journey that both verifies the system works and records usable footage
of it working.

**Business Value**: The product is assessed entirely from a three-minute
recording. A capture that is scripted rather than performed can be re-run
after any change, at any hour, without a steady hand or a second take. It
is also the only end-to-end test that exercises every feature together.

**Business Actors**:
- Operator — triggers the capture, reviews assertion failures, and
  collects the resulting footage

**Business Capability**: Demonstration and End-to-End Verification

**Reference**: `.antabay/demo-sequence-diagram.md` defines the sequence,
its seven segments, and the narration timings the capture must
accommodate. `.antabay/demo-scenario.md` defines the expected values at
each step and records the project's own intended approach: capture a
real end-to-end run as an event stream and drive the recorded footage
from that stream, at a controllable pace, independent of live network
conditions.

---

## Clarifications

### Session 2026-08-29

- Q: The reference narration is fixed and pre-written around specific
  real values (ZE605 at $90.39, the Busan trap at $98.93, LJ201 recovery
  at +$6.24) — if a fresh live run returns different prices or a
  different winning option, footage from that run would no longer match
  the narration even though the run is structurally correct. Should
  there be one designated, verified event-stream capture that is the
  canonical source for submission footage, rather than treating every
  live run as equally valid for producing final footage? → A: Yes — one
  designated, verified event-stream capture is the canonical source for
  submission footage. Later live runs remain valuable for
  re-verification (proving the system still behaves correctly against
  the live provider), but they do not automatically replace the
  canonical capture; promoting a new run to canonical is a deliberate
  decision, not an automatic side effect of running the capture again.
- Q: Should partial footage from a failed run be discarded automatically,
  or retained but excluded from valid output? → A: Retained for
  diagnosis, but named/marked so it is never mistaken for valid output —
  deleting it automatically would remove the only direct evidence of
  what the interface was showing when the assertion failed.
- Q: Must every demonstration run (primary, refusal-path, and any
  re-verification run) execute against its own independent journey, so
  none can observe or be affected by another's bookings or state? → A:
  Yes — every demonstration run MUST execute against its own independent
  journey; no run may share a journey, booking, or held session with
  another. Without this, a duplicate-booking rejection or a stray spend
  from one run could be misattributed to another, corrupting the
  assertions this feature exists to make trustworthy.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Execute and Verify the Complete Journey Unattended (Priority: P1)

The operator triggers a single run that carries the journey from stating
the objective through to the disruption being resolved, the recovery
being authorised, and monitoring resuming — with no manual step in
between. At every stage, the run checks that the actual outcome matches
what the scenario expects, and stops the moment one does not, rather than
continuing on a journey that has already gone wrong.

**Why this priority**: Nothing else in this feature is trustworthy until
a run can be proven correct on its own. Footage of an unverified run is
just a video, not a demonstration.

**Independent Test**: Trigger the run twice in immediate succession with
no manual step between attempts and confirm each one either completes
with every expected outcome satisfied, or halts at the first outcome
that does not match — never silently continuing past a mismatch.

**Acceptance Scenarios**:

1. **Given** the run is triggered, **When** it executes, **Then** it
   proceeds from the stated objective to monitoring resumed without any
   operator action in between, other than triggering the disruption and
   responding to the authorisation request called for by the scenario
   itself.

2. **Given** each step of the run, **When** that step completes, **Then**
   its actual observable outcome is checked against the outcome the
   scenario expects for that step.

3. **Given** a step whose outcome does not match what was expected,
   **When** this is detected, **Then** the run stops immediately and is
   reported as failed — it does not continue to later steps on the
   strength of an already-broken journey.

4. **Given** the simulated disruption is due, **When** the run reaches
   that point, **Then** it is triggered automatically, without an
   operator initiating it by hand.

5. **Given** an authorisation request is raised during the run, **When**
   the run reaches that point, **Then** it is responded to automatically
   as the scenario calls for, without an operator approving it by hand.

---

### User Story 2 — Capture Legible Footage From a Verified Run (Priority: P1)

Once a run is underway, the operator console is recorded to video for
its entire duration, at a pace a person can actually follow rather than
the pace the system would otherwise run at, holding on each of the three
moments the demonstration is built around for long enough that a viewer
can read what happened before it moves on.

**Why this priority**: The recording is the entire deliverable — a
correct run that produces no usable footage, or footage no one can read,
has not accomplished this feature's purpose.

**Independent Test**: Produce a recording of a verified run and confirm
it covers the run's full duration, that its pacing is slow enough for
each step's outcome to be legible rather than a blur of machine-speed
updates, and that each of the three emphasised moments is held on screen
for a deliberate pause before the recording continues.

**Acceptance Scenarios**:

1. **Given** a run that is executing, **When** it is being recorded,
   **Then** the recording covers the operator console for the run's
   entire duration as a single video file.

2. **Given** the run reaches the rejection of an option that satisfies
   the numeric constraints, the statement that the objective is
   violated, or the authorisation gate, **When** each of these moments
   occurs, **Then** the recording holds on it long enough for a viewer
   to read it before continuing.

3. **Given** the interface is advancing through the run, **When** this is
   captured, **Then** it advances at a pace a viewer can follow, not at
   the system's own machine-speed pace.

4. **Given** a completed recording, **When** it is named, **Then** its
   file name identifies the specific verified run that produced it.

---

### User Story 3 — Reproduce the Run From Recorded Events, Without the Live Provider (Priority: P1)

Once a run has executed against the live provider and been verified, its
entire emitted event stream is kept in durable storage in a form the
interface can play back on its own. From that recording, an equivalent
capture can be produced again — driving the same interface through the
same sequence at a controllable pace — without making a single call to
the live provider.

**Why this priority**: A demonstration that can only ever be captured
live is fragile: it depends on network conditions, on the provider's own
data staying available, and on nothing else changing between attempts.
Recording once and reproducing footage from that recording is what makes
the capture something that can be safely repeated, reviewed, and
re-cut without repeating the live run itself.

**Independent Test**: Capture a run's event stream, then reproduce a
recording from that stored stream alone, with no network access
available, and confirm the resulting footage shows the same sequence of
steps and the same three emphasised moments as the original.

**Acceptance Scenarios**:

1. **Given** a run has executed against the live provider, **When** it
   completes, **Then** its full emitted event stream has been written to
   durable storage in a form the interface can replay.

2. **Given** a stored event stream from a previously verified run,
   **When** the capture is asked to reproduce it, **Then** it drives the
   interface through that same sequence without contacting the live
   provider at all.

3. **Given** a recording produced from a stored event stream, **When** it
   is compared to a recording of the original live run, **Then** it
   shows the same sequence of steps, the same three emphasised moments,
   and the same final position.

---

### User Story 4 — Capture the Traveller's Handheld View of the Same Journey (Priority: P2)

Alongside the operator recording, a second recording shows the identical
journey from the traveller-facing surface, sized as it would appear on a
handheld device, so the demonstration shows both surfaces the product
actually has.

**Why this priority**: The operator console is the primary evidence of
correctness; the handheld view is a secondary, confirming angle on the
same verified journey rather than a separately verified capability.

**Independent Test**: Produce a handheld-sized recording of the same
underlying journey used for the operator recording and confirm it
reflects the traveller-facing surface rather than the operator console,
at a viewport sized for a handheld device.

**Acceptance Scenarios**:

1. **Given** a verified run, **When** the handheld recording is
   produced, **Then** it shows the traveller-facing surface, not the
   operator console, for the same underlying journey.

2. **Given** the handheld recording, **When** its viewport is set,
   **Then** it is sized as a handheld device rather than the operator
   console's own viewport.

---

### User Story 5 — Verify and Record the Refusal Path (Priority: P2)

A separate run exercises what happens when the traveller does not grant
the authorisation the recovery requires. This run asserts that refusing
authorisation results in no spend at all, and that the refusal itself is
durably recorded rather than silently dropped.

**Why this priority**: The refusal path is a required, previously
identified critical journey, but it is a single additional assertion on
top of the authorisation mechanism proven by User Story 1 — it does not
block the primary capture from being useful on its own.

**Independent Test**: Trigger a run in which the authorisation request
raised during recovery is refused, and confirm no spend occurred as a
result and that the refusal was recorded durably.

**Acceptance Scenarios**:

1. **Given** a run reaches the authorisation gate for the recovery
   action, **When** authorisation is refused, **Then** no spend occurs as
   a result of that refusal.

2. **Given** authorisation has been refused, **When** this is recorded,
   **Then** the refusal itself is durably recorded, not merely absent
   from the record.

3. **Given** the refusal-path run and the primary (approval) run, **When**
   both have executed, **Then** each ran against its own independent
   journey — neither shares a booking or held session with the other,
   and neither run's spend or state is attributable to the other.

---

### Edge Cases

- An assertion fails partway through a run that is being recorded. The
  run stops and is reported as failed; the partial footage from that
  attempt is retained (for diagnosing the failure) but is named and
  marked so it is never mistaken for valid output (NFR-004 — a failed
  assertion fails the run rather than producing footage of a broken
  journey; it does not mean the partial footage is deleted).
- The live provider returns different option data on a later live run
  than it did on an earlier one (real sandbox data is not guaranteed to
  stay identical between calls). The run's assertions check the
  scenario's structural expectations (an option satisfying the numeric
  constraints is still rejected on the excluded-connection constraint;
  the objective is still found violated; recovery still restores it) —
  not fixed prices or flight numbers — so the run remains verifiable even
  when the underlying live data drifts. This later run does not replace
  the canonical capture on its own (FR-013) — it demonstrates the system
  still behaves correctly, which is a separate concern from which
  capture's footage is used for submission.
- The disruption cannot be triggered because the capability that injects
  it is disabled or misconfigured. The run fails at that step rather than
  silently skipping the disruption segment and continuing as if nothing
  were meant to happen there.
- The authorisation request receives no response within the time the
  scenario allows. This is treated as a refusal, consistent with how
  authorisation already treats silence elsewhere in the system — the run
  either exercises this deliberately (User Story 5) or fails if it was
  not the run's intent to test non-response.
- A run is triggered again immediately after a previous run against the
  live provider already created a real booking for the same journey
  parameters. The provider rejects a duplicate booking; the run accounts
  for this so that back-to-back live runs do not require an operator to
  manually clear state first.
- The recorded event stream from an earlier run is replayed after the
  interface itself has changed. The replay still reproduces the original
  sequence of steps and outcomes; how a changed interface renders that
  sequence is a presentation concern, not a correctness one.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST execute the complete journey unattended,
  from stating the objective through to recovery verified and monitoring
  resumed.

- **FR-002**: The system MUST record the operator console throughout
  that run as a video file.

- **FR-003**: The system MUST record a second run of the same journey at
  a handheld viewport, showing the traveller surface.

- **FR-004**: The system MUST assert, at each step, the expected
  observable outcome, and MUST fail the run when an expectation is not
  met.

- **FR-005**: The system MUST pause at each of the three emphasised
  moments for long enough that a viewer can read them: the rejection of
  an option satisfying the numeric constraints, the statement that the
  objective is violated, and the authorisation gate.

- **FR-006**: The system MUST drive the interface at a pace legible to a
  viewer rather than at machine speed.

- **FR-007**: The system MUST trigger the simulated disruption as part
  of the run, without manual intervention.

- **FR-008**: The system MUST respond to the authorisation request as
  part of the run.

- **FR-009**: The system MUST additionally execute a run in which
  authorisation is refused, and MUST assert that no spend occurred and
  the refusal was recorded.

- **FR-010**: The system MUST record the emitted event stream for the
  run to durable storage, in a form the interface can replay.

- **FR-011**: The system MUST be capable of executing the run against
  recorded events instead of the live provider, producing equivalent
  footage without network access.

- **FR-012**: The system MUST name each output file for the run that
  produced it, so footage can be traced to a verified execution. Partial
  footage from a failed run MUST be retained, not deleted, and MUST be
  named or marked so it is never mistaken for valid output.

- **FR-013**: The system MUST allow exactly one verified event-stream
  capture to be designated as canonical, and MUST reproduce submission
  footage from that designated capture rather than from an arbitrary
  fresh run.

- **FR-014**: The system MUST execute every demonstration run — the
  primary run, the refusal-path run, and any re-verification run —
  against its own independent journey, and MUST NOT let any run share a
  journey, booking, or held session with another.

### Non-Functional Requirements

- **NFR-001**: The capture MUST run against the live sandbox by default
  and against recorded events on request. Exactly one verified
  event-stream capture at a time MUST be designated canonical; footage
  intended for submission MUST be reproduced from the canonical capture,
  not from an arbitrary fresh live run. A live run remains useful for
  re-verifying the system without being automatically promoted to
  canonical.

- **NFR-002**: The recorded viewport MUST be sized so that trace text
  remains legible when the footage is viewed at reduced size.

- **NFR-003**: The run MUST be repeatable without manual reset between
  executions, accounting for the provider's rejection of duplicate
  bookings.

- **NFR-004**: A failed assertion MUST fail the run rather than produce
  footage of a broken journey.

### Key Entities

- **Demonstration Run**: One end-to-end execution of the journey, either
  against the live provider or against a previously recorded event
  stream, that either completes with every expected outcome satisfied or
  fails at the first one that is not (FR-001, FR-004). Always executes
  against its own independent journey, never sharing a booking or held
  session with another run (FR-014).

- **Expected Observable Outcome**: The scenario's own statement of what a
  given step should produce, checked against the step's actual result
  before the run is allowed to continue (FR-004).

- **Recording**: A video output covering a run's full duration from one
  surface — the operator console or the traveller's handheld view —
  named so it traces back to the specific run that produced it
  (FR-002, FR-003, FR-012).

- **Event Stream Capture**: The durable, replayable record of everything
  a run emitted, independent of whether that run's own footage was ever
  produced from it directly (FR-010, FR-011). At most one such capture is
  designated the **canonical capture** at any time — the source of
  submission footage (FR-013).

- **Refusal-Path Run**: A demonstration run whose recovery authorisation
  is deliberately refused, verified to produce no spend and a durable
  record of the refusal (FR-009).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of triggered runs either complete with every expected
  outcome satisfied or fail at the first one that is not — none complete
  having silently passed over a mismatched outcome.

- **SC-002**: 100% of produced recordings hold on each of the three
  emphasised moments for a deliberate pause before continuing, confirmed
  by review of the recording.

- **SC-003**: 100% of handheld recordings and their corresponding
  operator recordings trace to the same underlying verified run.

- **SC-004**: 100% of refusal-path runs result in zero spend and a
  durably recorded refusal.

- **SC-005**: A recording reproduced from a stored event stream, with no
  network access, shows the same sequence of steps and the same three
  emphasised moments as the original live run, every time it is
  regenerated.

- **SC-006**: 100% of output recording files can be traced to the
  specific run, and that run's pass/fail result, that produced them.

- **SC-007**: A run triggered immediately after a prior completed run
  succeeds without requiring any manual cleanup step in between.

- **SC-008**: Submission footage is always traceable to exactly one
  designated canonical capture; producing a new live run never silently
  changes which capture is canonical.

- **SC-009**: 100% of demonstration runs execute against an independent
  journey — zero instances of two runs observed sharing a booking or
  held session.

---

## Out of Scope

- Video editing, narration, captions, and any assembly of the final
  submission
- Detecting disruption, evaluating impact, scoring alternatives,
  obtaining authorisation, or executing recovery — this feature
  orchestrates and captures those existing capabilities; it does not
  reimplement or alter them
- Choosing or changing how the live sandbox itself behaves — the capture
  observes and asserts against whatever the live provider returns

---

## Assumptions

- The live run and the produced footage are decoupled: the run itself
  proceeds fast enough to complete before time-limited provider state
  (an offer's freshness window, a payment session) lapses, and the
  human-legible pacing and pauses required by FR-005/FR-006 are applied
  when producing the recording from the run's captured event stream, not
  by slowing the live run itself down to reading speed. This is the
  approach the project's own reference material for this feature already
  describes: capture a real run as an event stream and drive the
  recording from that stream at a controllable pace.
- "The same journey" for the handheld recording (FR-003) means a replay
  of the same recorded event stream produced by User Story 1/2's verified
  run, driving the traveller-facing surface instead of the operator
  console — not a second independent execution against the live
  provider. This is what makes NFR-003's repeatability practical: only
  the original live run touches the provider and risks a duplicate-
  booking rejection; every reproduction after that replays a recording.
- "The three emphasised moments" (FR-005) are exactly the three named in
  this specification's reference material and named explicitly in
  FR-005 itself — no additional moments are in scope for a mandated
  pause.
- The refusal-path run (FR-009, User Story 5) is a separate demonstration
  run from the primary journey, not a variant branch within the same
  recording — it exists to verify and document the refusal behaviour,
  not to appear in the primary footage.
- "Recorded events" (FR-011, NFR-001) refers to this feature's own
  Event Stream Capture (FR-010) from a prior verified live run — not a
  hand-authored or fabricated event sequence. A run "against recorded
  events" is always ultimately traceable to a live run that was itself
  verified against the live provider at least once.
