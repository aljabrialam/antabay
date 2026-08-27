# Data Model: Journey and Objective Model

**Feature**: `001-journey-objective-model`
**Date**: 2026-08-28
**Status**: Authoritative — this document drives all implementation tasks.
**Inputs**: `spec.md` (FR-001–FR-012, NFR-001–NFR-004), `research.md` (Decisions 1–8)

---

## Contents

1. [Entities](#1-entities)
   - 1.1 [ConstraintType](#11-constrainttype)
   - 1.2 [ConstrainedField[T]](#12-constrainedfieldt)
   - 1.3 [TravelObjective](#13-travelobjective)
   - 1.4 [JourneyState](#14-journeystate)
   - 1.5 [JourneyRecord](#15-journeyrecord)
   - 1.6 [AuditEntry](#16-auditentry)
   - 1.7 [AuditEntryType](#17-auditentrytype)
   - 1.8 [HeldIdentifier](#18-heldidentifier)
   - 1.9 [AuthorisationOutcome](#19-authorisationoutcome)
   - 1.10 [AuthorisationResult](#110-authorisationresult)
2. [State Machine](#2-state-machine)
3. [ER Diagram](#3-er-diagram)
4. [Traceability Matrix](#4-traceability-matrix)

---

## 1. Entities

### 1.1 `ConstraintType`

**Kind**: `str` enum (Pydantic / Python `enum.Enum`)
**Module**: `src/models/constraint.py`

| Member | Serialised value | Description |
|--------|-----------------|-------------|
| `HARD` | `"hard"` | The element is a non-negotiable constraint. Violating it means the objective is not met. |
| `SOFT` | `"soft"` | The element is a stated preference. Violation degrades quality but does not fail the objective. |

**Constraints**:
- Only these two members are defined for this feature. Extension requires a new Alembic migration to update the `CHECK` constraint on dependent columns.
- Serialised as a lowercase string so stored JSON and audit entries are human-readable without a code lookup.

**Used by**: `ConstrainedField[T]`

---

### 1.2 `ConstrainedField[T]`

**Kind**: Generic Pydantic v2 `BaseModel` with `Generic[T]`
**Module**: `src/models/constraint.py`

| Field | Python type | Nullable | Description |
|-------|------------|----------|-------------|
| `value` | `T` | No | The extracted value of the objective element. |
| `constraint_type` | `ConstraintType` | No | Hard or soft classification for this value. |

**Constraints**:
- `value` and `constraint_type` are always set together; there is no state where a value exists without a classification or vice versa.
- The generic parameter `T` is instantiated to a concrete type at each use site in `TravelObjective` (see §1.3). Valid instantiations in this feature: `str`, `int`, `datetime`, `Decimal`.
- Serialises to JSON as `{"value": <serialised T>, "constraint_type": "hard" | "soft"}`.
- The full `TravelObjective` model (including all `ConstrainedField` wrappers) is generated as a JSON schema via `model_json_schema()` and passed to the DashScope Qwen API as the structured-output schema. This keeps the extraction schema and the storage model in sync with a single source of truth (Research Decision 1, 2).

**Relationships**: Composed as fields of `TravelObjective`.

---

### 1.3 `TravelObjective`

**Kind**: Pydantic v2 `BaseModel`
**Module**: `src/models/objective.py`
**Storage**: Serialised as JSON and stored in the `objective_json` column of the `journeys` table.

| Field | Python type | Nullable | Description |
|-------|------------|----------|-------------|
| `origin` | `ConstrainedField[str] \| None` | Yes | Departure location as supplied by the traveller (free text; may be a city name, airport code, or region). |
| `destination` | `ConstrainedField[str] \| None` | Yes | Arrival location as supplied by the traveller. |
| `latest_arrival` | `ConstrainedField[datetime] \| None` | Yes | Latest acceptable local arrival date/time at the destination. Serialised as an ISO-8601 string in UTC. Default classification per spec: HARD unless the traveller explicitly states it is a preference. |
| `budget_amount` | `ConstrainedField[Decimal] \| None` | Yes | Maximum acceptable total cost as a decimal (avoids floating-point rounding). |
| `budget_currency` | `ConstrainedField[str] \| None` | Yes | ISO 4217 currency code (e.g., `"GBP"`). Recorded as stated; no conversion is performed. |
| `pax_count` | `ConstrainedField[int] \| None` | Yes | Number of travellers. Must be a positive integer when present. |
| `preferences` | `list[ConstrainedField[str]]` | No | Ordered list of stated preferences (e.g., `"window seat"`). Defaults to an empty list. Each item has its own classification; items in this list are typically SOFT but may be HARD if so stated. |

**Constraints**:
- All fields default to `None`. A `None` field means the traveller did not supply that element. The system MUST ask for any `None` field before presenting the objective for confirmation (FR-005).
- `budget_amount` and `budget_currency` are separate `ConstrainedField` instances but MUST always be present or absent together. If one is `None`, the other MUST also be `None`. This invariant is enforced by a Pydantic model validator.
- `pax_count.value` MUST be `>= 1` when present.
- The system MUST NOT set any field to a non-`None` value unless the traveller explicitly provided that information (NFR-003).
- A `TravelObjective` is considered complete when all of `origin`, `destination`, `latest_arrival`, `budget_amount`, `budget_currency`, and `pax_count` are non-`None`. `preferences` may remain empty.
- Once confirmed and stored in a `JourneyRecord`, the `TravelObjective` is immutable. Modification of a confirmed objective is out of scope for this feature.

**Relationships**: Owned by one `JourneyRecord`.

---

### 1.4 `JourneyState`

**Kind**: `str` enum (Pydantic / Python `enum.Enum`)
**Module**: `src/models/journey.py`

| Member | Serialised value | Description |
|--------|-----------------|-------------|
| `OBJECTIVE_PENDING` | `"objective_pending"` | The traveller has submitted a goal but the parsed objective has not yet been confirmed. Parsing and clarification are in progress. The journey record does not yet exist in durable storage. |
| `OBJECTIVE_CONFIRMED` | `"objective_confirmed"` | The traveller has confirmed the parsed objective. The journey record has been created in durable storage. This is the initial persisted state. |
| `OBJECTIVE_REJECTED` | `"objective_rejected"` | The traveller rejected the parsed objective without requesting correction. Terminal state for this attempt. |
| `CANCELLED` | `"cancelled"` | The journey was explicitly cancelled by the traveller or by the system. Terminal state. |

**Constraints**:
- `OBJECTIVE_PENDING` is a transient in-process state: no `JourneyRecord` row exists in the database while a journey is in this state.
- A `JourneyRecord` row is created only on the transition from `OBJECTIVE_PENDING` to `OBJECTIVE_CONFIRMED`. The initial value written to the `state` column is always `"objective_confirmed"`.
- `OBJECTIVE_REJECTED` and `CANCELLED` are terminal: no further transitions out of these states are permitted.
- States for flight search, booking, disruption, and payment are out of scope for this feature and are deliberately absent.

**Used by**: `JourneyRecord`, `JourneyStateMachine` (see §2).

---

### 1.5 `JourneyRecord`

**Kind**: Pydantic v2 `BaseModel` (in-memory); mapped to the `journeys` table (in storage)
**Module**: `src/models/journey.py`
**Table**: `journeys`

| Field | Python type | Column type | Nullable | Description |
|-------|------------|-------------|----------|-------------|
| `journey_id` | `str` (UUID4) | `TEXT PRIMARY KEY` | No | Globally unique identifier for the journey. Generated at creation time using `uuid.uuid4()`. Immutable after creation. |
| `state` | `JourneyState` | `TEXT NOT NULL` | No | Current state of the journey. Serialised as the enum's string value. Initial value: `"objective_confirmed"`. |
| `objective` | `TravelObjective` | `TEXT NOT NULL` (JSON) | No | The confirmed, complete `TravelObjective`. Stored as a JSON blob in the `objective_json` column. |
| `audit_entries` | `list[AuditEntry]` | — (separate table) | No | All audit entries for this journey. Not a column; populated by joining the `audit_entries` table. Defaults to an empty list before any entries are appended. |
| `held_identifiers` | `list[HeldIdentifier]` | — (separate table) | No | All externally issued identifiers currently held for this journey. Not a column; populated by joining the `held_identifiers` table. Defaults to an empty list. |
| `authorisation_history` | `list[AuthorisationOutcome]` | — (separate table) | No | All authorisation outcomes for this journey. Not a column; populated by joining the `authorisation_outcomes` table. Defaults to an empty list. |
| `schema_version` | `int` | `INTEGER NOT NULL DEFAULT 1` | No | Schema version of the journey record at the time of creation. Used to detect incompatible records on load. Current version: `1`. |
| `created_at` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp of journey record creation. ISO-8601 format. Set once at creation; never updated. |
| `updated_at` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp of the most recent change to the `journeys` row (state change or schema migration). ISO-8601 format. |

**Constraints**:
- `journey_id` is immutable after creation.
- `objective` is immutable after creation (modification of a confirmed objective is out of scope).
- `state` transitions MUST be performed only through `JourneyStateMachine.transition()`, which validates the transition against the allow-list and appends an audit entry atomically (Research Decision 3).
- `schema_version` is checked on load: if the stored value is greater than the current application version, the load MUST be refused with an explicit error.
- `created_at` and `updated_at` are set by the application layer, not by a database default, so they are observable in tests without querying the database clock (Research Decision 6).
- `audit_entries`, `held_identifiers`, and `authorisation_history` are not columns on the `journeys` table. They are populated at read time by loading the corresponding child rows.

**Relationships**:
- Has many `AuditEntry` records (one-to-many via `audit_entries.journey_id`).
- Has many `HeldIdentifier` records (one-to-many via `held_identifiers.journey_id`).
- Has many `AuthorisationOutcome` records (one-to-many via `authorisation_outcomes.journey_id`).

---

### 1.6 `AuditEntry`

**Kind**: Pydantic v2 `BaseModel` (in-memory); mapped to the `audit_entries` table (in storage)
**Module**: `src/models/audit.py`
**Table**: `audit_entries`

| Field | Python type | Column type | Nullable | Description |
|-------|------------|-------------|----------|-------------|
| `entry_id` | `int` | `INTEGER PRIMARY KEY AUTOINCREMENT` | No | Monotonically increasing surrogate key. Auto-assigned by the database. The ordering of `entry_id` values reflects insertion order within a journey. |
| `journey_id` | `str` (UUID4) | `TEXT NOT NULL REFERENCES journeys(journey_id)` | No | Foreign key to the parent `JourneyRecord`. |
| `timestamp` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp at which the entry was recorded by the application. ISO-8601 format. Set at insert time; never updated. |
| `entry_type` | `AuditEntryType` | `TEXT NOT NULL` | No | Classification of the event being recorded. See §1.7. |
| `content` | `str` (JSON) | `TEXT NOT NULL` | No | JSON-serialised body of the event. Structure is defined per `entry_type`. Human-readable and machine-parseable. |

**Constraints**:
- The `audit_entries` table has no `UPDATE` or `DELETE` code paths in the application layer. No `update_entry()` or `delete_entry()` method exists on `AuditRepository` (Research Decision 5, NFR-002).
- `entry_id` is an autoincrement integer, not a UUID, to preserve natural insertion order without sorting by timestamp (which could have sub-millisecond collisions).
- `timestamp` is set by the application, not by a `DEFAULT CURRENT_TIMESTAMP` column constraint, to ensure full testability (Research Decision 6).
- `content` is a JSON string. The schema of `content` varies by `entry_type` and is documented in the contracts directory. For state-transition entries, `content` MUST include `{"from_state": "<state>", "to_state": "<state>"}`.
- Every call to `JourneyStateMachine.transition()` MUST insert an `AuditEntry` with `entry_type = DECISION` in the same database transaction as the `UPDATE` to `journeys.state`. If the transaction fails, neither change is committed.

**Relationships**:
- Belongs to one `JourneyRecord` (many-to-one via `journey_id`).

---

### 1.7 `AuditEntryType`

**Kind**: `str` enum (Pydantic / Python `enum.Enum`)
**Module**: `src/models/audit.py`

| Member | Serialised value | When to use |
|--------|-----------------|-------------|
| `OBSERVATION` | `"observation"` | A fact recorded about the external world or the traveller's input (e.g., "goal received", "clarification answer received"). |
| `DECISION` | `"decision"` | A decision made by the system, including every state transition (e.g., "objective confirmed", "journey cancelled"). |
| `EXTERNAL_CALL` | `"external_call"` | An outbound call to an external API or service (e.g., "DashScope Qwen API called for objective parsing"). |
| `AUTHORISATION_REQUEST` | `"authorisation_request"` | An authorisation request was made to the traveller or the policy engine. Must be followed by an `AUTHORISATION_OUTCOME` entry. |
| `AUTHORISATION_OUTCOME` | `"authorisation_outcome"` | The recorded result of an authorisation request. Links back to the corresponding `AUTHORISATION_REQUEST` entry via the `content` JSON. |

**Constraints**:
- Every `AUTHORISATION_REQUEST` entry MUST have a corresponding `AUTHORISATION_OUTCOME` entry in the audit trail (FR-012). The `content` of the outcome entry MUST reference the `entry_id` of the request entry.
- `AUTHORISATION_REQUEST` and `AUTHORISATION_OUTCOME` are written as two separate entries, not as a single entry updated in place (NFR-002, FR-012 acceptance scenario 4).

---

### 1.8 `HeldIdentifier`

**Kind**: Pydantic v2 `BaseModel` (in-memory); mapped to the `held_identifiers` table (in storage)
**Module**: `src/models/identifier.py`
**Table**: `held_identifiers`

| Field | Python type | Column type | Nullable | Description |
|-------|------------|-------------|----------|-------------|
| `identifier_id` | `int` | `INTEGER PRIMARY KEY AUTOINCREMENT` | No | Surrogate key. Auto-assigned by the database. |
| `journey_id` | `str` (UUID4) | `TEXT NOT NULL REFERENCES journeys(journey_id)` | No | Foreign key to the parent `JourneyRecord`. |
| `value` | `str` | `TEXT NOT NULL` | No | The externally issued identifier value (e.g., a booking reference, session token, or reservation code). |
| `issued_at` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp at which the external system issued this identifier. ISO-8601 format. Set at insert time; never updated. |
| `stale_after` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp after which this identifier MUST be considered stale. Set by the caller at creation time based on the issuing subsystem's policy. Immutable after insert. |

**Methods**:

| Method | Signature | Description |
|--------|-----------|-------------|
| `is_stale` | `(self, now: datetime) -> bool` | Returns `True` if `now >= self.stale_after`. The caller supplies `now`; the method never calls `datetime.now()` internally (Research Decision 6). In production, pass `datetime.now(timezone.utc)`; in tests, pass a fixed `datetime`. |

**Constraints**:
- `stale_after` is set at creation time by the caller based on the issuing subsystem's staleness window. The system does not hardcode a default window.
- `issued_at` and `stale_after` are both required at insert time; neither may be deferred.
- `stale_after` MUST be strictly greater than `issued_at`. This invariant is enforced by a Pydantic model validator.
- The `is_stale()` method is the only point in the codebase where staleness is assessed. All callers that need to know whether an identifier is fresh MUST call this method with the current time; they MUST NOT reimplement the comparison inline.
- Identifiers are never deleted from the table; they accumulate as a historical record. An identifier that is stale remains in the table.

**Relationships**:
- Belongs to one `JourneyRecord` (many-to-one via `journey_id`).

---

### 1.9 `AuthorisationOutcome`

**Kind**: Pydantic v2 `BaseModel` (in-memory); mapped to the `authorisation_outcomes` table (in storage)
**Module**: `src/models/authorisation.py`
**Table**: `authorisation_outcomes`

| Field | Python type | Column type | Nullable | Description |
|-------|------------|-------------|----------|-------------|
| `outcome_id` | `int` | `INTEGER PRIMARY KEY AUTOINCREMENT` | No | Surrogate key. Auto-assigned by the database. |
| `journey_id` | `str` (UUID4) | `TEXT NOT NULL REFERENCES journeys(journey_id)` | No | Foreign key to the parent `JourneyRecord`. |
| `request_description` | `str` | `TEXT NOT NULL` | No | Human-readable description of what was requested for authorisation (e.g., "Proceed to flight search for LHR-SIN"). |
| `outcome` | `AuthorisationResult` | `TEXT NOT NULL` | No | Result of the authorisation request. See §1.10. |
| `timestamp` | `datetime` | `TEXT NOT NULL` | No | UTC timestamp at which the outcome was recorded. ISO-8601 format. Set by the application at insert time; never updated. |
| `recorded_by` | `str` | `TEXT NOT NULL` | No | Identifier of the component or agent that recorded the outcome (e.g., `"journey_service"`, `"authorisation_policy_engine"`). |

**Constraints**:
- Every `AuthorisationOutcome` row MUST have a corresponding `AUTHORISATION_REQUEST` + `AUTHORISATION_OUTCOME` pair in the `audit_entries` table for the same `journey_id` (FR-012). The `authorisation_outcomes` table is a structured complement to the audit trail, not a replacement.
- Rows in this table are insert-only. No `UPDATE` or `DELETE` is permitted.
- `timestamp` is set by the application layer, not by a database default.
- `recorded_by` is a free-form string for this feature; a controlled vocabulary may be introduced in a later feature.

**Relationships**:
- Belongs to one `JourneyRecord` (many-to-one via `journey_id`).

---

### 1.10 `AuthorisationResult`

**Kind**: `str` enum (Pydantic / Python `enum.Enum`)
**Module**: `src/models/authorisation.py`

| Member | Serialised value | Description |
|--------|-----------------|-------------|
| `APPROVED` | `"approved"` | The authorisation request was granted. |
| `REFUSED` | `"refused"` | The authorisation request was denied by the traveller or the policy engine. |

**Constraints**:
- Both outcomes, including refusals, MUST be recorded (FR-012). A refusal MUST NOT be silently discarded.

---

## 2. State Machine

### States and Transitions

```
                            ┌─────────────────────┐
                            │   OBJECTIVE_PENDING  │
                            │  (transient; no DB   │
                            │   row exists yet)    │
                            └─────────┬───────────┘
                                      │
                   ┌──────────────────┼──────────────────────┐
                   │                  │                       │
         traveller │        traveller │             traveller │
          confirms │          rejects │               cancels │
                   ▼                  ▼                       ▼
     ┌─────────────────────┐  ┌──────────────────┐  ┌──────────────┐
     │  OBJECTIVE_CONFIRMED│  │OBJECTIVE_REJECTED│  │  CANCELLED   │
     │  (initial persisted │  │   (terminal)     │  │  (terminal)  │
     │       state)        │  └──────────────────┘  └──────────────┘
     └─────────┬───────────┘
               │
               │ traveller or system
               │ cancels journey
               ▼
        ┌──────────────┐
        │  CANCELLED   │
        │  (terminal)  │
        └──────────────┘
```

### Permitted Transition Table

| From state | To state | Trigger | Audit entry written |
|------------|----------|---------|---------------------|
| `OBJECTIVE_PENDING` | `OBJECTIVE_CONFIRMED` | Traveller confirms the parsed objective | `DECISION`: `{"from_state": "objective_pending", "to_state": "objective_confirmed"}` — but this transition is in-process only; the first DB write creates the row with `state = "objective_confirmed"` |
| `OBJECTIVE_PENDING` | `OBJECTIVE_REJECTED` | Traveller rejects the parsed objective without requesting correction | `DECISION`: `{"from_state": "objective_pending", "to_state": "objective_rejected"}` — no DB row is created |
| `OBJECTIVE_CONFIRMED` | `CANCELLED` | Traveller or system explicitly cancels the journey | `DECISION`: `{"from_state": "objective_confirmed", "to_state": "cancelled"}` |

### Rules

- Any attempted transition not listed in the table above raises `InvalidTransitionError`. The journey state is unchanged and no audit entry is written.
- `OBJECTIVE_REJECTED` and `CANCELLED` are terminal states. No transitions out of these states are defined or permitted.
- `OBJECTIVE_PENDING` is a transient in-process state. No `journeys` table row exists while a journey is in this state. The row is created atomically when the state transitions to `OBJECTIVE_CONFIRMED`.
- Every permitted transition (except the `PENDING → CONFIRMED` creation, which is handled by the initial `INSERT`) is executed as a database transaction containing: (1) `UPDATE journeys SET state = ?, updated_at = ?` and (2) `INSERT INTO audit_entries ...`. If the transaction fails, neither change is committed.

---

## 3. ER Diagram

```
journeys
──────────────────────────────────────────────────────────────
PK  journey_id        TEXT            UUID4, immutable
    state             TEXT            JourneyState enum value
    objective_json    TEXT            JSON blob (TravelObjective)
    schema_version    INTEGER         Default 1; checked on load
    created_at        TEXT            ISO-8601 UTC
    updated_at        TEXT            ISO-8601 UTC


audit_entries
──────────────────────────────────────────────────────────────
PK  entry_id          INTEGER         AUTOINCREMENT
FK  journey_id        TEXT            → journeys.journey_id
    timestamp         TEXT            ISO-8601 UTC
    entry_type        TEXT            AuditEntryType enum value
    content           TEXT            JSON blob


held_identifiers
──────────────────────────────────────────────────────────────
PK  identifier_id     INTEGER         AUTOINCREMENT
FK  journey_id        TEXT            → journeys.journey_id
    value             TEXT            Externally issued ID string
    issued_at         TEXT            ISO-8601 UTC
    stale_after       TEXT            ISO-8601 UTC


authorisation_outcomes
──────────────────────────────────────────────────────────────
PK  outcome_id        INTEGER         AUTOINCREMENT
FK  journey_id        TEXT            → journeys.journey_id
    request_description TEXT          Human-readable description
    outcome           TEXT            AuthorisationResult enum value
    timestamp         TEXT            ISO-8601 UTC
    recorded_by       TEXT            Component identifier


Relationships
──────────────────────────────────────────────────────────────
journeys          ||──o{ audit_entries           (journey_id)
journeys          ||──o{ held_identifiers         (journey_id)
journeys          ||──o{ authorisation_outcomes   (journey_id)
```

### Notes on storage representation

- All `datetime` values are stored as `TEXT` in ISO-8601 UTC format (`YYYY-MM-DDTHH:MM:SS.ffffffZ`). SQLite has no native datetime type; using text with ISO-8601 preserves lexicographic ordering and full precision.
- All enum values are stored as their lowercase string serialisations (e.g., `"objective_confirmed"`, `"hard"`, `"approved"`).
- `objective_json` is the full Pydantic JSON serialisation of `TravelObjective`, including all `ConstrainedField` wrappers. It is read back and deserialised via `TravelObjective.model_validate_json()`.
- The `alembic_version` table (managed by Alembic) is present in the database but is not part of the application data model.
- `schema_version` on the `journeys` table starts at `1` for this feature. Application code that loads a journey MUST refuse to proceed if `schema_version > CURRENT_APP_SCHEMA_VERSION` and MUST log a clear error.

---

## 4. Traceability Matrix

| Requirement | Entity / Field / Method | How satisfied |
|-------------|------------------------|---------------|
| **FR-001** — Accept a travel goal stated in natural language | `TravelObjective` (parsing entry point); `AuditEntry` with `entry_type = OBSERVATION` | The objective parsing layer accepts free-text input and records an OBSERVATION audit entry. `TravelObjective` fields are nullable, so partial input is valid at parse time. |
| **FR-002** — Extract a structured objective with origin, destination, latest arrival, budget, pax count, preferences | `TravelObjective.origin`, `.destination`, `.latest_arrival`, `.budget_amount`, `.budget_currency`, `.pax_count`, `.preferences` | Each element is a dedicated nullable field on `TravelObjective`. The full model is the structured output of the parsing step. |
| **FR-003** — Classify each element as hard or soft and record the classification alongside it | `ConstraintType`, `ConstrainedField[T].constraint_type` | Every objective field is a `ConstrainedField[T]`, pairing value and classification atomically. Classification is co-located with the value in both the in-memory model and the stored JSON. |
| **FR-004** — Present the parsed objective for confirmation before any downstream action | `TravelObjective` (complete model presented to traveller); `JourneyState.OBJECTIVE_PENDING` | The objective is surfaced while the journey is in `OBJECTIVE_PENDING` state. No `JourneyRecord` is created and no downstream action is taken until the traveller confirms. |
| **FR-005** — Identify absent or ambiguous elements; ask the traveller; do not infer or default | `TravelObjective` nullable fields; NFR-003 enforced at parse time | All `TravelObjective` fields are `None` by default. The application layer checks for `None` fields after parsing and requests them from the traveller. No field is given a non-`None` value without explicit traveller input. |
| **FR-006** — Create a journey record with unique ID, confirmed objective, and initial state on confirmation | `JourneyRecord.journey_id` (UUID4), `.objective` (confirmed `TravelObjective`), `.state` (initial `OBJECTIVE_CONFIRMED`) | The `JourneyRecord` row is created atomically on the `OBJECTIVE_PENDING → OBJECTIVE_CONFIRMED` transition. `journey_id` is a UUID4; `state` is set to `OBJECTIVE_CONFIRMED`; `objective` holds the confirmed model. |
| **FR-007** — Maintain defined journey states; permit only documented transitions; reject undocumented transitions | `JourneyState` (enum), `JourneyStateMachine` (allow-list), `InvalidTransitionError` | `JourneyState` enumerates valid states. `JourneyStateMachine.transition()` checks the allow-list and raises `InvalidTransitionError` for any undocumented transition without modifying state. |
| **FR-008** — Persist the full journey record in durable storage external to any running process | `journeys` table (SQLite via SQLAlchemy Core + Alembic); `audit_entries`, `held_identifiers`, `authorisation_outcomes` tables | All entities are persisted to a SQLite database file (survives process restart). `JourneyRepository` abstracts the storage layer. `JourneyRecord` can be fully reconstructed from the database tables. |
| **FR-009** — Record issue time and staleness threshold for every held external identifier | `HeldIdentifier.issued_at`, `HeldIdentifier.stale_after`, `HeldIdentifier.is_stale(now)` | `HeldIdentifier` has dedicated `issued_at` and `stale_after` fields, both required at insert time. `is_stale(now)` provides the freshness check without hiding the system clock. |
| **FR-010** — Maintain an append-only audit trail with timestamp for every observation, decision, external call, and authorisation event | `AuditEntry`, `AuditEntryType` (all five members), `audit_entries` table (insert-only) | `AuditEntry` has `entry_type` covering all required event classes. The `audit_entries` table has no `UPDATE` or `DELETE` code paths. `timestamp` is written at insert time. |
| **FR-011** — Expose current journey state, confirmed objective, and full audit trail on demand | `JourneyRecord.state`, `.objective`, `.audit_entries`; `JourneyRepository.get(journey_id)` | `JourneyRecord` aggregates state, objective, and the audit entry list. `get()` loads the record and its child rows from the database, making all three queryable in O(1) by `journey_id`. |
| **FR-012** — Record every authorisation outcome, including refusals, in the audit trail | `AuthorisationOutcome`, `AuthorisationResult` (APPROVED, REFUSED), `AuditEntryType.AUTHORISATION_REQUEST`, `AuditEntryType.AUTHORISATION_OUTCOME` | `AuthorisationOutcome` records the structured outcome. Two `AuditEntry` rows (one REQUEST, one OUTCOME) are written for every authorisation event, including refusals. Neither row may be omitted or modified. |

### Non-Functional Requirement coverage

| Requirement | Satisfied by |
|-------------|-------------|
| **NFR-001** — Journey record in durable storage is the single source of truth | `journeys` table is the authoritative store. `JourneyRecord` is always loaded from the database; no in-process or context-window cache is the authoritative state. |
| **NFR-002** — Audit trail is append-only; no entry modified or deleted after write | `audit_entries` table: no `UPDATE`/`DELETE` code paths exist. `AuditRepository` exposes only `append_entry()`. `entry_id` is autoincrement with no natural key to enable collision-based "replacement". |
| **NFR-003** — System must not author, infer, or default any travel fact | All `TravelObjective` fields are nullable with no defaults. Parser emits `null` for absent fields (enforced by JSON schema in structured-output API call). Application checks for `None` and requests missing values from the traveller. |
| **NFR-004** — Objective parsing must be reproducible | Enforced by: temperature `0` on the DashScope API call; pinned model version; canonical input normalisation before the API call. These are constraints on the parsing service, which uses `TravelObjective.model_json_schema()` as the extraction schema. |
