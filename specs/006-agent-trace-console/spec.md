# Feature Specification: Agent Trace and Journey Console

**Feature Branch**: `006-agent-trace-console`

**Created**: 2026-08-28

**Status**: Draft

---

## Business Context

**Business Goal**: Make the agent's behaviour observable in real time, to a
person watching a screen, without reading logs.

**Business Value**: Three purposes at once: the primary debugging surface
during development, the artifact by which the product is judged, and a
recorded output that drives demonstrations without live network access.

**Business Actors**:
- Traveller — the person whose objective and journey are being observed
- Observer — the person watching the console, including during development
  and demonstrations

**Business Capability**: Observability

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Live Journey Observation (Priority: P1)

A person watching the console during a live journey can see the agent's
objective, the current journey state, every external call made, every
decision taken, and the time remaining on every held identifier — all
updating in real time as the agent acts, without any manual refresh.

**Why this priority**: This is the primary debugging surface and the
product's most visible capability. It is the foundation on which all
other stories depend.

**Independent Test**: Open the console against a running agent session;
confirm that events appear as the agent acts, that the objective is
visible, and that expiry clocks count down.

**Acceptance Scenarios**:

1. **Given** a journey is active, **When** the agent makes an external
   call, **Then** an event appears in the console stating the endpoint,
   the outcome, and the elapsed time, without any user action.

2. **Given** a journey is active and an identifier is held, **When** the
   observer opens the console, **Then** each identifier shows a clock
   with time remaining and a proportional indicator.

3. **Given** an identifier expires, **When** the clock reaches zero,
   **Then** the clock is shown as spent and is not removed from the
   display.

4. **Given** a journey is active, **When** the agent makes a decision,
   **Then** an event appears stating what was decided and why.

5. **Given** the objective includes hard constraints and preferences,
   **When** the observer views the objective panel, **Then** hard
   constraints and preferences are visually distinct from each other.

---

### User Story 2 — Authorisation Gate (Priority: P2)

When the agent reaches a point requiring human authorisation, the console
presents the request clearly — stating the action, its cost, and its
effect on the objective — and records the outcome, including any refusal.

**Why this priority**: Human authorisation for high-impact actions is a
core safety principle. The console is the gate through which that
authorisation flows.

**Independent Test**: Trigger a journey that requires an authorisation
step; confirm the request is surfaced with the required fields; confirm
approve and refuse both record an outcome.

**Acceptance Scenarios**:

1. **Given** an authorisation is required, **When** the request is
   raised, **Then** the console displays the action, the cost, and the
   effect on the objective before any response is accepted.

2. **Given** an authorisation request is displayed, **When** the
   observer approves, **Then** the outcome is recorded and the event
   stream shows approval with the rule identifier.

3. **Given** an authorisation request is displayed, **When** the
   observer refuses, **Then** the outcome is recorded as a refusal and
   the event stream reflects the refusal with the rule identifier.

4. **Given** an authorisation request is outstanding, **When** the
   observer views the console, **Then** the request is given visual
   emphasis consistent with FR-015.

---

### User Story 3 — Simulation and Replay (Priority: P3)

An observer can replay a previously recorded event stream through the
same console at a controllable pace, with the replay clearly labelled,
and the console behaving identically to live operation in appearance.
Simulated events during live operation are visually distinguished from
real provider events.

**Why this priority**: Replay enables demonstration without live network
access and serves as the recorded output by which the product is judged.
Simulation labelling is a constitution requirement (Principle V).

**Independent Test**: Record an event stream during a live journey; load
the recording into the replay interface; confirm it plays back at
adjustable speed; confirm no external calls are made; confirm the replay
label is visible; confirm simulated events carry distinct visual marking.

**Acceptance Scenarios**:

1. **Given** a recorded event stream exists, **When** the observer
   starts replay, **Then** the console presents events in the recorded
   order and the replay label is permanently visible.

2. **Given** replay is in progress, **When** the observer adjusts the
   pace, **Then** the interval between events changes accordingly.

3. **Given** replay is in progress, **Then** no calls are made to any
   external service.

4. **Given** a live journey contains simulated events, **When** those
   events appear in the console, **Then** they are visually
   distinguishable from events originating from the real provider.

