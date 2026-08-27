# Quickstart: Option Scoring Against Objective

**Feature**: 003-option-scoring
**Date**: 2026-08-28

This guide describes how to validate that the scoring feature works end-to-end.
Run these scenarios after implementation to confirm each user story is satisfied.
See [data-model.md](../data-model.md) and [contracts/scoring_service.md](../contracts/scoring_service.md)
for entity and interface details.

---

## Prerequisites

```bash
cd backend
pip install -e ".[dev]"   # installs pytest and all runtime deps
```

The scoring service has no database dependency. All scenarios run in-memory.

---

## Scenario 1 — Hard Constraint Elimination (US1, P1)

**Validates**: FR-001, FR-002, FR-009, FR-011, SC-001, SC-002, SC-003

**Setup**: Construct a `TravelObjective` with `budget_amount = HARD 300 USD`
and a `latest_arrival = HARD "202609051400"`. Create three `FlightOption`
objects:

- Option A: cost = 280 USD, arrives 13:00 → survives
- Option B: cost = 350 USD, arrives 12:00 → eliminated (budget exceeded)
- Option C: cost = 200 USD, arrives 15:00 → eliminated (arrival too late)

**Run**:

```bash
pytest backend/tests/unit/test_scoring_service.py::TestHardConstraintElimination -v
```

**Expected outcomes**:
- `ScoringRun.selected_option` is Option A.
- Option B has `elimination.reason_code == "budget_exceeded"` and `elimination.constraint_id == "budget_amount"`.
- Option C has `elimination.reason_code == "arrival_too_late"` and `elimination.constraint_id == "latest_arrival"`.
- `len(scoring_run.scored_options) == 3` (no option silently skipped).

---

## Scenario 2 — All Options Eliminated (US1, P1)

**Validates**: FR-011, SC-006

**Setup**: Same objective as Scenario 1. All three options violate at least
one hard constraint.

**Expected outcomes**:
- `ScoringRun.selected_option is None`.
- `ScoringRun.no_satisfying_option` is not `None`.
- `no_satisfying_option.unsatisfied_constraints` names every constraint that
  could not be satisfied; none are omitted.

---

## Scenario 3 — Preference Ranking (US2, P2)

**Validates**: FR-003, FR-009, FR-010, SC-004

**Setup**: Three options all satisfying hard constraints. Preferences list:
`["cost", "arrival_margin"]`. Options ordered by cost: cheap, medium, expensive.

**Expected outcomes**:
- Selected option is the cheapest (cost preference is index 0).
- `ScoringRun.selected_option.rationale` names `"cost"` as a satisfied element.
- `ScoringRun.selected_option.rationale.total_cost` equals `adult_price + adult_tax`.

**Determinism check** — run the same call with options supplied in reversed
order:

```bash
pytest backend/tests/unit/test_scoring_service.py::TestPreferenceRankingDeterminism -v
```

Both runs must return an identical `selected_option.option.option_id` and
identical `rationale.summary`.

---

## Scenario 4 — Arrival Margin Tiebreaker (US2, P2)

**Validates**: FR-004, SC-004

**Setup**: Two options with identical cost. Preferences: `["cost", "arrival_margin"]`.
Option X arrives 30 minutes before deadline; Option Y arrives 90 minutes before
deadline.

**Expected outcomes**:
- Option Y is selected (larger arrival margin wins when cost is tied).
- `selected_option.rationale.arrival_margin_minutes` equals the margin for
  Option Y.

---

## Scenario 5 — Connection Exclusion (US3, P3)

**Validates**: FR-006, FR-007, SC-002

**Setup**: Objective preferences: `["direct_only"]`. Two options: one direct,
one multi-leg. Both satisfy all hard constraints.

**Expected outcomes**:
- Multi-leg option is eliminated with `reason_code == "connection_excluded"` and
  `constraint_id == None` (this is a preference exclusion, not a hard constraint
  field).
- Direct option is selected.

---

## Scenario 6 — Connection Time Calculation (US3, P3)

**Validates**: FR-006

**Setup**: Multi-leg option, no connection exclusion in objective. Leg 0 arrives
`"202609051200"`, Leg 1 departs `"202609051330"`. Expected connection time: 90 minutes.

**Expected outcomes**:
- `ScoredOption.connection_eval.connection_times == [90]`.
- `connection_eval.connection_excluded == False`.

---

## Scenario 7 — Impossible Connection (edge case)

**Validates**: edge case from spec (zero/negative connection time)

**Setup**: Multi-leg option where Leg 0 arrives `"202609051400"` and Leg 1
departs `"202609051330"` (departs before previous arrival).

**Expected outcomes**:
- Option is eliminated with `reason_code == "impossible_connection"`.
- `connection_eval.impossible_connections == [0]`.

---

## Scenario 8 — Expired Offer Eliminated (US1, P1)

**Validates**: FR-012

**Setup**: Two options. Option A: `expire_at` is 5 minutes in the past
relative to `now`. Option B: `expire_at` is 10 minutes in the future.

**Expected outcomes**:
- Option A eliminated with `reason_code == "offer_expired"`.
- Option B survives (assuming it also satisfies hard constraints).

---

## Scenario 9 — Currency Mismatch Flagged (US1, P1 edge case)

**Validates**: FR-013

**Setup**: Objective `budget_currency = USD`. One option in USD (survives),
one option in EUR (flagged).

**Expected outcomes**:
- EUR option has `elimination.reason_code == "currency_mismatch"`.
- USD option proceeds to hard constraint evaluation normally.

---

## Scenario 10 — Scarcity Signal Incorporated (US2, P2)

**Validates**: FR-008

**Setup**: Two options with identical cost. Preferences: `["cost", "scarcity"]`.
Option A: `seat_count = 2, risk_sellout = True`. Option B: `seat_count = 9, risk_sellout = False`.

**Expected outcomes**:
- Option B selected (higher seat count, no sellout risk).
- Rationale for Option B references `"scarcity"` as a satisfied element.

---

## Running the Full Unit Suite

```bash
pytest backend/tests/unit/test_scoring_service.py -v
```

All tests must pass. No external services are contacted.

---

## Running the Integration Suite

```bash
pytest backend/tests/integration/test_scoring_persistence.py -v
```

Verifies that a `ScoringRun` can be persisted to and reloaded from the
journey database with all fields intact.
