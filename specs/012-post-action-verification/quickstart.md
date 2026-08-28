# Quickstart: Post-Action Verification (012)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- No external sandbox access or VCR cassette needed — this feature is
  provider-agnostic (research.md); its tests exercise the gate against
  plain constructed query results, including the ticketing condition's
  query-result shapes already proven by spec 005's cassette

---

## Scenario 1 — Independent Confirmation Gate (US1, FR-001–004)

**Goal**: Confirm journey state is derived only from the query, never
from the action's own response, and that the ticketing condition
reproduces 005's own rule.

**Steps**:
1. Call `PostActionVerifier.verify()` for `action_type="ticketing"` with
   an `action_response` claiming success but a `query_fn` returning a
   result with empty `ticketNos` for every passenger.
2. Inspect the resulting `VerificationAttempt`.

**Expected**:
- `classification` is not `SUCCESS`, even though `action_response` claimed
  it — state is derived from `query_result_json`, not `action_response_json`.
- Re-running with a `query_fn` returning non-empty `ticketNos` for every
  passenger produces `classification = SUCCESS`.
- Feeding the exact query-result shapes from 005's
  `TestConfirmTicketingAllPassengers`/`TestConfirmTicketingPartialResult`/
  `TestConfirmTicketingTerminalError` fixtures through the ticketing
  condition reproduces the same classification 005 already asserts.

---

## Scenario 2 — Discrepancy Detection and Audit Trail (US2, FR-005, FR-009)

**Goal**: Confirm a discrepancy is recorded, and every attempt — clean or
not — lands in the audit trail.

**Steps**:
1. Call `verify()` with an `action_response` claiming success and a
   `query_fn` result showing failure.
2. Call `verify()` again with both agreeing.
3. Read all `VerificationAttempt` rows for the `affected_record_id`.

**Expected**:
- Step 1's attempt has `has_discrepancy = True`.
- Step 2's attempt has `has_discrepancy = False`.
- Both attempts exist in the audit trail — neither is only recorded
  because it was "interesting."

---

## Scenario 3 — Unresolved Outcome Handling (US3, FR-006, FR-007)

**Goal**: Confirm an inconclusive query stays unresolved, a persistent
not-found becomes failure at the bound, and reconciliation never repeats
the original action.

**Steps**:
1. Call `verify()` with a `query_fn` that raises (simulating a failed
   query) — confirm `classification = UNRESOLVED`.
2. Call `ReconcileUnresolved()` — confirm it issues a new query, not a
   repeat of the original action (no `action_response` parameter exists
   on this operation at all).
3. Call `verify()` repeatedly with a `query_fn` that consistently returns
   `NotFound`, until the registered bound is reached.
4. Repeat with a `query_fn` that consistently returns `Inconclusive`
   instead.

**Expected**:
- Step 1: `UNRESOLVED`.
- Step 3: the final attempt at the bound has `classification = FAILURE`.
- Step 4: the final attempt at the bound still has
  `classification = UNRESOLVED`.

---

## Scenario 4 — Cross-Surface Type Normalisation (US4, FR-008)

**Goal**: Confirm a status normalised by the condition doesn't produce a
false discrepancy.

**Steps**:
1. Call `has_discrepancy()` on the ticketing condition with an
   `action_response` reporting a status as one type and a `query_result`
   reporting the equivalent status as a different type.

**Expected**: No discrepancy — the condition normalises before comparing.

---

## Scenario 5 — Verified-Only Reporting (US5, FR-010)

**Goal**: Confirm no reportable outcome exists until verification
resolves.

**Steps**:
1. Call `ReportableOutcome()` for a record with only an `UNRESOLVED`
   attempt.
2. Call it again after a subsequent attempt resolves to `SUCCESS`.

**Expected**:
- Step 1: nothing returned (not a placeholder value).
- Step 2: `SUCCESS` returned.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_verification_gate.py \
                  tests/unit/test_ticketing_success_condition.py \
                  --tb=short --html=reports/report_012.html
```

**Expected**: All tests pass, with no network access required.

---

## References

- Internal service contract: [`contracts/verification_gate.md`](contracts/verification_gate.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- The concrete instance this generalises: spec 005's
  `BookingService.confirm_ticketing()`
