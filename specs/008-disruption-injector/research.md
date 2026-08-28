# Research: Disruption Injector

## R1: "The same reception path" (FR-002) means calling 007's methods directly, not a second HTTP round-trip

**Decision**: The injector delivers its constructed notification by calling
`WebhookService.receive(raw_body, received_at, simulated=True)` directly —
the identical method a real notification's arrival at
`POST /webhooks/atlas` invokes — followed by `confirm()` exactly as the
router already schedules it. It does not make an internal HTTP call back
to its own running instance's public endpoint.

**Rationale**: "The same reception path" is about not having a second,
parallel implementation of routing, association, persistence, throttling,
or confirmation logic — not literally about the transport. Every other
feature in this session that reuses another feature's mechanism (007
reusing 012's `PostActionVerifier`, 010 reusing 006's `EventService`) does
so via a direct call, not a self-directed network round-trip. An internal
HTTP call to `localhost` would add latency, a new failure mode (what if
the loopback call fails?), and no actual improvement in "sameness" — the
logic executed would be identical either way.

**Alternatives considered**: An internal HTTP POST to the running
instance's own `/webhooks/atlas` — rejected as adding transport-layer risk
and complexity with no corresponding benefit; the two approaches execute
the same code, so "sameness" is already satisfied by the direct call.

---

## R2: The `simulated` marker is a new field on 007's existing `InboundNotification`, threaded as an explicit parameter — not a field inside the notification's own JSON envelope

**Decision**: `WebhookService.receive()` gains a new parameter,
`simulated: bool = False`. The injector calls it with `simulated=True`;
007's own router (handling a real, provider-originated POST) always calls
it with the default, `False`. The flag is not embedded anywhere in the
notification's JSON body.

**Rationale**: FR-001 requires the envelope to conform to the structure
observed from the real provider, and NFR-003 requires that structure to be
derived from a real capture, never handwritten. The one real capture
(`order.ticketed`, §7c) has no `simulated` field anywhere in it — adding
one to the JSON body, even as an "extra" field alongside a
structurally-faithful envelope, would mean the injected envelope no longer
matches what was actually observed. Keeping the marker out of the body
entirely and passing it as a parameter alongside the call keeps the
envelope's structure byte-for-byte faithful to the observation, while
still letting `receive()` record the fact permanently on the resulting
`InboundNotification` row (FR-003).

**Alternatives considered**: A `simulated: true` field inside the JSON
`data` object — rejected per the reasoning above. An HTTP header
(`X-Antabay-Simulated`) — considered as a second option that would also
have kept the JSON body pure, but rejected once R1 established that
delivery is a direct method call, not an HTTP request at all; a header
only makes sense if there's a request to attach it to.

---

## R3: `WAKE_REQUESTED` events inherit `simulated` from the notification that produced them, reusing 006's existing field

**Decision**: `WebhookService.confirm()` passes
`simulated=notification.simulated` to `EventService.append(...)` when it
appends a `WAKE_REQUESTED` event. `reconcile_active_journeys()` always
passes `simulated=False` (or omits it, taking the default), since a sweep
always confirms against the real provider directly, regardless of any
notification's history — Clarifications already establish that a
simulated notification's presence has zero effect on independently
sourced confirmations.

**Rationale**: `EventType`/`JourneyEvent.simulated` and `EventService.append(...,
simulated: bool = False, ...)` already exist, built by feature 006, and
006's console already renders that field on every event's SSE envelope.
Building a second, competing simulation-marking mechanism for events
derived from this feature's notifications would violate Principle XVI and
create exactly the kind of "two ways to know if something is simulated"
confusion Principle V's honesty requirement exists to prevent.

**Alternatives considered**: A separate `simulated` flag scoped only to
webhook-derived events — rejected; 006's field is already general-purpose
and already wired into the one interface (the console) that currently
renders events at all.

---

## R4: FR-004 is currently satisfied vacuously for schedule-change specifically, and that is acceptable

**Decision**: Because 007 has no registered confirmation handler for a
`schedule.changed` type (no query interface for schedule changes is
documented anywhere in the capability map), an injected notification is
received, persisted, and marked simulated (FR-003, fully exercised and
tested), but currently never produces a `WAKE_REQUESTED` event — R3's
plumbing has nothing to carry `simulated` onto yet in real usage. This
feature does not build a schedule-change confirmation handler to manufacture
something for FR-004 to act on; that would be scope creep into 007's or a
future feature's territory (spec.md Out of Scope: "evaluating impact").

**Rationale**: This is the same posture 007 itself took toward unrecognised
event types (research.md R5, that document's own precedent) — building a
handler only when a real, documented confirmation mechanism exists to back
it. R3's plumbing is proven correct via a direct, constructed test (a stub
handler registered only for the duration of that test) rather than by
building the exact production feature that would exercise it for real.

**Alternatives considered**: Building a stub or placeholder schedule-change
confirmation handler just so FR-004 has something to demonstrate end-to-end
in production — rejected; a stub confirmation for a type with no real
query interface would either always resolve to a made-up outcome
(violating Truth Over Fluency) or always stay unresolved (providing no
real demonstration value), and either way constitutes scope this feature's
Out of Scope explicitly excludes.

---

## R5: Operator-only access control is a shared-secret token, checked against an environment variable — fail closed if unset

**Decision**: `POST /operator/disruptions` requires a header (e.g.
`X-Operator-Token`) matching a value read from an environment variable at
startup. If that environment variable is unset or empty, the endpoint
treats every request as unauthorised — the injector is inert by default,
not open by default.

**Rationale**: This codebase has no existing authentication/authorisation
system to hook into (no prior feature builds one), and building a general
one is disproportionate scope for a single, narrow, operator-only demo
tool (Principle XVI). A shared-secret token is the simplest mechanism that
satisfies NFR-002 and is fully exercisable by the automated test suite
(unlike a network-topology-based restriction, which can't meaningfully be
asserted in a unit/contract test). Failing closed when unset directly
matches this project's established "fail-safe, not fail-open" posture
(e.g., feature 010's authorisation engine, feature 007's throttle
defaults).

**Alternatives considered**: Restricting reachability by network/deployment
topology (an internal-only interface) — rejected as an infrastructure
concern outside this codebase's own test suite's ability to verify, and
not mutually exclusive with a token check in any case (both could be used
together operationally; this feature only owns the application-level
check). No token requirement, relying solely on the endpoint being
undocumented ("security by obscurity") — rejected outright as not meeting
NFR-002 at all.

---

## R6: Rejecting a nonexistent journey vs. a real journey with no order yet are two distinct, named errors

**Decision**: `DisruptionInjectorService.inject()` raises
`JourneyNotFoundError` when the target `journey_id` does not correspond to
any journey, and a new, distinct `JourneyHasNoOrderError` when the journey
exists but has no order with a real `order_no` yet. `InjectorDisabledError`
is raised separately when the injector's enabled/disabled state (FR-008)
is off.

**Rationale**: Directly implements this spec's own Clarification: an
operator triggering the tool needs to be able to tell "you gave me a
reference to nothing" from "this journey is real but not ready" from "the
tool itself is switched off" — three different corrective actions. This
mirrors the existing convention in `journey/errors.py` (e.g.,
`OrderNotFoundError`, `SessionExpiredError`) of one specific exception type
per distinct failure condition, rather than one generic error with a
message to parse.

**Alternatives considered**: A single generic `InjectionRejectedError`
carrying a reason string — rejected; this codebase's established
convention is a distinct exception type per distinct condition, which also
makes each condition independently, structurally testable (matching
NFR-004-style "every rule testable in isolation" precedent from feature
010).
