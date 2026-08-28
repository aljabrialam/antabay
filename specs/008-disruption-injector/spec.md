# Feature Specification: Disruption Injector

**Feature Branch**: `008-disruption-injector`

**Created**: 2026-08-28

**Status**: Draft

**Input**: `.antabay/atlas-capability-map.md` section 7c — the real
`order.ticketed` webhook envelope captured live on 2026-08-15. No
schedule-change event has ever been observed from the provider (the
sandbox documents no means of triggering one), so this feature's envelope
is derived from the same observed structural convention (a dotted `type`
string, a `data` object) that capture established, not from a
schedule-change-specific capture that does not exist. This is also the
feature 007's own specification named directly: "Feature 008... is
expected to inject simulated events of the same envelope shape into this
same receiver."

---

## Business Context

**Business Goal**: Produce a schedule-change notification on demand, for
demonstration and testing, without ever misrepresenting it as
provider-originated.

**Business Value**: The sandbox provides no documented means of triggering
a schedule change. Without this, the product's central capability cannot
be demonstrated at all. Honesty about the simulation is what keeps it
legitimate.

**Business Actors**:
- Operator — the sole party who can trigger an injection; no other actor
  may reach this capability

**Business Capability**: Test Instrumentation

**Reference**: `.antabay/atlas-capability-map.md` section 7c; Constitution
Principle V (Honest Simulation — "Simulated events MUST be labelled as
simulated in the interface, the README, and the demo narration... Travel
options MUST always come from live API responses, never from fabricated
or cached simulation data"). Feature 007 (Event Reception and
Reconciliation) is the receiver this feature's output is delivered
through, per feature 007's own specification.

---

## Clarifications

### Session 2026-08-28

- Q: If a real, provider-originated notification arrives for the same order shortly after a simulated one, must the two be processed completely independently — the simulated marking as the *only* difference, zero cross-contamination — or is some interaction acceptable? → A: Fully independent. A simulated notification's presence has zero effect on how a real notification for the same order is received, confirmed, throttled, or ordered; the simulation marker is the only distinguishing fact.
- Q: Must the target journey's order be ticketed (confirmed) for a schedule-change injection to be valid, or is any real order sufficient regardless of ticketing status? → A: Any real order is sufficient. FR-005 is satisfied by the order simply existing and being real; ticketing status is not a precondition.
- Q: Should targeting a journey that does not exist at all be handled identically to targeting a real journey that has no order yet, or should the operator be able to tell which occurred? → A: Distinguish them. A nonexistent journey is rejected as an invalid reference (an input error); a real journey with no order yet is rejected as not-yet-ready (a legitimate lifecycle state) — the operator can tell which happened.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Produce a Conforming Schedule-Change Notification (Priority: P1)

The operator triggers the injector against a specific existing journey,
specifying a revised arrival time. The injector produces a notification
whose envelope structure matches the shape observed from the real
provider, referencing that journey's real order. Nothing about any travel
option, price, or availability is invented, changed, or added — only the
schedule-change claim itself.

**Why this priority**: This is the actual output the whole feature exists
to produce. Without a correctly-shaped, correctly-targeted notification,
nothing downstream can be demonstrated.

**Independent Test**: Trigger the injector for a known journey with a
specified revised arrival time, and confirm the produced envelope's
structure matches the observed convention, carries that journey's real
order reference, and carries the specified time — with no other travel
data present or altered.

**Acceptance Scenarios**:

1. **Given** an existing journey with a real order, **When** the operator
   triggers an injection with a revised arrival time, **Then** a
   notification is produced whose envelope structure conforms to the
   shape observed from the real provider.

2. **Given** a triggered injection, **When** the resulting notification is
   inspected, **Then** it references the targeted journey's real order,
   unmodified.

3. **Given** a triggered injection, **When** the resulting notification is
   inspected, **Then** the revised arrival time specified by the operator
   is exactly what it carries.

