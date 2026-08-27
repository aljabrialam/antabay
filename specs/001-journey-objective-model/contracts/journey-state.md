# Contract: Journey State Machine and Audit Trail

Feature: 001 — Journey and Objective Model  
Scope: `JourneyStateService` — state transitions, audit trail, authorisation outcomes, held identifiers  
Status: DRAFT

---

## Overview

This contract defines the observable behaviour of the `JourneyStateService` interface, which governs:

1. **State machine** — the permitted lifecycle states of a `JourneyRecord` and the transitions between them.
2. **Audit trail** — an append-only, immutable log of significant events.
3. **Authorisation outcome recording** — structured capture of authorisation decisions.
4. **Held identifiers** — time-bounded reference values (e.g. hold tokens, booking references) with freshness semantics.

No implementation detail is specified. A test author must be able to write contract tests from this document alone.

---

## Types

### `JourneyState` (enumeration)

| Value                    | Meaning                                                         |
|--------------------------|-----------------------------------------------------------------|
| `OBJECTIVE_CONFIRMED`    | Initial state. Traveller has confirmed the travel objective.    |
| `SEARCHING`              | A flight search is in progress. *(Entry point reserved; search is out of scope for this feature.)* |
| `OPTIONS_PRESENTED`      | Search results have been presented to the traveller.            |
| `SELECTION_CONFIRMED`    | Traveller has confirmed a selected option.                      |
| `AUTHORISATION_PENDING`  | An authorisation request has been submitted.                    |
| `AUTHORISATION_APPROVED` | Authorisation was granted.                                      |
| `AUTHORISATION_DECLINED` | Authorisation was refused.                                      |
| `BOOKING_IN_PROGRESS`    | A booking attempt is under way. *(Reserved; booking is out of scope.)* |
| `BOOKED`                 | Booking is confirmed.                                           |
| `CANCELLED`              | Journey has been cancelled.                                     |
| `ABANDONED`              | Journey was abandoned by the traveller without completion.      |

### Permitted State Transitions

A transition is **permitted** only if it appears in the table below. Any transition not listed is **forbidden**.

| From state                | To state                  | Triggering event                                                    |
|---------------------------|---------------------------|---------------------------------------------------------------------|
| `OBJECTIVE_CONFIRMED`     | `SEARCHING`               | A flight search is initiated for the confirmed objective.           |
| `OBJECTIVE_CONFIRMED`     | `CANCELLED`               | Traveller cancels before any search.                                |
| `OBJECTIVE_CONFIRMED`     | `ABANDONED`               | Journey is abandoned before any search.                             |
| `SEARCHING`               | `OPTIONS_PRESENTED`       | Search completes and results are presented.                         |
| `SEARCHING`               | `OBJECTIVE_CONFIRMED`     | Search returns no results; journey reverts for objective revision.  |
| `SEARCHING`               | `CANCELLED`               | Traveller cancels during search.                                    |
| `SEARCHING`               | `ABANDONED`               | Journey is abandoned during search.                                 |
| `OPTIONS_PRESENTED`       | `SELECTION_CONFIRMED`     | Traveller confirms a presented option.                              |
| `OPTIONS_PRESENTED`       | `SEARCHING`               | Traveller rejects all options and triggers a new search.            |
| `OPTIONS_PRESENTED`       | `CANCELLED`               | Traveller cancels after options are shown.                          |
| `OPTIONS_PRESENTED`       | `ABANDONED`               | Journey is abandoned after options are shown.                       |
| `SELECTION_CONFIRMED`     | `AUTHORISATION_PENDING`   | An authorisation request is submitted to the approver.              |
| `SELECTION_CONFIRMED`     | `OPTIONS_PRESENTED`       | Traveller wishes to revise the selected option.                     |
| `SELECTION_CONFIRMED`     | `CANCELLED`               | Traveller cancels after confirming a selection.                     |
| `SELECTION_CONFIRMED`     | `ABANDONED`               | Journey is abandoned after selection.                               |
| `AUTHORISATION_PENDING`   | `AUTHORISATION_APPROVED`  | Authorisation request is approved by the authoriser.                |
| `AUTHORISATION_PENDING`   | `AUTHORISATION_DECLINED`  | Authorisation request is refused by the authoriser.                 |
| `AUTHORISATION_PENDING`   | `CANCELLED`               | Journey is cancelled while awaiting authorisation.                  |
| `AUTHORISATION_APPROVED`  | `BOOKING_IN_PROGRESS`     | Booking process is initiated following approval.                    |
| `AUTHORISATION_APPROVED`  | `CANCELLED`               | Journey is cancelled after approval.                                |
| `AUTHORISATION_DECLINED`  | `SELECTION_CONFIRMED`     | Traveller selects an alternative option for re-submission.          |
| `AUTHORISATION_DECLINED`  | `CANCELLED`               | Journey is cancelled following declined authorisation.              |
| `AUTHORISATION_DECLINED`  | `ABANDONED`               | Journey is abandoned after declined authorisation.                  |
| `BOOKING_IN_PROGRESS`     | `BOOKED`                  | Booking completes successfully.                                     |
| `BOOKING_IN_PROGRESS`     | `AUTHORISATION_APPROVED`  | Booking attempt fails; journey reverts for a retry.                 |
| `BOOKING_IN_PROGRESS`     | `CANCELLED`               | Journey is cancelled during booking.                                |
| `BOOKED`                  | `CANCELLED`               | Confirmed booking is cancelled.                                     |

