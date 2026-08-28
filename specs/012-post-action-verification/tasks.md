# Tasks: Post-Action Verification

**Input**: Design documents from `specs/012-post-action-verification/`

**Feature**: 012-post-action-verification | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `ImportError` or `AttributeError` satisfy the gate.

**Fixture discipline (Constitution Principle XI)**: This feature calls no Atlas endpoint of its own (plan.md, research.md) — it is exercised entirely against plain constructed query-result objects, not VCR cassettes. `test_ticketing_success_condition.py` reuses the exact query-result shapes already proven by spec 005's cassette-backed contract tests (`TestConfirmTicketingAllPassengers`/`PartialResult`/`TerminalError`), so trust in those shapes traces back to a real capture without this feature needing a cassette of its own.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: `backend/journey/services/booking_service.py` is NOT modified by any task in this file. This feature proves its general mechanism against 005's already-verified ticketing rule; migrating `BookingService` itself onto this gate is explicitly a future, separate capability.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema groundwork.

- [x] T001 [P] Added `verification_attempts` table to `backend/journey/storage/tables.py` per data-model.md
- [x] T002 Migration `backend/journey/migrations/versions/i9d085m41n68_add_verification_attempts.py` created, `down_revision = 'h8c974l30m57'`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 252 passed, 12 deselected. No regressions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model types, storage methods, and gate skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] `backend/journey/models/verification_gate.py` created with `VerificationOutcome`, `ConditionResult`, `ReconciliationBound`, `VerificationAttempt`, `SuccessCondition` (as a `typing.Protocol`) per data-model.md
- [x] T004 [P] `save_verification_attempt()`, `get_verification_attempts()`, `get_latest_applied_attempt()` added to `backend/journey/storage/repository.py`
- [x] T005 [P] `UnregisteredActionTypeError` added to `backend/journey/errors.py`
- [x] T006 `PostActionVerifier` skeleton created
- [x] T007 [P] `backend/journey/services/conditions/__init__.py` and `ticketing_condition.py` (skeleton) created

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 252 passed. `from journey.services.verification_gate import PostActionVerifier` succeeds.

---

## Phase 3: User Story 1 — Independent Confirmation Gate (Priority: P1) 🎯 MVP

**Goal**: Journey state is derived only from an independent query, never from the action's own response; every action type must register an explicit success condition (no default); the ticketing condition reproduces spec 005's already-verified rule; concurrent verifications for the same record resolve by observed timestamp, not processing order.

**Independent Test**: Call `verify()` with an `action_response` claiming success and a `query_fn` returning failure; confirm the resulting classification reflects the query, not the claim. Call `verify()` for an unregistered `action_type` and confirm it raises before any query. Feed two attempts with different `observed_at` for the same record and confirm the later-observed one governs regardless of which was processed first.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T008 [P] [US1] `TestVerifyDerivesFromQueryNotAction` written
- [x] T009 [P] [US1] `TestUnregisteredActionTypeRejected` written
- [x] T010 [P] [US1] `TestConcurrencyOrdering` written
- [x] T011 [P] [US1] `TestTicketingConditionMatchesSpec005` written, reusing `_query_response()` copied verbatim from `test_booking_service.py`
- [x] T012 [US1] Confirmed: all 4 failed with `NotImplementedError` before implementation

### Implementation for User Story 1

- [x] T013 [US1] `verify()` core implemented in `backend/journey/services/verification_gate.py`
- [x] T014 [US1] Concurrency-ordering implemented via `_should_apply()`, comparing against `get_latest_applied_attempt()`
- [x] T015 [US1] `TicketingSuccessCondition.classify()` implemented, reproducing `BookingService._query_order()`'s exact rule independently
- [x] T016 [US1] `python -m pytest backend/tests/unit/test_verification_gate.py backend/tests/unit/test_ticketing_success_condition.py -v -k "VerifyDerivesFromQuery or UnregisteredActionType or ConcurrencyOrdering or TicketingConditionMatches"` — 6 passed

**Checkpoint**: US1 complete. The gate derives state only from queries, rejects unregistered action types, resolves concurrent attempts by observed time, and its ticketing condition reproduces 005's already-verified behaviour.