4. **Given** a triggered injection, **When** the resulting notification is
   inspected, **Then** no travel option, price, or availability value has
   been fabricated, altered, or supplemented — only the schedule-change
   claim exists.

---

### User Story 2 — Delivery Through the Real Reception Path, Marked Simulated (Priority: P1)

The produced notification is delivered through the exact same reception
path that a real, provider-originated notification would use — no
separate or shortcut mechanism. At the moment of reception, and
permanently afterward in storage, it is marked as simulated. A simulated
record is never merged with, or made indistinguishable from, a
provider-originated one.

**Why this priority**: This is where the feature's central honesty
guarantee is actually enforced. A correctly-shaped notification (User
Story 1) that entered through a different path, or that lost its
simulated marking somewhere along the way, would defeat the entire
purpose.

**Independent Test**: Deliver an injected notification and confirm it
passed through the identical reception path a real notification would.
Inspect storage and confirm the record is marked simulated at the point
of reception and remains so afterward. Confirm that a simulated and a
real record for the same journey remain individually distinguishable.

**Acceptance Scenarios**:

1. **Given** an injected notification, **When** it is delivered, **Then**
   it passes through the same reception path defined for
   provider-originated notifications, with no dedicated shortcut.

2. **Given** an injected notification is received, **When** it is
   persisted, **Then** it is marked as simulated at that exact point, not
   at some later step.

3. **Given** a notification marked simulated, **When** its stored record
   is inspected at any later time, **Then** it is still marked simulated —
   the marking does not lapse, get overwritten, or get dropped.

4. **Given** both a simulated and a provider-originated record exist for
   the same journey, **When** either is inspected, **Then** each remains
   individually identifiable as what it actually is — never merged into
   one indistinguishable record.

5. **Given** a real, provider-originated notification for the same order
   arrives shortly after a simulated one, **When** the real one is
   received, **Then** it is processed exactly as it would be had no
   simulated notification ever existed — the simulated one has no bearing
   on its reception, confirmation, throttling, or ordering.

---

### User Story 3 — Simulation Visibility Everywhere Downstream (Priority: P1)

Every event that traces back to an injected notification is presented as
simulated in every interface that shows it — without exception, and
without relying on a viewer to infer it from context.

**Why this priority**: This is the payoff of User Story 2's storage-level
marking — an honest mark that never reaches the interfaces a person
actually looks at provides no protection against the product misleading
someone. This directly instantiates Constitution Principle V.

**Independent Test**: Trigger an injection that produces a downstream
event, and confirm that event is labelled as simulated in every interface
capable of displaying it, with no interface presenting it as
indistinguishable from a real event.

**Acceptance Scenarios**:

1. **Given** an event derives from an injected notification, **When** it
   is presented in any interface, **Then** it is shown as simulated.

2. **Given** an interface presents a mix of simulated and real events,
   **When** a person views them, **Then** they can distinguish which is
   which without needing to consult anything outside that interface.

---

### User Story 4 — Operator-Only Control, Disableable (Priority: P2)

Only the operator can reach the injector; no other party can trigger it.
The injector can be disabled, and while disabled it produces no effect
whatsoever — not a queued, delayed, or partial injection.

**Why this priority**: This is the safety boundary around the capability
the first three stories deliver. It is P2 because it constrains an
already-working capability rather than delivering new demonstrable
behaviour on its own — but it is what makes leaving the capability
present in a shared or long-running environment acceptable.

**Independent Test**: Attempt to trigger the injector as a party other
than the operator and confirm it cannot be reached. Disable the injector,
attempt to trigger it, and confirm no notification is produced and no
effect occurs.

**Acceptance Scenarios**:

1. **Given** a party other than the operator attempts to reach the
   injector, **When** that attempt is made, **Then** it is not reachable
   to them.

2. **Given** the injector is disabled, **When** an injection is
   attempted, **Then** no notification is produced and nothing downstream
   is affected.

3. **Given** the injector is re-enabled after being disabled, **When** an
   injection is subsequently triggered, **Then** it behaves exactly as
   before being disabled.

