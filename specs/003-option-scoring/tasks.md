---
description: "Task list for Option Scoring Against Objective (003-option-scoring)"
---

# Tasks: Option Scoring Against Objective

**Input**: Design documents from `specs/003-option-scoring/`

**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/scoring_service.md ✅, quickstart.md ✅

**TDD**: Test tasks are written BEFORE implementation tasks. Tests MUST be confirmed failing before the corresponding implementation task runs (Constitution Principle IX).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm test infrastructure and package layout are in place.

- [x] T001 Verify `backend/tests/unit/` directory exists; create it with an empty `__init__.py` if absent
- [x] T002 Verify `backend/tests/integration/` directory exists; confirm existing `__init__.py` is present
- [x] T003 Confirm `backend/journey/services/` directory exists; create with empty `__init__.py` if absent

---

## Phase 2: Foundational — Scoring Models (Blocking Prerequisite)

**Purpose**: Define all output dataclasses in `backend/journey/models/scoring.py`. Every user story depends on these types. No database dependency. All dataclasses are `frozen=True`.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Write failing unit test skeleton for `ScoringOutcome` enum and all dataclass types in `backend/tests/unit/test_scoring_service.py` — import only, assert type names exist (TDD gate: MUST fail before T005)
- [x] T005 Implement `ScoringOutcome` enum (`SELECTED`, `ELIMINATED`, `RANKED`) in `backend/journey/models/scoring.py`
- [x] T006 Implement `EliminationRecord` frozen dataclass (fields: `option_id`, `reason_code`, `reason_detail`, `constraint_id`) in `backend/journey/models/scoring.py`
- [x] T007 Implement `Rationale` frozen dataclass (fields: `option_id`, `objective_elements`, `summary`, `arrival_margin_minutes`, `total_cost`) in `backend/journey/models/scoring.py`
- [x] T008 Implement `RejectionReason` frozen dataclass (fields: `option_id`, `reason_code`, `reason_detail`) in `backend/journey/models/scoring.py`
- [x] T009 Implement `ConnectionEvaluation` frozen dataclass (fields: `option_id`, `connection_times`, `connection_excluded`, `exclusion_rule`, `impossible_connections`) in `backend/journey/models/scoring.py`
- [x] T010 Implement `NoSatisfyingOptionReport` frozen dataclass (fields: `unsatisfied_constraints`, `eliminated_count`, `summary`) in `backend/journey/models/scoring.py`
- [x] T011 Implement `ScoredOption` frozen dataclass (fields: `option`, `outcome`, `rank`, `rationale`, `elimination`, `rejection_reason`, `connection_eval`) in `backend/journey/models/scoring.py`
- [x] T012 Implement `ScoringRun` frozen dataclass (fields: `run_id`, `objective`, `evaluated_at`, `scored_options`, `selected_option`, `no_satisfying_option`) in `backend/journey/models/scoring.py`
- [x] T013 Confirm T004 test now passes (all types importable and constructable); update test assertions to match final field signatures

**Checkpoint**: All scoring model types defined and importable. User story phases can now begin.

---

## Phase 3: User Story 1 — Hard Constraint Elimination and Selection (Priority: P1) 🎯 MVP

**Goal**: The scoring engine eliminates every option violating a hard constraint, selects the best surviving option, produces a rationale, and reports when no option survives.

**Independent Test**:
```bash
pytest backend/tests/unit/test_scoring_service.py::TestHardConstraintElimination -v
pytest backend/tests/unit/test_scoring_service.py::TestNoSatisfyingOption -v
pytest backend/tests/unit/test_scoring_service.py::TestExpiryElimination -v
pytest backend/tests/unit/test_scoring_service.py::TestCurrencyMismatch -v
pytest backend/tests/unit/test_scoring_service.py::TestDeterminism -v
```

### TDD Tests for User Story 1 ⚠️ Write FIRST — confirm FAILING before T019

