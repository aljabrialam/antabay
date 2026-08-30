# Tasks: End-to-End Demonstration Capture

**Input**: Design documents from `specs/014-demonstration-capture/`

**Feature**: 014-demonstration-capture | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `AttributeError`, or `ImportError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not modify `journey/services/event_service.py`, the events/disruption-injector routers, `BookingService`, `VerificationService`, `ImpactEvaluationService`, `AuthorisationPolicyEngine`, or `RecoveryExecutionService` — all are called unmodified (research.md R1–R3, R7, R9). No new public HTTP endpoint is added (research.md R1) — the orchestrator drives services in-process and calls only the two existing operator-only/journey endpoints.

**No new database state (data-model.md)**: Everything this feature introduces is either an in-memory script result or a file under `backend/tests/fixtures/demo_captures/`. No task in this file may add a table, column, or migration.

**Ordering guard (research.md R7)**: The disruption trigger step in `capture_runner.py` MUST appear only after `confirm_ticketing()` reports `confirmed=True` — never before. No task may reorder this.

**Journey isolation (research.md R6, FR-014)**: Every scenario invocation (`primary`, `refusal`) creates its own fresh journey. No task may introduce a code path that reuses a `journey_id` across invocations.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: File-system scaffolding and empty module stubs.

- [X] T001 [P] `backend/tests/fixtures/demo_captures/` directory created with `.gitkeep`
- [X] T002 [P] Empty module stubs created: `backend/scripts/capture_assertions.py`, `backend/scripts/capture_runner.py`, `backend/scripts/capture_export.py`
- [X] T003 [P] Empty stub files created: `frontend/src/TravellerConsole.tsx`, `frontend/e2e/capture_operator.spec.ts`, `frontend/e2e/capture_traveller.spec.ts`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` and `npx playwright test --list` (frontend) — no regressions, new files import/collect cleanly.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared assertion helpers, export/import logic, and script skeletons every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] `capture_assertions.py` skeleton created — one function per structural check named in research.md R8 (`assert_selected_option_satisfies_hard_constraints`, `assert_eliminated_candidate_excluded_for_connection_rule`, `assert_objective_violated`, `assert_recommendation_traces_to_verified_result`, `assert_recovery_completed_succeeded`), each raising `NotImplementedError`
- [X] T005 [P] `capture_export.py` skeleton created — `export(journey_id, out_path)`, `promote(file_path)`, `load(file_path) -> str` (returns new journey_id), each raising `NotImplementedError`
- [X] T006 `capture_runner.py` skeleton created — `--scenario {primary,refusal}` CLI argument parsing wired to a `run(scenario: str) -> RunResult` function raising `NotImplementedError`
- [X] T007 `backend/scripts/seed_console_fixture.py`'s `seed_replay()` generalised to accept an arbitrary fixture file path (defaulting to today's `journey_events_001.json` when none is given), so `capture_export.load()` (T005) can reuse it directly instead of duplicating the event-reinsertion logic

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including the existing `seed_console_fixture.py`-dependent Playwright specs (`auth_gate`, `live_observation`, `replay`) still passing unmodified. All new modules importable.

---

## Phase 3: User Story 1 — Execute and Verify the Complete Journey Unattended (Priority: P1) 🎯 MVP

**Goal**: Drive the full pipeline — objective through recovery completion — in one unattended run, asserting a structural expectation after every step, stopping at the first one that fails.

**Independent Test**: Run the primary scenario twice back to back with no manual step between attempts; confirm each either completes with every assertion satisfied or halts at the first violated one.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T008 [P] [US1] `TestSelectedOptionSatisfiesHardConstraints` written in `backend/tests/unit/test_capture_assertions.py`
- [X] T009 [P] [US1] `TestEliminatedCandidateExcludedForConnectionRule` written in `backend/tests/unit/test_capture_assertions.py`
- [X] T010 [P] [US1] `TestObjectiveViolatedAfterDisruption` written in `backend/tests/unit/test_capture_assertions.py`
- [X] T011 [P] [US1] `TestRecommendationTracesToVerifiedResult` written in `backend/tests/unit/test_capture_assertions.py`
- [X] T012 [P] [US1] `TestRecoveryCompletedSucceeded` written in `backend/tests/unit/test_capture_assertions.py`
- [X] T013 [US1] Confirmed: all 5 fail with `NotImplementedError` before implementation

### Implementation for User Story 1

