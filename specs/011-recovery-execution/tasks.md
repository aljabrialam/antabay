# Tasks: Recovery Execution

**Input**: Design documents from `specs/011-recovery-execution/`

**Feature**: 011-recovery-execution | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `AttributeError`, or `ImportError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not modify `journey/services/booking_service.py`, `journey/services/verification_service.py`, or `journey/services/authorisation_policy_engine.py` — all three are called unmodified (research.md R2–R3). This feature does not build a bridge from a `Recommendation` to an authorisation request — it only ever calls `AuthorisationPolicyEngine.enforce_authorised()`, never `.evaluate()`/`.request_if_required()` (research.md R2); tests construct the "already granted" precondition directly.

**Disclosed provisional gap (research.md R1)**: No Atlas endpoint for cancellation has ever been verified against the sandbox. This feature's cancellation call and its success predicate are explicitly provisional — flagged in code comments at the call site, not hidden. No task in this file may present this as verified.

**No new lock primitive (research.md R5)**: Duplicate-attempt protection is a single, checked-first `RecoveryExecution` row per `recommendation_id` — never a mutex.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema groundwork.

- [X] T001 [P] `recovery_executions` and `cancellation_attempts` tables, and `journeys.current_order_no` column, added to `backend/journey/storage/tables.py`
- [X] T002 Migration created for both new tables and the new column in `backend/journey/migrations/versions/`
- [X] T003 [P] `RecommendationNotFoundError`, `RecoveryAlreadyAttemptedError` added to `backend/journey/errors.py`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The models, event types, storage methods, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] `RecoveryExecutionStatus`, `ReplacementOutcome`, `CancellationOutcome` enums and `RecoveryExecution`, `CancellationAttempt` dataclasses created in `backend/journey/models/recovery_execution.py`
- [X] T005 [P] New `EventType` members (`RECOVERY_EXECUTION_ABANDONED`, `REPLACEMENT_SECURED`, `CANCELLATION_OUTCOME_RECORDED`, `RECOVERY_EXECUTION_COMPLETED`) added to `backend/journey/models/events.py`, with matching payload models registered in `_PAYLOAD_MODELS`
- [X] T006 [P] `save_recovery_execution`, `update_recovery_execution`, `get_recovery_execution_by_recommendation`, `save_cancellation_attempt`, `set_current_order`, `get_current_order_no`, `get_recommendation` added to `backend/journey/storage/repository.py`
- [X] T007 `backend/journey/services/recovery_execution_service.py` created — `RecoveryExecutionService.execute(recommendation_id, now)` raises `NotImplementedError`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including 004/005/009/010's own test suites passing exactly as before. `from journey.services.recovery_execution_service import RecoveryExecutionService` succeeds.

---

## Phase 3: User Story 1 — Execute Only What Was Authorised (Priority: P1) 🎯 MVP

**Goal**: Refuse execution without a matching authorisation; abandon if the alternative's price or availability has changed since authorisation was granted.

**Independent Test**: Attempt execution with no authorisation and confirm refusal. Grant authorisation, then change the option's price/availability, and confirm execution is abandoned rather than proceeding.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T008 [P] [US1] `TestRefusedWithoutMatchingAuthorisation` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T009 [P] [US1] `TestAbandonedWhenPriceChanged` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T010 [P] [US1] `TestAbandonedWhenAlternativeUnavailable` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T011 [US1] Confirmed: all 3 fail with `NotImplementedError` before implementation

### Implementation for User Story 1

- [X] T012 [US1] `RecoveryExecutionService.execute()` implemented through the authorisation-gate step: lookup `Recommendation` (`RecommendationNotFoundError` if missing), duplicate-attempt guard (`RecoveryAlreadyAttemptedError`), insert `IN_PROGRESS` row, fresh `VerificationService.verify()` call, abandon on non-`VERIFIED` outcome, `AuthorisationPolicyEngine.enforce_authorised()` check, abandon on refusal — no replacement-booking or cancellation logic yet (US2/US3 add it)
- [X] T013 [US1] `python -m pytest backend/tests/unit/test_recovery_execution_service.py -v -k "RefusedWithoutMatchingAuthorisation or AbandonedWhenPriceChanged or AbandonedWhenAlternativeUnavailable"` — 3 passed

**Checkpoint**: US1 complete. Execution never proceeds without a valid, price-matched authorisation.

---

## Phase 4: User Story 2 — Secure the Replacement Before Releasing the Original (Priority: P1)

**Goal**: Create and pay for the replacement, confirm its ticketing by independent query, and only then update the journey's current-order pointer — with the superseded order_no captured before the replacement exists, and the superseded booking always left untouched on any replacement-side failure.

**Independent Test**: Execute a recovery and confirm the replacement is created, paid, and ticketing-confirmed before `journeys.current_order_no` changes. Force replacement creation/payment to fail and confirm the superseded booking is untouched and the traveller still holds a confirmed booking.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T014 [P] [US2] `TestReplacementCreatedPaidAndTicketingConfirmed` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T015 [P] [US2] `TestCurrentOrderPointerUpdatesOnlyAfterTicketingConfirmed` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T016 [P] [US2] `TestSupersededOrderCapturedBeforeReplacementCreated` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T017 [P] [US2] `TestReplacementCreationFailureLeavesSupersededUntouched` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T018 [P] [US2] `TestReplacementPaymentFailureLeavesSupersededUntouched` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T019 [P] [US2] `TestTravellerNeverWithoutConfirmedBooking` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T020 [US2] Confirmed: all 6 fail before implementation

### Implementation for User Story 2

- [X] T021 [US2] `execute()` extended: capture `superseded_order_no` via `get_order_no_for_journey()` before any replacement call; `BookingService.create_order()` → `.submit_payment()` → `.confirm_ticketing()` in sequence, each failure/non-confirmation abandoning with the appropriate reason and `cancellation_outcome = NOT_ATTEMPTED`; on success, `set_current_order(journey_id, replacement_order_no)`
- [X] T022 [US2] `python -m pytest backend/tests/unit/test_recovery_execution_service.py -v -k "ReplacementCreatedPaidAndTicketingConfirmed or CurrentOrderPointerUpdatesOnlyAfterTicketingConfirmed or SupersededOrderCapturedBeforeReplacementCreated or ReplacementCreationFailureLeavesSupersededUntouched or ReplacementPaymentFailureLeavesSupersededUntouched or TravellerNeverWithoutConfirmedBooking"` — 6 passed

**Checkpoint**: US2 complete. The safety ordering — replacement secured before original released — holds in every tested path.

---

## Phase 5: User Story 3 — Treat Replacement and Cancellation as Separate Outcomes (Priority: P2)

**Goal**: Initiate cancellation only after replacement confirmation; record and surface a cancellation failure distinctly from a fully successful recovery; refuse a duplicate execution attempt against the same recommendation; report the final position in objective terms; record the full sequence including the authorisation that permitted it.

**Independent Test**: Force a cancellation failure after a successful replacement and confirm the exact partial state is recorded and surfaced. Confirm a full success returns a final position in objective terms with the complete sequence in the audit trail. Confirm a second `execute()` call against the same `recommendation_id` is refused.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [X] T023 [P] [US3] `TestCancellationInitiatedOnlyAfterReplacementConfirmed` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T024 [P] [US3] `TestCancellationFailureRecordedAndSurfaced` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T025 [P] [US3] `TestCancellationSuccessRecorded` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T026 [P] [US3] `TestCancellationAlwaysReconciledByQuery` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T027 [P] [US3] `TestDuplicateExecutionRefused` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T028 [P] [US3] `TestFinalPositionReportedInObjectiveTerms` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T029 [P] [US3] `TestAuditTrailIncludesAuthorisation` written in `backend/tests/unit/test_recovery_execution_service.py`
- [X] T030 [US3] Confirmed: all 7 fail before implementation

### Implementation for User Story 3

- [X] T031 [US3] Cancellation pipeline added: best-effort `void.do` call → `CancellationAttempt` persisted → independent `queryOrderDetails.do` reconciliation query → `confirmed_cancelled` set per research.md R1's success predicate (mirror of `TicketingSuccessCondition`) — called only after `replacement_outcome = SUCCEEDED`
- [X] T032 [US3] `final_position_description` built in objective terms and `status = COMPLETED` set regardless of `cancellation_outcome` (research.md R6 — the journey never left `MONITORING`)
- [X] T033 [US3] Every step's event append verified to carry `recommendation_id`; audit trail confirmed traceable to the specific `AUTHORISATION_OUTCOME` event via the authorisation engine's own event log
- [X] T034 [US3] `python -m pytest backend/tests/unit/test_recovery_execution_service.py -v -k "CancellationInitiatedOnlyAfterReplacementConfirmed or CancellationFailureRecordedAndSurfaced or CancellationSuccessRecorded or CancellationAlwaysReconciledByQuery or DuplicateExecutionRefused or FinalPositionReportedInObjectiveTerms or AuditTrailIncludesAuthorisation"` — 7 passed

**Checkpoint**: US3 complete. Replacement and cancellation are fully independent, auditable outcomes; the feature is demonstrable end-to-end from an authorised recommendation to a final, objective-terms position.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [X] T035 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_011.html` — full suite, no new regressions
- [X] T036 [P] Walked through all five quickstart.md scenarios against the passing test suite; re-confirmed 004/005/006/009/010's own test suites still pass unmodified
- [X] T037 [P] NFR-001 confirmed: cancellation call site is only reachable after `replacement_outcome = SUCCEEDED` is set — no code path reaches it earlier
- [X] T038 [P] NFR-002 confirmed: every retried/ambiguous step (cancellation) is preceded by a reconciliation query before any conclusion is drawn; no step is called twice on the same uncertain outcome without one
- [X] T039 `backend/journey/__init__.py` updated to export `RecoveryExecutionService` — checked for naming collisions against existing exports
- [X] T040 `mypy journey` run before and after (via `git stash -u` baseline) — no new errors introduced by this feature's new or extended modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3
- **US2 (Phase 4)**: Depends on US1's authorisation-gate step (T012) existing
- **US3 (Phase 5)**: Depends on US2's replacement pipeline (T021) — cancellation only makes sense once a replacement can succeed
- **Polish (Phase 6)**: Depends on US1 + US2 + US3

