# Tasks: Objective Impact Evaluation and Alternative Discovery

**Input**: Design documents from `specs/009-impact-evaluation/`

**Feature**: 009-impact-evaluation | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `AttributeError`, or `ImportError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not build a `schedule.changed` confirmation handler in `journey/services/webhook_service.py`'s `_EVENT_TYPE_HANDLERS` — research.md R1 establishes that the existing `reconcile_active_journeys()` sweep already reaches every active journey independently of any notification, and is used as this feature's trigger instead. This feature does not modify `journey/services/flight_search.py`, `journey/services/scoring_service.py`, or `journey/services/verification_service.py` — all three are called unmodified (research.md R5–R6). This feature does not execute recovery (011's concern) or decide authorisation (010's concern).

**No re-derivation of the claimed value (research.md R2)**: No Atlas endpoint returns a booked order's current flight schedule. The evaluation compares the objective against the exact `data.revisedArrivalTime` value the `schedule.changed` notification carries (feature 008) — it does not attempt to independently re-query that specific value, and this limitation is disclosed, not hidden.

**"Most recent wake wins" (research.md R8, FR-002)**: Concurrency is handled by re-checking for a newer `WAKE_REQUESTED` event at each checkpoint, not by a lock. No task in this file may introduce a mutex/lock primitive.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema groundwork.

- [X] T001 [P] `impact_evaluations` and `recommendations` tables added to `backend/journey/storage/tables.py`
- [X] T002 Migration created for both new tables in `backend/journey/migrations/versions/`
- [X] T003 [P] `NoOrderReferenceForJourneyError` added to `backend/journey/errors.py`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The models, event types, storage methods, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] `EvaluationStatus` enum, `ImpactEvaluation`, `Recommendation` dataclasses created in `backend/journey/models/impact_evaluation.py`
- [X] T005 [P] `IMPACT_EVALUATION_SATISFIED`, `ALTERNATIVE_RECOMMENDED`, `NO_ALTERNATIVE_FOUND`, `IMPACT_EVALUATION_SUPERSEDED` added to `EventType` in `backend/journey/models/events.py`, with matching payload models registered in `_PAYLOAD_MODELS`
- [X] T006 [P] `save_impact_evaluation`, `update_impact_evaluation`, `get_impact_evaluation`, `get_latest_impact_evaluation`, `save_recommendation` added to `backend/journey/storage/repository.py`
- [X] T007 `WebhookService.__init__` in `backend/journey/services/webhook_service.py` gains `on_wake: Callable[[str, JourneyEvent], None] | None = None`; `confirm()` and `reconcile_active_journeys()` invoke it immediately after their existing `WAKE_REQUESTED` append — no consumer wired yet, so `on_wake` stays `None` in all existing call sites and tests
- [X] T008 `backend/journey/services/impact_evaluation_service.py` created — `ImpactEvaluationService.evaluate_wake(journey_id, wake_event)` raises `NotImplementedError`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including 007's own test suites (`test_webhook_service.py`, `test_webhook_reconciliation.py`, `test_webhook_contract.py`) passing exactly as before. `from journey.services.impact_evaluation_service import ImpactEvaluationService` succeeds.

---

## Phase 3: User Story 1 — Evaluate the Confirmed Change Against the Objective (Priority: P1) 🎯 MVP

**Goal**: On wake, reconstruct the journey and objective from durable storage, evaluate the claimed change against every objective element, and — when a hard constraint is violated — state the result in objective terms with a quantified extent.

**Independent Test**: Wake a journey with a `HARD` `latest_arrival` objective and a `schedule.changed` notification claiming a later time; confirm the evaluation reads state fresh from storage, names `latest_arrival` (not the raw flight fact), and quantifies the overage.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T009 [P] [US1] `TestRehydratesFromDurableStorage` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T010 [P] [US1] `TestViolationStatedInObjectiveTerms` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T011 [P] [US1] `TestViolationExtentQuantified` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T012 [P] [US1] `TestSoftLatestArrivalNotAViolation` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T013 [US1] Confirmed: all 4 fail with `NotImplementedError` before implementation

### Implementation for User Story 1

- [X] T014 [US1] `ImpactEvaluationService.evaluate_wake()` implemented through the violation-determination step: insert `IN_PROGRESS` row, load journey via `JourneyRepository.get_journey()`, extract the claim via `get_notifications_for_order()` + parse `data.revisedArrivalTime` (research.md R3), evaluate `latest_arrival` per research.md R4, append `OBJECTIVE_VIOLATED` with quantified extent when violated, mark `COMPLETED` — no search/score/verify yet (US3 adds it), no past-departure or supersede check yet (also US3)
- [X] T015 [US1] `python -m pytest backend/tests/unit/test_impact_evaluation_service.py -v -k "RehydratesFromDurableStorage or ViolationStatedInObjectiveTerms or ViolationExtentQuantified or SoftLatestArrivalNotAViolation"` — 4 passed

**Checkpoint**: US1 complete. Evaluation correctly determines and states a violation from durable state alone.

---

## Phase 4: User Story 2 — No Action, Recorded, When the Objective Still Holds (Priority: P1)

**Goal**: When the claimed change does not violate the objective — including when it improves the traveller's position — no search/score/verify activity occurs, and the satisfied determination is itself recorded.

**Independent Test**: Wake a journey with a claimed change that does not breach any hard constraint (including one that is strictly favourable) and confirm no `SearchRecord`/`ScoringRun`/`VerificationResult` is created, while an `IMPACT_EVALUATION_SATISFIED` event and a `COMPLETED`/`objective_satisfied=True` row are still produced.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T016 [P] [US2] `TestNoSearchActivityWhenSatisfied` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T017 [P] [US2] `TestSatisfiedDeterminationRecorded` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T018 [P] [US2] `TestFavourableChangeTreatedAsSatisfied` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T019 [US2] Confirmed: pass/fail status checked against US1's implementation before any US2-specific code is written

### Implementation for User Story 2

- [X] T020 [US2] `evaluate_wake()` extended to append `IMPACT_EVALUATION_SATISFIED` (not just skip silently) on the satisfied path, if not already covered by T014
- [X] T021 [US2] `python -m pytest backend/tests/unit/test_impact_evaluation_service.py -v -k "NoSearchActivityWhenSatisfied or SatisfiedDeterminationRecorded or FavourableChangeTreatedAsSatisfied"` — 3 passed

**Checkpoint**: US2 complete. A satisfied objective produces no wasted search activity, and the determination is auditable exactly like a violation is.

---

## Phase 5: User Story 3 — Search, Score, Verify, and Recommend Alternatives When the Objective Is Violated (Priority: P2)

**Goal**: On a violation, search for alternatives (feature 002), score them with the original objective's existing rules (feature 003), verify the best-ranked candidate independently before recommending it (feature 004), state cost relative to the current position with a one-sentence rationale, flag a constraint-breach-only alternative explicitly, report plainly when nothing restores the objective (folding budget exhaustion and freshness lapse into the same report), and count every search against the call budget. Also covers the past-departure short-circuit and concurrent-second-wake supersede behaviour, since both only matter once real evaluation work is underway.

**Independent Test**: Trigger a violated-objective wake with a seeded search response containing a satisfying option; confirm search → score → verify → recommend runs in order, the recommendation traces to a `VERIFIED` result, cost is relative, and a one-sentence rationale is present. Separately, confirm a no-satisfying-option, a budget-exhausted, and a freshness-lapsed scenario all produce the identical no-alternative report. Separately, confirm a past-departure journey short-circuits before any of this runs, and a second, newer wake for the same journey supersedes an in-progress evaluation.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T022 [P] [US3] `TestSearchTriggeredOnViolation` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T023 [P] [US3] `TestSameScoringRulesAsOriginalSelection` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T024 [P] [US3] `TestRecommendationTracesToVerifiedResult` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T025 [P] [US3] `TestCostRelativeAndOneSentenceRationale` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T026 [P] [US3] `TestConstraintBreachCaveatStatedExplicitly` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T027 [P] [US3] `TestNoAlternativeReportedPlainly` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T028 [P] [US3] `TestBudgetExhaustionFoldedIntoNoAlternative` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T029 [P] [US3] `TestFreshnessLapseFoldedIntoNoAlternative` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T030 [P] [US3] `TestNextRankedTriedWhenTopVerificationFails` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T031 [P] [US3] `TestEverySearchCountsAgainstCallBudget` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T032 [P] [US3] `TestPastDepartureJourneyInert` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T033 [P] [US3] `TestSupersededByNewerWake` written in `backend/tests/unit/test_impact_evaluation_service.py`
- [X] T034 [P] [US3] `TestOnWakeFiresFromConfirmAndReconcile` written in `backend/tests/contract/test_impact_evaluation_wiring.py`
- [X] T035 [US3] Confirmed: all 13 fail (`NotImplementedError`/`AttributeError`) before implementation

### Implementation for User Story 3

- [X] T036 [US3] Past-departure short-circuit added at the start of `evaluate_wake()` (research.md R9) — marks `INERT_PAST_DEPARTURE`, returns before the claim-extraction step
- [X] T037 [US3] Supersede check helper added (research.md R8) — re-reads `get_events_from_sequence(journey_id, since=triggering_sequence + 1)` for a newer `WAKE_REQUESTED`; called after the violation determination and between each verification attempt
- [X] T038 [US3] Alternative search added: `FlightSearchService.search(journey_id, now)` called on violation, `BudgetExhaustedError` caught and folded into `no_alternative_reason = "budget_exhausted"`
- [X] T039 [US3] Scoring + rank-order verification loop added: `ScoringService.score()` then `VerificationService.verify()` per ranked survivor until one returns `VERIFIED`, re-running the supersede check between attempts; freshness-lapsed/`PRICE_CHANGED`/`UNAVAILABLE` candidates are skipped, not retried
- [X] T040 [US3] `Recommendation` construction added: relative cost description, one-sentence rationale, constraint-breach check against the objective's `HARD` fields (FR-011), persisted and appended as `ALTERNATIVE_RECOMMENDED`
- [X] T041 [US3] No-alternative folding added: exhausted ranked list, full tie (`ScoringRun.selected_option is None`), `no_satisfying_option`, and budget exhaustion all converge on the same `NO_ALTERNATIVE_FOUND` event and report text
- [X] T042 [US3] `ImpactEvaluationService` wired into `backend/journey/api/main.py` (`_reconciliation_loop`'s `WebhookService()`) and `backend/journey/api/routers/webhooks.py` (`get_webhook_service()`'s `WebhookService()`) via `on_wake=impact_evaluation_service.evaluate_wake`
- [X] T043 [US3] `python -m pytest backend/tests/unit/test_impact_evaluation_service.py backend/tests/contract/test_impact_evaluation_wiring.py -v` — 17 passed

**Checkpoint**: US3 complete. A violated objective drives a full, independently-verified alternative-discovery cycle end-to-end, demonstrable via the disruption injector (008) → reconciliation sweep (007) → evaluation (009) chain.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [X] T044 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_009.html` — full suite, no new regressions
- [X] T045 [P] Walked through all five quickstart.md scenarios against the passing test suite; re-confirmed 002/003/004/006/007/008's own test suites still pass unmodified
- [X] T046 [P] NFR-001 confirmed: grep for every `Recommendation` construction path, verify each traces to a `VerificationResult.outcome == VERIFIED`
- [X] T047 [P] NFR-002 confirmed: every `Recommendation.rationale` is a single sentence (no internal period beyond the terminal one) in the test fixtures exercised
- [X] T048 `backend/journey/__init__.py` updated to export `ImpactEvaluationService` — checked for naming collisions against existing exports
- [X] T049 `mypy journey` run before and after (via `git stash -u` baseline) — no new errors introduced by this feature's new or extended modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3
- **US2 (Phase 4)**: Depends on US1's `evaluate_wake()` (T014) existing
- **US3 (Phase 5)**: Depends on US1's `evaluate_wake()` (T014) and US2's satisfied-path handling (T020) — extends the same method with the violated branch
- **Polish (Phase 6)**: Depends on US1 + US2 + US3

