# Research: Option Scoring Against Objective

**Feature**: 003-option-scoring
**Date**: 2026-08-28

---

## Decision 1: Scoring Architecture — Pure Function vs Service

**Decision**: Implement scoring as a pure, stateless function that accepts a
`TravelObjective` and a list of `FlightOption` objects and returns a
`ScoringRun` result. No database reads during scoring; all inputs are passed
in.

**Rationale**: NFR-001 mandates determinism and order-independence. A pure
function with no I/O or mutable state satisfies this trivially. It also makes
unit testing straightforward — no mocks needed for the core logic.

**Alternatives considered**:
- Service class reading options from the DB: rejected because it couples the
  scoring logic to storage and makes determinism harder to verify in tests.
- Async pipeline: rejected as over-engineering; scoring is CPU-bound and
  synchronous by nature.

---

## Decision 2: Preference Priority Ordering Representation

**Decision**: `TravelObjective.preferences` is a `ConstrainedField[list[str]]`
where the list is ordered by priority (index 0 = highest priority). Each
string names a preference dimension (e.g., `"cost"`, `"arrival_margin"`,
`"scarcity"`). The scoring engine iterates the list in order, applying each
dimension as a comparator, falling through to the next only on a tie.

**Rationale**: The existing `TravelObjective` model already has a `preferences`
field typed as `list[str]`. Using list order as priority order requires no
model changes, is directly testable, and aligns with the clarification from
`/speckit.clarify` (Session 2026-08-28).

**Alternatives considered**:
- `dict[str, int]` mapping preference name to weight: rejected because it
  introduces implicit numeric weighting that is harder to explain in plain
  language (NFR-002) and harder to make order-independent.
- Separate `PreferenceOrder` model: deferred; the existing list is sufficient
  for the current feature scope.

**Supported preference dimension names**:
- `"cost"` — total cost (adult_price + adult_tax); lower is better
- `"arrival_margin"` — margin between arr_time and latest_arrival; higher is
  better (more buffer)
- `"scarcity"` — seat_count signal; higher seat count preferred; risk_sellout
  flag penalises

---

## Decision 3: Hard Constraint Evaluation

**Decision**: Hard constraints are those `ConstrainedField` entries in
`TravelObjective` where `constraint_type == ConstraintType.HARD`. Each
hard-constraint field maps to an elimination check:

| Objective field      | Elimination condition                                          |
|----------------------|----------------------------------------------------------------|
| `budget_amount`      | `(adult_price + adult_tax) > budget_amount`                   |
| `latest_arrival`     | `arr_time` of last leg (parsed from `YYYYMMDDHHMM`) > `latest_arrival` |
| `departure_date`     | `dep_time` date portion ≠ `departure_date`                    |
| `origin`             | `dep_airport` of first leg ≠ `origin`                         |
| `destination`        | `arr_airport` of last leg ≠ `destination`                     |

Preferences (`ConstraintType.SOFT`) are never used as elimination criteria.

**Rationale**: Mirrors the existing `ConstraintType` enum already in the
codebase. No new model changes required.

---

## Decision 4: Connection Exclusion

**Decision**: Connection exclusion is represented as a preference entry with
the value `"direct_only"` in the preferences list. When `"direct_only"` is
present (at any priority position), any `FlightOption` where `is_multi_leg
== True` is eliminated regardless of cost/arrival. A minimum connection time
threshold (e.g., `"min_connection_60"`) can be added as a further exclusion
prefix pattern `"min_connection_{N}"` where N is minutes.

**Rationale**: Reuses the existing `preferences` list without requiring a new
field. The string-based encoding is human-readable and aligns with NFR-002
(rationale must be verifiable by a non-technical traveller). The connection
time check uses computed connection minutes between consecutive leg
`arr_time`/`dep_time` values.

---

## Decision 5: Expiry Handling

**Decision**: Use `FlightOption.is_expired(now)` (already implemented) for
expiry elimination. Options where `expire_at is None` are treated as
expiry-unknown and eliminated with reason `"expiry_unknown"`.

**Rationale**: The method already exists on `FlightOption`. Treating unknown
expiry as eliminated is the safe default per the spec edge case.

---

## Decision 6: Currency Safety

**Decision**: Before scoring, validate that all surviving options share the
currency from `TravelObjective.budget_currency.value`. Options in a different
currency are removed from cost evaluation and flagged with reason
`"currency_mismatch"`. If `budget_currency` is absent from the objective,
cost comparison is skipped for all options.

**Rationale**: FR-013 is a hard prohibition on cross-currency comparison.
Enforcing it as a pre-scoring check keeps the scoring function clean.

---

## Decision 7: File Structure

Scoring lives entirely in the existing `backend/journey/` package:

```
backend/journey/
├── models/
│   ├── scoring.py          # ScoredOption, EliminationRecord, Rationale,
│   │                       # RejectionReason, ConnectionEvaluation, ScoringRun
│   └── objective.py        # existing — no changes needed
├── services/
│   └── scoring_service.py  # ScoringService.score(objective, options, now)
└── storage/
    └── tables.py           # add scoring_runs table (ScoringRun persistence)
```

Tests:
```
backend/tests/
├── unit/
│   └── test_scoring_service.py
└── integration/
    └── test_scoring_persistence.py
```