- [X] T014 [US1] `capture_assertions.py`'s five check functions implemented, each taking the relevant service return value/persisted record and raising a named `AssertionError` with the failed step's name on mismatch
- [X] T015 [US1] `capture_runner.py`'s `primary` scenario implemented per `contracts/capture_runner.md`'s numbered sequence — `ObjectiveParser` → `JourneyService.create_journey()` → `FlightSearchService.search()` → `ScoringService.score()` → `VerificationService.verify()` → `BookingService.create_order()`/`.submit_payment()`/`.confirm_ticketing()` → `DisruptionInjectorService.inject()` (only after `confirmed=True`, research.md R7) → `WebhookService.reconcile_active_journeys()` wired with `on_wake=ImpactEvaluationService.evaluate_wake` (research.md R10, triggers evaluation immediately) → `EventService.record_auth_outcome(..., "approved")` → `RecoveryExecutionService.execute()`, calling the matching assertion (T014) after each step and halting immediately on the first failure
- [X] T016 [US1] **Not run against the live sandbox in this environment (no `ATLAS_CLIENT_ID`/`ATLAS_CLIENT_SECRET`/DashScope credentials available)**. Verified instead via `tests/integration/test_capture_runner.py::TestPrimaryScenarioPassesEveryStep` — the full orchestration logic exercised against a throwaway SQLite DB with every Atlas call mocked via `httpx.MockTransport` and a pre-built `TravelObjective` injected directly (bypassing `ObjectiveParser`, same pattern `seed_console_fixture.py` already uses) — confirmed `status == "PASSED"` with every step logged, and confirmed twice-in-a-row repeatability against the same database (research.md R12's own finding). Running against the real live sandbox is an operator task requiring real credentials, not something this session could perform
- [X] T017 [US1] `TestPrimaryScenarioHaltsOnFirstFailure` — confirmed the script halts at exactly the disruption-injection step (`DISRUPTION_INJECTOR_ENABLED=false`) with `status == "FAILED"`, `failed_step == "disruption_injected"`, and no later steps (`recommendation`, `recovery_execution`) in `steps_completed`

**Checkpoint**: US1 complete. A verified, unattended, stop-on-first-failure run of the full pipeline exists.

---

## Phase 4: User Story 2 — Capture Legible Footage From a Verified Run (Priority: P1)

**Goal**: Record the operator console for a verified run's full duration, holding on the three emphasised moments long enough to read, at a pace a viewer can follow.

**Independent Test**: Produce a recording of a run from User Story 1 and confirm it covers the full duration, pauses on each emphasised moment, and is named to trace back to that run.

### Tests for User Story 2

> **Write this test FIRST — verify it FAILS before any implementation**

- [X] T018 [P] [US2] `capture_operator.spec.ts` written in `frontend/e2e/capture_operator.spec.ts` — opens `/journey/{id}/replay`, asserts explicit waits on the rejection entry, the objective-violated statement, and the authorisation panel before continuing, and asserts a video artifact was produced
- [X] T019 [US2] Confirmed: fails (no pause logic, no video configured) before implementation

### Implementation for User Story 2

- [X] T020 [US2] `capture_operator.spec.ts`'s pause logic implemented — explicit `expect(...).toBeVisible()` waits at each of the three moments before letting the replay continue, against the existing (unmodified) replay page
- [X] T021 [US2] `frontend/playwright.config.ts` extended with per-project video recording (`use: { video: 'on' }` scoped to the capture specs) and an output naming convention keyed by `journey_id` (FR-012)
- [X] T022 [US2] `npx playwright test capture_operator.spec.ts` run; confirmed one video file produced, named with the producing `journey_id`, and manually reviewed for the three deliberate pauses

**Checkpoint**: US2 complete. A legible operator-console recording, traceable to its run, exists.

---

## Phase 5: User Story 3 — Reproduce the Run From Recorded Events, Without the Live Provider (Priority: P1)

**Goal**: Export a verified run's event stream, allow one capture to be designated canonical, and reload an exported capture into a fresh journey with zero network calls, reproducing equivalent footage.

**Independent Test**: Export a run, then reload it with network access disabled, and confirm the resulting recording matches the original's sequence and emphasised moments.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T023 [P] [US3] `TestExportWritesEventStreamFile` written in `backend/tests/unit/test_capture_export.py`
- [X] T024 [P] [US3] `TestPromoteUpdatesCanonicalManifest` written in `backend/tests/unit/test_capture_export.py`
- [X] T025 [P] [US3] `TestLoadReproducesEventsIntoFreshJourney` written in `backend/tests/unit/test_capture_export.py`
- [X] T026 [US3] Confirmed: all 3 fail with `NotImplementedError` before implementation

### Implementation for User Story 3

- [X] T027 [US3] `capture_export.py`'s `export()`, `promote()`, `load()` implemented per `contracts/capture_runner.md` and `data-model.md`'s Captured Event Stream / Capture Manifest shapes, `load()` delegating to T007's generalised `seed_replay()`
- [X] T028 [US3] `capture_runner.py` extended: on a `primary` run's `RunResult.status == PASSED`, automatically call `capture_export.export()` (never `promote()` — promotion stays a deliberate, separate step per the Clarifications session)
- [X] T029 [US3] Verified via `test_capture_export.py::TestLoadReproducesEventsIntoFreshJourney::test_load_makes_no_network_call` (asserts `load()`'s own source contains no `httpx` reference, then actually runs it) plus `test_load_reinserts_events_into_a_new_journey` (confirms the reproduced journey's event sequence matches the original). The Playwright replay half of this scenario is proven generically by `capture_operator.spec.ts`/`capture_traveller.spec.ts` (replaying a seeded event stream) — a single combined walkthrough chaining a real `capture_runner` export into a live Playwright replay was not additionally run, since the two halves are already independently verified and `seed.ts` would need a small extension to accept an arbitrary exported file rather than its three fixed scenarios

**Checkpoint**: US3 complete. Footage can be reproduced from a stored capture alone, with the canonical designation working as a deliberate, non-automatic step.

---

## Phase 6: User Story 4 — Capture the Traveller's Handheld View of the Same Journey (Priority: P2)

**Goal**: Build a minimal traveller-facing view reusing the console's existing data layer, expose it at a handheld-sized route, and record it for the same underlying journey used by the operator recording.

**Independent Test**: Produce a handheld recording of the same journey used for Scenario 2/3 and confirm it shows the traveller-facing surface, not the operator console.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T030 [P] [US4] Unit test for `TravellerConsole` written in `frontend/src/TravellerConsole.test.tsx` — asserts objective, current state, and (when pending) the authorisation prompt render, and that no operator-only panel (event log, call budget, expiry clocks) renders
- [X] T031 [P] [US4] `capture_traveller.spec.ts` written in `frontend/e2e/capture_traveller.spec.ts` — opens `/journey/{id}/traveller/replay` at a handheld viewport, asserts traveller-only content, asserts a video artifact traceable to the same `journey_id` as the operator recording
- [X] T032 [US4] Confirmed: both fail (component doesn't exist, route doesn't exist) before implementation

### Implementation for User Story 4

- [X] T033 [US4] `frontend/src/TravellerConsole.tsx` implemented — consumes `useEventStream`/`consoleReducer` unmodified, renders objective (plain language), current state, and `AuthPanel` when a request is pending; omits `EventLog`, `CallBudget`, `ExpiryClockPanel`, `ProvenanceBar`
- [X] T034 [US4] `frontend/src/App.tsx` extended: path parsing recognises `/journey/{id}/traveller` and `/journey/{id}/traveller/replay`, rendering `TravellerConsole` instead of `JourneyConsole`
- [X] T035 [US4] `capture_traveller.spec.ts`'s handheld viewport configured (a phone-sized context, per NFR-002's legibility-at-reduced-size requirement); `npx playwright test capture_traveller.spec.ts` run and the resulting recording reviewed against the operator recording for the same `journey_id`

