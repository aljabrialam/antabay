# Tasks: Disruption Injector

**Input**: Design documents from `specs/008-disruption-injector/`

**Feature**: 008-disruption-injector | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `AttributeError`, or `ImportError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not build a schedule-change confirmation handler (research.md R4 — no query interface for schedule changes is documented anywhere), and does not build a general-purpose authentication system (research.md R5 — a single shared-secret token check is sufficient for this one operator-only endpoint). It extends `journey/models/webhook.py`, `journey/services/webhook_service.py`, `journey/storage/tables.py`/`repository.py` additively (new field, new optional parameter with a default, new column) — it does not modify `journey/services/verification_gate.py`, `journey/services/conditions/ticketing_condition.py`, or `journey/api/routers/webhooks.py`'s existing route.

**"Same reception path" (FR-002, research.md R1)**: Delivery is a direct call to `WebhookService.receive()`/`.confirm()` — the identical methods a real notification's arrival triggers — never a second, parallel implementation or a self-directed HTTP round-trip.

**Fail-closed default (research.md R5, extended to FR-008)**: Both the operator token check and the injector's own enabled/disabled state default to the *safer* outcome — unauthorised, and disabled — when their configuration is absent, never to open/enabled by default.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema groundwork.

- [x] T001 [P] `simulated` column added to `webhook_notifications` in `backend/journey/storage/tables.py`
- [x] T002 Migration `k1f207o63p80_add_simulated_to_webhook_notifications.py` created, `down_revision = 'j0e196n52o79'`
- [x] T003 [P] `JourneyNotFoundError`, `JourneyHasNoOrderError`, `InjectorDisabledError` added to `backend/journey/errors.py`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including 007's own suites this feature builds on.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model field, storage methods, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] `InboundNotification` gains a `simulated: bool = False` field
- [x] T005 [P] `save_notification()`/`_row_to_notification()` extended to persist/read `simulated`
- [x] T006 [P] `get_order_no_for_journey(journey_id) -> str | None` added to `repository.py`
- [x] T007 `WebhookService.receive()` gains a `simulated: bool = False` parameter, stored on the resulting `InboundNotification` — `confirm()`'s `WAKE_REQUESTED` threading is deferred to US3 (T026/T027), not part of this task
- [x] T008 `backend/journey/services/disruption_injector_service.py` created — `DisruptionInjectorService.inject()` raises `NotImplementedError`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including 007's own test suites (`test_webhook_service.py`, `test_webhook_reconciliation.py`, `test_webhook_contract.py`) passing exactly as before. `from journey.services.disruption_injector_service import DisruptionInjectorService` succeeds.

---

## Phase 3: User Story 1 — Produce a Conforming Schedule-Change Notification (Priority: P1) 🎯 MVP

**Goal**: Given a target journey with a real order and a specified revised arrival time, produce and deliver a notification whose envelope structurally conforms to the observed convention, references the real order unmodified, carries the specified time, and touches no travel data. Reject a nonexistent journey and a real journey with no order yet, distinguishably.

**Independent Test**: Inject against a seeded journey+order and inspect the resulting persisted notification's raw envelope for structure, order reference, and revised time. Inject against a nonexistent journey and a real journey with no order, and confirm each raises its own distinct error.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T009 [P] [US1] `TestEnvelopeStructureConformsToObservedShape` written
- [x] T010 [P] [US1] `TestEnvelopeReferencesRealOrderUnmodified` written
- [x] T011 [P] [US1] `TestEnvelopeCarriesSpecifiedRevisedTime` written
- [x] T012 [P] [US1] `TestNoTravelDataFabricated` written
- [x] T013 [P] [US1] `TestNonexistentJourneyRejected` written
- [x] T014 [P] [US1] `TestJourneyWithNoOrderRejected` written
- [x] T015 [US1] Confirmed: all 6 failed with `NotImplementedError` before implementation

### Implementation for User Story 1

- [x] T016 [US1] `DisruptionInjectorService.inject()` implemented — `get_journey()`'s `NoResultFound` translated to `JourneyNotFoundError`, `get_order_no_for_journey()` gates `JourneyHasNoOrderError`, envelope constructed per data-model.md, delivered via `WebhookService.receive(raw_body, now, simulated=True)` then `.confirm()` if triggered; no enabled/disabled check yet (US4 adds it)
- [x] T017 [US1] `python -m pytest backend/tests/unit/test_disruption_injector_service.py -v -k "EnvelopeStructure or EnvelopeReferences or EnvelopeCarries or NoTravelData or NonexistentJourney or JourneyWithNoOrder"` — 6 passed

**Checkpoint**: US1 complete. The injector produces a correctly-shaped, correctly-targeted notification and rejects an invalid or not-yet-ready target with distinguishable errors.

---

## Phase 4: User Story 2 — Delivery Through the Real Reception Path, Marked Simulated (Priority: P1)

**Goal**: Confirm delivery reuses 007's own `WebhookService` logic exactly (no shortcut), the resulting record is marked simulated permanently, and a real notification for the same order is completely unaffected by a coexisting simulated one.

**Independent Test**: Inject a notification and confirm it is indistinguishable, in its handling, from what `WebhookService.receive()` would do for any input except for the `simulated` flag. Re-read the stored record later and confirm the marking persists. Deliver a real notification for the same order and confirm its own handling is unaffected.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T018 [P] [US2] `TestDeliveredViaSameReceptionPath` written
- [x] T019 [P] [US2] `TestMarkedSimulatedPermanently` written
- [x] T020 [P] [US2] `TestRealNotificationIndependentOfSimulatedOne` written
- [x] T021 [US2] Confirmed: all 3 passed immediately against US1's implementation — the same "already-true-against-the-prior-story's-code" pattern seen repeatedly across this codebase's features; no TDD-gate violation since these assert behaviour the prior story's own implementation already had to get right to pass its own tests

### Implementation for User Story 2

- [x] T022 [US2] No new implementation needed — confirmed
- [x] T023 [US2] `python -m pytest backend/tests/unit/test_disruption_injector_service.py -v -k "DeliveredViaSameReceptionPath or MarkedSimulatedPermanently or RealNotificationIndependent"` — 3 passed

**Checkpoint**: US2 complete. Delivery is provably the same logic path 007 already has, the simulated marking is permanent, and a real notification for the same order is never affected by a simulated one.

---

## Phase 5: User Story 3 — Simulation Visibility Everywhere Downstream (Priority: P1)

**Goal**: Any event derived from an injected notification carries the simulated marking, reusing feature 006's existing `JourneyEvent.simulated` field — proven structurally, since no schedule-change confirmation handler exists in production yet to exercise this for real (research.md R4).

**Independent Test**: Using a test-only stub confirmation handler registered for `"schedule.changed"`, inject a notification and confirm the resulting `WAKE_REQUESTED` event carries `simulated=True`.

### Tests for User Story 3

> **Write this test FIRST — verify it FAILS before any implementation**

- [x] T024 [P] [US3] `TestWakeEventCarriesSimulatedFlag` written — a test-only stub `SuccessCondition` registered directly on `webhook_service._EVENT_TYPE_HANDLERS`/`self._verifier._conditions` for the duration of the test, restored in a `finally` block
- [x] T025 [US3] Confirmed: failed with `simulated=False` on the resulting event before implementation (**test bug of my own found and fixed first**: the test originally called `service._webhook_service.confirm(notification)` a second time in addition to `inject()`'s own internal call, producing 2 `WAKE_REQUESTED` events instead of 1 — fixed by removing the redundant call, since `inject()` already calls `confirm()` when `confirmation_triggered` is `True`)

### Implementation for User Story 3

- [x] T026 [US3] `WebhookService.confirm()` extended: passes `simulated=notification.simulated` to `EventService.append()` for the `WAKE_REQUESTED` event (research.md R3). `reconcile_active_journeys()` left unchanged — it always confirms independently and its `WAKE_REQUESTED` events keep the default `simulated=False`.
- [x] T027 [US3] `python -m pytest backend/tests/unit/test_disruption_injector_service.py -v -k WakeEventCarriesSimulatedFlag` — 1 passed

**Checkpoint**: US3 complete. The simulated marking reaches any event this feature's plumbing produces, reusing 006's existing mechanism — proven correct even though no production schedule-change handler exists yet to trigger it for real.

---

## Phase 6: User Story 4 — Operator-Only Control, Disableable (Priority: P2)

**Goal**: The injector's HTTP trigger is reachable only with a valid operator token, fails closed (unauthorised) if that token is unconfigured, and produces no effect at all while disabled — checked before any target lookup.

**Independent Test**: Attempt to trigger without a token, with a wrong token, and with a correct token while disabled — confirm none produce a notification. Confirm a correct token while enabled behaves exactly as User Story 1.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T028 [P] [US4] `TestDisabledInjectorRejectsInjection` written
- [x] T029 [P] [US4] `TestEndpointRejectsMissingOrWrongToken` written
- [x] T030 [P] [US4] `TestEndpointRejectsWhenDisabled` written
- [x] T031 [P] [US4] `TestEndpointAcceptsValidTokenWhenEnabled` written
- [x] T032 [P] [US4] `TestEndpointTranslatesTargetErrors` written (two cases: 404, 409)
- [x] T033 [US4] Confirmed: unit test failed with `TypeError` (`enabled` kwarg didn't exist yet); contract tests failed with `404` (route didn't exist) — except the nonexistent-journey case, which passed vacuously since "route doesn't exist" and "journey doesn't exist" both happen to be `404` (not a real pass, just a coincidence of status codes, corrected once the route existed for real)

### Implementation for User Story 4

- [x] T034 [US4] `DisruptionInjectorService.__init__` extended with `enabled: bool | None = None`, defaulting to `os.environ.get("DISRUPTION_INJECTOR_ENABLED", "").lower() == "true"` when not explicitly passed — disabled unless explicitly opted in. `inject()` checks this first, before any journey lookup.
- [x] T035 [US4] `backend/journey/api/routers/disruption_injector.py` created — `POST /operator/disruptions`, `X-Operator-Token` checked against `os.environ.get("DISRUPTION_INJECTOR_TOKEN")` (unset/empty → every request unauthorised); translates `InjectorDisabledError`/`JourneyNotFoundError`/`JourneyHasNoOrderError` to `401`/`404`/`409`
- [x] T036 [US4] Router wired into `backend/journey/api/main.py`
- [x] T037 [US4] `python -m pytest backend/tests/unit/test_disruption_injector_service.py backend/tests/contract/test_disruption_injector_contract.py -v -k "Disabled or Token or TranslatesTargetErrors"` — 7 passed

**Checkpoint**: US4 complete. The injector is unreachable without the correct token, fails closed if unconfigured, and is fully inert while disabled — checked before any other logic runs.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [x] T038 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_008.html` — 344 passed, 4 pre-existing failures (`test_objective_parser.py`, unrelated `DASHSCOPE_API_KEY` dependency, predate this feature)
- [x] T039 [P] Walked through all four quickstart.md scenarios — each maps directly to a passing test class already in the suite; also re-confirmed `test_webhook_service.py`/`test_webhook_reconciliation.py`/`test_webhook_contract.py` (007) and `test_auth_contract.py`/`test_auth_gate.py` (006) all still pass unmodified (28 passed) — no discrepancy found
- [x] T040 [P] NFR-002/FR-008 confirmed: `expected = os.environ.get(_TOKEN_ENV_VAR, "")` combined with `if not expected or ...` rejects every request when unset; `os.environ.get(_ENABLED_ENV_VAR, "").lower() == "true"` evaluates to `False` when unset — both default to the rejecting branch, no code path defaults to open or enabled
- [x] T041 [P] FR-007 confirmed: zero matches for `price`/`availability`/`option`/`flight` anywhere in `disruption_injector_service.py` — already covered by T012
- [x] T042 `backend/journey/__init__.py` updated to export `DisruptionInjectorService` — no naming collision found
- [x] T043 `mypy journey` run before and after (via `git stash -u` baseline): 13 pre-existing errors in `scoring_service.py`/`repository.py`, identical in both runs — zero new errors from any of this feature's new or extended modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on US1's `inject()` (T016) existing — purely additive test coverage, no new production code expected
- **US3 (Phase 5)**: Depends on US1's `inject()` (T016) and Foundational's `receive()` extension (T007) — additive to `WebhookService.confirm()`
- **US4 (Phase 6)**: Depends on US1's `inject()` (T016) — extends it with the enabled check, and adds the router that calls it
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4, and is the true MVP — a correctly-shaped, correctly-targeted, correctly-delivered notification is independently demonstrable.
- **US2** is a pure test-rigor addition on US1's `inject()`, the same "already-true-against-the-prior-story's-implementation" pattern used repeatedly across this codebase's features.
- **US3** extends `WebhookService.confirm()` (007), reusing US1's delivery path as its trigger.
- **US4** extends `inject()` with one more precondition check and adds the HTTP-layer access control around it.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003 (Setup) — T002 depends on T001
- T004, T005, T006 (Foundational) can run in parallel; T007 and T008 have no cross-dependency on each other
- Within US1: T009–T014 (tests) all parallel
- Within US2: T018–T020 (tests) all parallel
- Within US4: T028–T032 (tests) all parallel
- T038–T041 (Polish) all parallel

