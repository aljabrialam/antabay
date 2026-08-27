# Research: Journey and Objective Model

**Feature**: `001-journey-objective-model`
**Date**: 2026-08-28
**Input**: Feature spec FR-001–FR-012, NFR-001–NFR-004; Constitution principles I, VI, VII, VIII, XIII

---

## Decision 1: Natural-Language Objective Parsing

**Decision**: Use the DashScope Qwen API with a single structured-output prompt that supplies a fixed JSON schema in the `response_format` parameter (or an equivalent `tools`/function-calling declaration). The prompt instructs the model to extract only what is explicitly present in the traveller's text and to emit `null` for any absent field. Temperature is fixed at `0`. The model version is pinned by name in the request (e.g., `qwen-max-2025-01-25`), not resolved via a floating alias such as `qwen-max-latest`.

**Rationale**:
- NFR-003 forbids the system from inferring or defaulting any travel fact. A JSON schema with nullable required fields forces the model to surface absences as explicit `null` rather than fabricating values, because the model must conform to the schema rather than fill in plausible text.
- NFR-004 requires reproducibility. Temperature `0` collapses the sampling distribution to the greedy argmax, giving deterministic token selection for the same prompt and model weights. A pinned model version ensures weights do not change beneath the application between releases.
- Structured output / function calling is preferable to prompting for plain JSON and then parsing it, because: (a) the API validates the response against the schema before returning it, so malformed JSON cannot reach the application layer; (b) the field names and types are declared once in code, not buried in a prompt string; (c) Pydantic v2 model classes can be translated directly to the JSON schema required by the API using `model_json_schema()`, keeping the schema definition in one place.
- The DashScope Qwen API supports OpenAI-compatible function calling, meaning the same `tools` parameter pattern used in the OpenAI SDK works with minimal adaptation.

**Alternatives considered**:
- **Plain-text JSON prompt with regex/json.loads parsing**: Unreliable. The model may add prose around the JSON block, or produce subtly invalid JSON (trailing commas, single quotes). A schema-validated response eliminates this failure mode entirely.
- **Chain-of-thought extraction followed by a second structuring call**: Increases latency, cost, and the number of non-deterministic steps. The two-call approach means errors can compound. For a well-defined fixed schema this is unnecessary complexity.
- **LangChain or a structured-output framework**: Adds a third-party abstraction layer. Constitution Principle XVII (Built With Qoder) and the general constraint against unnecessary dependencies favour a direct API call with the schema embedded as a Pydantic model. A thin wrapper written for this project is auditable and has no hidden upgrade surface.

---

## Decision 2: Hard vs. Soft Constraint Classification

**Decision**: Embed the classification as a `ConstraintType` enum (`HARD` / `SOFT`) directly on each objective field by pairing every extracted value with its classification in a typed Pydantic v2 model. Concretely, each field that can be classified is represented as a small `ConstrainedField[T]` generic model containing `value: T` and `constraint: ConstraintType`. The top-level `TravelObjective` model composes these constrained fields rather than storing raw scalars.

Example shape (illustrative, not final code):

```python
class ConstraintType(str, Enum):
    HARD = "hard"
    SOFT = "soft"

class ConstrainedField(BaseModel, Generic[T]):
    value: T
    constraint: ConstraintType

class TravelObjective(BaseModel):
    origin: ConstrainedField[str] | None = None
    destination: ConstrainedField[str] | None = None
    latest_arrival: ConstrainedField[datetime] | None = None
    budget: ConstrainedField[Budget] | None = None
    pax_count: ConstrainedField[int] | None = None
    preferences: list[ConstrainedField[str]] = Field(default_factory=list)
```

**Rationale**:
- Inline pairing keeps value and classification co-located. There is no risk of the two becoming misaligned through independent updates, because they are a single atomic unit in the data model and in storage.
- A separate classification dict (e.g., `classifications: dict[str, ConstraintType]`) requires a string key that matches a field name, creating an implicit coupling that is not enforced by the type system and breaks silently on rename.
- Pydantic v2 generic models (`BaseModel` with `Generic[T]`) are fully supported and serialise cleanly to JSON. The JSON schema for `TravelObjective` is self-describing and can be passed directly to the LLM API as the extraction schema (Decision 1), closing the loop between the model definition and the prompt.
- The `ConstraintType` enum serialises as a string (`"hard"` / `"soft"`), which is human-readable in the stored JSON and in audit trail entries, satisfying the audit-trail legibility requirement implied by FR-010.