- [x] T01_DONE [US1] Write `TestHardConstraintElimination` class in `backend/tests/unit/test_scoring_service.py`: test budget_exceeded, arrival_too_late, wrong_departure_date, wrong_origin, wrong_destination elimination reasons; assert `elimination.reason_code` and `elimination.constraint_id` on each (FR-002, SC-002)
- [x] T01_DONE [US1] Write `TestNoSatisfyingOption` class in `backend/tests/unit/test_scoring_service.py`: all options violate constraints; assert `selected_option is None` and `no_satisfying_option.unsatisfied_constraints` names every failing field (FR-011, SC-006)
- [x] T01_DONE [US1] Write `TestExpiryElimination` class in `backend/tests/unit/test_scoring_service.py`: expired option eliminated with `reason_code == "offer_expired"`; `expire_at is None` eliminated with `reason_code == "expiry_unknown"` (FR-012)
- [x] T01_DONE [US1] Write `TestCurrencyMismatch` class in `backend/tests/unit/test_scoring_service.py`: option currency ≠ objective budget_currency eliminated with `reason_code == "currency_mismatch"` (FR-013)
- [x] T01_DONE [US1] Write `TestDeterminism` class in `backend/tests/unit/test_scoring_service.py`: call `score()` twice with same options in reversed order; assert `selected_option.option.option_id` and `rationale.summary` are identical both times (NFR-001, SC-004)
- [x] T01_DONE [US1] Write `TestRationaleConstruction` class in `backend/tests/unit/test_scoring_service.py`: surviving option produces `rationale.objective_elements` naming each satisfied hard-constraint field; `rationale.total_cost == adult_price + adult_tax` (FR-009, SC-005)
- [x] T020 [US1] Confirm all T014–T019 tests FAIL with `ImportError` or `AttributeError` (no `ScoringService` yet) — document the failure reason in a comment above each test class

### Implementation for User Story 1

- [x] T02_DONE [US1] Create `backend/journey/services/scoring_service.py` with `ScoringService` class and empty `score()` stub returning `ScoringRun` with empty fields
- [x] T02_DONE [US1] Implement input sorting by `option_id` inside `score()` to satisfy order-independence (NFR-001) in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Implement expiry check pipeline step (reason codes `offer_expired`, `expiry_unknown`) in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Implement currency pre-check pipeline step (reason code `currency_mismatch`) in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Implement hard constraint evaluation for all five objective fields (`budget_exceeded`, `arrival_too_late`, `wrong_departure_date`, `wrong_origin`, `wrong_destination`) in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Implement `NoSatisfyingOptionReport` construction when all options are eliminated in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Implement `Rationale` construction for the selected option (naming satisfied objective elements, computing `total_cost`) in `backend/journey/services/scoring_service.py`
- [x] T02_DONE [US1] Run `pytest backend/tests/unit/test_scoring_service.py::TestHardConstraintElimination backend/tests/unit/test_scoring_service.py::TestNoSatisfyingOption backend/tests/unit/test_scoring_service.py::TestExpiryElimination backend/tests/unit/test_scoring_service.py::TestCurrencyMismatch backend/tests/unit/test_scoring_service.py::TestDeterminism backend/tests/unit/test_scoring_service.py::TestRationaleConstruction -v` — all must pass before proceeding

**Checkpoint**: US1 complete. Hard constraint elimination, expiry, currency safety, rationale construction, and determinism all pass independently.

---

## Phase 4: User Story 2 — Preference Ranking and Rejection Explanation (Priority: P2)

**Goal**: Surviving options are ranked by the declared preference priority order. High-ranking rejected options carry a rejection reason. Arrival margin and scarcity signals are incorporated.

**Independent Test**:
```bash
pytest backend/tests/unit/test_scoring_service.py::TestPreferenceRanking -v
pytest backend/tests/unit/test_scoring_service.py::TestRejectionReason -v
pytest backend/tests/unit/test_scoring_service.py::TestArrivalMargin -v
pytest backend/tests/unit/test_scoring_service.py::TestScarcitySignal -v
pytest backend/tests/unit/test_scoring_service.py::TestTieBreaking -v
```

### TDD Tests for User Story 2 ⚠️ Write FIRST — confirm FAILING before T036

