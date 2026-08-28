# Implementation Plan: Recovery Execution

**Branch**: `011-recovery-execution` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-recovery-execution/spec.md`

## Summary

Build `RecoveryExecutionService.execute()`, which consumes an already-
authorised `Recommendation` (feature 009) and carries out the only
mechanism the provider supports for changing a booking: create and pay
for a replacement, independently confirm its ticketing, and only then
initiate cancellation of the superseded booking — replacement and
cancellation tracked as two separate, independently-verified outcomes.
Research surfaced two real gaps neither upstream nor downstream feature
owns: (1) no cancellation endpoint has ever been verified against the
sandbox — the capability map names `void`/`refund` as the mechanism but
never captured its shape, so this feature builds it as clearly-flagged,
provisional plumbing (research.md R1); (2) nothing bridges feature 009's
`Recommendation` output to feature 010's authorisation request path — per
both features' own stated scope, this feature does not build that bridge
either, and instead consumes an authorisation already granted, correlated
by `action_id = recommendation_id` (research.md R2). The replacement
booking itself reuses `BookingService`'s existing three-call pipeline
(005) unmodified — the same path the traveller's original booking went
through, not a parallel implementation (research.md R3).

## Technical Context

**Language/Version**: Python 3.11 (backend only)

**Primary Dependencies**: None new. Reuses `VerificationService` (004),
`BookingService` (005), `EventService` (006), `AuthorisationPolicyEngine`
(010), `Recommendation`/`ImpactEvaluationService` (009),
`JourneyRepository` (existing).

**Storage**: Same SQLite/SQLAlchemy store. Two new tables
(`recovery_executions`, `cancellation_attempts`) and one new column
(`journeys.current_order_no`), via one additive Alembic migration.

**Testing**: pytest. All Atlas-facing calls (verify, order, pay,
queryOrderDetails, the new void call) are exercised via constructed
`httpx.MockTransport` responses, matching every prior feature's test
convention — no live sandbox call in CI.

**Target Platform**: Backend service. No new HTTP endpoint — triggered
internally by whatever hosts the agent loop, the same "no endpoint of its
own" shape feature 009 already established.

**Performance Goals**: Not applicable beyond what 004/005 already
require. One execution attempt performs a bounded number of calls: one
verify, one create-order, one payment, one ticketing query, one
cancellation attempt, one cancellation-reconciliation query.

**Constraints**: MUST NOT release the superseded booking before the
replacement is independently confirmed (NFR-001) — enforced by ordering
in `execute()`, not a database constraint. MUST NOT repeat any step on an
uncertain outcome without an intervening reconciliation query (NFR-002).
MUST NOT introduce a locking primitive for duplicate-attempt protection —
a single, checked-first `RecoveryExecution` row per `recommendation_id`
is the guard (research.md R5), consistent with this codebase's existing
synchronous style.

**Scale/Scope**: One `RecoveryExecution` row and at most one
`CancellationAttempt` row per authorised recommendation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | The one unverified piece (cancellation's request/response shape) is explicitly disclosed as provisional in research.md, code comments, and the quickstart — not presented as verified; no travel data is fabricated anywhere else in the pipeline | PASS (disclosed exception, not a violation) |
| II. Verification After Action | Neither order creation, payment, nor cancellation is ever treated as confirmation on its own — each is followed by an independent query (`confirm_ticketing`, the cancellation reconciliation query) before journey state is updated | PASS |
| III. Separation of Reasoning and Authority | This feature only executes a decision already made by the deterministic `AuthorisationPolicyEngine` (010) — it never evaluates or grants authorisation itself | PASS |
| IV. Human Authorisation for High-Impact Actions | Every execution requires a pre-existing, exact-match (action_id + current cost) approved grant (FR-001); silence or a stale/mismatched grant is refused, never treated as consent | PASS |
| V. Honest Simulation | No simulation concept applies to this feature directly; it operates on whatever the journey's booking state already is, real or simulated upstream | N/A |
| VI. State Outside the Agent | Every step's outcome (`RecoveryExecution`, `CancellationAttempt`, the replacement's own `Order`/`PaymentAttempt`/`TicketingQuery` rows) is persisted durably before the next step proceeds | PASS |
| VII. Operational Discipline | A failed replacement creation/payment degrades into a stated, recorded `ABANDONED` outcome (FR-008) — the superseded booking is never touched in that path | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit test in Phase 1/tasks | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XIV. Auditability | Every step appends an event, including the specific `recommendation_id` and (transitively, via the authorisation engine's own event log) the authorisation that permitted the attempt (FR-011) | PASS |
| XVI. Single Capability Principle | This feature does not detect disruption, evaluate impact, score alternatives, or obtain authorisation — all Out of Scope per spec.md | PASS |

**Post-Phase 1 re-check**: All gates pass. The cancellation-shape gap
(R1) is the one deliberate, disclosed exception to "no unverified
endpoint" — documented with rationale and an explicit provisional flag
rather than silently assumed or hidden.

## Project Structure

### Documentation (this feature)

```text
specs/011-recovery-execution/
├── plan.md               ← this file
├── research.md           ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── recovery_execution_service.md   ← Phase 1 output
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/                                          ← existing Python package
├── journey/
│   ├── models/
│   │   ├── recovery_execution.py                 ← new: RecoveryExecution,
│   │   │                                              CancellationAttempt,
│   │   │                                              RecoveryExecutionStatus,
│   │   │                                              ReplacementOutcome,
│   │   │                                              CancellationOutcome
│   │   └── events.py                             ← extend: new EventType
│   │                                                  members + payload models
│   │                                                  for each execution step
│   ├── services/
│   │   └── recovery_execution_service.py         ← new: RecoveryExecutionService —
│   │                                                  .execute(recommendation_id, now)
│   ├── storage/
│   │   ├── tables.py                             ← extend: new
│   │   │                                              recovery_executions,
│   │   │                                              cancellation_attempts tables;
│   │   │                                              journeys gains current_order_no
│   │   └── repository.py                         ← extend: save/get/update methods
│   │                                                  for both new tables,
│   │                                                  set/get_current_order,
│   │                                                  get_recommendation
│   └── errors.py                                 ← extend:
│                                                      RecommendationNotFoundError,
│                                                      RecoveryAlreadyAttemptedError
├── journey/migrations/versions/
│   └── xxxx_add_recovery_execution_tables.py     ← new migration
└── tests/
    └── unit/
        └── test_recovery_execution_service.py    ← new — authorisation/price-change
                                                        gating, replacement-then-cancel
                                                        ordering, partial-outcome
                                                        surfacing, duplicate-attempt
                                                        refusal, final-position reporting
```

**Structure Decision**: This feature extends the existing single-package
`backend/journey` structure — no new project or service boundary. It adds
one new service module and one new model module, and extends three
existing files additively (`events.py`, `tables.py`/`repository.py`,
`errors.py`). It does not modify `journey/services/booking_service.py`,
`journey/services/verification_service.py`, or
`journey/services/authorisation_policy_engine.py` — all three are called,
not changed (research.md R2–R3).

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Cancellation built against an unverified endpoint shape (research.md R1) | FR-005–007 are core, demonstrable requirements; omitting cancellation entirely would leave the feature unable to demonstrate its own central safety property (replace-then-release) | Refusing to build it until a live Tier 2 capture is performed would block a required capability this session cannot perform a sandbox capture for; the gap is disclosed, not hidden, and isolated to one call site |
