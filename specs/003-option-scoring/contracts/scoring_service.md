# Contract: ScoringService

**Feature**: 003-option-scoring
**Date**: 2026-08-28

This document defines the Python interface contract for the `ScoringService`
that implements FR-001 through FR-013 from the feature specification.

---

## Module: `journey.services.scoring_service`

### Class: `ScoringService`

Stateless scoring engine. No constructor arguments. No database access.

---

### Method: `score`

```python
def score(
    self,
    objective: TravelObjective,
    options: list[FlightOption],
    now: datetime,
) -> ScoringRun:
    ...
```

**Parameters**:

| Parameter   | Type               | Description                                                       |
|-------------|--------------------|-------------------------------------------------------------------|
| `objective` | `TravelObjective`  | The confirmed travel objective. Must be fully validated.          |
| `options`   | `list[FlightOption]` | All options returned by the flight search for this objective.   |
| `now`       | `datetime`         | Reference time used for expiry checks. Must be timezone-aware.    |

**Returns**: `ScoringRun`

A complete, immutable record of the scoring run. Fields:

- `run_id` — UUID (str) assigned during construction.
- `objective` — the passed-in objective, unmodified.
- `evaluated_at` — equals `now`.
- `scored_options` — all options evaluated; sorted by `option_id` ascending
  (order-independent guarantee per NFR-001).
- `selected_option` — the `ScoredOption` with outcome `SELECTED`, or `None`.
- `no_satisfying_option` — a `NoSatisfyingOptionReport` when no option
  survives hard-constraint elimination, otherwise `None`.

**Guarantees**:

1. **Determinism**: Identical `objective` + any permutation of `options` + same
   `now` always produces an output where `selected_option`, rankings, and
   `rationale.summary` are identical (NFR-001).
2. **No I/O**: The method MUST NOT read from or write to any database,
   filesystem, or network resource.
3. **No mutation**: Input arguments are never modified.
4. **Total coverage**: Every element of `options` appears in
   `scored_options` with a non-`None` outcome (SC-001).
5. **Elimination traceability**: Every `ScoredOption` with outcome
   `ELIMINATED` has a non-`None` `elimination.reason_code` (SC-002).

**Raises**:

| Exception            | Condition                                                     |
|----------------------|---------------------------------------------------------------|
| `ValueError`         | `now` is not timezone-aware.                                  |
| `ValueError`         | Any `FlightOption` in `options` has an empty `legs` list.     |

**Empty input**: If `options` is empty, the method returns a `ScoringRun`
with `selected_option = None`, `no_satisfying_option = None`, and
`scored_options = []`. This is not an error.

---

## Module: `journey.models.scoring`

Defines all output types. All are dataclasses or Pydantic models; none has
mutable default state.

### Enum: `ScoringOutcome`

```python
class ScoringOutcome(str, Enum):
    SELECTED   = "SELECTED"
    ELIMINATED = "ELIMINATED"
    RANKED     = "RANKED"
```

### Dataclass: `EliminationRecord`

```python
@dataclass(frozen=True)
class EliminationRecord:
    option_id: str
    reason_code: str       # See data-model.md Reason Codes table
    reason_detail: str     # Human-readable, verifiable against option data
    constraint_id: str | None  # Objective field name, e.g. "budget_amount"
```

### Dataclass: `Rationale`

```python
@dataclass(frozen=True)
class Rationale:
    option_id: str
    objective_elements: list[str]       # Names of satisfied objective fields
    summary: str                        # Single short paragraph
    arrival_margin_minutes: int | None  # Computed when latest_arrival in objective
    total_cost: Decimal | None          # adult_price + adult_tax when evaluated
```

### Dataclass: `RejectionReason`

```python
@dataclass(frozen=True)
class RejectionReason:
    option_id: str
    reason_code: str    # e.g. "outranked_cost"
    reason_detail: str
```

### Dataclass: `ConnectionEvaluation`

```python
@dataclass(frozen=True)
class ConnectionEvaluation:
    option_id: str
    connection_times: list[int]         # Minutes between consecutive legs
    connection_excluded: bool
    exclusion_rule: str | None          # Preference string that caused exclusion
    impossible_connections: list[int]   # Indices of connections with time <= 0
```

### Dataclass: `NoSatisfyingOptionReport`

```python
@dataclass(frozen=True)
class NoSatisfyingOptionReport:
    unsatisfied_constraints: list[str]  # Objective field names
    eliminated_count: int
    summary: str
```

### Dataclass: `ScoredOption`

```python
@dataclass(frozen=True)
class ScoredOption:
    option: FlightOption
    outcome: ScoringOutcome
    rank: int | None                    # 1-based; None if ELIMINATED
    rationale: Rationale | None         # Present only when SELECTED
    elimination: EliminationRecord | None  # Present only when ELIMINATED
    rejection_reason: RejectionReason | None  # Present for high-rank RANKED
    connection_eval: ConnectionEvaluation | None  # Present for multi-leg
```

### Dataclass: `ScoringRun`

```python
@dataclass(frozen=True)
class ScoringRun:
    run_id: str
    objective: TravelObjective
    evaluated_at: datetime
    scored_options: list[ScoredOption]
    selected_option: ScoredOption | None
    no_satisfying_option: NoSatisfyingOptionReport | None
```

---

## Evaluation Pipeline Contract

The scorer MUST apply checks in this order for each option:

1. Expiry check (`is_expired(now)` or `expire_at is None`)
2. Currency pre-check (option currency vs `budget_currency`)
3. Hard constraint checks (iterating `TravelObjective` HARD fields)
4. Connection exclusion checks (from `preferences` list)
5. Preference ranking (iterating `preferences` list by index for surviving options)
6. Selection (rank-1 option becomes `SELECTED`; tie handling per spec)

An option eliminated at step N is not evaluated at steps N+1..6. Its
`EliminationRecord` records the first failing check only.

---

## Preference Dimension Contract

| Preference string       | Comparison direction | Evaluated field(s)                  |
|-------------------------|----------------------|-------------------------------------|
| `"cost"`                | Lower is better      | `adult_price + adult_tax`           |
| `"arrival_margin"`      | Higher is better     | `latest_arrival − last_leg.arr_time` in minutes |
| `"scarcity"`            | Higher seat count preferred; `risk_sellout == True` penalises | `seat_count`, `risk_sellout` |

Dimensions not listed above are ignored with no error.

The scorer iterates preferences in list order. If two options are equal on
dimension D, the scorer proceeds to dimension D+1. If equal on all dimensions,
the tie is reported in `NoSatisfyingOptionReport`-style detail within
`selected_option.rationale` and the `rank` of tied options is equal.

---

## Connection Time Calculation Contract

For a multi-leg option with legs `[L0, L1, ..., LN]`:

- Connection time at index `i` = `parse_dt(L[i+1].dep_time) − parse_dt(L[i].arr_time)` in whole minutes.
- `dep_time` and `arr_time` are `YYYYMMDDHHMM` strings (local time; no timezone adjustment applied during calculation).
- A result ≤ 0 → reason code `impossible_connection`; option is eliminated.