- [x] T02_DONE [US2] Write `TestPreferenceRanking` class in `backend/tests/unit/test_scoring_service.py`: three options with preferences `["cost"]`; assert cheapest is `SELECTED`; assert others are `RANKED` in cost order (FR-003)
- [x] T03_DONE [US2] Write `TestRejectionReason` class in `backend/tests/unit/test_scoring_service.py`: second-ranked option has `rejection_reason.reason_code == "outranked_cost"`; `rejection_reason.reason_detail` is non-empty string (FR-010)
- [x] T03_DONE [US2] Write `TestArrivalMargin` class in `backend/tests/unit/test_scoring_service.py`: preferences `["arrival_margin"]`; assert selected option has largest arrival margin; `rationale.arrival_margin_minutes` equals computed value (FR-004)
- [x] T03_DONE [US2] Write `TestScarcitySignal` class in `backend/tests/unit/test_scoring_service.py`: preferences `["cost", "scarcity"]`; cost-tied options differ on `seat_count` and `risk_sellout`; assert option with higher seat_count and no risk_sellout is selected (FR-008)
- [x] T03_DONE [US2] Write `TestTieBreaking` class in `backend/tests/unit/test_scoring_service.py`: two options equal on all preference dimensions and scarcity; assert tie reported in `rationale.summary`; neither option has outcome `SELECTED` (edge case from spec)
- [x] T03_DONE [US2] Write `TestNoPreferencesObjective` class in `backend/tests/unit/test_scoring_service.py`: objective with no preferences; options differ on scarcity; assert scarcity used as implicit tiebreaker (edge case from spec)
- [x] T03_DONE [US2] Confirm all T029–T034 tests FAIL (preference ranking not yet implemented) before proceeding

### Implementation for User Story 2

- [x] T03_DONE [US2] Implement preference ranking loop (iterating `preferences` list in index order, each dimension as a comparator) in `backend/journey/services/scoring_service.py`
- [x] T03_DONE [US2] Implement `"cost"` preference comparator (lower `adult_price + adult_tax` preferred) in `backend/journey/services/scoring_service.py`
- [x] T03_DONE [US2] Implement `"arrival_margin"` preference comparator (higher margin between `latest_arrival` and last-leg `arr_time` preferred); compute and store `arrival_margin_minutes` in `Rationale` in `backend/journey/services/scoring_service.py`
- [x] T03_DONE [US2] Implement `"scarcity"` preference comparator (higher `seat_count` preferred; `risk_sellout == True` penalises) in `backend/journey/services/scoring_service.py`
- [x] T04_DONE [US2] Implement implicit scarcity tiebreaker when all explicit preferences are exhausted and `"scarcity"` not in objective preferences in `backend/journey/services/scoring_service.py`
- [x] T04_DONE [US2] Implement `RejectionReason` construction for high-ranking non-selected options (reason codes: `outranked_cost`, `outranked_arrival_margin`, `outranked_scarcity`) in `backend/journey/services/scoring_service.py`
- [x] T04_DONE [US2] Run `pytest backend/tests/unit/test_scoring_service.py::TestPreferenceRanking backend/tests/unit/test_scoring_service.py::TestRejectionReason backend/tests/unit/test_scoring_service.py::TestArrivalMargin backend/tests/unit/test_scoring_service.py::TestScarcitySignal backend/tests/unit/test_scoring_service.py::TestTieBreaking backend/tests/unit/test_scoring_service.py::TestNoPreferencesObjective -v` — all must pass before proceeding

**Checkpoint**: US2 complete. Preference ranking, rejection reasons, arrival margin, scarcity, and tie-breaking all pass independently.

---

## Phase 5: User Story 3 — Connection and Multi-Leg Evaluation (Priority: P3)

**Goal**: Multi-leg options have connection times computed between consecutive legs. Excluded connection types are eliminated. Impossible connections (≤ 0 minutes) are eliminated.

**Independent Test**:
```bash
pytest backend/tests/unit/test_scoring_service.py::TestConnectionTimeCalculation -v
pytest backend/tests/unit/test_scoring_service.py::TestConnectionExclusion -v
pytest backend/tests/unit/test_scoring_service.py::TestImpossibleConnection -v
```

### TDD Tests for User Story 3 ⚠️ Write FIRST — confirm FAILING before T049

