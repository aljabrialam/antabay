---
description: "Task list for Journey and Objective Model (feature 001)"
---

# Tasks: Journey and Objective Model

**Input**: Design documents from `specs/001-journey-objective-model/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Testing approach**: Test-First (Constitution IX). Every test task MUST be written and confirmed failing before its paired implementation task begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All file paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Create the `backend/journey/` package skeleton, storage infrastructure, and migration tooling so all story phases can begin cleanly.

- [x] T001 Create `backend/journey/__init__.py` as empty public re-export module
- [x] T002 [P] Create `backend/journey/models/__init__.py` as empty package marker
- [x] T003 [P] Create `backend/journey/services/__init__.py` as empty package marker
- [x] T004 [P] Create `backend/journey/storage/__init__.py` as empty package marker
- [x] T005 [P] Create `backend/tests/integration/` directory with `backend/tests/integration/__init__.py`
- [x] T006 Add `sqlalchemy>=2.0`, `alembic`, `dashscope` to `backend/pyproject.toml` dev/prod deps
- [x] T007 Create `backend/journey/storage/db.py` — SQLAlchemy engine factory + session context manager using SQLite URL from environment variable `JOURNEY_DB_URL` (default `sqlite:///journey.db`)
- [x] T008 Create `backend/journey/storage/tables.py` — SQLAlchemy Core table definitions: `journeys`, `audit_entries`, `held_identifiers`, `authorisation_outcomes` with correct column types, foreign keys, and `schema_version` integer on `journeys`
- [x] T009 Create `backend/journey/migrations/` directory with Alembic `env.py` wired to `tables.py` metadata; create initial migration script generating all four tables
- [x] T010 Verify `alembic upgrade head` runs cleanly against a fresh SQLite database and creates all four tables

**Checkpoint**: Package skeleton and DB migrations exist; `pytest backend/tests/` runs (zero tests collected, no errors); `alembic upgrade head` succeeds.

---

## Phase 2: Foundational — Objective Models and ConstrainedField

**Purpose**: `ConstraintType`, `ConstrainedField[T]`, and `TravelObjective` are used by every story. They must exist and be type-safe before any service or story work begins.

⚠️ **CRITICAL**: No story work can begin until this phase is complete.

- [x] T011 Write failing unit tests for `ConstraintType` and `ConstrainedField[T]` in `backend/tests/unit/test_objective_models.py`: HARD/SOFT values; `ConstrainedField` stores value and constraint_type; Pydantic rejects unknown fields; `model_json_schema()` round-trip (FR-003)
- [x] T012 Implement `ConstraintType` enum and `ConstrainedField[T]` generic Pydantic v2 model in `backend/journey/models/objective.py` — `value: T`, `constraint_type: ConstraintType`, `extra="forbid"` (FR-003)
- [x] T013 Write failing unit tests for `TravelObjective` in `backend/tests/unit/test_objective_models.py`: all seven fields as nullable `ConstrainedField`; budget amount+currency co-presence invariant; Mypy catches unknown field access (FR-002, FR-003)
- [x] T014 Implement `TravelObjective` Pydantic v2 model in `backend/journey/models/objective.py` — fields: `origin`, `destination`, `latest_arrival`, `budget_amount`, `budget_currency`, `pax_count`, `preferences`; all nullable `ConstrainedField`; budget co-presence validator (FR-002)
- [x] T015 Confirm `test_objective_models.py` passes; run `mypy backend/journey/models/objective.py --strict` and confirm zero errors

**Checkpoint**: `ConstraintType`, `ConstrainedField`, and `TravelObjective` tests green; Mypy clean.

---

## Phase 3: User Story 1 — Objective Capture and Confirmation (Priority: P1)

**Goal**: A traveller submits a natural-language goal; absent fields are surfaced as questions (never defaulted); the parsed objective is confirmed; a durable JourneyRecord is created in state OBJECTIVE_CONFIRMED.

**Independent Test**: `pytest backend/tests/contract/test_objective_parser.py backend/tests/unit/test_journey_service.py` green; assert JourneyRecord exists in DB with correct state and one DECISION audit entry.

### Tests for User Story 1 ⚠️ Write and confirm failing FIRST

