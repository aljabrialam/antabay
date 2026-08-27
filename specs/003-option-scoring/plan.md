# Implementation Plan: Option Scoring Against Objective

**Branch**: `003-option-scoring` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-option-scoring/spec.md`

---

## Summary

Implement a deterministic, stateless scoring engine that eliminates flight
options violating hard constraints, ranks surviving options by stated
preferences, and returns a fully traced `ScoringRun` with a human-verifiable
rationale. No I/O occurs during scoring; all inputs are passed in and all
outputs are returned as value objects.

---

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: pydantic (already in project), pytest (tests), uuid (stdlib)

**Storage**: SQLite via SQLAlchemy (existing `journey` store); one new `scoring_runs` table for `ScoringRun` persistence

**Testing**: pytest (unit + integration); no Playwright for this feature

**Target Platform**: Linux server (same deployment as feature 002)

**Project Type**: Library/service within `backend/journey/` package

**Performance Goals**: No latency SLA; scoring is CPU-bound and synchronous

**Constraints**: NFR-001 (determinism + order-independence); NFR-003 (no travel facts outside journey record)

**Scale/Scope**: Single `ScoringRun` per invocation; option sets expected < 100 items

---

## Constitution Check

*GATE: Must pass before implementation. Re-checked post-design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Truth Over Fluency | Scoring MUST only consume `FlightOption` data from the journey record; no travel facts authored | ✅ — pure function reads only passed-in `FlightOption` objects |
| VIII. End-to-End Traceability | Every FR has acceptance criteria; every AC maps to a test | ✅ — quickstart.md maps 10 scenarios to FRs |
| IX. Test First Development | Tests written before implementation (TDD gate) | ✅ — tasks.md will sequence test tasks before implementation tasks |
| XIII. Deterministic Automation | Order-independent tests; no arbitrary sleeps | ✅ — NFR-001 explicitly requires order-independence; tests will verify |
| XIV. Auditability | Scoring decisions recorded in journey store | ✅ — `ScoringRun` persisted to `scoring_runs` table |
| XVI. Single Capability Principle | One feature, one scoring capability | ✅ |
| XVII. Built With Qoder | All files generated via Qoder CLI | ✅ |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-option-scoring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── scoring_service.md  # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code

```text
backend/journey/
├── models/
│   ├── objective.py         # existing — no changes
│   ├── flight.py            # existing — no changes
│   └── scoring.py           # NEW — ScoredOption, EliminationRecord, Rationale,
│                            #        RejectionReason, ConnectionEvaluation,
│                            #        ScoringRun, NoSatisfyingOptionReport,
│                            #        ScoringOutcome
├── services/
│   └── scoring_service.py   # NEW — ScoringService.score(objective, options, now)
└── storage/
    └── tables.py            # MODIFY — add scoring_runs table

backend/tests/
├── unit/
│   └── test_scoring_service.py      # NEW — unit tests (TDD)
└── integration/
    └── test_scoring_persistence.py  # NEW — persist + reload ScoringRun
```

---

## Implementation Strategy

### Phase 1: Models

Define all output dataclasses in `backend/journey/models/scoring.py`.
All dataclasses are `frozen=True` (immutable). No dependencies on storage.

Key types (see [contracts/scoring_service.md](contracts/scoring_service.md)):
- `ScoringOutcome` (enum)
- `EliminationRecord`, `Rationale`, `RejectionReason`, `ConnectionEvaluation`
- `ScoredOption`, `ScoringRun`, `NoSatisfyingOptionReport`

### Phase 2: Scoring Service

Implement `ScoringService.score()` in `backend/journey/services/scoring_service.py`
following the evaluation pipeline:

1. **Sort input options** by `option_id` (guarantees order-independence).
2. **Per-option evaluation** (in pipeline order from contracts doc):
   a. Expiry check
   b. Currency pre-check
   c. Hard constraint checks (iterate HARD fields of objective)
   d. Connection evaluation + exclusion checks
3. **Preference ranking** of surviving options (iterate `preferences` list).
4. **Selection**: rank-1 option → `SELECTED`; tie handling.
5. **Rationale construction** for selected option.
6. **Rejection reasons** for high-ranking non-selected options.
7. **Assemble** and return `ScoringRun`.

### Phase 3: Storage

Add `scoring_runs` table to `backend/journey/storage/tables.py`.

Columns:
- `run_id` TEXT PRIMARY KEY
- `journey_id` TEXT (FK to journeys)
- `evaluated_at` TEXT (ISO datetime)
- `objective_json` TEXT (serialised TravelObjective)
- `result_json` TEXT (full ScoringRun as JSON)
- `selected_option_id` TEXT NULLABLE
- `option_count` INTEGER
- `eliminated_count` INTEGER
- `created_at` TEXT

Add `save_scoring_run(run: ScoringRun, journey_id: str)` and
`get_scoring_run(run_id: str) -> ScoringRun` to `JourneyRepository`.

---

## Evaluation Pipeline Detail

See [contracts/scoring_service.md](contracts/scoring_service.md) for the full
pipeline contract, preference dimension definitions, and connection time
calculation rules.

See [data-model.md](data-model.md) for Reason Codes and entity field definitions.

---

## Hard Constraint Mapping

| `TravelObjective` field | Constraint type | Elimination condition                          | Reason code          |
|-------------------------|-----------------|------------------------------------------------|----------------------|
| `budget_amount`         | HARD            | `total_cost > budget_amount`                   | `budget_exceeded`    |
| `latest_arrival`        | HARD            | last-leg `arr_time` > `latest_arrival`         | `arrival_too_late`   |
| `departure_date`        | HARD            | first-leg `dep_time` date ≠ `departure_date`   | `wrong_departure_date` |
| `origin`                | HARD            | first-leg `dep_airport` ≠ `origin`             | `wrong_origin`       |
| `destination`           | HARD            | last-leg `arr_airport` ≠ `destination`         | `wrong_destination`  |

Fields where `constraint_type == SOFT` are never used for elimination.

---

## Datetime Parsing

`dep_time` and `arr_time` are `YYYYMMDDHHMM` strings (local time).

Parsing helper: `datetime.strptime(s, "%Y%m%d%H%M")` (naive datetime, no
timezone adjustment). Comparisons between option times and objective deadline
strings use the same naive parse.

---

## Tie-Breaking Rules

When two or more options are equal on all preference dimensions:
1. If `"scarcity"` is not in `preferences`, apply it as the final implicit
   tiebreaker (higher `seat_count`, no `risk_sellout` preferred).
2. If still tied after scarcity, report the tie in `rationale.summary`; do not
   break arbitrarily. Both tied options receive equal `rank`; neither is
   `SELECTED`; `no_satisfying_option` is `None` (the tie is not a no-options
   condition).

---

## Testing Approach

**Unit tests** (`test_scoring_service.py`):
- Written before implementation (TDD per Principle IX).
- One test class per user story + one class per edge case group.
- No database; no mocks for scoring logic (pure function).
- Verify determinism by running each test twice with permuted input order.

**Integration tests** (`test_scoring_persistence.py`):
- Persist a `ScoringRun` to SQLite in-memory DB and reload it.
- Verify all fields survive the round-trip.
- Separate transaction for save vs. load (two `Session` objects).

Test file paths match Decision 7 in `research.md`.