---

## Phase 4: User Story 2 — Discrepancy Detection and Audit Trail (Priority: P1)

**Goal**: A disagreement between an action's response and the subsequent query is recorded, not silently resolved; every verification attempt lands in the audit trail regardless of outcome.

**Independent Test**: Call `verify()` with a claimed-success `action_response` and a query showing failure; confirm `has_discrepancy=True`. Call it again with both agreeing; confirm `has_discrepancy=False` and that both calls produced audit rows.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T017 [P] [US2] `TestDiscrepancyRecorded` written
- [x] T018 [P] [US2] `TestNoDiscrepancyWhenAgreeing` written
- [x] T019 [P] [US2] `TestEveryAttemptAudited` written
- [x] T020 [P] [US2] `TestTicketingConditionDiscrepancy` written, grounded in the webhook-vs-query `orderStatus` scenario (capability map §7c)
- [x] T021 [US2] Confirmed: all 4 failed with `NotImplementedError` before implementation

### Implementation for User Story 2

- [x] T022 [US2] Discrepancy detection implemented in `verify()` — calls `has_discrepancy()` whenever `action_response` is provided
- [x] T023 [US2] `TicketingSuccessCondition.has_discrepancy()` implemented, comparing normalised `orderStatus` between the action response and the query result
- [x] T024 [US2] `python -m pytest backend/tests/unit/test_verification_gate.py backend/tests/unit/test_ticketing_success_condition.py -v -k "Discrepancy or EveryAttemptAudited"` — 4 passed

**Checkpoint**: US2 complete. Discrepancies are recorded, not resolved by preference, and the audit trail is complete regardless of outcome.

---

## Phase 5: User Story 3 — Unresolved Outcome Handling (Priority: P1)

**Goal**: An inconclusive query result stays unresolved even at the reconciliation bound; a consistently not-found result resolves to failure at the bound; reconciliation only ever queries again, never repeats the original action.

