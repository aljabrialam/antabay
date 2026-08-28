# Data Model: Recovery Execution

## Entities

### RecoveryExecution

One row per execution attempt, keyed uniquely by `recommendation_id`
(FR-014 — an authorisation, hence a recommendation, produces at most one
execution attempt).

| Field | Type | Notes |
|---|---|---|
| `recovery_execution_id` | str (uuid) | Primary key |
| `recommendation_id` | str | Unique — the authorised action this execution consumes (research.md R2, R5) |
| `journey_id` | str | FK to `journeys` |
| `started_at` | datetime | |
| `concluded_at` | datetime \| None | Null while `IN_PROGRESS` |
| `status` | enum: `IN_PROGRESS`, `COMPLETED`, `ABANDONED` | |
| `abandonment_reason` | str \| None | One of `not_authorised`, `price_changed`, `alternative_unavailable`, `replacement_creation_failed`, `replacement_payment_failed` (FR-002, FR-001) |
| `superseded_order_no` | str \| None | Captured before replacement creation (research.md R3) |
| `replacement_order_no` | str \| None | Set once `create_order` succeeds |
| `replacement_outcome` | enum \| None: `SUCCEEDED`, `FAILED` | FR-006 |
| `cancellation_outcome` | enum \| None: `SUCCEEDED`, `FAILED`, `NOT_ATTEMPTED` | FR-006 — `NOT_ATTEMPTED` only when replacement itself failed |
| `final_position_description` | str \| None | Stated in objective terms (FR-012) |

### CancellationAttempt

One row per cancellation attempt against the superseded booking
(research.md R1 — provisional pending a Tier 2 capture).

| Field | Type | Notes |
|---|---|---|
| `attempt_id` | str (uuid) | Primary key |
| `journey_id` | str | FK to `journeys` |
| `order_no` | str | The superseded booking's order_no |
| `requested_at` | datetime | |
| `responded_at` | datetime \| None | Null only on a request-level error |
| `raw_response_json` | str \| None | The `void.do` call's raw response (provisional shape) |
| `outcome` | enum: `INITIATED`, `ERROR` | Whether the call itself succeeded, not whether cancellation is confirmed |
| `reconciliation_raw_json` | str \| None | The independent `queryOrderDetails.do` response used to confirm (FR-006, NFR-002) |
| `confirmed_cancelled` | bool | True only if the reconciliation query no longer shows a fully ticketed state (research.md R1's success predicate) |

## Journey table extension

- `journeys.current_order_no` (nullable `String`) — an explicit pointer to
  the journey's authoritative current booking, distinct from
  `get_active_journeys_with_order_reference()`'s recency heuristic
  (research.md R4). Set only by `set_current_order()`, called only after
  the replacement's ticketing is independently confirmed (FR-009).

## New repository methods (`journey/storage/repository.py`)

- `save_recovery_execution(execution: RecoveryExecution) -> None`
- `update_recovery_execution(execution: RecoveryExecution) -> None`
- `get_recovery_execution_by_recommendation(recommendation_id: str) -> RecoveryExecution | None`
- `save_cancellation_attempt(attempt: CancellationAttempt) -> None`
- `set_current_order(journey_id: str, order_no: str) -> None`
- `get_current_order_no(journey_id: str) -> str | None`
- `get_recommendation(recommendation_id: str) -> Recommendation | None` — a
  lookup for feature 009's `recommendations` table that did not previously
  need a by-id getter (only `save_recommendation` existed)

## New tables (`journey/storage/tables.py`)

- `recovery_executions` — columns mirror `RecoveryExecution` above, with a
  `UniqueConstraint` on `recommendation_id` (FR-014).
- `cancellation_attempts` — columns mirror `CancellationAttempt` above.

One additive Alembic migration adds both tables and the
`journeys.current_order_no` column.

## New exceptions (`journey/errors.py`)

- `RecommendationNotFoundError(recommendation_id)` — execution requested
  for an unknown `recommendation_id`.
- `RecoveryAlreadyAttemptedError(recommendation_id)` — a second execution
  attempt against a `recommendation_id` that already has a
  `RecoveryExecution` row, in any status (FR-014).

## Integration points on existing modules

- **No changes** to `journey/services/booking_service.py`,
  `journey/services/verification_service.py`, or
  `journey/services/authorisation_policy_engine.py` — all three are
  called unmodified (research.md R2, R3).
- **`journey/storage/tables.py`**: `journeys` table gains
  `current_order_no`; two new tables added.
