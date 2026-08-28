# Tasks: Flight Search

**Input**: Design documents from `specs/002-flight-search/`

**Prerequisites**: plan.md ✅, spec.md ✅, data-model.md ✅, research.md ✅, contracts/ ✅

**Tests**: TDD is MANDATORY per Constitution IX — test tasks must be written and confirmed FAILING before their implementation tasks begin.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish test infrastructure and fixture wiring before any feature code is written.

- [x] T001 Create VCR cassette directory `backend/fixtures/atlas/cassettes/flight_search/` and add placeholder `.gitkeep`
- [x] T002 [P] Copy `backend/fixtures/atlas/sel_tyo_search.json` as `backend/fixtures/atlas/cassettes/flight_search/search_sel_tyo.yaml` seed cassette (convert JSON fixture to VCR YAML format matching pytest-recording schema)
- [X] T003 [P] Create empty test files with module docstrings: `backend/tests/unit/test_flight_option.py`, `backend/tests/unit/test_flight_search_service.py`, `backend/tests/integration/test_flight_search_persistence.py`, `backend/tests/contract/test_flight_search_contract.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema and model changes that ALL user story phases depend on. No story work begins until this phase is complete.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [x] T004 Add `departure_date: ConstrainedField[str] | None = None` field to `TravelObjective` in `backend/journey/models/objective.py` (distinct from `latest_arrival`; represents Atlas `fromDate` `YYYYMMDD`)
- [x] T005 Add `departure_date` to the `_OBJECTIVE_FIELDS` list and `_build_tool_schema` in `backend/journey/services/objective_parser.py` so the ObjectiveParser extracts it from user input
- [x] T006 [P] Create Alembic migration `backend/journey/migrations/versions/XXXX_add_call_budget_to_journeys.py`: add `call_budget INTEGER NOT NULL DEFAULT 20` to `journeys` table
- [x] T007 [P] Create Alembic migration `backend/journey/migrations/versions/XXXX_create_search_records.py`: create `search_records` table per data-model.md schema
- [x] T008 [P] Create Alembic migration `backend/journey/migrations/versions/XXXX_create_flight_options.py`: create `flight_options` table per data-model.md schema
- [x] T009 [P] Create Alembic migration `backend/journey/migrations/versions/XXXX_create_legs.py`: create `legs` table per data-model.md schema
- [x] T010 Extend `backend/journey/storage/tables.py` with SQLAlchemy `Table` definitions for `search_records`, `flight_options`, and `legs` (matching the DDL in the migrations above)
- [x] T011 Run all existing tests to confirm foundational changes do not break Feature 001 (`pytest backend/tests/ -x`)

**Checkpoint**: All migrations applied, tables defined, `TravelObjective.departure_date` present, existing tests green.

---

## Phase 3: User Story 1 — Search for Flights from a Confirmed Objective (Priority: P1) 🎯 MVP

**Goal**: Submit a `search.do` request using objective parameters, record raw response + budget decrement atomically, map all routings to `FlightOption`/`Leg` records, return `SearchResult`.

**Independent Test**: `pytest backend/tests/ -k "flight_option or flight_search or flight_search_persistence or flight_search_contract" -x`

### Tests for User Story 1 ⚠️ WRITE FIRST — CONFIRM FAILING BEFORE IMPLEMENTATION

- [x] T012 [P] [US1] Write unit tests for `FlightOption` model in `backend/tests/unit/test_flight_option.py`:
  - `test_identifiers_preserved_verbatim` — `fid` and `routing_identifier` stored byte-for-byte (FR-003)
  - `test_freshness_timestamps_recorded` — `refreshed_at` and `expire_at` mapped from ISO8601 strings (FR-004)
  - `test_remaining_seconds_uses_now_not_receipt` — `remaining_seconds(now)` uses injected `now`, not internal clock (FR-005)
  - `test_remaining_seconds_raises_if_expire_at_none` — `remaining_seconds(now)` raises `ValueError` when `expire_at is None` (contract flight-option.md; F5)
  - `test_is_expired_uses_injected_now` — `is_expired(now)` returns `True` when `now >= expire_at`, `False` otherwise; never reads internal clock (contract flight-option.md; F6)
  - `test_multi_leg_detection` — `is_multi_leg` = `len(legs) > 1` (FR-007)
  - `test_scarcity_fields_recorded` — `seat_count` and `risk_sellout` per leg (FR-008)
  - `test_no_field_enrichment` — all values trace to raw response dict, no authored values (FR-011)
- [x] T013 [P] [US1] Write unit tests for `FlightSearchService` in `backend/tests/unit/test_flight_search_service.py`:
  - `test_search_params_from_objective` — request body contains correct `fromCity`, `toCity`, `fromDate`, `adultNum`, `currency` (FR-001)
  - `test_currency_from_objective` — `currency` taken from `budget_currency.value` (FR-002)
  - `test_atlas_status_nonzero_raises_error` — HTTP 200 with `response.status ≠ 0` raises `AtlasSearchError`; outcome recorded as `"ERROR"` in `SearchRecord` (spec edge case; F3)
  - `test_result_summary_fields` — `SearchResult.option_count` and `carriers` populated correctly (FR-006)
  - `test_budget_decremented` — `call_budget` decremented by 1 after successful search (FR-009)
  - `test_rate_limit_no_retry` — HTTP 429 raises `RateLimitError`; no retry before `retryAfter` (NFR-002)
  - `test_empty_result_no_exception` — zero routings returns `SearchResult` with `no_options=True`, no exception (FR-010)
- [x] T014 [P] [US1] Write integration test in `backend/tests/integration/test_flight_search_persistence.py`:
  - `test_raw_response_persisted` — raw JSON written to `search_records` before option mapping (NFR-001)
  - `test_transaction2_failure_does_not_rollback_transaction1` — simulate Transaction 2 mapping failure (e.g. malformed leg data); assert `SearchRecord` row and budget decrement from Transaction 1 remain committed in DB (NFR-001 isolation guarantee; F2)
  - `test_search_record_and_options_round_trip` — persist search result, reload from DB, assert all fields intact
  - `test_budget_before_after_recorded` — `SearchRecord.budget_before` and `budget_after` match decrement
  - `test_get_options_raises_if_search_record_not_found` — `get_options(unknown_search_id)` raises `SearchRecordNotFoundError` (contract flight-search.md; F4)
- [x] T015 [P] [US1] Write VCR contract test in `backend/tests/contract/test_flight_search_contract.py`:
  - `test_search_returns_options_from_cassette` — plays back `search_sel_tyo.yaml` cassette; asserts `option_count ≥ 1`, at least one `fid`, `carriers` non-empty
  - `test_cassette_options_have_legs` — all options from cassette have at least one `Leg` with `seat_count` and `risk_sellout`
- [x] T016 [US1] Confirm all T012–T015 tests FAIL (no production code yet). Document failure output. Do not proceed until failures confirmed.

### Implementation for User Story 1

- [X] T017 [US1] Create `backend/journey/models/flight.py` with:
  - `Leg` dataclass (all fields from data-model.md `Leg` entity)
  - `FlightOption` dataclass (all fields including `remaining_seconds(now)` method and `is_expired(now)` method)
  - `SearchResult` dataclass (`option_count`, `no_options`, `carriers`, `options`)
  - `SearchRecord` dataclass (audit record fields)
- [X] T018 [US1] Extend `backend/journey/storage/repository.py` with:
  - `save_search_record(record: SearchRecord) -> None`
  - `save_flight_options(options: list[FlightOption]) -> None` (saves legs in same call)
  - `decrement_call_budget(journey_id: str) -> tuple[int, int]` — returns `(budget_before, budget_after)`; raises `BudgetExhaustedError` if already 0
  - `get_search_record(search_id: str) -> SearchRecord | None`
  - `get_options(search_id: str) -> list[FlightOption]` — raises `SearchRecordNotFoundError` if `search_id` does not exist in `search_records` (contract flight-search.md; F4)
- [X] T019 [US1] Create `backend/journey/services/flight_search.py` with `FlightSearchService`:
  - `__init__(self, repo: JourneyRepository, http_client: httpx.Client)` — injected dependencies
  - `search(self, journey_id: str, now: datetime) -> SearchResult`
    - Loads journey; validates `call_budget > 0`, objective fields present
    - Builds Atlas `search.do` request from `TravelObjective` (uses `departure_date`, `origin`, `destination`, `pax_count`, `budget_currency`; defaults currency to `"USD"` if `budget_currency` is None)
    - Sends HTTP POST; records `requested_at` before send, `responded_at` on receipt
    - **Transaction 1**: persists `SearchRecord` (with raw response JSON) + decrements `call_budget` + appends audit entry
    - Parses routings; drops any missing `fid` or `routingIdentifier` (logged to audit trail)
    - **Transaction 2**: persists `FlightOption` and `Leg` rows (mapping failure does not roll back Transaction 1)
    - Returns `SearchResult`
  - `_enforce_rate_gate(self, now: datetime) -> None` — enforces 100ms minimum inter-call gap
  - Rate-limit fields: `_last_call_at: datetime | None`
- [X] T020 [US1] Define and raise `RateLimitError(retry_after_seconds: float)`, `BudgetExhaustedError`, `AtlasSearchError`, `SearchRecordNotFoundError` in `backend/journey/errors.py` (or existing errors module)
- [X] T021 [US1] Run T012–T015 tests; confirm all pass (`pytest backend/tests/ -k "flight_option or flight_search" -x`)

**Checkpoint**: US1 fully functional — a confirmed journey can be searched, all options recorded, budget decremented, SearchResult returned.

---

## Phase 4: User Story 2 — Handle Empty and No-Option Results (Priority: P2)

**Goal**: Zero-routing response is a valid `SearchResult`; no exception raised; budget still decremented; `no_options=True`.

**Independent Test**: `pytest backend/tests/ -k "empty" -v`

### Tests for User Story 2 ⚠️ WRITE FIRST — CONFIRM FAILING BEFORE IMPLEMENTATION

- [X] T022 [P] [US2] Extend `backend/tests/unit/test_flight_search_service.py`:
  - `test_empty_routings_returns_no_options_true` — `{ "routings": [], "status": 0 }` → `SearchResult.no_options = True`, `option_count = 0` (FR-010)
  - `test_empty_result_budget_still_decremented` — budget decremented even when `routings` is empty (FR-009 + spec US2 scenario 2)
  - `test_empty_result_search_record_outcome` — `SearchRecord.outcome == "EMPTY"` for zero-routing response
- [X] T023 [US2] Confirm T022 tests FAIL before implementation changes. Document failure output.

### Implementation for User Story 2

- [X] T024 [US2] Update `FlightSearchService.search` in `backend/journey/services/flight_search.py`:
  - When parsed routings list is empty, set `SearchRecord.outcome = "EMPTY"` and build `SearchResult` with `option_count=0`, `no_options=True`, empty `options` and `carriers`
  - Ensure `call_budget` is still decremented (Transaction 1 runs regardless of option count)
- [X] T025 [US2] Run T022 tests; confirm all pass

**Checkpoint**: US1 and US2 both pass independently.

---

## Phase 5: User Story 3 — Respect Rate Limits and Call Budget (Priority: P2)

**Goal**: HTTP 429 raises `RateLimitError` without retry; inter-call gap enforced at 100ms; `call_budget = 0` raises `BudgetExhaustedError` before HTTP call is made.

**Independent Test**: `pytest backend/tests/ -k "rate_limit or budget" -v`

### Tests for User Story 3 ⚠️ WRITE FIRST — CONFIRM FAILING BEFORE IMPLEMENTATION

- [X] T026 [P] [US3] Extend `backend/tests/unit/test_flight_search_service.py`:
  - `test_rate_limit_raises_error_with_retry_after` — HTTP 429 with `retryAfter: 5` → `RateLimitError(retry_after_seconds=5)` raised (NFR-002)
  - `test_rate_limit_no_internal_retry` — after 429, no second HTTP request is made (assert `httpx.Client.post` called exactly once)
  - `test_rate_limit_budget_decremented` — HTTP 429 response still decrements `call_budget` by exactly 1; budget_before and budget_after recorded in `SearchRecord` (FR-009 / spec US3 independent test)
  - `test_rate_limit_audit_trail_entry` — 429 outcome recorded in `SearchRecord` as `"RATE_LIMITED"`
  - `test_budget_zero_raises_before_http_call` — `call_budget = 0` → `BudgetExhaustedError` raised; `httpx.Client.post` never called (FR-009)
  - `test_rate_gate_enforces_100ms_gap` — if `_last_call_at` is less than 100ms ago, rate gate raises or waits (research Decision 4)
- [X] T027 [US3] Confirm all 6 T026 sub-tests FAIL before any implementation changes (`pytest backend/tests/unit/test_flight_search_service.py -k "rate_limit or budget" -v`). Every sub-test must show `FAILED` or `ERROR` — not `PASSED` or `no tests ran`. Document failure output. Do not proceed to T028 until all 6 failures are confirmed.

### Implementation for User Story 3

- [X] T028 [US3] Update `FlightSearchService` in `backend/journey/services/flight_search.py`:
  - `search()`: before HTTP call, call `_enforce_rate_gate(now)`; if `call_budget == 0` raise `BudgetExhaustedError` immediately (no HTTP call made)
  - HTTP 429 handler: decrement `call_budget` atomically (same as success path), read `retryAfter` from response body, set `SearchRecord.outcome = "RATE_LIMITED"` with `budget_before`/`budget_after`, raise `RateLimitError(retry_after_seconds=retryAfter)`; do NOT sleep or retry
  - `_enforce_rate_gate`: if `_last_call_at` is not None and `(now - _last_call_at).total_seconds() < 0.1`, raise `RateLimitError(retry_after_seconds=0.1 - elapsed)` to signal the caller
  - Update `_last_call_at = now` after a successful HTTP call (not on 429)
- [X] T029 [US3] Run all 6 T026 sub-tests and confirm all pass (`pytest backend/tests/unit/test_flight_search_service.py -k "rate_limit or budget" -v`). Every sub-test must show `PASSED` — not `FAILED` or `ERROR`.

**Checkpoint**: All three user stories pass independently. Full feature is functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Traceability confirmation, type checking, and cassette infrastructure.

- [X] T030 [P] Run full test suite and confirm all tests pass (`pytest backend/tests/ -v --tb=short`)
- [X] T031 [P] Run mypy on new modules (`mypy backend/journey/models/flight.py backend/journey/services/flight_search.py backend/journey/storage/repository.py`)
- [X] T032 [P] Verify traceability matrix from `data-model.md` — each FR/NFR test name must exist and pass:
  - `test_flight_option.py::test_identifiers_preserved_verbatim` (FR-003)
  - `test_flight_option.py::test_freshness_timestamps_recorded` (FR-004)
  - `test_flight_option.py::test_remaining_seconds_uses_now_not_receipt` (FR-005)
  - `test_flight_option.py::test_multi_leg_detection` (FR-007)
  - `test_flight_option.py::test_scarcity_fields_recorded` (FR-008)
  - `test_flight_option.py::test_no_field_enrichment` (FR-011)
  - `test_flight_search_service.py::test_search_params_from_objective` (FR-001)
  - `test_flight_search_service.py::test_currency_from_objective` (FR-002)
  - `test_flight_search_service.py::test_result_summary_fields` (FR-006)
  - `test_flight_search_service.py::test_budget_decremented` (FR-009)
  - `test_flight_search_service.py::test_rate_limit_no_retry` (NFR-002)
  - `test_flight_search_service.py::test_empty_result_no_exception` (FR-010)
  - `test_flight_search_persistence.py::test_raw_response_persisted` (NFR-001)
- [X] T033 Document Tier 2 cassette recording procedure in `specs/002-flight-search/quickstart.md` (add note: requires `ATLAS_CLIENT_ID` + `ATLAS_CLIENT_SECRET`; run `pytest --record-mode=new_episodes` to capture live cassettes)
- [X] T034 Run quickstart.md Tier 1 validation scenarios and confirm output matches expected (Scenario 1 and Scenario 2)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 completion — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 completion — US1 recommended first (overlapping service code)
- **US3 (Phase 5)**: Depends on Phase 2 completion — US1 recommended first (same service file)
- **Polish (Phase 6)**: Depends on all three user story phases complete

### Within Each User Story

1. Test tasks FIRST — write tests, confirm they FAIL
2. Model/entity before service
3. Service before repository extension (service defines what it needs from repo)
4. All tests must PASS before the story is marked complete
5. Commit after each story phase

### Parallel Opportunities

```bash
# Phase 1 — all three setup tasks in parallel:
Task: "Create cassette directory and .gitkeep"
Task: "Convert sel_tyo_search.json to VCR YAML seed cassette"
Task: "Create empty test files"

# Phase 2 — migrations in parallel (T006, T007, T008, T009):
Task: "Migration: add call_budget to journeys"
Task: "Migration: create search_records table"
Task: "Migration: create flight_options table"
Task: "Migration: create legs table"

# Phase 3 tests in parallel (T012, T013, T014, T015):
Task: "Unit tests for FlightOption model"
Task: "Unit tests for FlightSearchService"
Task: "Integration tests for persistence"
Task: "VCR contract tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run independent test command for US1
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. User Story 1 → Core search works end-to-end → **MVP**
3. User Story 2 → Empty results handled gracefully
4. User Story 3 → Rate limits and budget enforced
5. Polish → Full traceability confirmed

---

## Notes

- [P] tasks = different files, no shared state — safe to run in parallel
- [US1]/[US2]/[US3] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests MUST be written and FAIL before implementation — Constitution IX (Test-First Development)
- Commit after each phase or logical group
- Stop at any checkpoint to validate story independently
- `departure_date` on `TravelObjective` is a Feature 002 prerequisite (T004/T005) — do not skip
