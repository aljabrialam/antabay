# Implementation Plan: End-to-End Demonstration Capture

**Branch**: `014-demonstration-capture` | **Date**: 2026-08-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/014-demonstration-capture/spec.md`

## Summary

Build an orchestration script that drives the complete journey pipeline
in-process, end to end, asserting a structural expectation after every
step and stopping at the first one that fails. Once a run passes, its
event stream is exported to a file-based fixture that can be promoted to
"canonical" and later reloaded to reproduce footage without the live
provider — extending the exact fixture/replay pattern
`backend/scripts/seed_console_fixture.py` and feature 006's
`EventService.replay_events` already establish, rather than inventing new
recording infrastructure. Video capture extends the existing
`frontend/e2e/` Playwright scaffold (already a real dependency and test
suite, not new tooling). Research surfaced that no traveller-facing UI
exists at all — only the operator console — so this plan also builds a
minimal, second view reusing the console's own data layer, per the
user's explicit decision, to give FR-003 something to record.

## Technical Context

**Language/Version**: Python 3.11 (orchestration, export/import) and the
existing TypeScript/React frontend (new traveller view; new Playwright
specs)

**Primary Dependencies**: None new in the backend — reuses
`ObjectiveParser`, `JourneyService`, `FlightSearchService`,
`ScoringService`, `VerificationService`, `BookingService`,
`ImpactEvaluationService` (via its existing wake wiring),
`AuthorisationPolicyEngine`, `RecoveryExecutionService`,
`EventService.replay_events`, and the existing disruption-injector and
authorisation-outcome HTTP endpoints, called either in-process or over
HTTP exactly as they already are. None new in the frontend — `@playwright/
test` is already a devDependency; the new traveller view reuses the
existing `useEventStream` hook and `consoleReducer` unmodified.

**Storage**: No new tables or columns. New file-based artifacts only,
under `backend/tests/fixtures/demo_captures/` (research.md R4),
alongside the existing `journey_events_001.json` fixture convention.

**Testing**: pytest for the orchestration script's own assertion logic
(unit-testable independent of a live run, by constructing the expected/
actual comparison functions directly); Playwright for the video-capture
specs, extending `frontend/e2e/`. The orchestration script itself is
exercised against the live sandbox by default (NFR-001) and against a
recorded-events journey on request.

**Target Platform**: A locally-run capture (operator's machine or CI),
producing files on disk — no new deployed service, no new public HTTP
surface.

**Performance Goals**: Not applicable in the traditional sense — the
constraint is that the live-provider portion of a run completes within
the provider's own freshness windows (the shortest observed being a
~7m43s offer window), not a throughput or latency target.

**Constraints**: MUST NOT add a new public HTTP endpoint to create a
journey from a stated goal (research.md R1 — this feature calls existing
services in-process instead). MUST NOT let the disruption trigger fire
before ticketing is confirmed (research.md R7, enforced by the
orchestrator's own step ordering). MUST NOT let two demonstration runs
share a journey, booking, or held session (FR-014, research.md R6).
MUST NOT slow the underlying live provider interaction to human-legible
pace — pacing and pauses are applied only when producing the recording
from an already-completed run's replay (research.md R3).

**Scale/Scope**: A handful of script invocations and Playwright specs;
one new minimal frontend view; no scale/concurrency concerns — this is a
tooling capability run by an operator, not a production request path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | The orchestrator never fabricates travel data — every value asserted comes from a real service response already verified by that feature's own tests; the recorded-events path replays only what a prior live run actually produced | PASS |
| II. Verification After Action | Reuses every existing feature's own verification discipline unmodified (verify-before-book, confirm-ticketing-by-query, confirm-cancellation-by-query) — this feature adds no new state-changing action of its own | PASS |
| IV. Human Authorisation for High-Impact Actions | The orchestrator's automated "approve"/"refuse" response is a scripted stand-in for the human step FR-008/FR-009 describe — it submits to the same endpoint a real human would, not a bypass of the authorisation gate | PASS |
| V. Honest Simulation | The disruption remains explicitly `simulated`-labelled throughout, exactly as feature 008 already establishes; this feature does not alter that labelling | PASS |
| VI. State Outside the Agent | No new database state; the Captured Event Stream file is an export of what `journey_events` already durably holds, not a second source of truth | PASS |
| VII. Operational Discipline | A failed assertion stops the run and is reported, never silently continuing or producing invalid-looking-valid output (NFR-004) | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit/contract/Playwright test in tasks | PASS |
| IX. Test-First Development | Tasks phase requires each test written and failing before its implementation | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XIV. Auditability | Every step of a run is already recorded in the journey's own event stream by the feature that produced it; the export (R4) is a durable copy of that same audit trail, not a separate one | PASS |
| XVI. Single Capability Principle | This feature detects nothing, evaluates nothing, scores nothing, authorises nothing, and executes no recovery of its own — it orchestrates, asserts, and records | PASS |
| XVIII. Demonstrability | This feature exists entirely to serve Demonstrability — no additional check needed beyond its own spec | PASS |
| XX. Visual Discipline | The new traveller view is scoped explicitly to satisfy "operator and traveller surfaces render from the same event stream at different densities" — it does not introduce a third visual language | PASS |

**Post-Phase 1 re-check**: All gates pass. The one deliberate scope
addition — a new, minimal traveller-facing view — was surfaced to the
user as a real gap (no such view existed) and built only because the
user explicitly chose to, rather than assumed silently.

## Project Structure

### Documentation (this feature)

```text
specs/014-demonstration-capture/
├── plan.md               ← this file
├── research.md           ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── capture_runner.md ← Phase 1 output — script/endpoint contract
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/
├── scripts/
│   ├── capture_runner.py                 ← new: orchestrates the full
│   │                                          pipeline for --scenario
│   │                                          primary|refusal
│   ├── capture_assertions.py             ← new: structural expectation
│   │                                          checks per step (research.md R8)
│   ├── capture_export.py                 ← new: export/promote/load
│   │                                          (research.md R4)
│   └── seed_console_fixture.py           ← extend: generalise seed_replay()
│                                              to load an arbitrary capture
│                                              file, not only the one fixed
│                                              journey_events_001.json fixture
├── tests/fixtures/demo_captures/
│   ├── canonical.json                    ← new: capture manifest
│   └── .gitkeep
└── tests/unit/
    ├── test_capture_assertions.py        ← new
    └── test_capture_export.py            ← new