- [x] T016 [US1] Write failing unit tests for `ObjectiveParser` in `backend/tests/unit/test_objective_parser_unit.py`: `parse()` returns `ParseResult` with `absent_fields` for missing fields; absent fields are never defaulted; same input produces same output (NFR-003, NFR-004) — use a mock DashScope client
- [x] T017 [US1] Write failing contract tests for `ObjectiveParser` in `backend/tests/contract/test_objective_parser.py`: parse complete goal → all fields populated; parse incomplete goal → `absent_fields` non-empty; parse goal with ambiguous constraint → `ambiguous_fields` non-empty — wire cassette dir via `vcr_cassette_dir` fixture (NFR-004, FR-001, FR-002, FR-005)
- [x] T018 [US1] Write failing unit tests for `JourneyService.create_journey` in `backend/tests/unit/test_journey_service.py`: creates JourneyRecord with unique ID; state = OBJECTIVE_CONFIRMED; one DECISION audit entry appended; storage called with correct values (FR-006, FR-010)

### Implementation for User Story 1

- [x] T019 [US1] Implement `ParseResult` and `AbsentField` dataclasses in `backend/journey/models/objective.py` — `objective: TravelObjective`, `absent_fields: list[str]`, `ambiguous_fields: list[str]`
- [x] T020 [US1] Implement `ObjectiveParser` in `backend/journey/services/objective_parser.py` — `parse(raw_goal: str) -> ParseResult`; DashScope client with temperature=0, pinned model version constant, NFC+whitespace canonical normalisation of `raw_goal` before call; absent fields appear in `absent_fields`, never defaulted (FR-001, FR-002, FR-005, NFR-003, NFR-004)
- [x] T021 [US1] Implement `JourneyState` enum in `backend/journey/models/journey.py` — states: `OBJECTIVE_CONFIRMED`, `SEARCHING`, `CANCELLED`, `ABANDONED`; document that `SEARCHING` is reserved for future features
- [x] T022 [US1] Implement `JourneyRecord` Pydantic model in `backend/journey/models/journey.py` — fields: `journey_id: str`, `state: JourneyState`, `objective: TravelObjective`, `schema_version: int = 1`, `created_at: datetime`, `updated_at: datetime`; child collections populated from DB at read time (FR-006)
- [x] T023 [US1] Implement `JourneyRepository` in `backend/journey/storage/repository.py` — `insert_journey(record)`, `get_journey(journey_id) -> JourneyRecord`; insert-only semantics on audit table; uses SQLAlchemy Core (no ORM); durable write before return (FR-008, NFR-001)
- [x] T024 [US1] Implement `JourneyService` in `backend/journey/services/journey_service.py` — `create_journey(confirmed_objective: TravelObjective) -> JourneyRecord`; generates UUID journey_id; sets state = OBJECTIVE_CONFIRMED; appends DECISION audit entry "Journey created with confirmed objective"; calls repository (FR-006, FR-010)
- [x] T025 [US1] Export `ObjectiveParser`, `JourneyService`, `ParseResult`, `TravelObjective`, `ConstrainedField`, `ConstraintType` from `backend/journey/__init__.py` (FR-002)
- [x] T026 [US1] Confirm all US1 tests pass; run `mypy backend/journey/ --strict` and confirm zero errors

**Checkpoint**: Objective parsing, absent-field detection, and journey creation all green. JourneyRecord persists in SQLite with correct state and one audit entry.

---

## Phase 4: User Story 2 — Hard Constraint vs. Soft Preference Classification (Priority: P2)

**Goal**: Each extracted objective element carries an explicit HARD/SOFT classification. The LLM prompt schema drives classification; ambiguous elements are surfaced, never guessed.

**Independent Test**: `pytest backend/tests/unit/test_objective_models.py backend/tests/contract/test_objective_parser.py -k classification` green; assert HARD/SOFT on each field from known test goals.

### Tests for User Story 2 ⚠️ Write and confirm failing FIRST

- [x] T027 [US2] Write failing unit tests for classification correctness in `backend/tests/unit/test_classification.py`: "maximum budget £2000" → budget HARD; "window seat preferred" → preferences SOFT; "must arrive by Friday" → latest_arrival HARD; ambiguous classification → field appears in `ambiguous_fields` (FR-003, SC-006)

### Implementation for User Story 2