### User Story Dependencies

- **US1** is the necessary gate — nothing else in this feature is safe to demonstrate until execution is provably bounded by a real, price-matched authorisation.
- **US2** is the safety-critical core (replacement before release) and depends on US1's gate holding first.
- **US3** is P2 — the refinement that makes a partial outcome trustworthy and auditable, layered on top of US2's already-correct ordering.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003 (Setup) — T002 depends on T001
- T004, T005, T006 (Foundational) can run in parallel
- Within US1: T008–T010 (tests) all parallel
- Within US2: T014–T019 (tests) all parallel
- Within US3: T023–T029 (tests) all parallel
- T035–T038 (Polish) all parallel

---

## Parallel Example: User Story 2 Tests

```bash
# T014-T019 all write to the same test file but assert independent
# scenarios with no shared mutable state (each seeds its own journey/order
# in its own tmp_path DB) — safe to parallelize:
T014: TestReplacementCreatedPaidAndTicketingConfirmed
T015: TestCurrentOrderPointerUpdatesOnlyAfterTicketingConfirmed
T016: TestSupersededOrderCapturedBeforeReplacementCreated
T017: TestReplacementCreationFailureLeavesSupersededUntouched
T018: TestReplacementPaymentFailureLeavesSupersededUntouched
T019: TestTravellerNeverWithoutConfirmedBooking
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T007)
3. Complete Phase 3: US1 tests (T008–T011) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T012)
5. Run T013 gate — all tests must pass
6. Complete Phase 4: US2 (T014–T022)
7. **STOP and VALIDATE**: An authorised, price-matched recommendation reliably produces a confirmed replacement booking before the original is ever touched, and any replacement-side failure leaves the traveller exactly as they were — the safety property this feature exists to guarantee

### Incremental Delivery

1. Setup + Foundational → schema, event types, and skeleton ready
2. US1 → execution is correctly bounded by authorisation and current price
3. US2 → the replace-before-release ordering holds in every tested path
4. US3 → cancellation's own outcome is independently tracked and surfaced, duplicates are refused, and the final position is reported
5. Polish → full regression + quickstart walkthrough + NFR confirmation + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `booking_service.py`, `verification_service.py`, or `authorisation_policy_engine.py` — see the Scope Boundary note at the top
- No task in this file builds a `Recommendation → ProposedAction` bridge — tests construct the granted-authorisation precondition directly (research.md R2)
- The cancellation call and its success predicate are explicitly provisional (research.md R1) — no task may present this as a verified capability