frontend/
├── src/
│   ├── TravellerConsole.tsx              ← new: minimal traveller view
│   │                                          (research.md R5), reuses
│   │                                          useEventStream/consoleReducer
│   └── App.tsx                           ← extend: route
│                                              /journey/{id}/traveller[/replay]
└── e2e/
    ├── capture_operator.spec.ts          ← new: records the operator
    │                                          console replay with pauses
    └── capture_traveller.spec.ts         ← new: records the traveller
                                                view replay, handheld viewport
```

**Structure Decision**: This feature adds new scripts and test files
alongside the existing `backend/scripts/`/`backend/tests/` and
`frontend/src/`/`frontend/e2e/` layout — no new top-level package or
service boundary. It extends `seed_console_fixture.py` and `App.tsx`
additively; it does not modify `event_service.py`, the events/disruption-
injector routers, `BookingService`, `VerificationService`,
`ImpactEvaluationService`, `AuthorisationPolicyEngine`, or
`RecoveryExecutionService` — all are called, not changed.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| A new traveller-facing UI view is built (research.md R5) | FR-003 requires recording a traveller surface that has never existed in this codebase; without it, User Story 4 has nothing to capture | Recording the operator console at phone size was considered and explicitly rejected by the user — it would satisfy FR-003's letter but not the constitution's own "different densities" requirement, and the reference narration explicitly describes a distinct, simpler traveller-facing moment ("same journey on the traveller's phone, one tap") |