**Alternatives considered**:
- **Separate `classifications` dict keyed on field name**: Decoupled from the value; requires maintaining synchronisation manually. Rejected because it is error-prone and not enforced by the type system.
- **Separate `ClassificationRecord` table in the database**: Normalised but over-engineered for a fixed, small set of fields. The classification is intrinsic to the objective element, not a separately queryable entity. Adds join complexity for no query benefit at this scale.
- **Boolean `is_hard: bool` per field (flat approach)**: Less expressive than an enum if a third category (e.g., `CONDITIONAL`) is introduced later. An enum is equally compact and more extensible.

---

## Decision 3: Journey State Machine

**Decision**: Define a minimal `JourneyState` string enum and enforce transitions with an explicit allow-list dictionary in a `JourneyStateMachine` class. No external state-machine library is introduced. The minimal viable state set for this feature (objective capture only) is:

```
OBJECTIVE_PENDING       — journey record not yet created; parsing/clarification in progress
OBJECTIVE_CONFIRMED     — traveller has confirmed the parsed objective; journey record exists
OBJECTIVE_REJECTED      — traveller rejected the parsed objective; terminal state for this attempt
CANCELLED               — journey explicitly cancelled by traveller or system
```

Permitted transitions:

```
OBJECTIVE_PENDING   → OBJECTIVE_CONFIRMED
OBJECTIVE_PENDING   → OBJECTIVE_REJECTED
OBJECTIVE_CONFIRMED → CANCELLED
```

Any attempted transition not in this table raises a `InvalidTransitionError` and leaves state unchanged.

**Rationale**:
- FR-007 requires that only documented transitions are permitted and that any undocumented transition is rejected. An explicit allow-list table is the simplest data structure that provides this guarantee: `if (current, target) not in ALLOWED_TRANSITIONS: raise`.
- Scope is objective capture only. States for flight search, booking, disruption, and payment are deliberately absent; adding them later requires only extending the enum and the allow-list, not restructuring the model.
- A plain class over an allow-list dict is fully testable, has zero dependencies, and is auditable in a single file. The state machine module can be imported and unit-tested in isolation.
- Every transition is recorded in the audit trail (FR-010), so the `transition()` method must also append an `AuditEntry`. Keeping this in the state machine class rather than scattering it across callers ensures the audit trail is never bypassed.

**Alternatives considered**:
- **`transitions` library (pytransitions)**: Mature library with decorator-based definition. Rejected because it adds a dependency for functionality that is trivially implemented in ~30 lines of plain Python, and the decorator-based DSL makes it harder to audit which transitions are permitted at a glance.
- **`python-statemachine`**: Similar reasoning. The library's auto-generated diagram is useful for large machines, but the 4-state machine here is documented clearly in a table.
- **State stored as a free-form string with no enforcement**: Violates FR-007 directly. Any string assignment would be a permitted "transition".
- **Event-sourcing with no explicit state (derive state from audit log)**: The journey state must be queryable in O(1) for FR-011 (display on demand). Deriving state by replaying the audit log on every read is acceptable at small scale but introduces complexity and a performance assumption that will break under load. Storing explicit state alongside the append-only audit trail is cleaner.

---

## Decision 4: Durable Storage for Journey Records

**Decision**: SQLite for the initial development and demonstration phase, with the storage layer abstracted behind a `JourneyRepository` interface so that PostgreSQL can be substituted without changing application code. SQLAlchemy Core (not ORM) is used for all database interactions to keep queries explicit and auditable.

**Rationale**:
- FR-008 and NFR-001 require storage external to any running process. SQLite is a file on disk; it survives process restart and satisfies this requirement with zero operational overhead.
- The project is in early development. SQLite requires no server installation, no connection pooling configuration, and no credentials. A developer can clone the repo and run tests without any infrastructure setup.
- SQLAlchemy Core with a SQLite connection string (`sqlite:///./antabay.db`) can be swapped to PostgreSQL by changing the connection string alone, provided the schema uses only standard SQL types. This is explicitly tested in the repository interface layer.
- Alembic (Decision 8) works identically against both SQLite and PostgreSQL, so the migration path is not disrupted.

**Alternatives considered**:
- **PostgreSQL from day one**: Correct for production but adds operational overhead (server, connection string management, Docker Compose dependency) that slows early development and makes the project harder to demonstrate. Premature optimisation at this stage.
- **Document store (MongoDB, TinyDB, or JSON files)**: Journey records have a well-defined, versioned schema and benefit from relational constraints (e.g., foreign key from `audit_entries` to `journeys`). A document store would require manual enforcement of these constraints in application code. JSON files provide no concurrent-write safety and no migration tooling.
- **SQLAlchemy ORM**: The ORM adds a mapping layer that obscures the exact SQL being executed, which matters for the append-only audit trail (Decision 5). Using Core keeps every `INSERT` and `SELECT` statement explicit and reviewable.

