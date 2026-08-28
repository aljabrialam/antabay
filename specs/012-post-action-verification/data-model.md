# Data Model: Post-Action Verification

## Entities

### VerificationAttempt

The persisted record of one independent query performed to establish the
actual outcome of a state-changing action, for any action type. One row
per query — including every reconciliation attempt for an unresolved
outcome (research.md R2), not just the final one — so the audit trail
(FR-009) is complete regardless of outcome.

| Field | Type | Notes |
|---|---|---|
| `attempt_id` | string (UUID) | Primary key |
| `journey_id` | string | FK → `journeys.journey_id` |
| `action_type` | string | The registered action type this attempt verifies (e.g. `"ticketing"`) |
| `affected_record_id` | string | The identifier of the record being verified (e.g. an `orderNo`) — scopes concurrency ordering (FR-011) |
| `action_response_json` | text \| null | The action's own response, if one was captured, for discrepancy comparison (FR-005) |
| `queried_at` | datetime (ISO-8601 UTC) | When this query was issued |
| `observed_at` | datetime (ISO-8601 UTC) | When the query's result reflects the record's state — governs FR-011 ordering; distinct from `queried_at` for a query whose result carries its own observation timestamp |
| `query_result_json` | text | The raw query result, in full (NFR-001 — always in terms of externally observable state) |
| `classification` | enum | `SUCCESS` \| `FAILURE` \| `UNRESOLVED` (research.md R1/R2 — the gate's final classification, after applying the bound rule) |
| `condition_result` | enum | `SUCCESS` \| `FAILURE` \| `INCONCLUSIVE` \| `NOT_FOUND` (the registered `SuccessCondition`'s raw classification for *this* attempt, before the gate's bound logic is applied) |
| `has_discrepancy` | bool | Whether `SuccessCondition.has_discrepancy()` returned true for this attempt (FR-005) |
| `applied_to_state` | bool | Whether this attempt's classification governed journey state, or was superseded by a later-observed concurrent attempt (FR-011) |

**Validation rules**:
- `classification` MUST be derived only from `condition_result` and the
  reconciliation history for `affected_record_id` — never set directly by
  a caller (FR-002, NFR-001).
- Every `VerificationAttempt` row MUST be written regardless of
  `classification` or `has_discrepancy` — there is no code path that
  performs a query without persisting its attempt (FR-009).
- For a given `affected_record_id`, at most one `VerificationAttempt` may
  have `applied_to_state = True` with a `classification` of `SUCCESS` or
  `FAILURE` at any time — reaching a new resolved classification for that
  record supersedes the previous one only if its `observed_at` is later
  (FR-011).

### SuccessCondition (registration, not a persisted entity)

The per-action-type definition an action type provides to the gate. Not
stored in the database — it is code registered at startup, one
implementation per `action_type` string.

| Responsibility | Maps to |
|---|---|
| Classify a raw query result | `condition_result` on the resulting `VerificationAttempt` (FR-003) |
| Detect a discrepancy against the action's own response | `has_discrepancy` (FR-005) |
| Declare a reconciliation bound (max attempts or max duration) | Enforced by the gate when reconciling `UNRESOLVED` outcomes (FR-003, FR-007) |

**Validation rule**: No action type may use another action type's
condition, and the gate MUST reject verifying an `action_type` with no
registered condition — there is no default condition (FR-003).

### Discrepancy (embedded on VerificationAttempt, not a separate table)

Represented by `has_discrepancy` plus the already-persisted
`action_response_json` and `query_result_json` on the same row — both
sides of the disagreement are visible from the one `VerificationAttempt`
without a join. A separate table was considered and rejected; see
data-model rationale in research.md R4 (a discrepancy has no independent
lifecycle beyond the attempt that found it).

### ReportableOutcome (derived, not persisted)

Computed on read from `VerificationAttempt` rows for a given
`affected_record_id`: the most recently `applied_to_state` attempt whose
`classification` is `SUCCESS` or `FAILURE`. `None` if no such attempt
exists yet (research.md R6) — there is no stored "pending" row and no
placeholder value.

## Relationships

```text
journeys (1) ──< verification_attempts (many)
verification_attempts (many) -- affected_record_id --> an action-type-specific
                                  record this feature does not itself own
                                  (e.g. an orders.order_no from spec 005)
```

`VerificationAttempt` does not carry a foreign key to any action-specific
table (e.g. `orders`) — `affected_record_id` is an opaque string from this
feature's point of view, consistent with the gate being action-agnostic
(research.md R1).

## Safety Properties Enforced By This Model (traceability to FR/NFR)

- FR-001, FR-002: journey state is never derived except by reading
  `VerificationAttempt.classification` from the most recent
  `applied_to_state = True` row — there is no other path.
- FR-003: enforced by the `SuccessCondition` registration contract above,
  not by data model validation alone (a missing registration is a
  programming error caught at call time, not a row that could be
  malformed).
- FR-004: proven by `condition_result` values produced by the ticketing
  `SuccessCondition` reproducing 005's own rule (research.md R7).
- FR-005: `has_discrepancy` plus both raw JSON columns on the same row.
- FR-006, FR-007: `condition_result = INCONCLUSIVE` vs `NOT_FOUND`
  distinction plus the bound-tracking logic in research.md R2.
- FR-008: not a data-model concern — normalisation happens inside a
  `SuccessCondition` before it ever produces a `condition_result`
  (research.md R5).
- FR-009: the "every attempt is a row" validation rule above.
- FR-010: `ReportableOutcome`'s derivation rule above.
- FR-011: `observed_at` plus `applied_to_state`'s supersession rule.
- NFR-001: `query_result_json` is always the literal externally observed
  response — `classification` is derived from it, never from
  `action_response_json` (which exists only for discrepancy comparison).