**Terminal states**: `BOOKED`, `CANCELLED`, `ABANDONED`. No transition out of a terminal state is permitted.

---

## Interface: `JourneyStateService`

### Method: `transition`

```
transition(journey_id: str, to_state: JourneyState, reason: str) -> JourneyRecord
```

#### Purpose

Advance the state machine of the identified journey from its current state to `to_state`, recording the reason in the audit trail.

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` identifies an existing journey in durable storage. |
| P2 | `to_state` is a valid `JourneyState` value. |
| P3 | `reason` is a non-empty string. |
| P4 | The transition `(current_state → to_state)` appears in the Permitted State Transitions table. |
| P5 | The current state of the journey is not a terminal state (`BOOKED`, `CANCELLED`, `ABANDONED`). |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | `JourneyRecord.state` equals `to_state` in durable storage after the call. |
| Q2 | An `AuditEntry` of type `STATE_TRANSITION` is appended to the audit trail with: the previous state, `to_state`, and `reason`. |
| Q3 | The returned `JourneyRecord` reflects the updated state and the new audit entry. |
| Q4 | The transition and the audit entry are committed atomically — storage never holds a state change without its corresponding audit entry, nor an audit entry without a state change. |
| Q5 | Pre-existing audit entries are unmodified. |

#### Rejection Conditions

The method rejects the call (raises an exception and performs no mutation) in any of the following cases:

| Condition | Raised exception |
|-----------|-----------------|
| No record for `journey_id` | `JourneyNotFoundError(journey_id)` |
| Transition not in permitted table | `InvalidTransitionError(from_state, to_state)` |
| Current state is a terminal state | `InvalidTransitionError(from_state, to_state)` |
| `reason` is empty or whitespace | `ValueError("reason must be non-empty")` |
| Storage write fails | `StorageError`; state and audit trail are unchanged |

---

### Method: `append_audit_entry`

```
append_audit_entry(journey_id: str, entry_type: AuditEntryType, content: str) -> AuditEntry
```

#### Purpose

Append an arbitrary audit entry to the journey's audit trail. Used for events that do not involve a state transition (e.g. system notes, informational records, manual annotations).

#### Types

##### `AuditEntryType` (enumeration)

| Value          | Intended use                                   |
|----------------|------------------------------------------------|
| `DECISION`     | A deliberate decision was made.                |
| `STATE_TRANSITION` | A state change occurred (appended by `transition`; callers should not use this type directly). |
| `AUTHORISATION`| An authorisation outcome was recorded.         |
| `SYSTEM_NOTE`  | An automated system event.                     |
| `MANUAL_NOTE`  | A human-authored annotation.                   |

##### `AuditEntry`

| Attribute      | Type              | Description                                      |
|----------------|-------------------|--------------------------------------------------|
| `entry_id`     | `str`             | Unique identifier for this entry.                |
| `entry_type`   | `AuditEntryType`  | Classification of the entry.                     |
| `content`      | `str`             | Human-readable description of the event.         |
| `recorded_at`  | `datetime`        | UTC timestamp of the moment the entry was appended. |
| `sequence`     | `int`             | Monotonically increasing integer, unique within the journey, reflecting append order. |

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` identifies an existing journey. |
| P2 | `entry_type` is a valid `AuditEntryType` value. |
| P3 | `content` is a non-empty string. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | The new `AuditEntry` appears at the end of `JourneyRecord.audit_trail` in durable storage. |
| Q2 | The new entry's `sequence` value is greater than every existing entry's `sequence` for the same journey. |
| Q3 | `recorded_at` is a UTC timestamp reflecting the time of the call. |
| Q4 | All pre-existing entries are unmodified — their `entry_id`, `entry_type`, `content`, `recorded_at`, and `sequence` values are unchanged. |
| Q5 | The returned `AuditEntry` matches the persisted entry exactly. |

