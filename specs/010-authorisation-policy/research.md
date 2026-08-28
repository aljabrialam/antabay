# Research: Authorisation Policy Engine

## Context

The `/speckit-clarify` session for this feature was started but interrupted
after its first question (compensating actions after a failure) was posed
and before it was answered. The decisions below carry forward the
*recommended* answer from that unanswered question, plus reasoned defaults
for the other ambiguities the clarify session had queued but never reached.
Each is flagged so a future `/speckit-clarify` pass can revisit it
specifically if a different answer is wanted; none of them block planning,
since each has a safety-favouring default consistent with the spec's own
Assumptions section.

---

## R1: Do compensating/cleanup actions get an authorisation exception?

**Decision**: No. A compensating action (e.g., auto-voiding a partial hold
after a technical failure) is evaluated by the same four rules as any other
proposed action. If it cancels, voids, spends money, or is irreversible, it
still requires authorisation.

**Status**: Confirmed via `/speckit-clarify` on 2026-08-28 (spec.md
Clarifications, Edge Cases) — no longer just this document's assumption.
The implementation already matched this before the answer was recorded;
this session's answer changed nothing in code, only made the decision
explicit in the spec.

**Rationale**: This was the interrupted clarify session's first question,
and its recommended option. Letting the system decide unilaterally that
"this one is just cleanup" reopens exactly the reasoning-around-the-rule
loophole Principle IV exists to close. A stray hold sitting live briefly
while authorisation is sought is a bounded, recoverable cost; quietly
voiding something without consent is not.

**Alternatives considered**: Blanket exemption for all compensating
actions (rejected — reopens the loophole entirely); a narrower exemption
for compensating actions that only reverse an action the traveller already
authorised (rejected for this feature's scope — it would require this
engine to track provenance chains between actions, which is more than a
policy engine deciding "does this proposed action, on its own terms,
trigger a rule" should need to know; revisit only if a real instance of
this need materialises in a future action-producing feature).

---

## R2: Does FR-003 ("spends money") key on gross outflow or net effect?

**Decision**: Gross outflow. Any proposed action with a nonzero outgoing
cost triggers FR-003, regardless of whether a larger, simultaneous, or
subsequent inflow (a refund, a credit) would make the traveller's net
position better off.

**Rationale**: A rebooking that nets a savings can still involve a real
outgoing charge for the new segment, processed independently of the old
segment's refund. "The system spends the traveller's money" (Business
Value) describes the charge itself, not its eventual net accounting
outcome — and net-effect framing invites exactly the kind of persuasive
reasoning ("but it saves money overall") Principle IV is designed to be
immune to.

**Alternatives considered**: Net-effect gating, i.e. exempting an action
whose refund exceeds its new charge (rejected — makes the rule's trigger
depend on a second action's outcome that may not even be confirmed yet,
undermining NFR-001's determinism if the refund's timing or amount is
itself uncertain at evaluation time).

---

## R3: Reuse feature 006's event infrastructure, or build a dedicated store?

**Decision**: Reuse. `EventType.AUTHORISATION_REQUESTED` and
`AUTHORISATION_OUTCOME`, their Pydantic payload schemas, the
`POST /journeys/{id}/authorisation/{request_id}` endpoint, and the SSE
stream that renders them already exist (`journey/models/events.py`,
`journey/services/event_service.py`, `journey/api/routers/events.py`) and
are already covered by passing tests (`test_auth_contract.py`,
`test_auth_gate.py`). This feature's engine produces the payload those
existing calls expect (`action`, `cost`, `objective_effect`, `rule_id`)
and calls them — it does not duplicate them.

**Rationale**: Constitution Principle XVI (Single Capability). Rebuilding
a second request/response/audit mechanism when a tested one already exists
for exactly this purpose would be pure duplication, and would fragment the
audit trail 006 already streams live to the console.

**One gap found and closed**: nothing in the existing event vocabulary
expresses "a previously granted authorisation no longer applies" (needed
for FR-013). `EventType.AUTHORISATION_VOIDED` is added as a narrow,
additive extension to the existing enum and payload registry in
`events.py` — not a new mechanism, just one more case in the one that
already exists.

**Alternatives considered**: A separate `authorisation_decisions` table
mirroring `verification_attempts` (feature 012's pattern) — rejected,
because unlike verification (which had no prior audit mechanism at all),
authorisation already has one, built and tested in 006. Introducing a
second, competing record of the same facts would make "which one is the
audit trail" an open question the constitution's Principle XIV explicitly
does not tolerate.

---

## R4: What identifies "the one specific action" a grant is scoped to (FR-014)?

**Decision**: The calling feature supplies a stable `action_id` for each
distinct proposed action instance. A grant is valid only for the exact
`(action_id, cost)` pair it was issued against. An identical resubmission
of the same `action_id` at the same cost (the technical-retry case in
spec.md's Edge Cases) matches the existing grant and does not trigger a
fresh request. Any other action — a different `action_id`, or the same
`action_id` at a changed cost — does not match, and is evaluated on its
own.

**Rationale**: The policy engine cannot itself know whether two calls
represent "the same action, retried" or "a genuinely new action of the
same type" — only the calling feature (which knows why it is proposing the
action) can know that. This mirrors an established pattern in this
codebase: FR-002-style "pass the identifier unmodified" contracts (004,
005) already push identity integrity onto the caller rather than having
downstream infrastructure infer it. `(action_id, cost)` as the matching
key gives FR-013 (cost change voids the grant) and FR-014 (grant scoped to
one action) a single, shared mechanism instead of two.

**Alternatives considered**: Engine-derived fingerprinting from action
content (e.g., hashing type + target + cost) — rejected, because it would
require the engine to understand the shape of every action type in
advance, which contradicts NFR-002's "readable by a non-engineer" and this
feature's Out-of-Scope boundary against knowing about the actions
themselves.

---

## R5: How is FR-012 ("prevent execution... through every path") proven, given this feature does not wire into `BookingService`?

**Decision**: FR-012 is proven as a structural property of the enforcement
primitive's own public interface, the same way feature 012 proved "never
repeat the action" by inspecting `reconcile_unresolved()`'s signature
rather than auditing every caller. `AuthorisationPolicyEngine.enforce_authorised()`
is the *only* function in this feature's public surface that can produce a
"may proceed" answer, it reads only the persisted event stream (never a
caller-supplied flag — NFR-003), and it is exercised directly by this
feature's own tests standing in for a not-yet-built caller.

**Rationale**: Constitution Principle XVI. Auditing "every path" a future
action-executing feature might take is not this feature's job to
guarantee by wiring itself into code that does not yet exist; its job is
to make the primitive itself incapable of being bypassed once a real
caller does adopt it.

---

## R6: The response-window / deadline mechanism for FR-010

**Decision**: Out of scope for this feature, as already stated in spec.md's
Assumptions. `AuthorisationPolicyEngine` does not schedule or track
deadlines; whatever future feature owns an `AUTHORISATION_REQUESTED`
request's lifecycle and timing is responsible for calling the existing
`EventService.record_auth_outcome(journey_id, request_id, "refused")` when
its own deadline logic decides silence has occurred. FR-010's contribution
is narrower and already fully satisfiable today: `enforce_authorised()`
treats *any* state other than a live, matching, approved grant — explicit
refusal, an unanswered request, or no request at all — identically, as
"not authorised." No third state exists to leak into.

**Alternatives considered**: Building deadline/timeout scheduling into
this feature — rejected as scope creep per Out of Scope ("the user
interface presenting the request") and because no concrete timing
requirement (how long is the window) was specified for this feature to
implement against.