- [x] T04_DONE [US3] Write `TestConnectionTimeCalculation` class in `backend/tests/unit/test_scoring_service.py`: multi-leg option with two legs; assert `connection_eval.connection_times[0]` equals expected minutes computed from `arr_time`/`dep_time` strings (FR-006, quickstart Scenario 6)
- [x] T04_DONE [US3] Write `TestConnectionExclusion` class in `backend/tests/unit/test_scoring_service.py`: objective preferences include `"direct_only"`; multi-leg option eliminated with `reason_code == "connection_excluded"` and `exclusion_rule == "direct_only"`; direct option survives (FR-007)
- [x] T04_DONE [US3] Write `TestMinConnectionTime` class in `backend/tests/unit/test_scoring_service.py`: objective preferences include `"min_connection_60"`; multi-leg option with 45-minute connection eliminated with `reason_code == "min_connection_time"`; option with 90-minute connection survives (FR-007)
- [x] T04_DONE [US3] Write `TestImpossibleConnection` class in `backend/tests/unit/test_scoring_service.py`: multi-leg option where leg-1 departs before leg-0 arrives; eliminated with `reason_code == "impossible_connection"`; `connection_eval.impossible_connections == [0]` (edge case from spec)
- [x] T04_DONE [US3] Write `TestDirectVsConnectionRanking` class in `backend/tests/unit/test_scoring_service.py`: no connection exclusion; direct option and multi-leg option both satisfy hard constraints; with preferences not favouring connections, direct option ranks above multi-leg (US3 acceptance scenario 3)
- [x] T04_DONE [US3] Confirm all T043–T047 tests FAIL (connection evaluation not yet implemented) before proceeding

### Implementation for User Story 3

- [x] T04_DONE [US3] Implement `ConnectionEvaluation` computation for multi-leg options: parse `YYYYMMDDHHMM` strings, compute minutes between consecutive leg `arr_time`/`dep_time` pairs in `backend/journey/services/scoring_service.py`
- [x] T05_DONE [US3] Implement impossible connection detection (connection_time ≤ 0 → eliminate with `reason_code == "impossible_connection"`) in `backend/journey/services/scoring_service.py`
- [x] T05_DONE [US3] Implement `"direct_only"` exclusion check (any multi-leg option eliminated) in `backend/journey/services/scoring_service.py`
- [x] T05_DONE [US3] Implement `"min_connection_{N}"` exclusion check (parse N from string, compare against computed connection times) in `backend/journey/services/scoring_service.py`
- [x] T05_DONE [US3] Run `pytest backend/tests/unit/test_scoring_service.py::TestConnectionTimeCalculation backend/tests/unit/test_scoring_service.py::TestConnectionExclusion backend/tests/unit/test_scoring_service.py::TestMinConnectionTime backend/tests/unit/test_scoring_service.py::TestImpossibleConnection backend/tests/unit/test_scoring_service.py::TestDirectVsConnectionRanking -v` — all must pass before proceeding

**Checkpoint**: US3 complete. Connection time computation, exclusion rules, and impossible connection detection all pass independently.

---

## Phase 6: Storage and Persistence

**Purpose**: Add `scoring_runs` table and repository methods so `ScoringRun` can be persisted and reloaded from the journey database.

- [X] T054 Write failing integration tests in `backend/tests/integration/test_scoring_persistence.py`: `TestScoringRunRoundTrip` — persist a `ScoringRun` with a selected option, reload it, assert all scalar fields match; `TestScoringRunWithNoSatisfying` — persist a run where `no_satisfying_option` is set, reload and assert fields (TDD gate: MUST fail before T056)
- [X] T055 Write `TestGetScoringRunNotFound` in `backend/tests/integration/test_scoring_persistence.py`: `repo.get_scoring_run("nonexistent")` raises a named exception (TDD gate: MUST fail before T056)
- [X] T056 Add `scoring_runs` table to `backend/journey/storage/tables.py` with columns: `run_id` TEXT PK, `journey_id` TEXT, `evaluated_at` TEXT, `objective_json` TEXT, `result_json` TEXT, `selected_option_id` TEXT NULLABLE, `option_count` INT, `eliminated_count` INT, `created_at` TEXT
- [X] T057 Implement `save_scoring_run(run: ScoringRun, journey_id: str) -> None` in `backend/journey/storage/repository.py` — serialises `ScoringRun` to JSON and writes to `scoring_runs` table
- [X] T058 Implement `get_scoring_run(run_id: str) -> ScoringRun` in `backend/journey/storage/repository.py` — reads row, deserialises JSON, reconstructs `ScoringRun`; raises `ScoringRunNotFoundError` if absent
- [X] T059 Add `ScoringRunNotFoundError` to `backend/journey/errors.py`
- [X] T060 Run `pytest backend/tests/integration/test_scoring_persistence.py -v` — all tests must pass

