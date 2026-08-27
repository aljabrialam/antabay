# Contract: Objective Parsing and Journey Creation

Feature: 001 — Journey and Objective Model  
Scope: `ObjectiveParser`, `JourneyService`  
Status: DRAFT

---

## Overview

This contract defines the observable behaviour of two service interfaces:

- **`ObjectiveParser`** — converts raw free-text traveller input into a structured, partially or fully populated `TravelObjective`.
- **`JourneyService`** — creates, retrieves, and prepares display of `JourneyRecord` entities.

No implementation detail is specified. A test author must be able to write contract tests from this document alone.

---

## Types

### `ConstrainedField[T]`

A field wrapper that carries both a parsed value and its source confidence. A field is either **present** (has a value) or **absent** (was not derivable from input).

| Attribute      | Type      | Description                                      |
|----------------|-----------|--------------------------------------------------|
| `value`        | `T`       | The parsed value. Present only when field exists.|
| `source`       | `str`     | Literal indicating derivation source, e.g. `"explicit"`, `"inferred"`. |
| `present`      | `bool`    | `True` if the field carries a value.             |

### `TravelObjective`

All fields are `ConstrainedField`-wrapped. Required fields are marked R; optional fields are marked O.

| Field name           | Inner type          | R/O | Description                                      |
|----------------------|---------------------|-----|--------------------------------------------------|
| `origin`             | `str`               | R   | Departure location.                              |
| `destination`        | `str`               | R   | Arrival location.                                |
| `departure_date`     | `date`              | R   | Intended departure date.                         |
| `return_date`        | `date \| None`      | O   | Return date; `None` for one-way journeys.        |
| `traveller_count`    | `int`               | R   | Number of travellers (≥ 1).                      |
| `cabin_class`        | `str`               | O   | e.g. `"economy"`, `"business"`.                  |
| `budget_cap`         | `Decimal \| None`   | O   | Maximum spend expressed in the stated currency.  |
| `budget_currency`    | `str \| None`       | O   | ISO 4217 currency code.                          |
| `flexibility_days`   | `int`               | O   | Acceptable date shift window in days.            |

A `TravelObjective` is **complete** when all R fields are present.  
A `TravelObjective` is **partial** when one or more R fields are absent.

### `AbsentField`

| Attribute      | Type   | Description                                      |
|----------------|--------|--------------------------------------------------|
| `field_name`   | `str`  | Name of the absent `TravelObjective` field.      |
| `reason`       | `str`  | Human-readable explanation, e.g. `"not mentioned in input"`. |

### `ParseResult`

| Attribute          | Type                    | Description                                      |
|--------------------|-------------------------|--------------------------------------------------|
| `objective`        | `TravelObjective`       | Partially or fully populated objective.          |
| `absent_fields`    | `list[AbsentField]`     | Fields that could not be populated; empty when the objective is complete. |
| `ambiguous_fields` | `list[str]`             | Field names where the input was contradictory or unclear; parser made no assumption. |

### `JourneyRecord`

| Attribute     | Type              | Description                                      |
|---------------|-------------------|--------------------------------------------------|
| `journey_id`  | `str`             | Globally unique, assigned on creation.           |
| `state`       | `JourneyState`    | Current state machine state.                     |
| `objective`   | `TravelObjective` | The confirmed objective attached to this journey.|
| `audit_trail` | `list[AuditEntry]`| Append-only ordered sequence of audit entries.   |
| `created_at`  | `datetime`        | UTC timestamp of record creation.                |

### `JourneyDisplay`

| Attribute     | Type              | Description                                      |
|---------------|-------------------|--------------------------------------------------|
| `journey_id`  | `str`             | Identifies the journey.                          |
| `state`       | `JourneyState`    | Current state.                                   |
| `objective`   | `TravelObjective` | Objective as confirmed by the traveller.         |
| `audit_trail` | `list[AuditEntry]`| Full ordered audit trail.                        |

---

## Interface: `ObjectiveParser`

### Method: `parse`

```
parse(raw_goal: str) -> ParseResult
```

#### Purpose

Convert a raw natural-language travel goal into a structured `TravelObjective`, explicitly enumerating any fields that could not be determined from the input.

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `raw_goal` is a non-empty string. |
| P2 | `raw_goal` length ≤ 4 096 characters. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns a `ParseResult`; never raises an exception for parseable input. |
| Q2 | Every field that appears in `absent_fields` is absent (`.present == False`) in the returned `objective`. |
| Q3 | Every field that appears in `ambiguous_fields` is absent in the returned `objective`. |
| Q4 | No field name appears in both `absent_fields` and `ambiguous_fields`. |
| Q5 | `absent_fields` is empty if and only if all R fields are present in `objective`. |
| Q6 | The parser does **not** infer absent fields. A field not derivable from `raw_goal` must appear in `absent_fields`, not carry a guessed value. |
| Q7 | **Reproducibility**: given identical `raw_goal` input, the method returns an identical `ParseResult`. Side-effect-free. |
| Q8 | Present field values are consistent with the literal content of `raw_goal`; no information is invented beyond normalisation (e.g. date format). |