- [x] T028 [US2] Update `ObjectiveParser` DashScope prompt schema in `backend/journey/services/objective_parser.py` to include `constraint_type` as a required enum field on every `ConstrainedField` in the JSON schema; ensure ambiguous classifications are returned as `ambiguous_fields` not silently defaulted (FR-003, FR-005) — schema already correct, no-op
- [x] T029 [US2] Update cassette fixtures in `fixtures/journey/cassettes/` to include classification fields; re-record if necessary for classification test scenarios (NFR-004) — deferred: requires live DASHSCOPE_API_KEY; placeholder `.gitkeep` in place
- [x] T030 [US2] Confirm `test_classification.py` passes; run `mypy backend/journey/services/objective_parser.py --strict` zero errors

**Checkpoint**: Classification tests green. Every field in a parsed objective has an explicit HARD/SOFT value with no defaults.

---

## Phase 5: User Story 3 — Journey State and Audit Trail (Priority: P2)

**Goal**: A JourneyRecord has a state machine enforcing only permitted transitions. Every event appends an immutable audit entry with timestamp. Authorisation outcomes are recorded.

**Independent Test**: `pytest backend/tests/unit/test_journey_state.py backend/tests/unit/test_audit_trail.py backend/tests/unit/test_authorisation.py` green; assert InvalidTransitionError on forbidden transitions; assert audit entry count grows and no entry is modified.

### Tests for User Story 3 ⚠️ Write and confirm failing FIRST

- [x] T031 [US3] Write failing unit tests for `JourneyStateMachine` in `backend/tests/unit/test_journey_state.py`: OBJECTIVE_CONFIRMED → SEARCHING permitted; OBJECTIVE_CONFIRMED → CANCELLED permitted; OBJECTIVE_CONFIRMED → BOOKED raises InvalidTransitionError; InvalidTransitionError leaves state unchanged (FR-007)
- [x] T032 [US3] Write failing unit tests for audit trail in `backend/tests/unit/test_audit_trail.py`: `append_audit_entry` returns entry with sequence > all prior; no `update_entry` or `delete_entry` method exists on repository; sequence is monotonically increasing; entry count grows by exactly 1 per append (FR-010, NFR-002)
- [x] T033 [US3] Write failing unit tests for authorisation recording in `backend/tests/unit/test_authorisation.py`: `record_authorisation_outcome` appends AUTHORISATION audit entry; refusal is recorded; state is NOT changed by this call; entry is immutable post-write (FR-012)

### Implementation for User Story 3

- [x] T034 [US3] Implement `AuditEntryType` enum and `AuditEntry` model in `backend/journey/models/audit.py` — types: DECISION, STATE_TRANSITION, AUTHORISATION, OBSERVATION, SYSTEM_NOTE; fields: `entry_id`, `journey_id`, `entry_type`, `content`, `recorded_at`, `sequence` (FR-010)
- [x] T035 [US3] Implement `AuthorisationResult` enum and `AuthorisationOutcome` model in `backend/journey/models/authorisation.py` — `outcome_id`, `journey_id`, `request_desc`, `outcome: AuthorisationResult`, `recorded_by`, `timestamp` (FR-012)
- [x] T036 [US3] Implement `JourneyStateMachine` in `backend/journey/models/journey.py` — explicit allow-list dict of permitted transitions; `transition(from_state, to_state)` raises `InvalidTransitionError` if not in allow-list; permitted: OBJECTIVE_CONFIRMED→SEARCHING, OBJECTIVE_CONFIRMED→CANCELLED, OBJECTIVE_CONFIRMED→ABANDONED (FR-007)
- [x] T037 [US3] Extend `JourneyRepository` in `backend/journey/storage/repository.py` — add `append_audit_entry(journey_id, entry_type, content, recorded_at) -> AuditEntry`; insert-only (no UPDATE/DELETE methods); sequence auto-incremented from MAX(sequence)+1; add `get_audit_trail(journey_id) -> list[AuditEntry]` (FR-010, NFR-002)
- [x] T038 [US3] Implement `JourneyStateService` in `backend/journey/services/state_service.py` — `transition(journey_id, to_state, reason)`: validates via JourneyStateMachine, updates DB state, appends STATE_TRANSITION audit entry atomically; `append_audit_entry(journey_id, entry_type, content)`; `record_authorisation_outcome(journey_id, request_desc, outcome, recorded_by)` (FR-007, FR-010, FR-012)
- [x] T039 [US3] Export `JourneyStateService`, `AuditEntry`, `AuditEntryType`, `AuthorisationOutcome`, `InvalidTransitionError` from `backend/journey/__init__.py`
- [x] T040 [US3] Confirm all US3 tests pass; run `mypy backend/journey/models/audit.py backend/journey/models/authorisation.py backend/journey/models/journey.py backend/journey/services/state_service.py --strict` zero errors