---

## Decision 5: Append-Only Audit Trail Implementation

**Decision**: Implement the audit trail as a separate `audit_entries` table in SQLite/PostgreSQL with no `UPDATE` or `DELETE` permissions granted to the application database user, and with no `UPDATE`/`DELETE` statements anywhere in the codebase. The application layer enforces append-only at the Python level by exposing only an `append_entry()` method on the `AuditRepository`; no `update_entry()` or `delete_entry()` method exists. In production, database-level `REVOKE UPDATE, DELETE ON audit_entries FROM app_user;` provides a second enforcement layer.

Schema (illustrative):

```sql
CREATE TABLE audit_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id  TEXT NOT NULL REFERENCES journeys(id),
    recorded_at TEXT NOT NULL,   -- ISO-8601 UTC
    entry_type  TEXT NOT NULL,   -- observation | decision | external_call | authorisation
    content     TEXT NOT NULL    -- JSON-serialised entry body
);
-- No UPDATE or DELETE ever issued against this table.
```

**Rationale**:
- NFR-002 states that no entry may be modified or deleted after it is written. The simplest enforcement is structural absence: if the code has no `UPDATE` path, no bug or misconfiguration can accidentally mutate an entry.
- An autoincrement `id` with no natural key ensures entries cannot be "replaced" by inserting a new row with a conflicting primary key.
- The `recorded_at` timestamp is written at insert time by the application (not a database default) so that the value is visible in tests without querying the database for its clock.
- Separating audit entries into their own table (rather than embedding them as a JSON array in the journey row) allows individual entries to be queried, counted, and paginated efficiently. It also makes the append-only constraint enforceable at the SQL level.

**Alternatives considered**:
- **Embedded JSON array in the journey row (`audit_trail: JSON`)**: Requires an `UPDATE` on the journey row to append each entry, which conflicts with the append-only requirement and makes database-level enforcement impossible. Rejected.
- **Immutable log file (one file per journey)**: Satisfies append-only at the filesystem level but introduces file-handle management, concurrent-write hazards, and no query capability. Not compatible with the SQLAlchemy storage layer already chosen.
- **Full event sourcing (no mutable state, derive everything from events)**: Architecturally pure but significantly increases implementation complexity for no benefit at this stage. The journey has explicit state that must be queryable in O(1) (FR-011). Event sourcing would derive state from replay on every read — acceptable only with a snapshot mechanism that re-introduces mutable state. Overkill for a 4-state machine.
- **PostgreSQL audit triggers**: Elegant but SQLite-incompatible and makes the application harder to run locally. Deferred to production hardening.

---

## Decision 6: Identifier Staleness Tracking

**Decision**: Implement `HeldIdentifier` as a separate table in the database, associated with a journey via a foreign key, and as a Pydantic model with three fields: `identifier_value: str`, `issued_at: datetime`, and `stale_after: datetime`. The `is_stale(now: datetime) -> bool` method takes the current time as an explicit parameter; it does not call `datetime.now()` or `datetime.utcnow()` internally.

```python
class HeldIdentifier(BaseModel):
    identifier_value: str
    issued_at: datetime
    stale_after: datetime

    def is_stale(self, now: datetime) -> bool:
        return now >= self.stale_after
```

The caller is responsible for supplying the current time. In production this is `datetime.now(UTC)`; in tests this is a fixed `datetime` object.

**Rationale**:
- FR-009 requires that both the issue time and the staleness threshold are recorded. The `stale_after` field is the threshold; it is set by the caller at the time the identifier is acquired (e.g., `issued_at + timedelta(minutes=30)`), not computed on read. This means the threshold is durable and does not change if the staleness window policy changes later.
- Injecting `now` as a parameter (rather than calling the system clock internally) makes `is_stale()` a pure function of its inputs: deterministic, testable with time travel, and free of hidden side effects. This aligns with Constitution Principle XIII (Deterministic Automation).
- A separate `held_identifiers` table rather than embedding identifiers in the journey row allows multiple identifiers to be attached to a journey independently, queried individually, and marked stale without modifying the parent journey row.
- The `stale_after` field is distinct from "default staleness window". The system does not hardcode a default window; the window is determined by the subsystem that issues the identifier and passed explicitly at creation time.

**Alternatives considered**:
- **Embedded in the journey record as a JSON array**: Makes individual identifier queries require deserialising the whole array. Also complicates the append-only audit trail if identifier state changes are recorded. A dedicated table is cleaner.
- **`is_stale()` reads `datetime.now()` internally**: Makes the method non-deterministic and untestable without monkeypatching. Rejected in favour of explicit injection.
- **Storing only `issued_at` and computing `stale_after` from a configurable window at read time**: The staleness threshold would depend on whatever the current policy is, not the policy at the time of issuance. If the window is shortened, previously valid identifiers could appear stale retroactively. Storing `stale_after` explicitly is the correct approach.