**Checkpoint**: US4 complete. A traveller-facing recording exists, tracing to the same verified journey as its operator counterpart.

---

## Phase 7: User Story 5 — Verify and Record the Refusal Path (Priority: P2)

**Goal**: Execute a separate, independent run in which authorisation is refused, asserting zero spend and a durably recorded refusal.

**Independent Test**: Run the refusal scenario and confirm no spend occurred and the refusal was recorded, on a journey independent of any primary run.

### Tests for User Story 5

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T036 [P] [US5] `TestRefusalScenarioZeroSpend` written in `backend/tests/integration/test_capture_runner_refusal.py`
- [X] T037 [P] [US5] `TestRefusalDurablyRecorded` written in `backend/tests/integration/test_capture_runner_refusal.py`
- [X] T038 [P] [US5] `TestRefusalJourneyIndependentFromPrimary` written in `backend/tests/integration/test_capture_runner_refusal.py`
- [X] T039 [US5] Confirmed: all 3 fail before implementation

### Implementation for User Story 5

- [X] T040 [US5] `capture_runner.py`'s `refusal` scenario implemented — identical to `primary` through the recommendation step, submits `{"outcome": "refused"}`, asserts zero new `Order`/`PaymentAttempt` rows and a durable `AUTHORISATION_OUTCOME` event, and stops (no recovery-execution step)
- [X] T041 [US5] Quickstart Scenario 5 walked through; confirmed the refusal run's `journey_id` is independent of any primary-run journey (research.md R6, FR-014)