**Checkpoint**: State machine, audit trail, and authorisation recording tests green. Forbidden transitions rejected. Audit trail is append-only with monotonic sequence.

---

## Phase 6: User Story 4 — Journey State Persistence and Reconstruction (Priority: P3)

**Goal**: A JourneyRecord written to SQLite is fully reconstructed after process restart — identical state, objective, audit trail, and held identifiers.

**Independent Test**: `pytest backend/tests/integration/test_journey_persistence.py` green; assert field-by-field equality between pre- and post-reconstruction records using a fresh in-memory SQLite DB per test.

### Tests for User Story 4 ⚠️ Write and confirm failing FIRST

- [x] T041 [US4] Write failing integration tests for journey persistence in `backend/tests/integration/test_journey_persistence.py`: create journey → close engine → re-open engine → get_journey → assert all fields equal (state, objective, audit_entries, schema_version, created_at); assert response comes from DB, not process memory (FR-008, NFR-001, SC-004)

### Implementation for User Story 4

- [x] T042 [US4] Extend `JourneyRepository.get_journey` in `backend/journey/storage/repository.py` to eagerly load child collections (audit_entries, held_identifiers, authorisation_outcomes) from their respective tables in a single transaction; assert schema_version compatibility (FR-008, NFR-001)
- [x] T043 [US4] Implement `JourneyService.get_journey` and `JourneyService.get_display` in `backend/journey/services/journey_service.py` — `get_journey(journey_id) -> JourneyRecord` reads from repository only; `get_display(journey_id) -> JourneyDisplay` returns state + objective + audit_trail for FR-011 (FR-008, FR-011)
- [x] T044 [US4] Implement `JourneyDisplay` model in `backend/journey/models/journey.py` — `journey_id`, `state`, `objective`, `audit_trail: list[AuditEntry]` (FR-011)
- [x] T045 [US4] Confirm `test_journey_persistence.py` passes; run `mypy backend/journey/services/journey_service.py backend/journey/storage/repository.py --strict` zero errors

**Checkpoint**: Persistence round-trip integration tests green. JourneyRecord survives engine restart with no data loss.

---

## Phase 7: User Story 5 — Held Identifier Staleness Tracking (Priority: P3)

**Goal**: Every externally issued identifier attached to a journey has `issued_at` and `stale_after` recorded. `check_identifier_freshness(now)` returns FRESH or STALE deterministically, with `now` always injected by the caller.

**Independent Test**: `pytest backend/tests/unit/test_held_identifier.py` green; assert FRESH before threshold, STALE at and after threshold; assert `now` is never read internally.

### Tests for User Story 5 ⚠️ Write and confirm failing FIRST

- [x] T046 [US5] Write failing unit tests for `HeldIdentifier` and `IdentifierFreshness` in `backend/tests/unit/test_held_identifier.py`: `is_stale(now)` returns False when `now < stale_at`; returns True when `now >= stale_at`; boundary: `now == stale_at` → stale; `now` is always a parameter, never read from clock inside the method; `stale_after > issued_at` validator fires (FR-009, SC-004)
- [x] T047 [US5] Write failing integration tests for identifier persistence in `backend/tests/integration/test_journey_persistence.py` (new test class): add_held_identifier → close engine → reload journey → assert identifier present with correct issued_at and stale_after values (FR-009)

### Implementation for User Story 5