#### Immutability Guarantee

The audit trail is **append-only and immutable**:

- No existing entry may be deleted.
- No existing entry's fields may be updated after it is written.
- The ordering of existing entries (by `sequence`) is permanent.
- These guarantees hold regardless of subsequent state transitions, authorisation decisions, or any other operation.

#### Error Conditions

| Condition | Raised exception |
|-----------|-----------------|
| No record for `journey_id` | `JourneyNotFoundError(journey_id)` |
| `content` is empty or whitespace | `ValueError("content must be non-empty")` |
| `entry_type` is `STATE_TRANSITION` and the caller is not `transition` | `AuditEntryTypeRestrictionError` |
| Storage write fails | `StorageError`; no entry is appended |

---

### Method: `record_authorisation_outcome`

```
record_authorisation_outcome(
    journey_id: str,
    request_desc: str,
    outcome: AuthorisationOutcome,
    recorded_by: str
) -> AuditEntry
```

#### Purpose

Record the outcome of an authorisation request as a structured, immutable audit entry. This does **not** trigger a state transition; state must be advanced separately via `transition`.

#### Types

##### `AuthorisationOutcome` (enumeration)

| Value       | Meaning                                       |
|-------------|-----------------------------------------------|
| `APPROVED`  | The authorisation request was granted.        |
| `DECLINED`  | The authorisation request was refused.        |
| `DEFERRED`  | A decision was postponed; outcome is pending. |

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` identifies an existing journey. |
| P2 | `request_desc` is a non-empty string describing what was authorised. |
| P3 | `outcome` is a valid `AuthorisationOutcome` value. |
| P4 | `recorded_by` is a non-empty string identifying the authoriser or the system recording the outcome. |
| P5 | The journey's current state is `AUTHORISATION_PENDING` or, for deferred outcomes, any non-terminal state. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | An `AuditEntry` of type `AUTHORISATION` is appended to the audit trail. |
| Q2 | The entry's `content` encodes: `request_desc`, `outcome`, and `recorded_by` in a deterministic, human-readable format. |
| Q3 | The entry is durable and immutable from the moment of write. |
| Q4 | The journey's `state` is **not** changed by this call. |
| Q5 | The returned `AuditEntry` matches the persisted entry exactly. |

#### Error Conditions

| Condition | Raised exception |
|-----------|-----------------|
| No record for `journey_id` | `JourneyNotFoundError(journey_id)` |
| `request_desc` is empty or whitespace | `ValueError("request_desc must be non-empty")` |
| `recorded_by` is empty or whitespace | `ValueError("recorded_by must be non-empty")` |
| Journey is in a terminal state | `JourneyTerminalError(journey_id, current_state)` |
| Storage write fails | `StorageError`; no entry is appended |

---

### Method: `add_held_identifier`

```
add_held_identifier(
    journey_id: str,
    value: str,
    issued_at: datetime,
    stale_after: timedelta
) -> HeldIdentifier
```

#### Purpose

Attach a time-bounded held identifier (e.g. a flight hold token, a session reference, or a supplier booking code) to the journey. The identifier carries an explicit staleness window.

#### Types

##### `HeldIdentifier`

| Attribute       | Type        | Description                                              |
|-----------------|-------------|----------------------------------------------------------|
| `identifier_id` | `str`       | Unique identifier assigned to this held entry.           |
| `journey_id`    | `str`       | The journey this identifier belongs to.                  |
| `value`         | `str`       | The identifier value (e.g. a token or reference code).   |
| `issued_at`     | `datetime`  | UTC timestamp when the identifier was issued externally. |
| `stale_after`   | `timedelta` | Duration after `issued_at` at which the identifier becomes stale. |
| `stale_at`      | `datetime`  | Derived: `issued_at + stale_after`. Computed on write and stored. |

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` identifies an existing journey. |
| P2 | `value` is a non-empty string. |
| P3 | `issued_at` is a timezone-aware UTC datetime. |
| P4 | `stale_after` is a positive `timedelta` (> 0 seconds). |
| P5 | The journey is not in a terminal state. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns a `HeldIdentifier` with a unique `identifier_id`. |
| Q2 | `stale_at` stored equals `issued_at + stale_after`. |
| Q3 | The identifier is immediately retrievable via `check_identifier_freshness`. |
| Q4 | Multiple held identifiers may coexist on a single journey; adding a new one does not remove or modify existing ones. |
| Q5 | The identifier is persisted durably; it survives process restarts. |