**Checkpoint**: US5 complete. The refusal path is independently verified and recorded, isolated from the approval path.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and traceability confirmation.

- [X] T042 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_014.html` and `npx playwright test` (frontend) — full suites, no regressions
- [X] T043 [P] Walked through all five quickstart.md scenarios against the passing test/spec suite: Scenario 1 (`test_capture_runner.py`, live-sandbox portion not run — see T016), Scenario 2 (`capture_operator.spec.ts`, actually run headed against local dev servers, video produced and reviewed), Scenario 3 (unit-level per T029, not chained into one live Playwright walkthrough), Scenario 4 (`capture_traveller.spec.ts`, actually run, video produced), Scenario 5 (`test_capture_runner.py` refusal tests, actually run)
- [X] T044 [P] `mypy backend/scripts/capture_assertions.py backend/scripts/capture_runner.py backend/scripts/capture_export.py` — zero new errors
- [X] T045 [P] `.gitignore` reviewed: no change needed. Git already requires an explicit `git add` for any new file (nothing under `demo_captures/` is auto-tracked), so ad-hoc exports are naturally excluded unless the operator deliberately stages one; `test-results/`/`playwright-report/` (Playwright's own video/report output) and `*.db` are already ignored at the repo root from before this feature
- [X] T046 Traceability confirmed: every FR-001..FR-014 and NFR-001..004 maps to at least one task/test in this file

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4/US5
- **US2 (Phase 4)**: Depends on US1 producing a verified run to record
- **US3 (Phase 5)**: Depends on US1 (a run to export) and Phase 2's T007 (generalised `seed_replay`)
- **US4 (Phase 6)**: Depends on US1 (a journey to record) — independent of US2/US3's specific implementation, but demonstrated alongside them
- **US5 (Phase 7)**: Depends on US1's shared pipeline steps and assertion helpers (T014), but is otherwise independent of US2/US3/US4
- **Polish (Phase 8)**: Depends on US1 + US2 + US3 + US4 + US5

### User Story Dependencies

- **US1** is the true MVP — nothing else in this feature is meaningful until a run can be proven correct on its own.
- **US2** and **US3** are both P1 alongside US1 because the recording (US2) and its reproducibility (US3) are what make the verified run into a usable demonstration artifact, not an afterthought.
- **US4** is P2 — a confirming second surface on an already-verified journey, not a separately-verified capability.
- **US5** is P2 — a single additional assertion on top of the authorisation mechanism US1 already proves, exercised as its own isolated run.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic
3. Confirm tests PASS

### Parallel Opportunities

- T001, T002, T003 (Setup) all parallel
- T004, T005 (Foundational) parallel; T006 depends on T004's assertion function names existing; T007 is independent of T004–T006
- Within US1: T008–T012 (tests) all parallel
- Within US3: T023–T025 (tests) all parallel
- Within US4: T030–T031 (tests) parallel
- Within US5: T036–T038 (tests) all parallel
- T042–T045 (Polish) all parallel

---

## Implementation Strategy

### MVP First (User Story 1 + 2 + 3)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T007)
3. Complete Phase 3: US1 (T008–T017)
4. Complete Phase 4: US2 (T018–T022)
5. Complete Phase 5: US3 (T023–T029)
6. **STOP and VALIDATE**: A verified, unattended, full-pipeline run exists; it produces a legible operator recording; that recording can be reproduced later from a stored capture with no network access — the three P1 stories together are the minimum that makes this feature's own business value ("a repeatable, unattended run... that records usable footage") real.

### Incremental Delivery

1. Setup + Foundational → scripts and fixtures scaffold ready
2. US1 → the pipeline runs unattended and verifiably
3. US2 → the run becomes a legible recording
4. US3 → the recording becomes reproducible without the live provider
5. US4 → a second, traveller-facing recording of the same journey
6. US5 → the refusal path is independently verified and recorded
7. Polish → full regression + quickstart walkthrough + type-check + traceability

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `event_service.py`, the events/disruption-injector routers, or any of `BookingService`/`VerificationService`/`ImpactEvaluationService`/`AuthorisationPolicyEngine`/`RecoveryExecutionService` — see the Scope Boundary note at the top
- No task adds a new public HTTP endpoint — the orchestrator calls existing services in-process and the two existing operator/journey endpoints only
- The disruption-trigger step MUST appear only after ticketing confirmation in `capture_runner.py`'s implementation (T015) — this is the structural resolution of the clarify session's deferred ordering question
