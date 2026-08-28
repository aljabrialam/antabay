# Contract: Post-Action Verification Gate (internal, exposed)

**Feature**: 012-post-action-verification
**Type**: Internal service interface — consumed by whatever orchestrates a
state-changing action (the agent loop, or a feature-specific service such
as a future refund/void/rebook implementation)
**Consumed by**: Any code that performs a state-changing external action
and needs to establish, and record, what actually happened

---

## Registration: SuccessCondition

Before any action type can be verified through this gate, it registers a
`SuccessCondition` for its `action_type` string. There is no default —
attempting to verify an unregistered `action_type` is a caller error
(FR-003).

A `SuccessCondition` provides:

| Method | Contract |
|---|---|
| `classify(query_result)` | Returns one of `Success`, `Failure`, `Inconclusive`, `NotFound` (research.md R1) |
| `has_discrepancy(action_response, query_result)` | Returns whether the action's own response and the query disagree (FR-005) |
| `reconciliation_bound()` | Returns the max attempts or max duration this action type permits before an unresolved outcome stops being reconciled (FR-003, FR-007) |

The **ticketing condition** (FR-004, research.md R7) is the one shipped
with this feature: `classify()` returns `Success` when every passenger's
`ticketNos` is non-empty, `Failure` when the response carries a non-null
`errorCode`, `Inconclusive` otherwise; `has_discrepancy()` returns true
when the originating action's response implied a ticket was issued but
the query shows none.

## Operation: Verify

**Inputs**: `action_type`, `affected_record_id`, `action_response` (the
action's own response, for discrepancy comparison — may be absent if the
action's outcome was itself uncertain), a `query_fn` the gate calls to
perform the independent query, `now`.

**Behaviour**:
1. Calls `query_fn()` to obtain a query result and its `observed_at`.
2. Calls the registered `SuccessCondition.classify()` on the result.
3. Calls `SuccessCondition.has_discrepancy()` if an `action_response` was
   provided.
4. Applies the bound rule (research.md R2) if the raw classification is
   `Inconclusive` or `NotFound`, using the reconciliation history already
   recorded for `affected_record_id`.
5. Persists a `VerificationAttempt` row regardless of outcome (FR-009).
6. If this attempt's classification would change journey state, applies
   the concurrency-ordering rule (FR-011, research.md R3) against the
   most recent `applied_to_state` attempt for the same
   `affected_record_id` before actually applying it.

**Outputs**: The persisted `VerificationAttempt`.

**Error conditions**:

| Condition | Behaviour |
|---|---|
| `action_type` has no registered `SuccessCondition` | Raises before calling `query_fn()` — a caller error, not a verification outcome |
| `query_fn()` itself raises | Persists a `VerificationAttempt` with `condition_result = Inconclusive` and no `query_result_json` beyond whatever error detail is available, then applies the bound rule as usual |

## Operation: ReconcileUnresolved

**Inputs**: `action_type`, `affected_record_id`, `query_fn`, `now`.

**Behaviour**: Identical to `Verify`, except it is explicitly the
"try again" call for an outcome already known to be `UNRESOLVED` — it
never re-invokes the original state-changing action (FR-007). Calling
this after the registered bound has already been reached is a no-op that
returns the existing resolved-or-unresolved `VerificationAttempt` without
issuing a new query.

**Outputs**: The persisted `VerificationAttempt` for this reconciliation
call, or the prior terminal one if the bound was already reached.

## Operation: ReportableOutcome

**Inputs**: `affected_record_id`.

**Behaviour**: Returns the most recent `applied_to_state` attempt's
classification for `affected_record_id` if it is `SUCCESS` or `FAILURE`.
Returns nothing (research.md R6 — no "pending" placeholder) if no such
attempt exists yet, including while an unresolved outcome is still being
reconciled.

**Outputs**: `SUCCESS`, `FAILURE`, or absent.

---

## Relationship to feature 005

`BookingService.confirm_ticketing()` is not modified by this feature to
call through this gate (research.md R7, plan.md Constitution Check
Principle XVI). The ticketing `SuccessCondition` shipped here reproduces
the same rule independently, proven against the same fixture shapes, so
that a *future* migration of `BookingService` onto this gate — should one
ever be undertaken as its own feature — has a condition already proven
equivalent to what it would be replacing.
