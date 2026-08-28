# Tasks: Event Reception and Reconciliation

**Input**: Design documents from `specs/007-webhook-receiver/`

**Feature**: 007-webhook-receiver | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `AttributeError`, or `ImportError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not modify `journey/services/booking_service.py`, `journey/services/verification_gate.py`, `journey/services/conditions/ticketing_condition.py`, `journey/api/routers/events.py`, or `EventService`'s existing methods. It registers 012's existing `TicketingSuccessCondition` with a `PostActionVerifier` instance this feature owns, and it extends `journey/models/events.py`'s enum/payload registry additively (one new case), the same pattern feature 010 used for `AUTHORISATION_VOIDED`.

**The ack/confirm split (NFR-001)**: `WebhookService.receive()` is local-only — no network call — and is what the endpoint waits on before responding. `WebhookService.confirm()` makes the network call to the provider and is scheduled as a FastAPI `BackgroundTask`, running only *after* the response is sent. No task in this file may put `confirm()`'s logic on the request/response path.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema groundwork.

- [x] T001 [P] `webhook_notifications` table added to `backend/journey/storage/tables.py`
- [x] T002 Migration `j0e196n52o79_add_webhook_notifications.py` created, `down_revision = 'i9d085m41n68'`
- [x] T003 [P] `EventType.WAKE_REQUESTED` + `WakeRequestedPayload` added to `events.py`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions, including the existing `test_auth_contract.py`/`test_auth_gate.py` (006) and `test_verification_gate.py`/`test_ticketing_success_condition.py` (012) suites this feature builds on.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model type, storage methods, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] `backend/journey/models/webhook.py` created with `InboundNotification`
- [x] T005 [P] `save_notification()`, `_row_to_notification()`, `get_notifications_for_order()` added to `repository.py`
- [x] T006 [P] `get_active_journeys_with_order_reference()` added to `repository.py` — joins `journeys`/`orders`, excludes `CANCELLED`/`ABANDONED`, one (journey_id, order_no) pair per journey using its most recent order
- [x] T007 `backend/journey/services/webhook_service.py` created — `WebhookService.__init__` constructs its own `PostActionVerifier` registered with `TicketingSuccessCondition`; `receive()`/`confirm()`/`reconcile_active_journeys()` raise `NotImplementedError`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions. `from journey.services.webhook_service import WebhookService` succeeds.

---

## Phase 3: User Story 1 — Untrusted Notification Ingestion (Priority: P1) 🎯 MVP

**Goal**: Every inbound notification is persisted in full before anything else happens to it, and acknowledgement is returned without ever waiting on — or being affected by the outcome of — confirmation.

**Independent Test**: Call `receive()` directly and confirm the exact raw body is persisted, with no network call made. POST to the endpoint with `confirm()` stubbed to fail, and confirm the response is still `200 OK`.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T008 [P] [US1] `TestReceivePersistsFullRawPayload` written
- [x] T009 [P] [US1] `TestReceiveNeverCallsTheProvider` written
- [x] T010 [P] [US1] `TestEndpointAcknowledgesBeforeConfirmationRuns` written — **redesigned during TDD**: an earlier version drove the assertion through `TestClient.post()` with a raising stub `confirm()`, expecting the `200` to return despite the background task's failure; discovered that Starlette's `TestClient` executes background tasks synchronously within the same call, so an unhandled exception there propagates out of `client.post()` itself rather than being isolated the way a real deployed ASGI server would isolate it. Replaced with a precise, deterministic test: call the `receive_atlas_webhook` handler function directly with a real `BackgroundTasks()` and a `Request` built from a raw body, then assert the handler returns its ack payload *and* that `confirm` was merely scheduled (`background_tasks.tasks[0].func is service.confirm`), never invoked — proving the scheduling contract structurally rather than relying on TestClient's execution-order behaviour
- [x] T011 [P] [US1] `TestEndpointAcknowledgesMalformedBody` written (two cases: invalid JSON, and valid JSON with no recognisable fields)
- [x] T012 [US1] Confirmed: all failed (`NotImplementedError` for T008/T009; `ModuleNotFoundError`/`404` for T010/T011, since the router didn't exist yet) before implementation

### Implementation for User Story 1

- [x] T013 [US1] `WebhookService.receive()` implemented (persist-only slice) — parses tolerantly, persists via `save_notification()`, returns `associated=False`, `confirmation_triggered=False` (routing/throttle layered on in US3/US4)
- [x] T014 [US1] `POST /webhooks/atlas` implemented in `backend/journey/api/routers/webhooks.py`, wired into `journey/api/main.py`
- [x] T015 [US1] `python -m pytest backend/tests/unit/test_webhook_service.py backend/tests/contract/test_webhook_contract.py -v -k "PersistsFullRawPayload or NeverCallsTheProvider or ConfirmationRuns or AcknowledgesMalformedBody"` — 5 passed

**Checkpoint**: US1 complete. The endpoint exists, every notification is persisted in full, and acknowledgement is structurally decoupled from confirmation's outcome and timing.

---

## Phase 4: User Story 2 — Confirm Before Acting (Priority: P1)

**Goal**: Every notification's claim is confirmed against the provider independently via 012's existing gate before any journey state changes; the notification's own status value is never read as evidence; the agent is woken only once confirmation resolves.

**Independent Test**: Call `confirm()` with a notification claiming success but a stubbed query showing failure, and confirm the resulting classification reflects the query. Confirm a `WAKE_REQUESTED` event is appended only when the classification resolves to `SUCCESS`/`FAILURE`, never while `UNRESOLVED`.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T016 [P] [US2] `TestConfirmDerivesFromQueryNotClaim` written
- [x] T017 [P] [US2] `TestConfirmIgnoresStatusField` written
- [x] T018 [P] [US2] `TestConfirmRecordsDiscrepancyWhenClaimDisagrees` written
- [x] T019 [P] [US2] `TestNoWakeWhileUnresolved` written
- [x] T020 [P] [US2] `TestWakeAfterConfirmedOutcome` written
- [x] T021 [US2] Confirmed: all 5 failed (first with `AssertionError` on `notification.journey_id is not None` after the initial implementation attempt, `NotImplementedError` against the bare skeleton). **Test-isolation bug found and fixed here**: all 5 originally drove `confirm()` via `service.receive(_envelope(), ...)`, but `receive()`'s US1-only implementation always returns `journey_id=None` — routing/association doesn't exist until US3. Fixed by adding an `_associated_notification()` test helper that constructs an already-associated `InboundNotification` directly, decoupling US2's tests from US3's not-yet-built logic, consistent with `confirm()`'s own contract (it only needs `journey_id`/`order_reference` present, not *how* they got set)

### Implementation for User Story 2

- [x] T022 [US2] `WebhookService._query_order_details()` implemented — calls `queryOrderDetails.do` (`_ATLAS_QUERY_URL`, same request shape as `BookingService._query_order()`, research.md R2), returns `(query_result, observed_at)`
- [x] T023 [US2] `WebhookService.confirm()` implemented — builds a zero-arg closure over `order_reference` wrapping `_query_order_details()` (matching 012's `QueryFn` contract), calls `self._verifier.verify(...)` with the notification's parsed `data` as `action_response`, appends `WAKE_REQUESTED` only when the classification resolves
- [x] T024 [US2] `python -m pytest backend/tests/unit/test_webhook_service.py -v -k "DerivesFromQuery or IgnoresStatus or RecordsDiscrepancy or NoWakeWhileUnresolved or WakeAfterConfirmed"` — 5 passed

**Checkpoint**: US2 complete. Confirmation is 012's gate, reused verbatim — the notification's claim never governs, its status field is never read, disagreement is recorded, and the agent is woken only on a resolved outcome.

---

## Phase 5: User Story 3 — Correct Routing and Association (Priority: P1)

**Goal**: A notification is routed by its declared type, associated with a journey by order reference, and discarded (with no confirmation triggered) if the order reference matches no known journey, no handler is registered for the type, or the associated journey is already terminal.

**Independent Test**: Send notifications of different declared types and confirm each is handled — or correctly left inert — according to its own type. Send one whose order reference matches no known journey and confirm it is discarded with no journey affected.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T025 [P] [US3] `TestKnownTypeAndOrderTriggersConfirmation` written
- [x] T026 [P] [US3] `TestUnknownOrderReferenceDiscarded` written
- [x] T027 [P] [US3] `TestUnrecognisedEventTypeIsInert` written
- [x] T028 [P] [US3] `TestTerminalJourneySkipsConfirmation` written
- [x] T029 [P] [US3] `TestStatusTypeNormalisationFlowsThroughEndToEnd` written
- [x] T030 [US3] Confirmed: 4 of 5 failed (`associated` staying `False`, or the US2 assertion error on `journey_id`); `TestUnknownOrderReferenceDiscarded` passed immediately — US1's `receive()` already never associates, which happens to be exactly what this test expects, the same "already-true-against-the-prior-story's-code" pattern seen elsewhere in this codebase

### Implementation for User Story 3

- [x] T031 [US3] Event-type handler registry (`_EVENT_TYPE_HANDLERS = {"order.ticketed": "ticketing"}`) added — no default entry (research.md R5)
- [x] T032 [US3] `WebhookService.receive()` extended: looks up the journey via `get_order_by_order_no()`, sets `associated`/`journey_id`; checks the handler registry and the journey's state against a local `_TERMINAL_STATES` set (mirroring `event_service.py`'s own); `confirmation_triggered=True` only when order known, type registered, and journey non-terminal — throttle check still deferred to US4
- [x] T033 [US3] `python -m pytest backend/tests/unit/test_webhook_service.py -v -k "KnownTypeAndOrder or UnknownOrderReference or UnrecognisedEventType or TerminalJourney or StatusTypeNormalisation"` — 5 passed

**Checkpoint**: US3 complete. Notifications are routed, associated, and gated correctly before confirmation is ever attempted — an unknown order, an unrecognised type, or a terminal journey all inertly stop here, unconditionally still persisted (US1).

---

## Phase 6: User Story 4 — Duplicate Tolerance, Throttling, and Independent Reconciliation (Priority: P2)

**Goal**: A burst of notifications for one journey — duplicates, distinct notifications, or a forged flood — collapses into a bounded number of confirmation queries against the provider. Active journeys are reconciled against the provider on their own schedule, independent of notification history, using the same confirmation path and the same throttle.

**Independent Test**: Send the identical notification, and separately several distinct-looking notifications, for one journey in quick succession; confirm only one confirmation query is triggered in each case. Call the reconciliation sweep for a journey with no notification history and confirm it is still checked.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T034 [P] [US4] `TestDuplicateBurstCollapsesToOneConfirmation` written
- [x] T035 [P] [US4] `TestDistinctNotificationBurstCollapsesToo` written
- [x] T036 [P] [US4] `TestOutsideWindowTriggersFreshConfirmation` written
- [x] T037 [P] [US4] `TestReconciliationCoversJourneyWithNoNotificationHistory` written
- [x] T038 [P] [US4] `TestReconciliationSkipsTerminalJourneys` written
- [x] T039 [P] [US4] `TestReconciliationRespectsTheSameThrottle` written
- [x] T040 [US4] Confirmed: `TestDuplicateBurstCollapsesToOneConfirmation`/`TestDistinctNotificationBurstCollapsesToo` failed on the *first* implementation attempt too (see gap below) before the real fix; `TestOutsideWindowTriggersFreshConfirmation` passed immediately (no throttle existed yet, so every notification triggered, trivially matching); the three reconciliation tests failed with `NotImplementedError`

### Implementation for User Story 4

- [x] T041 [US4] `WebhookService.receive()` extended with a throttle check. **Real gap found and fixed here**: the first implementation checked only `get_verification_attempts()` (rows written by `confirm()`) — but `confirm()` runs as a background task, so a burst of `receive()` calls arriving before the *first* `confirm()` completes would find no `VerificationAttempt` yet and all slip through unthrottled (`TestDuplicateBurstCollapsesToOneConfirmation`/`TestDistinctNotificationBurstCollapsesToo` caught this: both failed with `[True, True, True, True, True]` instead of one `True`). Fixed by also checking prior notifications' `confirmation_triggered` flag (persisted synchronously by `receive()` itself, before `confirm()` ever runs) — `_within_confirmation_budget_window()` now checks both sources
- [x] T042 [US4] `WebhookService.reconcile_active_journeys(now)` implemented — iterates `get_active_journeys_with_order_reference()`, applies the same throttle, confirms via the same `PostActionVerifier` path, records `"reconciliation_sweep"` as the `declared_event_type` in any resulting `WAKE_REQUESTED` event
- [x] T043 [US4] Periodic reconciliation loop wired into `journey/api/main.py`'s `lifespan` via `asyncio.create_task`, cancelled cleanly on shutdown — a plain loop, no new scheduler dependency (research.md R6)
- [x] T044 [US4] `python -m pytest backend/tests/unit/test_webhook_service.py backend/tests/unit/test_webhook_reconciliation.py -v -k "DuplicateBurst or DistinctNotificationBurst or OutsideWindow or Reconciliation"` — 6 passed

**Checkpoint**: US4 complete. Confirmation-query volume per journey is bounded regardless of notification volume or source, duplicates never multiply resulting actions, and every active journey is covered independently of whether it ever received a notification.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [x] T045 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_007.html` — 327 passed, 4 pre-existing failures (`test_objective_parser.py`, unrelated `DASHSCOPE_API_KEY` dependency, predate this feature)
- [x] T046 [P] Walked through all four quickstart.md scenarios — each maps directly to a passing test class already in the suite; also re-confirmed `test_auth_contract.py`/`test_auth_gate.py` (006) and `test_verification_gate.py`/`test_ticketing_success_condition.py` (012) all still pass unmodified (28 passed) — no discrepancy found
- [x] T047 [P] NFR-001 confirmed: only one `self._http.post(...)` call exists in `webhook_service.py`, inside `_query_order_details()`, called only from `confirm()`/`reconcile_active_journeys()` — never from `receive()`; the router schedules `confirm` via `background_tasks.add_task`, never awaits it inline (T010 already proves this structurally)
- [x] T048 [P] FR-003/FR-006 confirmed: `attempt.classification` is only ever *read* from `PostActionVerifier.verify()`'s return value, never assigned from the notification's own fields; the notification's top-level `status` field is never even extracted anywhere in `webhook_service.py` — already covered by T017
- [x] T049 `backend/journey/__init__.py` updated to export `WebhookService`, `InboundNotification` — no naming collision found (both names were free)
- [x] T050 `mypy journey` run before and after (via `git stash -u` baseline): 13 pre-existing errors in `scoring_service.py`/`repository.py`, identical in both runs — zero new errors from any of this feature's modules

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on Phase 2 and US1's `receive()` (T013) existing to produce a notification to confirm — additive to `webhook_service.py`
- **US3 (Phase 5)**: Depends on Phase 2 and US1's `receive()` (T013) — additive to the same method; independent of US2's `confirm()` internals (US3's tests use `confirmation_triggered` as the observable outcome, not `confirm()`'s own behaviour, except T029 which does call `confirm()` end-to-end and therefore also depends on US2 being implemented)
- **US4 (Phase 6)**: Depends on US1 (T013) and US3 (T032, for `receive()`'s association/routing to exist before throttling it) and US2 (T023, `confirm()`/the sweep's equivalent confirmation call)
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4 and is the true MVP — ingestion, persistence, and ack/confirm decoupling are demonstrable alone.
- **US2**, **US3** are each additive to `receive()`/the service built in US1, the same shared-method pattern used across every prior feature's US2+ stories in this codebase (004, 005, 006, 010, 012).
- **US4** builds on both US2 (the confirmation call it throttles and reuses for the sweep) and US3 (the routing/association it throttles on top of).

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic in `webhook_service.py` / `webhooks.py` (router) / `repository.py`
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003 (Setup) — T002 depends on T001
- T004, T005, T006 (Foundational) can run in parallel; T007 depends on T004
- Within US1: T008–T011 (tests) all parallel
- Within US2: T016–T020 (tests) all parallel
- Within US3: T025–T029 (tests) all parallel
- Within US4: T034–T039 (tests) all parallel
- T045–T048 (Polish) all parallel