---

## Decision 7: Reproducible NL Parsing

**Decision**: Guarantee reproducibility (NFR-004) through three layered mechanisms, applied in order:
1. **Fixed temperature `0`** on every DashScope Qwen API call. This collapses sampling to greedy decoding, giving identical output for identical input and model weights.
2. **Pinned model version** in every API request (e.g., `model="qwen-max-2025-01-25"`). Floating aliases such as `qwen-max` or `qwen-max-latest` are prohibited; the model name is a constant defined in one configuration file.
3. **Canonical input normalisation** before the API call: strip leading/trailing whitespace, normalise Unicode to NFC, collapse internal runs of whitespace to a single space. This ensures that "London to Singapore" and "London  to Singapore" (double space) produce the same API call and therefore the same output.

Caching (keyed on the canonical input string) is an optional fourth layer for development environments to reduce API cost during repeated test runs, but is not relied upon for correctness.

**Rationale**:
- Temperature `0` is the primary correctness guarantee. At temperature `0`, modern transformer models use greedy decoding (argmax at each step), which is deterministic given fixed weights and context. This is well-documented for both OpenAI-compatible and DashScope APIs.
- Model pinning prevents silent regressions when the provider updates a floating alias. The pinned model name is kept in a single constant so that a deliberate upgrade is a one-line change with a clear diff.
- Canonical normalisation handles the most common sources of input variation that would otherwise produce different prompts and different outputs. It is cheap (pure string operations) and stateless.
- NFR-004 and SC-005 require that the same goal submitted in two separate sessions produces identical structured objectives. With these three layers in place, this is guaranteed for identical traveller text.

**Alternatives considered**:
- **Response caching only (no temperature fix)**: Caching is brittle: a cache miss (cold start, eviction, slightly different whitespace) falls through to a non-deterministic API call. Caching alone does not satisfy NFR-004.
- **Post-processing normalisation (round-trip JSON through Pydantic) without temperature fix**: Normalises the structure but not the field values. If the model extracts "London Heathrow" in one call and "LHR" in another, post-processing cannot reconcile them.
- **Deterministic seed parameter**: DashScope does not expose a seed parameter equivalent to OpenAI's `seed`. Temperature `0` is the available determinism control.
- **Two-call verification (parse twice, assert agreement)**: Doubles API cost and latency for a guarantee that temperature `0` already provides. Rejected as disproportionate.

---

## Decision 8: Journey Record Schema Versioning

**Decision**: Use Alembic for all database schema migrations, with a `schema_version` integer column on the `journeys` table to support future data migrations. The migration history is stored in `backend/alembic/versions/`. Every schema change, including the initial creation, is expressed as an Alembic revision. No migration is hand-applied directly to the database.

**Rationale**:
- Alembic is the standard migration tool for SQLAlchemy projects. It generates versioned migration scripts that are committed to the repository, making the schema history auditable and reproducible on any environment (developer machine, CI, production).
- SQLite and PostgreSQL are both supported by Alembic with the same migration scripts (subject to the standard SQLite DDL limitations, which Alembic handles via `batch_alter_table` for column modifications).
- A `schema_version` column on the `journeys` table allows application code to detect and refuse to load a journey record written by a future, incompatible version of the application. This is a simple guard against reading corrupted data in a downgrade scenario.
- At the scale of early development (one developer, SQLite), Alembic provides a lightweight migration discipline that scales linearly as the project grows. The cost of adopting it from day one is a few configuration files and the habit of generating revisions; the benefit is a complete, reviewable migration history from the first table creation.

**Alternatives considered**:
- **Manual schema management (hand-applied `CREATE TABLE` statements)**: No migration history, no reproducibility on a fresh environment, no upgrade path. Rejected entirely.
- **Event sourcing as the sole schema versioning strategy**: If the system were purely event-sourced, schema evolution would be handled by versioning event types rather than table columns. However, Decision 3 and Decision 5 establish that the system uses explicit mutable state alongside an append-only audit log. Alembic is the appropriate tool for the mutable-state tables.
- **SQLAlchemy `create_all()` on startup**: Creates tables if they do not exist but does not handle column additions, renames, or type changes. Suitable only for greenfield development; breaks the moment any schema modification is needed. Rejected as a permanent strategy.
- **A separate `schema_versions` table (single-row migration state)**: This is effectively what Alembic's `alembic_version` table already is. Rolling a custom version table duplicates Alembic's infrastructure for no benefit.
