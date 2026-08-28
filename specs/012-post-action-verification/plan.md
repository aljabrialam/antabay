# Implementation Plan: Post-Action Verification

**Branch**: `012-post-action-verification` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/012-post-action-verification/spec.md`

## Summary

Extract the "never trust the action's own response, always confirm by independent query" discipline — already implemented ad hoc for order/payment/ticketing in feature 005 — into a reusable, general-purpose verification gate that any future state-changing action (refunds, void, rebooking, and others not yet built) can register against, rather than reimplementing the same reconciliation, discrepancy-detection, unresolved-outcome, and audit-trail logic per action type. Feature 005's ticketing confirmation becomes this gate's first registered, already-verified success condition (FR-004) — proof that the general mechanism matches the concrete instance it was generalised from — but 005's own `BookingService` is not required by this feature to be refactored to call through it (the actions themselves are Out of Scope).

## Technical Context

**Language/Version**: Python 3.11 (backend only — this feature has no frontend surface)

**Primary Dependencies**: SQLAlchemy 2.0 (storage), no new external HTTP dependency — this feature does not call Atlas directly; it wraps *whatever query call* an action type's registered `SuccessCondition` performs

**Storage**: Same SQLite/SQLAlchemy store — one new `verification_attempts` table, generalising the shape already proven by 005's `ticketing_queries` table across any action type, not just ticketing

**Testing**: pytest. No new VCR cassette is needed — this feature is provider-agnostic by design (NFR-001: expressed in terms of externally observable state, not a specific provider's response shape); its own tests exercise the gate against injected query functions, and a dedicated test proves the ticketing `SuccessCondition` reproduces 005's already-cassette-verified behaviour using 005's existing fixtures

**Target Platform**: Backend service (no new deployable surface)

**Performance Goals**: The concurrency-ordering rule (FR-011) must be resolvable without a second query — the "most recent observed timestamp wins" comparison is a pure function of two already-fetched `VerificationAttempt` records, not a re-fetch

**Constraints**: This feature MUST NOT call any Atlas endpoint directly and MUST NOT hardcode a specific action type's success condition into the gate itself — every action type's condition is supplied by its own caller (FR-003), keeping this feature genuinely action-agnostic

**Scale/Scope**: One `VerificationAttempt` per independent query performed by any action type using this gate; concurrency ordering (FR-011) is evaluated per affected-record, not globally

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | The gate calls no endpoint of its own — it wraps a caller-supplied query, so it introduces no invented endpoint or field; the ticketing `SuccessCondition` reuses 005's already-verified `paxTicketInfos[].ticketNos` field exactly | PASS |
| II. Verification After Action | This feature *is* Principle II extracted into reusable form — every other principle gate below is really asking "does the general mechanism still satisfy this the way 005's specific instance already did" | PASS |
| VI. State Outside the Agent | Every `VerificationAttempt` persists to a new table; nothing about an outcome's classification lives only in a return value or in-memory flag | PASS |
| VII. Operational Discipline | FR-003's per-action-type bound requirement means no action type can register with this gate without also declaring how it stops retrying — no unbounded reconciliation loop is possible by construction | PASS |
| VIII. End-to-End Traceability | Every FR maps to a contract or unit test in Phase 1/tasks | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XII. Assertions Against Observable External State | The gate's entire contract is built on this: it only ever classifies from a query result, never from an action's own return value (FR-002) | PASS |
| XIV. Auditability | Every `VerificationAttempt` — success, failure, unresolved, discrepant or not — is persisted (FR-009); nothing is recorded only on the interesting path | PASS |
| XVI. Single Capability Principle | This feature builds the general gate and proves it once (via the ticketing condition); it explicitly does not also refactor 005's `BookingService` to adopt it, which would be a second, separate capability | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/012-post-action-verification/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── verification_gate.md    ← Phase 1 output — the internal interface this feature exposes
└── tasks.md              ← /speckit.tasks output (not yet created)
```

### Source Code

```text
backend/                                  ← existing Python package
├── journey/
│   ├── models/
│   │   └── verification_gate.py          ← new: VerificationOutcome (SUCCESS/FAILURE/
│   │                                          UNRESOLVED), VerificationAttempt,
│   │                                          Discrepancy, SuccessCondition protocol
│   ├── services/
│   │   ├── verification_gate.py          ← new: PostActionVerifier — the reusable
│   │   │                                      gate: .verify(), .reportable_outcome(),
│   │   │                                      .reconcile_unresolved()
│   │   └── conditions/
│   │       └── ticketing_condition.py    ← new: the flagship registered SuccessCondition
│   │                                          (FR-004), reusing 005's ticket-numbers rule
│   └── storage/
│       ├── tables.py                     ← extend: add verification_attempts table
│       └── repository.py                 ← extend: save_verification_attempt(),
│                                              get_verification_attempts(),
│                                              get_reportable_outcome()
├── journey/migrations/versions/
│   └── xxxx_add_verification_attempts.py ← new migration
└── tests/
    └── unit/
        ├── test_verification_gate.py           ← new — the general mechanism
        └── test_ticketing_success_condition.py ← new — proves FR-004 against 005's
                                                      already-verified fixture data
```

**Structure Decision**: This feature extends the existing single-package `backend/journey` structure used by 000–006 — no new project or service boundary. It introduces one new model module, one new service module (plus a small `conditions/` sub-package for per-action-type registrations, since FR-003 anticipates more than one over time), one storage table, and their tests. It does not modify `backend/journey/services/booking_service.py` — see Constitution Check, Principle XVI.

## Complexity Tracking

No constitution violations requiring justification.