---

### Edge Cases

- The operator targets a journey identifier that does not correspond to
  any existing journey at all. This is rejected as an invalid reference —
  an input error, distinct from the case below — since there is no
  journey to target in the first place.
- The operator targets a real, existing journey that has no real order yet
  (for example, one still at an earlier stage than booking). Since FR-005
  requires referencing that journey's real order, an injection cannot be
  produced for it — there is nothing real to reference. This is rejected
  as not-yet-ready, distinguishable from the nonexistent-journey case
  above, since the journey itself is genuinely real.
- The injected notification's declared type is not yet one the reception
  path (feature 007) has a confirmation mechanism for — schedule-change
  claims are not yet confirmable against the provider by any existing
  capability, since no such query interface has been documented. The
  notification is still received, persisted, and marked simulated exactly
  as this feature requires; whatever happens beyond that (confirmation, a
  resulting wake) is governed entirely by the reception path's own rules
  for an as-yet-unconfirmable claim, not by this feature.
- The targeted journey has already reached a terminal state by the time
  the injection is delivered. The reception path's own handling of a
  notification for a terminal journey applies unchanged — this feature
  does not carve out a special case for its own notifications.
- The same injection is triggered more than once for the same journey.
  The reception path's own duplicate handling applies unchanged; this
  feature does not need its own separate rule for it.
- The injector is disabled partway through — after being reachable, before
  an in-progress injection completes. The in-progress attempt still
  produces no effect, consistent with "inert when disabled" applying to
  the outcome, not only to attempts that begin after disablement.
- A real, provider-originated notification for the same order arrives
  shortly after a simulated one was injected. The two are processed
  completely independently — the simulated one's presence, timing, or
  content has no bearing on how the real one is received, confirmed,
  throttled, or ordered; only the simulation marker distinguishes them
  (NFR-001).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST produce a schedule-change notification whose
  envelope structure conforms to the structure observed from the real
  provider.

- **FR-002**: The system MUST deliver a produced notification through the
  same reception path defined for provider-originated notifications, with
  no separate or shortcut delivery mechanism.

- **FR-003**: The system MUST mark every injected notification as
  simulated at the point of reception, and that marking MUST persist
  permanently in storage.

- **FR-004**: The system MUST present every event derived from an
  injected notification as simulated, in every interface capable of
  displaying it.

- **FR-005**: The system MUST target one specific, existing journey per
  injection, and MUST reference that journey's real order, unmodified. Any
  real order satisfies this requirement, regardless of that order's
  ticketing status — ticketing confirmation is not a precondition for a
  valid injection.

- **FR-006**: The system MUST allow the operator to specify the revised
  arrival time carried by the injected notification.

- **FR-007**: The system MUST NOT fabricate, alter, or supplement any
  travel option, price, or availability value, in the injected
  notification or anywhere else, as a result of an injection.

- **FR-008**: The system MUST be capable of being disabled, and MUST
  produce no effect from any injection attempt while disabled.

### Non-Functional Requirements

- **NFR-001**: A simulated record and a provider-originated record MUST
  remain distinguishable in storage at all times, and MUST NOT be merged
  into a single, indistinguishable record. This extends to behaviour, not
  only storage: a simulated notification for a given order MUST have no
  effect on how a provider-originated notification for that same order is
  received, confirmed, throttled, or ordered — the simulation marker MUST
  be the only distinguishing fact between them.

- **NFR-002**: The injector MUST NOT be reachable by any party other than
  the operator.

- **NFR-003**: The envelope structure the injector produces MUST be
  derived from a captured real notification, and MUST NOT be handwritten.

### Key Entities

- **Injected Notification**: The envelope this feature produces —
  structurally conforming to the observed convention (FR-001, NFR-003),
  targeting one journey's real order (FR-005), carrying an
  operator-specified revised arrival time (FR-006), and marked simulated
  from the moment of reception onward (FR-003).

- **Target Reference**: The existing journey and its real order an
  injection concerns (FR-005). An injection cannot exist without one.