#### Error Conditions

| Condition | Raised exception |
|-----------|-----------------|
| No record for `journey_id` | `JourneyNotFoundError(journey_id)` |
| `value` is empty or whitespace | `ValueError("value must be non-empty")` |
| `issued_at` is not timezone-aware | `ValueError("issued_at must be a timezone-aware datetime")` |
| `stale_after` is zero or negative | `ValueError("stale_after must be a positive timedelta")` |
| Journey is in a terminal state | `JourneyTerminalError(journey_id, current_state)` |
| Storage write fails | `StorageError`; no identifier is added |

---

### Method: `check_identifier_freshness`

```
check_identifier_freshness(
    journey_id: str,
    identifier_id: str,
    now: datetime
) -> IdentifierFreshness
```

#### Purpose

Determine whether a held identifier is still within its valid freshness window at a given point in time.

#### Types

##### `IdentifierFreshness` (enumeration)

| Value   | Meaning                                                            |
|---------|--------------------------------------------------------------------|
| `FRESH` | `now < stale_at` — the identifier is within its validity window.  |
| `STALE` | `now >= stale_at` — the identifier has expired.                   |

#### Preconditions

| # | Condition |
|---|-----------|
| P1 | `journey_id` identifies an existing journey. |
| P2 | `identifier_id` identifies a held identifier belonging to `journey_id`. |
| P3 | `now` is a timezone-aware UTC datetime. |

#### Postconditions

| # | Guarantee |
|---|-----------|
| Q1 | Returns `FRESH` if and only if `now < HeldIdentifier.stale_at`. |
| Q2 | Returns `STALE` if and only if `now >= HeldIdentifier.stale_at`. |
| Q3 | The boundary condition is exact: `now == stale_at` returns `STALE`. |
| Q4 | The method is **pure** with respect to the `now` argument — it does not read system time. The caller is responsible for providing `now`. |
| Q5 | This method has no side effects; it does not modify the identifier or the journey. |

#### Error Conditions

| Condition | Raised exception |
|-----------|-----------------|
| No record for `journey_id` | `JourneyNotFoundError(journey_id)` |
| No identifier for `identifier_id` on this journey | `IdentifierNotFoundError(identifier_id)` |
| `now` is not timezone-aware | `ValueError("now must be a timezone-aware datetime")` |

---

## Cross-Cutting Invariants

### Atomicity

All methods that mutate state and append an audit entry do so atomically. The storage layer never reflects a state change without the corresponding audit entry, nor an audit entry without the state change that triggered it.

### Audit Trail Immutability

Once written, an `AuditEntry` is permanent:

- Its `entry_id`, `entry_type`, `content`, `recorded_at`, and `sequence` never change.
- It is never deleted.
- Its position in the trail (by `sequence`) is never altered.

This invariant holds for all entry types, including entries appended by `transition`, `append_audit_entry`, and `record_authorisation_outcome`.

### Durable Storage

All mutations are written to durable storage before the method returns. Methods that read (`get_journey`, `check_identifier_freshness`) always read from durable storage; process-memory caches that can return stale state are prohibited.

### Terminal State Finality

Once a journey reaches `BOOKED`, `CANCELLED`, or `ABANDONED`, no further state transitions are possible. Methods that would mutate the journey (add identifiers, transition state) raise `JourneyTerminalError`. The `append_audit_entry` method may still be called on a terminal journey to add post-close notes, provided the caller uses a permitted entry type.

### `now` Injection

Any method involving time comparison (`check_identifier_freshness`) accepts `now` as an explicit argument. No method reads the system clock internally for comparison logic. This ensures deterministic testability.

---

## Out of Scope

The following are explicitly outside this contract:

- Flight search, pricing, or availability.
- Booking or reservation creation.
- Payment processing or refunds.
- Error recovery workflows.
- Authentication, session management, or caller identity verification.
- Notification or messaging side effects.
- Deletion or archival of journey records.
