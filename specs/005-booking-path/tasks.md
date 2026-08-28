# Tasks: Order Creation and Payment

**Input**: Design documents from `specs/005-booking-path/`

**Feature**: 005-booking-path | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `ImportError` or `AttributeError` satisfy the gate.

**Fixture discipline (Constitution Principle XI)**: Two Tier 1 cassettes exist for this feature, both transcribed from real captures in `.antabay/atlas-capability-map.md`: `order_pay_query_jkt_sub.yaml` (the JKT→SUB order→pay→query sequence, §7b) and `order_duplicate_318.yaml` (the observed 318 duplicate response, §9 — this one genuinely was captured, unlike 004's price-change/unavailable scenarios). The order-creation-timeout scenario (retrying after no response at all) is **not** capturable — you cannot record a response that never arrived — so it is exercised with `httpx.MockTransport` sequencing in a unit test, not a cassette. Do not fabricate a cassette for it.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema and fixture groundwork used by every story.

- [x] T001 [P] Added `orders`, `payments`, `ticketing_queries` tables to `backend/journey/storage/tables.py` per data-model.md
- [x] T002 Migration `backend/journey/migrations/versions/h8c974l30m57_add_booking_tables.py` created, `down_revision = 'g7b863k29l46'`
- [x] T003 [P] `order_pay_query_jkt_sub.yaml` created — three interactions (order.do/pay.do/queryOrderDetails.do) transcribing the verified JKT→SUB capture. **Path correction**: written to `backend/fixtures/atlas/cassettes/booking/`, not `backend/tests/fixtures/...` as this task originally said — the project's actual convention (set by 002's `search_sel_tyo.yaml` and `conftest.py`'s `vcr_cassette_dir` default of `"fixtures/atlas/cassettes"`) is a top-level `fixtures/` sibling to `tests/`, not nested under it. 004's cassette was already correctly placed there; this task's own wording was wrong and is corrected here.
- [x] T004 [P] `order_duplicate_318.yaml` created at the same corrected path — the 318 rejection (every field null except `status`/`duplicateOrders`, per the capability map's exact "Observed" note) plus a `queryOrderDetails.do` interaction showing the referenced order already ticketed, to exercise full reconciliation in T045

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 237 passed, 8 deselected. No regressions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model types, storage methods, state-machine extension, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 [P] `backend/journey/models/booking.py` created with `Order`, `PaymentAttempt`, `TicketingQuery`, `OrderOutcome`, `PaymentOutcome` per data-model.md
- [x] T006 `JourneyState.MONITORING` added; `_ALLOWED_TRANSITIONS` extended with `VERIFIED → MONITORING` and `MONITORING → {CANCELLED, ABANDONED}`
- [x] T007 `get_order_by_order_no()`, `get_latest_order()`, `save_order()`, `save_payment()`, `get_declined_payment()`, `save_ticketing_query()`, `get_ticketing_queries()` added to `backend/journey/storage/repository.py`
- [x] T008 `SessionExpiredError`, `DuplicateOrderAnomalyError`, `PaymentDeclinedError`, `OrderNotFoundError` added to `backend/journey/errors.py`
- [x] T009 `BookingService` skeleton created

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 237 passed. `from journey.services.booking_service import BookingService` succeeds.

---

## Phase 3: User Story 1 — Create Order From a Verified Session (Priority: P1) 🎯 MVP

**Goal**: An order is created from a verified session; the session identifier is forwarded unmodified; the passenger form matches the verified requirements exactly; the order/booking references and ticketing deadline are recorded; a booking reference is never treated as ticketing evidence; an already-expired session refuses the attempt before any call.

**Independent Test**: Call `BookingService.create_order()` for a held, unexpired session against `order_pay_query_jkt_sub.yaml` and confirm the request's `sessionId` matches the held value byte-for-byte, `outcome == CREATED`, `order_no`/`booking_reference`/ticketing-deadline are all recorded correctly, and a call against an already-expired session never reaches Atlas.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T010 [P] [US1] `TestCreateOrderContract` written against `order_pay_query_jkt_sub.yaml`
- [x] T011 [P] [US1] `TestCreateOrderIdentifierIntegrity` written using `httpx.MockTransport`
- [x] T012 [P] [US1] `TestCreateOrderPassengerForm` written
- [x] T013 [P] [US1] `TestCreateOrderNeverTreatsBookingReferenceAsTicketing` written
- [x] T014 [P] [US1] `TestSessionExpiredPrecondition` written
- [x] T015 [US1] Confirmed: all 5 failed with `NotImplementedError` before implementation

### Implementation for User Story 1

- [x] T016 [US1] Session-freshness precondition implemented in `create_order()`, checked before any HTTP call (FR-014)
- [x] T017 [US1] Request construction implemented in `_build_order_request()`
- [x] T018 [US1] Outcome classification implemented in `_attempt_order()`: `CREATED`/`DUPLICATE_REJECTED`/`UNCERTAIN`/`ERROR` — all four classified here since they share one response-parsing pass, though the reconciliation *behaviour* for the latter two is US4's
- [x] T019 [US1] Ticketing-deadline freshness window implemented in `_on_created()`
- [x] T020 [US1] `Order` persisted via `save_order()` on every path
- [x] T021 [US1] `python -m pytest backend/tests/contract/test_booking_contract.py backend/tests/unit/test_booking_service.py -v -k "CreateOrder or SessionExpired or contract"` — 6 passed

**Checkpoint**: US1 complete. An order can be created from a verified session with correct identifier integrity, passenger-form fidelity, reference recording, and session-expiry precondition handling.

---

## Phase 4: User Story 2 — Payment Only After Order Exists (Priority: P1)

**Goal**: Payment is submitted only for an order that was successfully created; a successful payment response is recorded without confirming ticketing; a declined payment is never retried against the same order.

**Independent Test**: Attempt `submit_payment()` with no created order and confirm it refuses with zero HTTP calls. Seed a `CREATED` order and submit payment against `order_pay_query_jkt_sub.yaml`'s `pay.do` interaction; confirm success is recorded without any `JourneyState` change. Feed a decline response and confirm a second `submit_payment()` call for the same order is refused.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T022 [P] [US2] `TestSubmitPaymentContract` written
- [x] T023 [P] [US2] `TestSubmitPaymentPrecondition` written
- [x] T024 [P] [US2] `TestSubmitPaymentSuccessDoesNotConfirmTicketing` written
- [x] T025 [P] [US2] `TestPaymentDeclineNoRetry` written, using a dict fixture with `status: 604` (borrowing the VCC decline code from the capability map's §6 simulation table purely as a plausible non-success value — not claiming that code applies to this balance-payment path, per research.md R4's own caveat)
- [x] T026 [US2] Confirmed: all 4 failed with `NotImplementedError` before implementation

### Implementation for User Story 2

- [x] T027 [US2] Order-exists precondition implemented in `submit_payment()` (FR-008)
- [x] T028 [US2] Decline-no-retry guard implemented, checked before any HTTP call (FR-013)
- [x] T029 [US2] `pay.do` call and outcome classification implemented
- [x] T030 [US2] `PaymentAttempt` persisted via `save_payment()` on every path
- [x] T031 [US2] `python -m pytest backend/tests/contract/test_booking_contract.py backend/tests/unit/test_booking_service.py -v -k "SubmitPayment or PaymentDecline"` — 4 passed

**Checkpoint**: US2 complete. Payment is correctly gated on order existence, never confirms ticketing by itself, and a decline is permanently terminal for that order.

---

## Phase 5: User Story 3 — Independent Ticketing Confirmation and Monitoring Handoff (Priority: P1)

**Goal**: Ticketing is confirmed only by an independent query showing non-empty ticket numbers for every passenger; the journey moves to `MONITORING` only then; the query loop stops on confirmation, deadline passage, or a terminal error.

**Independent Test**: Call `confirm_ticketing()` against a query response with empty ticket numbers and confirm no transition. Call it against a response with ticket numbers for some but not all passengers and confirm still no transition. Call it against a response with every passenger ticketed and confirm the journey moves to `MONITORING`. Call it with `now` past the ticketing deadline and confirm no query is even attempted.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T032 [P] [US3] `TestConfirmTicketingContract` written — asserts the cassette's "paid is not ticketed" moment produces `confirmed == False`
- [x] T033 [P] [US3] `TestConfirmTicketingPartialResult` written
- [x] T034 [P] [US3] `TestConfirmTicketingAllPassengers` written
- [x] T035 [P] [US3] `TestConfirmTicketingTerminalError` written
- [x] T036 [P] [US3] `TestConfirmTicketingDeadlinePassed` written
- [x] T037 [US3] Confirmed: all 5 failed with `NotImplementedError` before implementation

### Implementation for User Story 3

- [x] T038 [US3] Deadline pre-check implemented in `confirm_ticketing()`, via `_find_ticketing_deadline_identifier()`; returns the last `TicketingQuery` (or an empty unconfirmed one if none exists) without an HTTP call once past the deadline
- [x] T039 [US3] `queryOrderDetails.do` call and `TicketingQuery` construction implemented in `_query_order()`
- [x] T040 [US3] `confirmed` computed as: non-empty `passenger_ticket_numbers` AND every entry non-empty (research.md R5)
- [x] T041 [US3] `is_terminal_error` computed from a non-null `errorCode` (research.md R6)
- [x] T042 [US3] `VERIFIED → MONITORING` transition implemented in `_query_order()`, guarded on `confirmed`
- [x] T043 [US3] `TicketingQuery` persisted via `save_ticketing_query()` on every call that reaches Atlas
- [x] T044 [US3] `python -m pytest backend/tests/contract/test_booking_contract.py backend/tests/unit/test_booking_service.py -v -k "ConfirmTicketing"` — 6 passed

**Checkpoint**: US3 complete. Ticketing confirmation is never assumed from payment or a booking reference, requires every passenger ticketed, and the polling loop terminates correctly in all three ways.

---

## Phase 6: User Story 4 — Duplicate Order Reconciliation (Priority: P2)

**Goal**: A duplicate-order rejection — whether from a genuine repeat attempt or from retrying after an uncertain outcome — is reconciled by reading the referenced order, querying it, and resuming from its real state; more than one referenced order is treated as an anomaly, not resolved automatically.

**Independent Test**: Call `create_order()` against `order_duplicate_318.yaml` and confirm the resulting state reflects the referenced order's real, queried status rather than a reported failure or a second order-creation attempt. Simulate an uncertain first attempt followed by a duplicate-rejecting retry and confirm the same reconciliation occurs.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T045 [P] [US4] `TestDuplicateOrderContract` written against `order_duplicate_318.yaml`
- [x] T046 [P] [US4] `TestUncertainOrderRetryReconciliation` written, using `httpx.MockTransport` sequencing (connection error, then a duplicate rejection, then the reconciling query)
- [x] T047 [P] [US4] `TestMultipleDuplicateOrdersAnomaly` written
- [x] T048 [US4] Confirmed: all 3 failed with `NotImplementedError` before implementation

### Implementation for User Story 4

- [x] T049 [US4] `DUPLICATE_REJECTED` reconciliation implemented in `_attempt_order()`/`_resolve_duplicate()`: reads `duplicateOrders`, raises `DuplicateOrderAnomalyError` on more than one entry, otherwise queries the referenced order
- [x] T050 [US4] `UNCERTAIN`-outcome retry implemented via `_resolve_uncertain_order()`, called once from `_attempt_order()`'s `httpx.HTTPError` handler
- [x] T051 [US4] `python -m pytest backend/tests/contract/test_booking_contract.py backend/tests/unit/test_booking_service.py -v -k "Duplicate or UncertainOrderRetry"` — 3 passed

**Checkpoint**: US4 complete. Duplicate rejections — whatever their cause — always resolve to a real, queried state rather than a failure or a second order.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and audit trail confirmation across all four stories.

- [x] T052 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_005.html` — 260 passed (245 baseline including 004 + 19 new from this feature: 17 from T010–T047, 2 more from T054's gap-closing below), 4 pre-existing failures unrelated to this feature (`DASHSCOPE_API_KEY` not set). Report at `backend/reports/report_005.html`.
- [x] T053 [P] Walked through all four quickstart.md scenarios — each is directly exercised by an automated test: Scenario 1 → `TestCreateOrderContract`/`TestCreateOrderIdentifierIntegrity`/`TestSessionExpiredPrecondition`; Scenario 2 → `TestSubmitPaymentContract`/`TestSubmitPaymentPrecondition`/`TestPaymentDeclineNoRetry`; Scenario 3 → `TestConfirmTicketing*`; Scenario 4 → `TestDuplicateOrderContract`/`TestUncertainOrderRetryReconciliation`
- [x] T054 [P] NFR-002 gap found and closed: the `ERROR` outcome (unparseable response body) was not exercised for either `create_order()` or `submit_payment()`. Added `TestCreateOrderErrorOutcome` and `TestSubmitPaymentErrorOutcome` to `test_booking_service.py`, asserting `raw_response_json` persists the raw bytes verbatim. All four `Order`/`PaymentAttempt` outcome types are now confirmed; `TicketingQuery.raw_response_json` is non-empty on every call by construction (T039).
- [x] T055 `backend/journey/__init__.py` now exports `BookingService`, `Order`, `PaymentAttempt`, `TicketingQuery`, `OrderOutcome`, `PaymentOutcome`
- [x] T056 `mypy` run on all touched files. Three real errors introduced by this feature were found and fixed: (1) `_row_to_order`'s `row` parameter was typed `object` (not indexable) instead of `Any`; (2)/(3) two `str | None` values (`order.order_no` in `_resolve_duplicate`, and both `order.order_no`/the `float`-vs-`int` mismatch in `_on_created`) reached functions expecting narrower types — resolved with an assertion (order_no is always set by the point it's used) and an explicit `int()` conversion. Remaining errors (`scoring_service.py`, `repository.py`'s pre-existing untyped-`dict` warnings) predate this feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on Phase 2 and on an `Order` existing to submit payment against — its own tests seed a `CREATED` order directly via the repository rather than calling US1's `create_order()`, keeping it independently testable
- **US3 (Phase 5)**: Depends on Phase 2 and on an `Order` existing to confirm ticketing for — same seeding approach as US2
- **US4 (Phase 6)**: Depends on Phase 2 and on US1's outcome classification (T018) already producing `DUPLICATE_REJECTED`/`UNCERTAIN` — extends the same `create_order()` method US1 delivers

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4.
- **US2** and **US3** each operate on an `Order` row seeded directly in their own tests — they do not require US1's tests to pass first, even though in the real orchestrated flow an order comes from `create_order()`.
- **US4** is additive to the single `create_order()` method US1 delivers, the same shared-endpoint pattern used for 004's US2/US3/US4 and 006's US2.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic in `booking_service.py` / `repository.py` / `journey.py`
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003, T004 (Setup) can run in parallel; T002 depends on T001
- T005, T006, T008 (Foundational) can run in parallel; T007 depends on T005; T009 depends on T005 + T007
- Within US1: T010–T014 (tests) all parallel; T017 must land before T018–T020 (sequential, same file)
- Within US2: T022–T025 (tests) parallel
- Within US3: T032–T036 (tests) parallel
- Within US4: T045–T047 (tests) parallel
- US2, US3, and US4's test-writing can all happen in parallel with each other once US1's T017–T018 exist

---

## Parallel Example: Foundational Phase

```bash
# T005, T006, T008 touch different files — safe to parallelize:
T005: backend/journey/models/booking.py
T006: backend/journey/models/journey.py
T008: backend/journey/errors.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T009)
3. Complete Phase 3: US1 tests (T010–T015) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T016–T020)
5. Run T021 gate — all tests must pass
6. **STOP and VALIDATE**: An order can be created from a verified session with correct identifier integrity and reference recording

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → order creation working → the entry point to the booking path exists
3. US2 → payment gate working → money can move, correctly gated
4. US3 → ticketing confirmation working → the second named failure mode (false confirmation) is prevented
5. US4 → duplicate reconciliation working → the first named failure mode (duplicate orders) is prevented
6. Polish → full regression + quickstart walkthrough + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files with no incomplete dependency — safe to parallelize
- `order_pay_query_jkt_sub.yaml` and `order_duplicate_318.yaml` are both real, verified captures (§7b and §9 respectively) — unlike 004's price-change/unavailable scenarios, the duplicate case genuinely was observed live, so it gets a real cassette, not a dict fixture. Only the order-creation-timeout scenario (T046) uses `httpx.MockTransport`, because a true network timeout cannot be "recorded."
- `sessionId` and `orderNo` both flow through as opaque values — no task in this file should introduce string concatenation, slicing, or parsing of either
- `order.do`, `pay.do`, and `queryOrderDetails.do` are already `verified` in `backend/atlas/allowlist.py` — no allowlist change is part of this feature
- No call-budget interaction is implemented for any of this feature's three endpoints (research.md R7) — do not add a task that decrements `call_budget` for `order.do`/`pay.do`/`queryOrderDetails.do`
