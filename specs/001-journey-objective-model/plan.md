# Implementation Plan: Journey and Objective Model

**Branch**: `001-journey-objective-model` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-journey-objective-model/spec.md`

## Summary

Turn a traveller's natural-language travel goal into a confirmed, structured
TravelObjective with hard/soft constraint classifications, create a durable
JourneyRecord with an append-only audit trail, and enforce a defined state
machine — all persisted in SQLite via SQLAlchemy Core so the journey survives
process restarts.

## Technical Context

**Language/Version**: Python 3.11 (project standard per Constitution)

**Primary Dependencies**:
- `pydantic>=2.0` — typed models, schema generation for LLM function-calling
- `sqlalchemy>=2.0` (Core, not ORM) — explicit INSERT/SELECT; no UPDATE on audit table
- `alembic` — migrations from first table, schema_version column
- `dashscope` / `openai`-compatible client — Qwen via DashScope for NL parsing
- `httpx` — HTTP client (already in project venv)
- `pytest`, `pytest-recording`, `pytest-html` — testing stack (already wired)
- `mypy` — strict type checking (already configured)

**Storage**: SQLite for initial development; JourneyRepository interface is
connection-string-swappable to PostgreSQL. Alembic manages migrations for both.

**Testing**: pytest with HTML reports; mypy --strict; Tier 1 (recorded), no
live DashScope calls in unit/contract tests.

**Target Platform**: Linux server backend (same FastAPI process as feature 000)

**Project Type**: Backend service library under `backend/journey/`

**Performance Goals**: Objective parse + journey creation completes in under
2 minutes end-to-end from traveller input to confirmed record (SC-001). DB
operations complete in under 500ms locally.

**Constraints**: NFR-001 (no in-process journey state), NFR-003 (no inferred
travel facts), NFR-004 (reproducible parsing — temperature=0, pinned model
version, canonical input normalisation).

**Scale/Scope**: Single-traveller sessions; one active journey per session in
scope. Concurrent multi-session editing is out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Gate | Status |
|---|-----------|------|--------|
| I | Truth Over Fluency | No travel fact inferred — FR-005 + NFR-003 require absent fields to be asked, never defaulted | ✅ PASS |
| II | Verification After Action | No state-changing external calls in this feature scope | ✅ N/A |
| III | Separation of Reasoning and Authority | LLM parses objective only; no authority decisions | ✅ PASS |
| IV | Human Authorisation for High-Impact Actions | No spending or booking in scope | ✅ N/A |
| V | Honest Simulation | No simulation in objective capture | ✅ N/A |
| VI | State Outside the Agent | NFR-001 + FR-008: journey state in durable storage, not process memory | ✅ PASS |
| VII | Operational Discipline | No rate-limited external calls in objective capture; DashScope calls are mocked in unit tests | ✅ PASS |
| VIII | End-to-End Traceability | FR-001–FR-012 + NFR-001–NFR-004 all map to acceptance scenarios; traceability matrix in data-model.md | ✅ PASS |
| IX | Test-First Development | Tests written before implementation per tasks.md | ✅ PASS |
| X | Testing Pyramid | Unit (state machine, models, staleness) ~70%; integration (DB round-trip) ~20%; contract (ObjectiveParser) ~10% | ✅ PASS |
| XI | Two-Tier E2E Testing | Tier 1: recorded DashScope responses via pytest-recording; Tier 2: live DashScope on demand | ✅ PASS |
| XII | Assertions Against Observable External State | Audit trail and DB state asserted, not function return values alone | ✅ PASS |
| XIII | Deterministic Automation | No arbitrary sleeps; `now` injected as arg in all time comparisons (never `datetime.now()` inside module) | ✅ PASS |
| XIV | Auditability | FR-010 + FR-012: append-only audit trail with timestamps for every event | ✅ PASS |
| XV | AI-Assisted Development Under Human Review | All artefacts AI-generated, human verification before commit | ✅ PASS |
| XVI | Single Capability Principle | One task per commit, one demonstrable capability | ✅ PASS |

## Project Structure

### Documentation (this feature)

```text
specs/001-journey-objective-model/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── journey-objective.md   # ObjectiveParser + JourneyService contracts
│   └── journey-state.md       # JourneyStateService + audit trail contracts
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── journey/
│   ├── __init__.py              # public re-exports
│   ├── models/
│   │   ├── __init__.py
│   │   ├── objective.py         # ConstraintType, ConstrainedField, TravelObjective
│   │   ├── journey.py           # JourneyRecord, JourneyState, JourneyStateMachine
│   │   ├── audit.py             # AuditEntry, AuditEntryType
│   │   ├── identifier.py        # HeldIdentifier, IdentifierFreshness
│   │   └── authorisation.py    # AuthorisationOutcome, AuthorisationResult
│   ├── services/
│   │   ├── __init__.py
│   │   ├── objective_parser.py  # ObjectiveParser (DashScope integration)
│   │   ├── journey_service.py   # JourneyService (create, get, display)
│   │   └── state_service.py     # JourneyStateService (transitions, audit, identifiers)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── db.py                # SQLAlchemy engine, session factory
│   │   ├── repository.py        # JourneyRepository (insert-only audit table)
│   │   └── tables.py            # SQLAlchemy Core table definitions
│   └── migrations/
│       ├── env.py               # Alembic env
│       └── versions/            # migration scripts
├── tests/
│   ├── unit/
│   │   ├── test_objective_models.py    # ConstrainedField, TravelObjective
│   │   ├── test_journey_state.py       # JourneyStateMachine transitions
│   │   ├── test_audit_trail.py         # append-only invariants
│   │   ├── test_held_identifier.py     # staleness, is_stale(now)
│   │   └── test_authorisation.py       # AuthorisationOutcome recording
│   ├── integration/
│   │   ├── test_journey_persistence.py # DB round-trip, reconstruction
│   │   └── test_state_transitions_db.py # state + audit atomicity in DB
│   └── contract/
│       └── test_objective_parser.py    # ObjectiveParser against recorded cassettes
└── pyproject.toml               # already present; add journey deps
```

## Complexity Tracking

No Constitution violations requiring justification. All gates pass.