**Checkpoint**: ScoringRun persists to and reloads from SQLite correctly.

---

## Phase 7: Polish and Cross-Cutting Concerns

**Purpose**: Full suite validation, traceability confirmation, and documentation.

- [X] T061 Run full unit suite `pytest backend/tests/unit/test_scoring_service.py -v` and confirm all tests pass (zero failures, zero errors)
- [X] T062 Run full integration suite `pytest backend/tests/integration/ -v` and confirm no regressions from feature 002 tests
- [X] T063 [P] Verify each quickstart.md scenario (Scenarios 1–10) maps to at least one passing test; document mapping in a comment block at the top of `backend/tests/unit/test_scoring_service.py`
- [X] T064 [P] Confirm `backend/journey/models/scoring.py` is importable from `backend/journey/__init__.py`; add re-exports if needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational Models)**: Depends on Phase 1
- **Phase 3 (US1)**: Depends on Phase 2 — BLOCKS nothing but is MVP
- **Phase 4 (US2)**: Depends on Phase 3 (ranking builds on constraint elimination)
- **Phase 5 (US3)**: Depends on Phase 2 (models); can start after Phase 2 if Phase 3 completes first for connection ranking test
- **Phase 6 (Storage)**: Depends on Phase 2 (needs `ScoringRun` type); can run after Phase 3 if desired
- **Phase 7 (Polish)**: Depends on Phases 3–6

### User Story Dependencies

- **US1 (P1)**: Foundation for US2; ranking requires some options to survive elimination
- **US2 (P2)**: Builds on US1 service; tests can be written in parallel with US1 implementation
- **US3 (P3)**: Connection evaluation runs as a pipeline step before preference ranking; models are shared with US1/US2

### Within Each User Story

1. TDD test tasks — write all, run and CONFIRM FAILING
2. Implementation tasks — make tests pass
3. Final `pytest` validation run before checkpoint

### Parallel Opportunities

- T001, T002, T003 can run in parallel (different directories)
- T005–T012 (model implementations in same file) must run sequentially
- T014–T020 (US1 test writing) can run in parallel [different test classes, same file — coordinate on class names]
- T029–T035 (US2 test writing) can run in parallel after T020
- T043–T048 (US3 test writing) can run in parallel after T020
- T054–T055 (integration test writing) can run in parallel with Phase 5

---

## Parallel Example: Foundational Models

```bash
# After T004 (skeleton test):
# T005–T012 must run sequentially (all in same file, each builds on previous import)
# Fastest path: implement all model types in one session
```

## Parallel Example: Test Writing (across user stories)

```bash
# After T020 confirms US1 tests fail:
# Developer A: T029–T035 (US2 tests)
# Developer B: T043–T048 (US3 tests)
# Developer C: T054–T055 (integration tests)
# All can proceed in parallel
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational Models (T004–T013)
3. Complete Phase 3: US1 — TDD tests then implementation (T014–T028)
4. **STOP and VALIDATE**: `pytest backend/tests/unit/test_scoring_service.py -v`
5. Hard constraint elimination is live and independently testable

### Incremental Delivery

1. Setup + Models → pure scoring types available
2. Add US1 → constraint elimination + selection + rationale (MVP)
3. Add US2 → preference ranking + rejection reasons
4. Add US3 → connection time + exclusion rules
5. Add Storage → ScoringRun persisted to journey database
6. Polish → full suite green, traceability confirmed

---

## Notes

- **TDD gate**: Every test phase task (T014–T020, T029–T035, T043–T048, T054–T055) MUST be confirmed failing before the corresponding implementation tasks run (Constitution Principle IX)
- **[P] tasks**: different files, no blocking dependencies
- **Determinism tests** in T018 must run `score()` with both the original and a reversed input list and compare output field-by-field
- **No mocks in unit tests**: `ScoringService.score()` is a pure function — supply real `TravelObjective` and `FlightOption` objects
- Commit after each checkpoint, not after individual tasks
