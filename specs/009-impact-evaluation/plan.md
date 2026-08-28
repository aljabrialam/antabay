# Implementation Plan: Objective Impact Evaluation and Alternative Discovery

**Branch**: `009-impact-evaluation` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-impact-evaluation/spec.md`

## Summary

Build `ImpactEvaluationService.evaluate_wake()`, the first real consumer
of feature 007's `WAKE_REQUESTED` event. On wake, it fully rehydrates the
journey (Constitution VI), checks whether the traveller's stated objective
still holds against the specific claim carried in the most recent
`schedule.changed` notification (feature 008), and — only when a hard
constraint is violated — searches for alternatives via feature 002,
scores them via feature 003 unmodified, and independently verifies the
best-ranked candidate via feature 004 before ever recommending it.
Research surfaced a real gap: 007's `confirm()` path can never fire
`WAKE_REQUESTED` for a `schedule.changed` notification today (no
registered handler), so this feature wires itself into 007's existing
periodic `reconcile_active_journeys()` sweep instead — the trigger 007
already built "independent of any notification" (FR-010) — via a new
`on_wake` callback parameter, rather than building a new confirmation
capability of its own (research.md R1).

## Technical Context

**Language/Version**: Python 3.11 (backend only — no new frontend work;
outcomes surface through feature 006's existing event-driven console)

**Primary Dependencies**: None new. Reuses `FlightSearchService` (002),
`ScoringService` (003), `VerificationService` (004), `EventService` (006),
`WebhookService` (007, extended additively), `JourneyRepository`
(existing).

**Storage**: Same SQLite/SQLAlchemy store. Two new tables,
`impact_evaluations` and `recommendations` (data-model.md), added via one
additive Alembic migration. No changes to any existing table.

**Testing**: pytest. Alternative search/scoring/verification tests use
the same recorded-response fixture pattern already established by
002/003/004's own test suites — no live sandbox call in CI, consistent
with Constitution XI (Tier 1 default).

**Target Platform**: Backend service. No new HTTP endpoint — triggered
internally via the existing reconciliation loop
(`journey/api/main.py`), consistent with this feature's spec never
describing a traveller- or operator-initiated action of its own.

**Performance Goals**: Not applicable beyond what 002/004 already
require. Evaluation adds bounded work per reconciliation sweep tick
(currently every 300s per `_RECONCILIATION_INTERVAL_SECONDS`), not a new
hot path.

**Constraints**: MUST NOT re-query flight schedule data from an
unverified or undocumented Atlas endpoint (research.md R2 — no such
endpoint exists; Constitution I). MUST NOT recommend an alternative that
has not been independently verified (NFR-001). MUST NOT introduce a
locking/mutex primitive foreign to this codebase's synchronous style for
concurrency handling — the "most recent wake wins" check (research.md R8)
is a re-read, not a lock.

**Scale/Scope**: One `ImpactEvaluation` row per wake per journey per
sweep interval; at most a handful of search/score/verify calls per
violated evaluation, bounded by `ScoringRun`'s ranked candidate list and
the journey's remaining `call_budget`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | No travel data is authored; the evaluation compares the objective against the exact claim value the notification carries (there is no verified endpoint to re-derive it independently — research.md R2), and every alternative traces to a live search/verify response | PASS |
| II. Verification After Action | Every alternative is independently verified (`VerificationService.verify`) before being recommended — never on the strength of a search or scoring result alone (NFR-001) | PASS |
| III. Separation of Reasoning and Authority | This feature only evaluates and recommends; it never books, cancels, or spends money — that remains feature 011's concern, gated by feature 010's authorisation policy | PASS |
| IV. Human Authorisation for High-Impact Actions | No high-impact action is taken here — a recommendation is a proposal, not an executed spend or booking | PASS |
| V. Honest Simulation | The schedule-change claim this feature reads may itself be simulated (feature 008's `simulated` flag on the notification); this feature does not need to re-check that flag itself since it never fabricates or labels travel data — the alternatives it presents always come from live search/verify responses (R2, R5) | PASS |
| VI. State Outside the Agent | `evaluate_wake()` loads the journey fresh from `JourneyRepository.get_journey()` on every invocation (FR-001); nothing is carried over from a prior wake in memory | PASS |
| VII. Operational Discipline | `BudgetExhaustedError` during alternative search degrades into a stated, recorded no-alternative outcome (FR-012), not a silent failure or exception propagated to the caller | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit/contract test in Phase 1/tasks | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XIV. Auditability | Every evaluation attempt — including superseded and past-departure-inert ones — is persisted (`impact_evaluations`), and every determination is also appended to the event stream | PASS |
| XVI. Single Capability Principle | This feature does not build a schedule-change confirmation handler (deliberately deferred by 007/008, and shown in research.md R1 to be unnecessary given the existing reconciliation sweep); it does not execute recovery (011) or decide authorisation (010) | PASS |

**Post-Phase 1 re-check**: All gates pass. The one notable design
decision — relying on the reconciliation sweep rather than building new
confirmation-dispatch logic for `schedule.changed` — is documented with
rationale and rejected alternatives in research.md R1, not silently
assumed.

## Project Structure

### Documentation (this feature)

```text
specs/009-impact-evaluation/
├── plan.md               ← this file
├── research.md           ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── impact_evaluation_service.md   ← Phase 1 output — internal service contract
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/                                          ← existing Python package
├── journey/
│   ├── models/
│   │   ├── impact_evaluation.py                  ← new: ImpactEvaluation,
│   │   │                                              Recommendation, EvaluationStatus
│   │   └── events.py                             ← extend: 4 new EventType members
│   │                                                  + payload models (data-model.md);
│   │                                                  OBJECTIVE_VIOLATED put into real use
│   ├── services/
│   │   ├── impact_evaluation_service.py          ← new: ImpactEvaluationService —
│   │   │                                              .evaluate_wake(journey_id, wake_event)
│   │   └── webhook_service.py                    ← extend: __init__ gains `on_wake`;
│   │                                                  confirm()/reconcile_active_journeys()
│   │                                                  invoke it after their existing
│   │                                                  WAKE_REQUESTED append (research.md R1)
│   ├── storage/
│   │   ├── tables.py                             ← extend: new impact_evaluations,
│   │   │                                              recommendations tables
│   │   └── repository.py                         ← extend: save/update/get methods
│   │                                                  for both new tables
│   ├── errors.py                                 ← extend: NoOrderReferenceForJourneyError
│   └── api/
│       └── main.py                               ← extend: construct ImpactEvaluationService
│                                                      once at startup; wire on_wake into
│                                                      both WebhookService() instantiations
├── journey/migrations/versions/
│   └── xxxx_add_impact_evaluation_tables.py      ← new migration
└── tests/
    ├── unit/
    │   └── test_impact_evaluation_service.py     ← new — objective evaluation,
    │                                                  search/score/verify sequencing,
    │                                                  no-alternative folding, supersede,
    │                                                  past-departure short-circuit
    └── contract/
        └── test_impact_evaluation_wiring.py      ← new — on_wake actually fires from
                                                        confirm() and reconcile_active_journeys()
```

**Structure Decision**: This feature extends the existing single-package
`backend/journey` structure — no new project or service boundary. It adds
one new service module and one new model module, and extends three
existing files additively (`events.py`, `webhook_service.py`,
`main.py`/`tables.py`/`repository.py`), the same "extend, don't duplicate"
pattern 007/008/010 already established. It does not modify
`journey/services/flight_search.py`, `journey/services/scoring_service.py`,
or `journey/services/verification_service.py` — all three are called, not
changed (research.md R5–R6).

## Complexity Tracking

No constitution violations requiring justification.
