# Data Model: Option Scoring Against Objective

**Feature**: 003-option-scoring
**Date**: 2026-08-28

---

## Entities

### ScoredOption

Wraps a `FlightOption` with the outcome of evaluating it against the confirmed
objective.

| Field              | Type                                         | Notes                                                |
|--------------------|----------------------------------------------|------------------------------------------------------|
| `option`           | `FlightOption`                               | The original option; never mutated                   |
| `outcome`          | `ScoringOutcome`                             | Enum: `SELECTED`, `ELIMINATED`, `RANKED`             |
| `rank`             | `int \| None`                                | 1-based rank among surviving options; `None` if eliminated |
| `rationale`        | `Rationale \| None`                          | Present only when `outcome == SELECTED`              |
| `elimination`      | `EliminationRecord \| None`                  | Present only when `outcome == ELIMINATED`            |
| `rejection_reason` | `RejectionReason \| None`                    | Present when ranked but not selected (high-rank rejected) |
| `connection_eval`  | `ConnectionEvaluation \| None`               | Present for multi-leg options                        |

**Validation rules**:
- Exactly one of `rationale` or `elimination` is populated; both cannot be set simultaneously.
- `rank` is `None` if and only if `outcome == ELIMINATED`.
- `rejection_reason` is populated only for options that survived hard-constraint elimination and ranked highly but were not selected.

---

### EliminationRecord

Records why a specific option was removed from contention.

| Field           | Type           | Notes                                                             |
|-----------------|----------------|-------------------------------------------------------------------|
| `option_id`     | `str`          | ID of the eliminated option                                       |
| `reason_code`   | `str`          | Machine-readable code (see Reason Codes below)                    |
| `reason_detail` | `str`          | Human-readable statement verifiable against the option data       |
| `constraint_id` | `str \| None`  | The objective field name that caused elimination (e.g. `"budget_amount"`) |

**Reason Codes**:

| Code                  | Trigger                                                            |
|-----------------------|--------------------------------------------------------------------|
| `budget_exceeded`     | `(adult_price + adult_tax) > budget_amount`                        |
| `arrival_too_late`    | Last-leg `arr_time` > `latest_arrival`                             |
| `wrong_departure_date`| First-leg `dep_time` date ≠ `departure_date`                       |
| `wrong_origin`        | First-leg `dep_airport` ≠ `origin`                                 |
| `wrong_destination`   | Last-leg `arr_airport` ≠ `destination`                             |
| `offer_expired`       | `is_expired(now) == True`                                          |
| `expiry_unknown`      | `expire_at is None`                                                |
| `currency_mismatch`   | Option currency ≠ `budget_currency.value`                          |
| `connection_excluded` | Option is multi-leg and `"direct_only"` is in preferences          |
| `min_connection_time` | Connection time < N minutes per `"min_connection_{N}"` preference  |
| `impossible_connection`| Connection time ≤ 0 between consecutive legs                      |

---

### Rationale

Human-readable explanation for the selected option.

| Field             | Type        | Notes                                                         |
|-------------------|-------------|---------------------------------------------------------------|
| `option_id`       | `str`       | ID of the selected option                                     |
| `objective_elements` | `list[str]` | Each objective element the option satisfies, named exactly as in the objective |
| `summary`         | `str`       | Single short paragraph; all claims traceable to option data   |
| `arrival_margin_minutes` | `int \| None` | Computed margin (latest_arrival − arr_time) in minutes; present when `latest_arrival` is in the objective |
| `total_cost`      | `Decimal \| None` | `adult_price + adult_tax`; present when cost is evaluated |

**Invariant**: `summary` MUST NOT contain any claim not derivable from the
`FlightOption` fields or the `TravelObjective` fields.

---

### RejectionReason

Explains why a high-ranking surviving option was not ultimately selected.

| Field           | Type    | Notes                                                         |
|-----------------|---------|---------------------------------------------------------------|
| `option_id`     | `str`   | ID of the rejected option                                     |
| `reason_code`   | `str`   | e.g. `"outranked_cost"`, `"outranked_arrival_margin"`, `"outranked_scarcity"` |
| `reason_detail` | `str`   | Human-readable statement referencing the specific dimension   |

---

### ConnectionEvaluation

Result of evaluating a multi-leg option's connection structure.

| Field                   | Type              | Notes                                              |
|-------------------------|-------------------|----------------------------------------------------|
| `option_id`             | `str`             | ID of the multi-leg option                         |
| `connection_times`      | `list[int]`       | Connection minutes between consecutive legs (index 0 = between leg 0 and leg 1) |
| `connection_excluded`   | `bool`            | True if any connection triggered an exclusion rule |
| `exclusion_rule`        | `str \| None`     | The preference string that caused exclusion (e.g. `"direct_only"`) |
| `impossible_connections`| `list[int]`       | Indices of connections with time ≤ 0              |

---

### ScoringRun

Complete output of one scoring invocation. Immutable after construction.

| Field                    | Type                   | Notes                                                      |
|--------------------------|------------------------|------------------------------------------------------------|
| `run_id`                 | `str`                  | UUID assigned at construction                              |
| `objective`              | `TravelObjective`      | The confirmed objective used for this run                  |
| `evaluated_at`           | `datetime`             | The `now` value passed into the scorer                     |
| `scored_options`         | `list[ScoredOption]`   | All options, in deterministic order (sorted by option_id)  |
| `selected_option`        | `ScoredOption \| None` | The top-ranked selected option; `None` if none survives    |
| `no_satisfying_option`   | `NoSatisfyingOptionReport \| None` | Present when all options are eliminated      |

---

### NoSatisfyingOptionReport

Produced when hard-constraint elimination leaves no surviving options.

| Field                  | Type        | Notes                                                     |
|------------------------|-------------|-----------------------------------------------------------|
| `unsatisfied_constraints` | `list[str]` | Names of objective fields whose constraints could not be simultaneously satisfied |
| `eliminated_count`     | `int`       | Total number of options eliminated                        |
| `summary`              | `str`       | Human-readable statement naming every unsatisfied constraint |

---

## Enumerations

### ScoringOutcome

```
SELECTED   — this option was chosen as the best
ELIMINATED — this option was removed by a hard constraint or exclusion rule
RANKED     — this option survived but was not selected (outranked or tied)
```

---

## Relationships

```
TravelObjective ──── (1:1) ──── ScoringRun
ScoringRun      ──── (1:N) ──── ScoredOption
ScoredOption    ──── (1:1) ──── FlightOption       (reference, not owned)
ScoredOption    ──── (0:1) ──── EliminationRecord
ScoredOption    ──── (0:1) ──── Rationale
ScoredOption    ──── (0:1) ──── RejectionReason
ScoredOption    ──── (0:1) ──── ConnectionEvaluation
ScoringRun      ──── (0:1) ──── NoSatisfyingOptionReport
```

---

## State Transitions

An option passes through the following evaluation stages in order:

```
1. Expiry check          → ELIMINATED (offer_expired / expiry_unknown)
2. Currency pre-check    → ELIMINATED (currency_mismatch)
3. Hard constraint check → ELIMINATED (budget_exceeded, arrival_too_late, etc.)
4. Connection exclusion  → ELIMINATED (connection_excluded / min_connection_time / impossible_connection)
5. Preference ranking    → ranked 1..N
6. Selection             → rank-1 option becomes SELECTED; remainder become RANKED
```

Options that are ELIMINATED at any stage do not proceed to later stages.