5. **Given** replay is active, **When** an observer compares the
   console to a live session visually, **Then** the layout and element
   positions are identical; only the replay label differs.

---

### Edge Cases

- What happens when the event stream is interrupted mid-journey? The
  console shows the last known state; events resume when the stream
  reconnects; no state is lost because the console holds none of its own.

- What if an identifier's expiry timestamp is missing from the event?
  The clock for that identifier is shown with no time value and marked
  as incomplete rather than hidden.

- What if an authorisation request arrives while the observer is not
  watching? The request remains outstanding and visually emphasised
  until explicitly resolved; silence does not constitute consent.

- What if replay speed is set to zero or a negative value? The replay
  pauses; it does not proceed until a valid positive pace is set.

- What if the recorded event stream is truncated or corrupt? The console
  replays up to the last valid event and indicates that the recording is
  incomplete.

- What if an event carries a provider value that is absent or null? The
  field is rendered as absent in the provider typeface; it is not
  substituted or inferred.

- What happens if more than three human interactions occur during a
  journey? The system does not enforce a hard limit at the interface
  level; the NFR is a design target. If the journey requires more, the
  additional interactions are accepted, but the design shall be reviewed.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST present the traveller's objective as
  structured elements, with hard constraints visually distinct from
  preferences.

- **FR-002**: The system MUST present the current journey state and the
  set of identifiers currently held.

- **FR-003**: The system MUST present, for each held identifier, the
  time remaining before it becomes unusable, updated continuously.

- **FR-004**: The system MUST emit an observable event for every
  external call, stating the endpoint, the outcome, and the elapsed
  time.

- **FR-005**: The system MUST emit an observable event for every
  decision, stating what was decided and the reason for the decision.

- **FR-006**: The system MUST stream events to the interface as they
  occur using Server-Sent Events (SSE); the interface MUST NOT poll
  for events.

- **FR-007**: The system MUST present the remaining call budget for the
  journey.

- **FR-008**: The system MUST present an authorisation request when one
  is outstanding, stating the action, its cost in full, and its effect
  on the objective.

- **FR-009**: The system MUST present the outcome of every authorisation
  request, including refusals, as part of the persistent event stream.

- **FR-010**: The system MUST visually distinguish events received from
  the external travel provider from events that are simulated.

- **FR-011**: The system MUST record a complete event stream for a
  journey to durable storage, such that no event is omitted.

- **FR-012**: The system MUST replay a recorded event stream through the
  same interface at a pace controllable by the observer via a speed
  multiplier (e.g. 0.5×, 1×, 2×, 4×) applied to the recorded
  inter-event intervals, without contacting any external service during
  replay.

- **FR-013**: The interface MUST hold no state of its own; it MUST
  derive all displayed state from the event stream.

- **FR-014**: The system MUST present expiry clocks persistently, each
  showing time remaining and a proportional indicator; a spent clock
  MUST be shown as spent and MUST NOT be removed.

- **FR-015**: The system MUST give visual emphasis to exactly three
  event classes: (1) rejection of an option that satisfies the
  traveller's numeric constraints, (2) determination that the objective
  is violated, (3) an outstanding authorisation request. All other
  events MUST be presented with uniform visual weight.

- **FR-016**: The system MUST present, alongside every option rejection,
  the specific constraint that was violated; and alongside every
  authorisation decision, the identifier of the rule that produced it.

- **FR-017**: The system MUST present the journey state as an ordered
  sequence of stages, showing completed, current, and pending stages.

- **FR-018**: The system MUST present provenance persistently: the
  environment in use, the reasoning model, and whether any simulated
  event is currently active.

- **FR-019**: The system MUST render values originating from the travel
  provider in a typeface visually distinct from interface text.

### Non-Functional Requirements

- **NFR-001**: The interface MUST be legible when captured as video and
  viewed at reduced size (assessed by reviewing a recording at 50% of
  native resolution).

- **NFR-002**: The interface MUST conform to the visual reference at
  `.antabay/console-mockup.html`. The palette is fixed; colour MUST
  carry meaning and MUST NOT be used decoratively.

- **NFR-003**: A complete journey MUST require no more than three human
  interactions at the console.

