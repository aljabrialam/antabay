# Implementation Plan: Authorisation Policy Engine

**Branch**: `010-authorisation-policy` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/010-authorisation-policy/spec.md`

## Summary

Build the deterministic rule engine that Constitution Principles III and IV describe but that does not yet exist in this codebase: given a proposed action, classify it as permitted autonomously or requiring human authorisation, using a fixed, individually testable, non-LLM rule set (money spent, cancellation/void, irreversibility, hard-constraint breach). Feature 006 already built the *downstream* plumbing this engine plugs into — the `AUTHORISATION_REQUESTED`/`AUTHORISATION_OUTCOME` event types, the `POST /journeys/{id}/authorisation/{request_id}` endpoint, `EventService.record_auth_outcome()`, and the live SSE stream that renders them — but nothing in that plumbing decides anything; its own tests seed `AUTHORISATION_REQUESTED` events by hand with a hardcoded `rule_id`. This feature supplies the missing decision (the classification, the real rule identifiers, and the enforcement primitive that blocks execution absent a matching grant); it does not rebuild or replace 006's request/response/stream mechanism.

## Technical Context

**Language/Version**: Python 3.11 (backend only — no new frontend surface; 006's console already renders `authorisation_requested`/`authorisation_outcome` events)

**Primary Dependencies**: None new. Pure in-process rule evaluation — FR-007 makes a language-model call in the decision path a constitutional violation (Principle III), not merely undesirable. Reuses feature 006's existing `EventService`/`JourneyEvent` infrastructure for recording and streaming decisions; does not reimplement it.

**Storage**: Same SQLite/SQLAlchemy store, same `journey_events` table 006 already created. One narrow addition: a new `EventType.AUTHORISATION_VOIDED` (+ Pydantic payload schema) in `journey/models/events.py`, because FR-013 requires actively recording that a prior grant no longer applies — today nothing expresses that fact; a stale grant would otherwise just be silently ignored, which fails FR-011's "every decision... recorded" and Constitution Principle XIV. No new table.

**Testing**: pytest. Unit tests exercise the rule engine and the enforcement/staleness logic directly (no DB needed for pure rule evaluation; a file-backed SQLite DB for the event-stream-backed enforcement tests, matching the pattern in `tests/unit/test_verification_gate.py`). No new API endpoint or contract test is needed — FR-009's "presents an authorisation request" is satisfied by handing a correctly-shaped payload to the already-existing, already-tested `EventService.append(..., AUTHORISATION_REQUESTED, ...)` call and `POST /journeys/{id}/authorisation/{request_id}` endpoint (`tests/contract/test_auth_contract.py`, `tests/integration/test_auth_gate.py`), which this feature does not modify.

**Target Platform**: Backend service, no new deployable surface.

**Performance Goals**: FR-001's evaluation must be resolvable synchronously from fields already present on the proposed action — a handful of boolean rule checks, no external call, no LLM round-trip (FR-007, NFR-001's determinism requirement would itself be at risk from any non-deterministic dependency).

**Constraints**: MUST NOT consult a language model anywhere in the decision path (FR-007, Principle III). MUST expose no parameter, flag, or configuration capable of marking an action authorised without a real recorded grant (NFR-003) — enforcement reads only the persisted event stream, never a caller-supplied "trust me" value.

**Scale/Scope**: One `AuthorisationDecision` per proposed action evaluated; at most one live (non-voided) grant per `action_id`/cost pair at a time. This feature does not wire its enforcement primitive into any action-executing service (e.g., `BookingService`) — see Constitution Check, Principle XVI, and Out of Scope in spec.md ("Executing the action itself"). It proves FR-012 the same way feature 012 proved its own gate: against the primitive's own contract, not against a real caller it does not yet have.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| III. Separation of Reasoning and Authority | This feature *is* that separation, made concrete: a deterministic engine decides; FR-007 forbids any LLM in the decision path | PASS |
| IV. Human Authorisation for High-Impact Actions | FR-003–006 encode exactly the four categories Principle IV names (money, cancel/void, commitment/irreversibility, constraint breach); FR-010 encodes "silence MUST NOT constitute consent" directly | PASS |
| VI. State Outside the Agent | Every decision, request, grant, refusal, and void is a persisted `JourneyEvent` via the existing (006) event store — nothing lives only in a return value or agent memory | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit test in Phase 1/tasks; each of the four rules is independently testable in both directions per NFR-004 | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XII. Assertions Against Observable External State | Enforcement tests assert against the actual persisted `JourneyEvent` rows the gate reads, never against an in-memory flag the test itself set | PASS |
| XIV. Auditability | FR-011: every decision — including refusals and non-responses — lands in the audit trail via the existing event mechanism; the new `AUTHORISATION_VOIDED` event closes the one gap (FR-013) that had no recorded trace before this feature | PASS |
| XVI. Single Capability Principle | This feature delivers the decision engine and enforcement primitive only. It does not modify `BookingService` or any other action-executing code to call through it — that integration is a separate, future capability, exactly as 012 kept its gate un-wired from `BookingService` | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/010-authorisation-policy/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── authorisation_policy.md   ← Phase 1 output — the internal interface this feature exposes
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/                                     ← existing Python package
├── journey/
│   ├── models/
│   │   ├── authorisation_policy.py          ← new: ProposedAction, Rule, AuthorisationDecision,
│   │   │                                         Classification enum
│   │   └── events.py                        ← extend: add EventType.AUTHORISATION_VOIDED +
│   │                                              AuthorisationVoidedPayload
│   └── services/
│       └── authorisation_policy_engine.py   ← new: AuthorisationPolicyEngine —
│                                                  .evaluate(), .request_if_required(),
│                                                  .enforce_authorised()
└── tests/
    └── unit/
        ├── test_authorisation_policy_engine.py   ← new — the four rules, determinism,
        │                                              no-LLM guarantee, rule attribution
        └── test_authorisation_enforcement.py     ← new — request/grant/refusal/void
                                                        lifecycle against the real event store
```

**Structure Decision**: This feature extends the existing single-package `backend/journey` structure used by 000–006 and 012 — no new project or service boundary. It adds one new model module (the rule/decision vocabulary), extends the existing `events.py` with one new event type, and adds one new service module. It does not touch `journey/api/routers/events.py`, `journey/services/event_service.py`'s existing methods, or `journey/services/booking_service.py` — see Constitution Check, Principle XVI.

## Complexity Tracking

No constitution violations requiring justification.