- **Simulation Marker**: The permanent, storage-level fact distinguishing
  a simulated record from a provider-originated one (FR-003, NFR-001) —
  and the basis for every downstream interface's simulated presentation
  (FR-004).

- **Injector Control**: The enabled/disabled state governing whether any
  injection can occur at all (FR-008), and the access boundary limiting
  who can change or use it (NFR-002).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every notification produced in the test suite has an
  envelope structure matching the observed real convention — 100%, with
  every structural element traceable to the capture it was derived from.

- **SC-002**: Every injected notification in the test suite passes through
  the identical reception path a real notification would, with zero
  special-cased handling observed in that path for injected input.

- **SC-003**: Every injected notification in the test suite is marked
  simulated at the moment of reception, and remains so in every
  subsequent read of its stored record — 100%.

- **SC-004**: Zero instances, across the test suite, of an event derived
  from an injected notification appearing in any interface without a
  simulated indicator.

- **SC-005**: Zero instances, across the test suite, of an injection
  fabricating, altering, or supplementing any travel option, price, or
  availability value.

- **SC-006**: 100% of injection attempts made while disabled produce zero
  notifications and zero downstream effect.

- **SC-007**: Zero instances, across the test suite, of the injector being
  reachable by a simulated or real attempt from any actor other than the
  operator.

- **SC-008**: Zero instances, across the test suite, of a simulated and a
  provider-originated record being merged or rendered indistinguishable.

---

## Out of Scope

- Evaluating the impact of an injected schedule change on the traveller's
  objective — this feature produces and delivers the notification; what
  anything downstream does with a confirmed claim is not this feature's
  concern
- Searching for alternatives in response to an injected disruption
- Recovery — deciding or executing what should happen as a result of an
  injected disruption
- Any simulation of travel data itself (options, prices, availability,
  itineraries) — this feature's only output is a schedule-change claim
  against a real, existing order

---

## Assumptions

- No schedule-change event has ever been captured from the real provider
  (the sandbox documents no means of triggering one). This feature's
  envelope is derived from the same structural convention the one real
  capture (`order.ticketed`, `.antabay/atlas-capability-map.md` §7c)
  established — a dotted `type` string, a `data` object — with a
  schedule-change-specific `type` and revised-time field anticipated to
  follow that same convention, consistent with feature 007's own
  Assumption that future event types will do so. NFR-003's "derived from a
  captured real notification, never handwritten" is satisfied at the
  level of structural convention, since no schedule-change-specific
  capture exists to derive from more directly.
- "The same reception path" (FR-002) means this feature submits its
  produced notification to feature 007's public receiving endpoint exactly
  as any sender would — it is not a special internal shortcut into
  feature 007's confirmation or wake logic, and feature 007's own rules
  for association, routing, duplicate handling, and terminal-journey
  handling apply to injected notifications exactly as they do to any
  other, without a carve-out.
- A schedule-change notification is not yet confirmable against the
  provider by any existing capability (feature 007 has no registered
  handler for it, since no query interface for schedule changes is
  documented). This feature does not build one — it produces and delivers
  the claim; whether or how that claim ever becomes confirmed is entirely
  a concern of whatever feature eventually defines that confirmation
  mechanism.
- "Present as simulated in every interface" (FR-004) is expected to reuse
  the simulation-marking convention already established for journey
  events (feature 006's Agent Trace Console, which already renders a
  simulated indicator) rather than this feature inventing a second,
  competing one.
- The operator-only reachability requirement (NFR-002) governs this
  feature's own triggering interface specifically — it does not change
  feature 007's reception endpoint, which remains open to any sender by
  design (feature 007's own non-functional requirement); the simulated
  marking is what keeps an injected notification honestly labelled once
  inside that otherwise-untrusted shared channel.
- The injector's enabled/disabled state (FR-008) is a single, global
  operational switch, not scoped per-journey or per-environment, unless a
  future need for finer scoping is identified.
