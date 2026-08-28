# Contract: Authorisation Policy Engine (internal, exposed)

**Feature**: 010-authorisation-policy
**Type**: Internal service interface — consumed by whatever proposes a
state-changing action (the agent loop, or a feature-specific service such
as a future `BookingService` integration)
**Consumed by**: Any code that is about to execute a proposed action and
needs to know whether it may proceed autonomously or must wait for a
grant

**Not part of this contract** (already exists, owned by feature 006, not
touched here): `POST /journeys/{id}/authorisation/{request_id}`, the
`authorisation_requested`/`authorisation_outcome` SSE stream, and
`EventService.record_auth_outcome()`. This engine calls into that existing
surface; it does not replace or extend its request/response shape.

---

## Operation: Evaluate

**Inputs**: One `ProposedAction`.

**Behaviour**: Checks all four rules (`AUTH-MONEY`, `AUTH-CANCEL`,
`AUTH-IRREVERSIBLE`, `AUTH-CONSTRAINT`) against the action, independently
of each other. No language model is consulted at any point (FR-007). The
same `ProposedAction` evaluated any number of times produces byte-identical
output (NFR-001).

**Outputs**: An `AuthorisationDecision` — `classification` is
`requires_authorisation` if one or more rules matched, `permitted_autonomously`
otherwise; `matched_rules` lists every rule ID that applied (FR-008), never
only the first.

**Error conditions**: None. `Evaluate` is a pure function over a
well-formed `ProposedAction`; malformed input (missing required field,
`cost_amount is None`) is rejected at `ProposedAction` construction, not
here.

---

## Operation: RequestIfRequired

**Inputs**: `journey_id`, one `ProposedAction`, `now`.

**Behaviour**:
1. Calls `Evaluate`.
2. If `permitted_autonomously`: returns the decision. Nothing is recorded
   — an autonomous action generates no authorisation request by
   definition, though the calling feature remains free to record the
   action itself through its own audit path.
3. If `requires_authorisation`: checks whether a live, matching grant
   already exists for this `ProposedAction`'s `(action_id, cost_amount)`
   pair (research.md R4).
   - If yes: returns the decision without issuing a new request — this is
     the technical-retry case (spec.md Edge Cases), not a fresh
     authorisation.
   - If no: calls the existing `EventService.append(journey_id,
     AUTHORISATION_REQUESTED, {request_id, action_id, action, cost,
     cost_amount, objective_effect, rule_id})` — `request_id` freshly
     generated, `action_id` and `cost_amount` echoing the `ProposedAction`
     (the two fields this feature adds to `AuthorisationRequestedPayload`,
     both additive and backward-compatible — see data-model.md), `rule_id`
     populated from `matched_rules` (joined if more than one) — then
     returns the decision.

**Outputs**: The `AuthorisationDecision`, and — as a side effect when a
new request was needed — a new `AUTHORISATION_REQUESTED` event, visible
immediately on 006's existing SSE stream and resolvable through 006's
existing `POST /journeys/{id}/authorisation/{request_id}` endpoint.

**Error conditions**: Propagates whatever the underlying
`EventService.append()` raises (e.g., an unknown `journey_id`) — this
feature adds no new error condition of its own at this layer.

---

## Operation: EnforceAuthorised

**Inputs**: `journey_id`, `action_id`, `current_cost_amount`.

**Behaviour**: The single source of truth for "may this action execute
now" (FR-012). Reads the persisted event stream for `journey_id`
(`JourneyRepository.get_events_from_sequence`) and determines, for the
most recent `AUTHORISATION_REQUESTED` matching `action_id`:

| Condition found | Result |
|---|---|
| No matching request exists at all | `False` — nothing to authorise from (also covers actions that were `permitted_autonomously` and never went through `RequestIfRequired`; those are not this operation's concern) |
| A matching `AUTHORISATION_OUTCOME` with `outcome = "approved"` exists, and its recorded cost still equals `current_cost_amount` | `True` |
| A matching `AUTHORISATION_OUTCOME` with `outcome = "approved"` exists, but its recorded cost no longer equals `current_cost_amount` | `False` — and an `AUTHORISATION_VOIDED` event is appended as a side effect (FR-013) before returning |
| A matching `AUTHORISATION_OUTCOME` with `outcome = "refused"` exists | `False` (FR-012) |
| A matching `AUTHORISATION_REQUESTED` exists with no `AUTHORISATION_OUTCOME` yet | `False` — an unanswered request is not a grant (FR-010); this is true regardless of *why* no outcome exists yet, including a deadline this feature does not itself track (research.md R6) |

**Outputs**: `bool`.

**Structural guarantee (NFR-003)**: This operation takes no parameter
through which a caller could assert "trust me, this was approved" — its
only inputs identify *which* action to check, never *what the answer
should be*. This is verified structurally (by inspecting the function's
signature), the same technique feature 012 used to prove
`reconcile_unresolved()` could not repeat an action.

---

## Relationship to feature 006

This feature reads and writes through 006's existing `EventService` and
`JourneyEvent` mechanism exclusively. It adds exactly one new case to that
mechanism's vocabulary (`AUTHORISATION_VOIDED`, research.md R3) and is the
first caller to populate `AuthorisationRequestedPayload.rule_id` with a
real, engine-derived value rather than a test fixture's placeholder
string. It does not modify `journey/api/routers/events.py`,
`EventService.record_auth_outcome()`, or any test in
`test_auth_contract.py` / `test_auth_gate.py` — those remain exactly as
006 left them, already passing.

## Relationship to feature 005 (and any future action-producing feature)

No existing feature is modified to call `RequestIfRequired`/
`EnforceAuthorised` (plan.md Constitution Check, Principle XVI; Out of
Scope: "Executing the action itself"). `BookingService` remains
unaware of this engine. Wiring a real caller through this contract is a
separate, future capability.
