# Quickstart Validation Guide: Journey and Objective Model

**Feature**: `001-journey-objective-model`
**Branch**: `001-journey-objective-model`
**Spec**: `specs/001-journey-objective-model/spec.md`
**Data model**: `specs/001-journey-objective-model/data-model.md`

This guide proves the feature works end-to-end. Follow each scenario in order; later scenarios depend on the state created by earlier ones.

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | `python --version` |
| SQLite 3.x | Bundled with CPython; no separate install needed |
| `backend/.venv` created | See Setup |
| Alembic migrations applied | See Setup |
| DashScope API key **not** required for unit tests | Unit tests mock the LLM call; only integration tests that exercise the real parser need `DASHSCOPE_API_KEY` |

Dependency versions are declared in `backend/pyproject.toml` under `[project.dependencies]` and `[project.optional-dependencies] dev`.

---

## Setup

All commands run from the **`backend/`** directory unless stated otherwise.

### 1. Create and activate the virtual environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 2. Install all dependencies (including dev extras)

```bash
pip install -e ".[dev]"
```

### 3. Apply database migrations

```bash
alembic upgrade head
```

This creates the SQLite database (default: `backend/antabay.db`) and applies all migrations under `backend/alembic/versions/`, including the tables for `journeys`, `audit_entries`, `held_identifiers`, and `authorisation_outcomes`.

Verify the migration completed cleanly:

```bash
alembic current
# expected: <revision-hash> (head)
```

---

## Validation Scenarios

### Scenario 1: Parse a complete travel goal

**Purpose**: FR-002, FR-003 — the parser extracts all fields and classifies each as hard or soft.

**Input goal** (used as a fixture or inline string in the test):

```
"I need to get from London to Singapore by Friday evening,
 budget £2,000, two adults, window seats preferred"
```

**Expected `TravelObjective`**:

| Field | Value | `constraint_type` |
|-------|-------|-------------------|
| `origin` | `"London"` (or `"LHR"`) | hard |
| `destination` | `"Singapore"` (or `"SIN"`) | hard |
| `latest_arrival` | Friday 23:59 local (UTC-normalised) | hard |
| `budget_amount` | `2000` | hard |
| `budget_currency` | `"GBP"` | hard |
| `pax_count` | `2` | hard |
| `preferences[0]` | `"window seats"` | soft |

**Run**:

```bash
pytest tests/unit/journey/test_objective_parser.py -v
```

**Pass criteria**: All assertions green; no `ParseResult.absent_fields` entries; every field non-`None`.

---

### Scenario 2: Parse a goal with absent fields

**Purpose**: FR-005, NFR-003 — absent facts are surfaced, never defaulted.

**Input goal**:

```
"Fly me from Dubai to Tokyo next month, budget AED 5,000"
```

(`pax_count` is absent.)

**Expected outcome**:

- `ParseResult.absent_fields` contains `"pax_count"`.
- `TravelObjective.pax_count` is `None`.
- The parser does **not** set `pax_count` to `1` or any other default value.

**Run**:

```bash
pytest tests/unit/journey/test_objective_parser.py::test_absent_pax_count -v
```

**Pass criteria**: Assertion on `absent_fields` passes; `objective.pax_count is None`.

---

### Scenario 3: Confirm objective and create journey

**Prerequisites**: Scenario 1 passed (establishes that a complete `TravelObjective` can be produced).

**Purpose**: FR-006 — confirming a parsed objective creates a persisted `JourneyRecord` in the correct initial state with one audit entry.

**What the test does**:

1. Constructs a complete `TravelObjective` (may reuse the fixture from Scenario 1).
2. Calls `create_journey(objective)`.
3. Loads the returned `JourneyRecord` from the database by `journey_id`.

**Expected outcome**:

- `JourneyRecord.state == JourneyState.OBJECTIVE_CONFIRMED`.
- `JourneyRecord.journey_id` is a valid UUID4 string.
- `JourneyRecord.objective` matches the input `TravelObjective` field-for-field.
- `len(JourneyRecord.audit_entries) == 1`.
- `audit_entries[0].entry_type == AuditEntryType.DECISION`.
- `audit_entries[0].content` contains `{"from_state": null, "to_state": "objective_confirmed"}` (or equivalent creation marker).

**Run**:

```bash
pytest tests/integration/journey/test_create_journey.py -v
```

**Pass criteria**: All assertions green; one row in `journeys`; one row in `audit_entries`.

---

### Scenario 4: Reject an invalid state transition

**Purpose**: FR-007 — only documented transitions are permitted; all others are rejected.

**Setup**: Load (or create inline) a `JourneyRecord` in state `OBJECTIVE_CONFIRMED`.

**Action**: Attempt to call `JourneyStateMachine.transition(journey, JourneyState.BOOKED)` directly (bypassing any intermediate states that do not exist in this feature scope).

**Expected outcome**:

- `InvalidTransitionError` (or equivalent domain exception) is raised.
- The `JourneyRecord.state` remains `OBJECTIVE_CONFIRMED` after the failed attempt.
- No new row is inserted into `audit_entries`.

**Run**:

```bash
pytest tests/unit/journey/test_state_machine.py::test_invalid_transition -v
```

**Pass criteria**: `pytest.raises(InvalidTransitionError)` passes; state is unchanged.

---

### Scenario 5: Append-only audit trail

**Purpose**: FR-010, NFR-002 — audit entries cannot be modified or deleted after creation.

**Setup**: Create a `JourneyRecord` with at least one audit entry (reuse Scenario 3 output or create inline).

**Actions tested**:

1. Attempt to call any `update_entry()` or equivalent method on `AuditRepository` — assert no such public method exists (static check or `AttributeError`).
2. Attempt to delete an audit entry directly via the repository — assert no `delete_entry()` method exists.
3. As a belt-and-suspenders check: issue a raw `DELETE FROM audit_entries WHERE entry_id = ?` and assert the entry count is unchanged after re-loading (the application layer must not expose this path).

**Expected outcome**:

- Entry count in `audit_entries` for the journey is identical before and after each attempted mutation.
- No `AuditRepository` method modifies or removes an existing entry.

**Run**:

```bash
pytest tests/unit/journey/test_audit_trail.py -v
```

**Pass criteria**: All immutability assertions green.

---

### Scenario 6: Held identifier staleness

**Purpose**: FR-009 — identifiers with an elapsed `stale_after` timestamp are reported as stale.

**Setup**: Create a `HeldIdentifier` with `stale_after` set to a timestamp **in the past** (e.g., `datetime.now(UTC) - timedelta(hours=1)`).

**Action**: Call `check_identifier_freshness(identifier)`.

**Expected outcome**:

- Return value is `FreshnessStatus.STALE` (or equivalent enum member).
- No exception is raised; the system does not silently treat the identifier as valid.

Control case: create a second `HeldIdentifier` with `stale_after` in the future and assert `FreshnessStatus.FRESH`.

**Run**:

```bash
pytest tests/unit/journey/test_held_identifier.py -v
```

**Pass criteria**: Stale case returns `STALE`; fresh case returns `FRESH`.

---

### Scenario 7: Journey reconstruction after process restart

**Purpose**: FR-008, NFR-001 — the complete journey record survives a process boundary.

**What the test does**:

1. Creates a `JourneyRecord` with a confirmed objective, at least one audit entry, and one `HeldIdentifier`.
2. Captures all field values in local variables.
3. Disposes of all in-process references (simulates process restart by discarding the object).
4. Re-loads the `JourneyRecord` from the database using only `journey_id`.
5. Compares every field of the reloaded record against the captured values.

**Expected outcome**: All of the following are identical before and after reload:

- `journey_id`, `state`, `schema_version`, `created_at`, `updated_at`
- Every field of `objective` (including nested `ConstrainedField` values and `constraint_type`)
- Length and content of `audit_entries`
- Length and content of `held_identifiers`

**Run**:

```bash
pytest tests/integration/journey/test_journey_persistence.py -v
```

**Pass criteria**: All equality assertions pass with no field drift.

---

## Running the Full Suite

### All unit + integration tests with HTML report

```bash
pytest tests/unit/ tests/integration/ \
  --html=reports/test-report-001.html \
  --self-contained-html \
  -v
```

The report is written to `backend/reports/test-report-001.html`. Open it in a browser to review results.

To include contract tests:

```bash
pytest tests/unit/ tests/integration/ tests/contract/ \
  --html=reports/test-report-001.html \
  --self-contained-html \
  -v
```

### Mypy strict type check

```bash
mypy backend/journey/ --strict
```

`[tool.mypy]` in `pyproject.toml` sets `strict = true` and `python_version = "3.11"`. A clean run produces no errors or warnings.

---

## Expected Test Report

A fully passing run for this feature should show:

| Metric | Expected |
|--------|----------|
| Total collected | All tests across `unit/journey/`, `integration/journey/` |
| Passed | All |
| Failed | 0 |
| Errors | 0 |
| Warnings | Pytest deprecation warnings only (none from feature code) |
| Mypy exit code | `0` |

The HTML report groups results by module. Each scenario above maps to a distinct test file, so failures are easy to isolate by file name.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `alembic: command not found` | Dev dependencies not installed | `pip install -e ".[dev]"` |
| `alembic.exc.CommandError: Can't locate revision` | `alembic/versions/` is empty or migration not yet generated | Generate the initial migration: `alembic revision --autogenerate -m "initial journey schema"`, then `alembic upgrade head` |
| `sqlite3.OperationalError: no such table: journeys` | Migrations not applied | `alembic upgrade head` |
| `sqlite3.OperationalError: database is locked` | Another process holds the SQLite connection open | Close any open DB browser or running server process; SQLite allows only one writer at a time |
| `ModuleNotFoundError: No module named 'journey'` | Package not installed in editable mode | `pip install -e ".[dev]"` from `backend/` |
| `DashScope API error` in unit tests | Unit test is calling the real LLM instead of the mock | Ensure the test patches `journey.parser.dashscope_client` (or equivalent); unit tests must not make outbound HTTP calls |
| `DASHSCOPE_API_KEY not set` in integration tests | Environment variable missing for real-parser integration tests | `export DASHSCOPE_API_KEY=<your-key>` or add to `.env` and load with `python-dotenv` |
| `InvalidTransitionError` not raised in Scenario 4 | State machine allow-list is too permissive | Review `JourneyStateMachine.ALLOWED_TRANSITIONS` in `backend/journey/state_machine.py`; `OBJECTIVE_CONFIRMED → BOOKED` must not appear |
| Audit entry count changes after delete attempt in Scenario 5 | `AuditRepository` exposes a delete path | Remove or raise `NotImplementedError` on any delete method; the table must be insert-only at the application layer |
| `FreshnessStatus.STALE` not returned in Scenario 6 | `check_identifier_freshness` compares naively without timezone awareness | Ensure both `stale_after` and `datetime.now()` use `UTC`-aware `datetime` objects (`datetime.now(timezone.utc)`) |
| Reloaded journey fields differ in Scenario 7 | Serialisation/deserialisation round-trip issue | Check that `ConstrainedField[Decimal]` serialises `Decimal` as a string in JSON and deserialises back to `Decimal`, not `float` |