---

## Parallel Example: Foundational Phase

```bash
# T004, T005, T006 touch different files — safe to parallelize:
T004: backend/journey/models/webhook.py
T005: backend/journey/storage/repository.py (save_notification, get_notifications_for_order)
T006: backend/journey/storage/repository.py (get_active_journeys_with_order_reference)
# Note: T005 and T006 both touch repository.py — coordinate as sequential edits
# to the same file even though they're logically independent additions.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T007)
3. Complete Phase 3: US1 tests (T008–T012) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T013–T014)
5. Run T015 gate — all tests must pass
6. **STOP and VALIDATE**: The endpoint exists, accepts and fully persists any notification, and acknowledgement is provably independent of whatever confirmation would later do — the actual security/reliability boundary this feature's "point of highest risk" framing cares most about first

### Incremental Delivery

1. Setup + Foundational → schema and skeleton ready
2. US1 → the endpoint, persistence, and the ack/confirm split — provable independently
3. US2 → confirmation reuses 012's gate verbatim; notification claims never govern
4. US3 → routing, association, and terminal/unrecognised-type gating are correct before confirmation is attempted
5. US4 → confirmation-query volume is bounded regardless of notification volume, and reconciliation covers what notifications miss
6. Polish → full regression + quickstart walkthrough + NFR confirmation + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `booking_service.py`, `verification_gate.py`, `ticketing_condition.py`, or `event_service.py`'s existing methods — see the Scope Boundary note at the top
- `receive()` MUST NOT gain a code path that makes a network call — that guarantee is what NFR-001 actually rests on, not just documentation (T009, T047)
- The confirmation budget window (FR-013) and the reconciliation interval (FR-010) are two distinct, independently tunable parameters (data-model.md's Confirmation Budget Window entity) — no task in this file should conflate them into one constant