---

## Parallel Example: User Story 1 Tests

```bash
# T009-T014 all write to the same new test file but assert independent
# scenarios with no shared mutable state (each seeds its own journey/order
# in its own tmp_path DB) — safe to parallelize:
T009: TestEnvelopeStructureConformsToObservedShape
T010: TestEnvelopeReferencesRealOrderUnmodified
T011: TestEnvelopeCarriesSpecifiedRevisedTime
T012: TestNoTravelDataFabricated
T013: TestNonexistentJourneyRejected
T014: TestJourneyWithNoOrderRejected
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T008)
3. Complete Phase 3: US1 tests (T009–T015) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T016)
5. Run T017 gate — all tests must pass
6. **STOP and VALIDATE**: A correctly-shaped, correctly-targeted schedule-change notification can be produced and delivered through 007's real reception path — the actual demonstrable capability this feature exists to provide

### Incremental Delivery

1. Setup + Foundational → schema and skeleton ready
2. US1 → the injector produces and delivers a real, correctly-shaped notification
3. US2 → delivery is provably the same path 007 already has, marking is permanent, real/simulated stay independent
4. US3 → the simulated marking reaches any downstream event, proven structurally
5. US4 → the capability is locked down to the operator and can be switched off entirely
6. Polish → full regression + quickstart walkthrough + NFR confirmation + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `verification_gate.py`, `ticketing_condition.py`, or `webhooks.py`'s existing route — see the Scope Boundary note at the top
- Both the operator-token check and the enabled/disabled default MUST fail closed when their configuration is absent — no task may introduce a code path that defaults to open or enabled (T040)
- This feature does not build a schedule-change confirmation handler — `TestWakeEventCarriesSimulatedFlag` (T024) uses a test-only stub condition specifically because no such handler exists in production (research.md R4)