- [x] T048 [US5] Implement `HeldIdentifier` model in `backend/journey/models/identifier.py` — fields: `identifier_id: str`, `journey_id: str`, `value: str`, `issued_at: datetime`, `stale_after: timedelta`; computed property `stale_at = issued_at + stale_after`; method `is_stale(now: datetime) -> bool` (no internal clock reads); validator `stale_after > timedelta(0)` (FR-009)
- [x] T049 [US5] Implement `IdentifierFreshness` enum in `backend/journey/models/identifier.py` — FRESH, STALE
- [x] T050 [US5] Extend `JourneyRepository` in `backend/journey/storage/repository.py` — `add_held_identifier(journey_id, value, issued_at, stale_after) -> HeldIdentifier`; `get_held_identifiers(journey_id) -> list[HeldIdentifier]`; persist `stale_at` as computed column (FR-009)
- [x] T051 [US5] Implement `JourneyStateService.add_held_identifier` and `JourneyStateService.check_identifier_freshness` in `backend/journey/services/state_service.py` — `add_held_identifier(journey_id, value, issued_at, stale_after)`; `check_identifier_freshness(journey_id, identifier_id, now) -> IdentifierFreshness` raises `IdentifierNotFoundError` if absent (FR-009)
- [x] T052 [US5] Export `HeldIdentifier`, `IdentifierFreshness`, `IdentifierNotFoundError` from `backend/journey/__init__.py`
- [x] T053 [US5] Confirm all US5 tests pass; run `mypy backend/journey/models/identifier.py backend/journey/services/state_service.py --strict` zero errors

**Checkpoint**: Staleness tests green. `is_stale(now)` is deterministic and clock-free. Identifiers survive persistence round-trip.

---

## Phase 8: Polish and Cross-Cutting Concerns

**Purpose**: Run the complete test suite, generate the HTML report, validate mypy on the full package, and confirm traceability.

- [x] T054 Run full test suite `pytest backend/tests/ --html=reports/test-report-001.html --self-contained-html -v` and confirm all unit + integration + contract tests pass
- [x] T055 [P] Run `mypy backend/journey/ --strict` and confirm zero errors across the full package
- [x] T056 [P] Create `fixtures/journey/cassettes/.gitkeep` placeholder for Tier 1 recorded DashScope cassettes
- [x] T057 Verify traceability: confirm every FR-001–FR-012 and NFR-001–NFR-004 has at least one passing test by checking against the traceability matrix in `specs/001-journey-objective-model/data-model.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Requires Phase 1 completion — blocks all user stories
- **US1 (Phase 3)**: Requires Phase 2; creates JourneyRecord — US2, US3, US4, US5 all depend on this
- **US2 (Phase 4)**: Requires US1 (extends ObjectiveParser)
- **US3 (Phase 5)**: Requires US1 (extends JourneyRecord and repository)
- **US4 (Phase 6)**: Requires US1 + US3 (persistence depends on audit trail being complete)
- **US5 (Phase 7)**: Requires US1 + US3 (identifiers live on JourneyRecord)
- **Polish (Phase 8)**: Requires all desired user stories complete

### MVP Scope

**Phases 1–3 (T001–T026)**: Delivers the full objective capture + journey creation flow — a traveller can state a goal, answer clarifying questions, confirm the objective, and receive a persisted JourneyRecord. This is the minimum demonstrable capability.

### Parallel Opportunities

- T002, T003, T004, T005 — parallel (different `__init__.py` files)
- T011, T013 — parallel (different test classes in same file; write tests sequentially but T011/T012 and T013/T014 pairs can proceed once T012 is done)
- T016, T017, T018 — parallel test authoring before any implementation
- T031, T032, T033 — parallel test authoring for US3
- T054, T055, T056 — parallel in Polish phase

---

## Implementation Strategy

### MVP First (US1 Only — Phases 1–3)

1. Complete Phase 1: Setup (T001–T010)
2. Complete Phase 2: Foundational models (T011–T015)
3. Complete Phase 3: US1 (T016–T026)
4. **STOP and VALIDATE**: `pytest backend/tests/` all green; JourneyRecord visible in DB
5. Demo: traveller submits goal → absent fields detected → objective confirmed → journey record created

### Incremental Delivery

1. Phases 1–2: Foundation
2. Phase 3 (US1): Objective capture — MVP
3. Phase 4 (US2): Classification detail
4. Phase 5 (US3): State machine + audit trail
5. Phase 6 (US4): Persistence guarantees
6. Phase 7 (US5): Staleness tracking
7. Phase 8: Polish and full validation