#### Error Conditions

| Condition | Raised exception / behaviour |
|-----------|-------------------------------|
| `raw_goal` is empty or whitespace-only | `ValueError("raw_goal must be non-empty")` |
| `raw_goal` exceeds 4 096 characters | `ValueError("raw_goal exceeds maximum length")` |

#### Invariants

- The method has no side effects. It does not write to storage, emit events, or mutate state.
- Calling `parse` twice with the same `raw_goal` produces structurally equal `ParseResult` objects.

---

## Interface: `JourneyService`

### Method: `create_journey`

```
create_journey(confirmed_objective: TravelObjective) -> JourneyRecord
```

#### Purpose

Persist a new journey record from a traveller-confirmed, complete `TravelObjective`, placing it immediately in the `OBJECTIVE_CONFIRMED` state.

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `confirmed_objective` is a complete `TravelObjective` — all R fields are present (`ConstrainedField.present == True`). |
| P2 | Each present field value satisfies its domain constraint (e.g. `traveller_count ≥ 1`, `return_date ≥ departure_date` when both present, `budget_currency` is a valid ISO 4217 code when `budget_cap` is present). |
| P3 | The caller has confirmed the objective with the traveller; this is a deliberate act, not a speculative call. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns a `JourneyRecord` with a non-empty, globally unique `journey_id`. |
| Q2 | `JourneyRecord.state == JourneyState.OBJECTIVE_CONFIRMED`. |
| Q3 | `JourneyRecord.objective` is structurally equal to `confirmed_objective`. |
| Q4 | `JourneyRecord.audit_trail` contains exactly one `AuditEntry` of type `DECISION` with content `"Journey created with confirmed objective"`. |
| Q5 | The record is immediately visible to `get_journey(journey_id)` in the same or any subsequent call — durably persisted. |
| Q6 | `JourneyRecord.created_at` reflects the UTC time of creation. |

#### Error Conditions

| Condition | Raised exception / behaviour |
|-----------|-------------------------------|
| Any R field absent in `confirmed_objective` | `IncompleteObjectiveError` |
| Any field value violates its domain constraint | `ObjectiveValidationError` with a list of offending field names |
| Storage write fails | `StorageError`; no partial record is committed |

#### Side Effects

- Appends exactly one `DECISION` audit entry as described in Q4.
- Assigns and persists `journey_id`.
- No other side effects.

---

### Method: `get_journey`

```
get_journey(journey_id: str) -> JourneyRecord
```

#### Purpose

Retrieve a fully reconstructed `JourneyRecord` from durable storage by its identifier.

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` is a non-empty string. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns the `JourneyRecord` as it exists in durable storage at the moment of the call. |
| Q2 | The returned record is **not** sourced from process memory, cache, or any non-durable store. Each call reflects the authoritative persisted state. |
| Q3 | `JourneyRecord.audit_trail` is ordered chronologically, oldest entry first, and is complete — no entries are omitted. |
| Q4 | The returned `journey_id` matches the argument. |

#### Error Conditions

| Condition | Raised exception / behaviour |
|-----------|-------------------------------|
| No record exists for `journey_id` | `JourneyNotFoundError(journey_id)` |
| `journey_id` is empty or whitespace | `ValueError("journey_id must be non-empty")` |
| Storage read fails | `StorageError` |

#### Invariants

- This method is read-only; it has no side effects.

---

### Method: `get_display`

```
get_display(journey_id: str) -> JourneyDisplay
```

#### Purpose

Produce a display-oriented projection of the journey for presentation to the traveller or an agent (FR-011). Includes current state, the confirmed objective, and the full audit trail.

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` is a non-empty string. |
| P2 | A journey record for `journey_id` exists in durable storage. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns a `JourneyDisplay` whose `journey_id` matches the argument. |
| Q2 | `JourneyDisplay.state` equals `JourneyRecord.state` at the time of the call. |
| Q3 | `JourneyDisplay.objective` equals `JourneyRecord.objective` at the time of the call. |
| Q4 | `JourneyDisplay.audit_trail` is complete, ordered chronologically, and reflects the full `JourneyRecord.audit_trail` — no entries are filtered or reordered. |
| Q5 | `JourneyDisplay` contains no fields beyond those listed in the type definition (no internal identifiers, implementation details, or raw storage artefacts are leaked). |

#### Error Conditions

| Condition | Raised exception / behaviour |
|-----------|-------------------------------|
| No record exists for `journey_id` | `JourneyNotFoundError(journey_id)` |
| `journey_id` is empty or whitespace | `ValueError("journey_id must be non-empty")` |
| Storage read fails | `StorageError` |

#### Invariants

- This method is read-only; it has no side effects.
- `JourneyDisplay` is a value object produced at call time; it does not stay synchronised with subsequent mutations.

---

## Out of Scope

The following are explicitly outside this contract:

- Flight search, pricing, or availability.
- Booking or reservation creation.
- Payment processing or refunds.
- Error recovery workflows.
- Authentication or session management.
- Any mutation to `TravelObjective` after journey creation.