- **NFR-004**: Replay MUST be visually indistinguishable from live
  operation except for a persistent replay label; the label MUST be
  visible throughout the replay session.

- **NFR-005**: Recorded event streams MUST be usable as fixtures by the
  automated test suite without modification.

- **NFR-006**: The event stream MUST be delivered over Server-Sent
  Events (SSE). The SSE endpoint MUST support `Last-Event-ID` so that
  a reconnecting client can resume from the last received event without
  replaying the full stream.

### Key Entities

- **JourneyEvent**: A single observable occurrence in the agent's
  operation — an external call, a decision, an authorisation request, an
  authorisation outcome, or a state change. Carries a timestamp, a type,
  a payload of observable fields, and a provenance marker
  (live or simulated).

- **EventStream**: The ordered, append-only sequence of JourneyEvents
  for a single journey. Persisted in full to a dedicated
  `journey_events` table and replayed without modification. Each record
  carries a sequence number used as the SSE event ID.

- **ExpiryIdentifier**: An identifier held by the system that has a
  known expiry time. Presented with a continuously updated time-remaining
  value and a proportional indicator.

- **AuthorisationRequest**: An event requiring a human decision. Carries
  the proposed action, its full cost, and its effect on the objective.
  Outstanding until explicitly resolved.

- **AuthorisationOutcome**: The recorded result of an AuthorisationRequest
  — approved or refused — with the rule identifier that produced the
  decision.

- **TravellerObjective**: The structured set of constraints and
  preferences governing the journey. Hard constraints and preferences are
  typed separately.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An observer can identify the agent's current action and
  the reason for it within five seconds of opening the console during
  a live journey.

- **SC-002**: Every external call and every decision taken by the agent
  during a journey is visible in the event stream; no event is silently
  omitted.

- **SC-003**: An authorisation request is visible on screen within one
  second of the agent raising it.

- **SC-004**: A recorded event stream can be replayed end-to-end without
  error, producing a console state that matches the original live
  session.

- **SC-005**: The console renders correctly when a recording of a live
  session is viewed at 50% of native resolution; all text remains
  readable and all visual indicators remain distinguishable.

- **SC-006**: A complete demonstration journey can be driven from a
  recording in under three minutes with no more than three human
  interactions.

- **SC-007**: A recorded event stream can be loaded by the test suite as
  a fixture and used to drive assertions against displayed state without
  modification to the recording.

---

## Out of Scope

- Agent reasoning and decision logic
- External API integration
- Authentication
- Multiple concurrent journeys
- The traveller-facing mobile surface

---

## Assumptions

- The event stream is produced by the backend agent and delivered to the
  interface over a push channel; the interface does not generate events.

- The visual reference at `.antabay/console-mockup.html` is the
  authoritative design source; this specification does not restate its
  visual details.

- A "human interaction" counts any deliberate action by the observer
  that advances the journey: submitting an objective, approving or
  refusing an authorisation, and starting a replay each count as one
  interaction.

- Replay pace control is a speed multiplier (e.g. 0.5×, 1×, 2×, 4×)
  applied to the recorded inter-event intervals; frame-level scrubbing
  is out of scope.

- The console renders a single journey at a time; multiple concurrent
  journeys are explicitly out of scope.

- The event stream is persisted in a dedicated `journey_events` table
  in the same store used by the rest of the journey system. This table
  is separate from `audit_entries`; it carries typed, sequenced,
  SSE-replayable records including a `simulated` flag and structured
  payload. No separate storage service is introduced by this feature.

- The "typeface visually distinct from interface text" for provider
  values is monospace, consistent with the flight-strip design language
  established in the visual reference.

---

## Clarifications

### Session 2026-08-28

- Q: What streaming transport protocol should the backend use to push events to the interface (FR-006)? → A: Server-Sent Events (SSE), with `Last-Event-ID` support for reconnection.
- Q: Should the event stream reuse the existing `audit_entries` table or have its own dedicated storage (FR-011)? → A: Dedicated `journey_events` table — typed, sequenced, SSE-replayable, with a `simulated` flag; separate from `audit_entries`.
- Q: What is the shape of the replay pace control (FR-012)? → A: Speed multiplier (e.g. 0.5×, 1×, 2×, 4×) applied to recorded inter-event intervals.