### User Story Dependencies

- **US1** is the true MVP — a correct violation determination from durable state alone is independently demonstrable (paired with the existing operator/traveller console rendering `OBJECTIVE_VIOLATED` events, feature 006).
- **US2** is the necessary complement to US1 within the same method — both are P1 because a violation-only implementation with no satisfied-path handling is not trustworthy (an unrecorded "everything's fine" is indistinguishable from "nobody checked").
- **US3** is P2 and depends on US1/US2's determination being correct first — nothing about search/score/verify/recommend is meaningful until the violation it responds to has been correctly identified.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003 (Setup) — T002 depends on T001
- T004, T005, T006 (Foundational) can run in parallel; T007 and T008 have no cross-dependency on each other
- Within US1: T009–T012 (tests) all parallel
- Within US2: T016–T018 (tests) all parallel
- Within US3: T022–T034 (tests) all parallel
- T044–T047 (Polish) all parallel

---

## Parallel Example: User Story 3 Tests

```bash
# T022-T034 all write to the same two new test files but assert independent
# scenarios with no shared mutable state (each seeds its own journey/order
# in its own tmp_path DB) — safe to parallelize:
T022: TestSearchTriggeredOnViolation
T023: TestSameScoringRulesAsOriginalSelection
T024: TestRecommendationTracesToVerifiedResult
T025: TestCostRelativeAndOneSentenceRationale
T026: TestConstraintBreachCaveatStatedExplicitly
T027: TestNoAlternativeReportedPlainly
T028: TestBudgetExhaustionFoldedIntoNoAlternative
T029: TestFreshnessLapseFoldedIntoNoAlternative
T030: TestNextRankedTriedWhenTopVerificationFails
T031: TestEverySearchCountsAgainstCallBudget
T032: TestPastDepartureJourneyInert
T033: TestSupersededByNewerWake
T034: TestOnWakeFiresFromConfirmAndReconcile
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T008)
3. Complete Phase 3: US1 tests (T009–T013) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T014)
5. Run T015 gate — all tests must pass
6. Complete Phase 4: US2 (T016–T021)
7. **STOP and VALIDATE**: A wake correctly determines and records whether the objective still holds, in objective terms, with no wasted search activity when it does — the core translation step the entire feature exists to perform

### Incremental Delivery

1. Setup + Foundational → schema, event types, and skeleton ready
2. US1 → violations are correctly determined and stated from durable state
3. US2 → satisfied determinations are equally recorded, with zero wasted search
4. US3 → a violation drives the full search/score/verify/recommend cycle, demonstrable end-to-end via the disruption injector
5. Polish → full regression + quickstart walkthrough + NFR confirmation + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `flight_search.py`, `scoring_service.py`, or `verification_service.py` — see the Scope Boundary note at the top
- No task in this file registers a `schedule.changed` handler in `webhook_service.py`'s `_EVENT_TYPE_HANDLERS` — the reconciliation sweep is this feature's trigger (research.md R1)
- No task in this file introduces a lock/mutex — concurrency is handled by re-checking for a newer wake (research.md R8, T037)