**Independent Test**: Drive `verify()`/`reconcile_unresolved()` with a condition that always returns `INCONCLUSIVE` until the declared bound is reached; confirm the final classification is still `UNRESOLVED`. Repeat with a condition that always returns `NOT_FOUND`; confirm the final classification is `FAILURE`. Confirm `reconcile_unresolved()`'s signature has no path to invoke the original action at all.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T025 [P] [US3] `TestInconclusiveStaysUnresolvedAtBound` written
- [x] T026 [P] [US3] `TestNotFoundBecomesFailureAtBound` written
- [x] T027 [P] [US3] `TestMixedHistoryStaysUnresolvedAtBound` written
- [x] T028 [P] [US3] `TestReconcileNeverRepeatsAction` written — this one passed immediately against the Phase 2 skeleton (a pure signature-shape assertion, already true before any behavioural implementation existed)
- [x] T029 [P] [US3] `TestBoundAlreadyReachedIsNoOp` written
- [x] T030 [US3] Confirmed: T025–T027 and T029 failed with `NotImplementedError` before implementation; T028 passed immediately (see note above — not a TDD-gate violation, just a test whose assertion the skeleton's interface shape already satisfied)

### Implementation for User Story 3

- [x] T031 [US3] Bound-tracking implemented via `_bound_reached_for_results()`, deriving history from `get_verification_attempts()`
- [x] T032 [US3] Bound-reached classification rule implemented in `_resolve_classification()`: all-`NOT_FOUND` history → `FAILURE`; anything else → stays `UNRESOLVED`
- [x] T033 [US3] `reconcile_unresolved()` implemented with the exact signature T028 already verified — no `action_response` parameter exists; a no-op returning `history[-1]` if the bound was already reached
- [x] T034 [US3] `python -m pytest backend/tests/unit/test_verification_gate.py -v -k "Unresolved or Bound or Reconcile"` — 5 passed

**Checkpoint**: US3 complete. Unresolved outcomes never default to a guessed success or failure except the one specifically evidenced case (persistent not-found), and reconciliation is structurally incapable of repeating the original action.

---

## Phase 6: User Story 4 — Cross-Surface Type Normalisation (Priority: P2)

**Goal**: A status reported as different types by two surfaces for the same underlying value does not produce a false discrepancy.

**Independent Test**: Feed the ticketing condition an `action_response` and a `query_result` reporting the same status as different types (string vs. integer); confirm no discrepancy is reported.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T035 [P] [US4] `TestNormalizedStatusNoFalseDiscrepancy` written
- [x] T036 [US4] Confirmed: failed with `NotImplementedError` before implementation

### Implementation for User Story 4

- [x] T037 [US4] `normalise_status()` helper implemented in `backend/journey/services/conditions/ticketing_condition.py`, used inside `has_discrepancy()`
- [x] T038 [US4] `python -m pytest backend/tests/unit/test_ticketing_success_condition.py -v -k NormalizedStatus` — 1 passed

**Checkpoint**: US4 complete. A type-only difference between surfaces never registers as a discrepancy.

---

## Phase 7: User Story 5 — Verified-Only Reporting (Priority: P2)

**Goal**: No reportable outcome exists for a record until its verification has resolved to success or failure; there is no "pending" placeholder.

**Independent Test**: Call `reportable_outcome()` while only an unresolved attempt exists; confirm nothing is returned. Resolve it, call again, confirm the resolved outcome is returned.

### Tests for User Story 5

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T039 [P] [US5] `TestReportableOutcomeAbsentWhileUnresolved` written
- [x] T040 [P] [US5] `TestReportableOutcomeAvailableAfterResolution` written
- [x] T041 [US5] Confirmed: both failed with `NotImplementedError` before implementation

### Implementation for User Story 5

- [x] T042 [US5] `PostActionVerifier.reportable_outcome()` implemented — reads `get_latest_applied_attempt()`, returns `classification` only if `SUCCESS`/`FAILURE`, else `None`
- [x] T043 [US5] `python -m pytest backend/tests/unit/test_verification_gate.py -v -k ReportableOutcome` — 2 passed

**Checkpoint**: US5 complete. Nothing downstream can read a reportable outcome before this gate has actually resolved one.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [x] T044 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_012.html` — 281 passed, 4 pre-existing failures (`test_objective_parser.py`, unrelated `DASHSCOPE_API_KEY` dependency, predate this feature)
- [x] T045 [P] Walked through all five quickstart.md scenarios against the test suite. Scenarios 1, 2, 4, 5 matched existing tests directly. **Scenario 3 step 1** ("a query_fn that raises... confirm classification = UNRESOLVED") surfaced a real gap: `verify()` did not catch exceptions from `query_fn()` at all — it would propagate uncaught, contradicting both quickstart.md and `contracts/verification_gate.md`'s explicit table entry ("`query_fn()` itself raises → Persists a `VerificationAttempt` with `condition_result = Inconclusive`... then applies the bound rule as usual") and spec.md's US3 Acceptance Scenario 1. Fixed: added `TestQueryFailureIsInconclusive` (confirmed failing first), then wrapped the `query_fn()` call in `verify()` in a try/except that records `condition_result = INCONCLUSIVE` with `observed_at = now` on exception. All 21 unit tests pass after the fix.
- [x] T046 [P] Confirmed NFR-001: `classification`/`condition_result` are derived only from `query_result` (via `condition.classify()`) in both `verification_gate.py` and `ticketing_condition.py`; `action_response` is read only inside `has_discrepancy()` and for the audit-trail `action_response_json` field — never for classification. Already covered by T008 (`TestVerifyDerivesFromQueryNotAction`).
- [x] T047 `backend/journey/__init__.py` updated to export `PostActionVerifier`, `VerificationAttempt`, `ConditionResult`, `TicketingSuccessCondition`. **Naming collision found and resolved**: `journey.models.verification.VerificationOutcome` (feature 004: `VERIFIED`/`PRICE_CHANGED`/`UNAVAILABLE`/`RATE_LIMITED`/`ERROR`) already occupied that name at package level. This feature's `VerificationOutcome` (`SUCCESS`/`FAILURE`/`UNRESOLVED`) is exported under the alias `GateVerificationOutcome` instead — both classes keep their real name inside their own modules; only the flattened top-level re-export needed disambiguation. Verified both import cleanly side by side.
- [x] T048 `mypy journey` run before and after (via `git stash -u` baseline): 13 pre-existing errors in `scoring_service.py`/`repository.py` (untyped dict/list generics, missing return annotations), identical in both runs — zero new errors from any of this feature's modules.

**Gap found and fixed during Polish (not part of the original task list)**: `_bound_reached_for_results()` only ever checked `bound.max_attempts`, never `bound.max_duration_seconds` — but `TicketingSuccessCondition.reconciliation_bound()` declares only `max_duration_seconds` (30 minutes), never `max_attempts`. This meant the ticketing condition's declared bound could never actually be reached; a persistently not-found or inconclusive ticketing verification would stay `UNRESOLVED` forever instead of resolving to `FAILURE` per FR-006/FR-007. Added `TestDurationBoundReached` (two cases: all-not-found → `FAILURE`, mixed history → stays `UNRESOLVED`), confirmed the first case failed against the old implementation, then implemented duration-based bound checking in `_bound_reached_for_results()` using `now` against the first attempt's `observed_at`. `_resolve_classification()` and `_bound_reached()` were updated to thread `now` through. All existing `max_attempts`-based tests remained unaffected.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4/US5
- **US2 (Phase 4)**: Depends on Phase 2 and on US1's `verify()` core (T013) existing — additive to the same method
- **US3 (Phase 5)**: Depends on Phase 2 and on US1's `verify()` core (T013) existing — additive to the same method
- **US4 (Phase 6)**: Depends on Phase 2 and on US1's `TicketingSuccessCondition` (T015) existing
- **US5 (Phase 7)**: Depends on Phase 2 and Foundational's repository methods (T004) — independent of US1–US4's gate logic beyond needing at least one resolved attempt to exist, which its own tests create directly
- **Polish (Phase 8)**: Depends on US1 + US2 + US3 + US4 + US5

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4/US5.
- **US2** and **US3** are each additive to `PostActionVerifier.verify()`, the single method US1 delivers — the same shared-method pattern used across every prior feature's US2+ stories in this codebase (004, 005, 006).
- **US4** extends `TicketingSuccessCondition` specifically, not the gate itself.
- **US5** is the most independent of the five — `reportable_outcome()` only reads what T004's repository methods already expose.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic in `verification_gate.py` / `ticketing_condition.py` / `repository.py`
3. Confirm tests PASS

### Parallel Opportunities

- T001 (Setup) — T002 depends on it
- T003, T004, T005 (Foundational) can run in parallel; T006 depends on T003; T007 depends on T003
- Within US1: T008–T011 (tests) all parallel
- Within US2: T017–T020 (tests) all parallel
- Within US3: T025–T029 (tests) all parallel
- Within US5: T039–T040 (tests) parallel

---

## Parallel Example: Foundational Phase

```bash
# T003, T004, T005 touch different files — safe to parallelize:
T003: backend/journey/models/verification_gate.py
T004: backend/journey/storage/repository.py
T005: backend/journey/errors.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T007)
3. Complete Phase 3: US1 tests (T008–T012) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T013–T015)
5. Run T016 gate — all tests must pass
6. **STOP and VALIDATE**: The general gate exists, rejects unregistered action types, orders concurrent results correctly, and its ticketing condition reproduces 005's already-trusted behaviour

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → the gate mechanism itself, proven against a real, previously-verified instance
3. US2 → discrepancies are recorded, not silently resolved
4. US3 → unresolved outcomes are handled correctly, including the not-found/inconclusive split
5. US4 → cross-surface type noise doesn't masquerade as a real discrepancy
6. US5 → downstream reporting can only ever see a truly resolved outcome
7. Polish → full regression + quickstart walkthrough + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files with no incomplete dependency — safe to parallelize
- No task in this file modifies `backend/journey/services/booking_service.py` — see the Scope Boundary note at the top
- `INCONCLUSIVE` and `NOT_FOUND` are deliberately distinct `ConditionResult` values — do not collapse them into a single "unresolved" input to the bound logic; their resolutions at the bound differ (research.md R2)
- `reconcile_unresolved()` MUST NOT gain an `action_response` or any other parameter that could be used to re-invoke the original action — this is a structural, not just documented, guarantee (FR-007, T028)
