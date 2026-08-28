# Quickstart: Recovery Execution (011)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- Features 004 (`VerificationService`), 005 (`BookingService`), 006
  (`EventService`), 009 (`Recommendation`), 010
  (`AuthorisationPolicyEngine`) must already be present (they are, in
  `master`)
- Tests construct the "authorisation already granted" precondition
  directly (research.md R2) — no live bridge from 009 to 010 exists yet
- Cancellation's `void.do` call and success predicate are provisional
  pending a Tier 2 sandbox capture (research.md R1) — flagged, not hidden

---

## Scenario 1 — Execute Only What Was Authorised, At The Verified Price (US1, FR-001–002)

**Goal**: Confirm execution is refused without a matching authorisation,
and abandoned if the alternative's price has changed since authorisation.

**Steps**:
1. Seed a journey, a `Recommendation` (from a constructed `ScoredOption`/
   `VerificationResult`), and grant authorisation for it
   (`action_id = recommendation_id`, `cost_amount` = the recommendation's
   verified price at grant time).
2. Call `RecoveryExecutionService.execute(recommendation_id, now)` with no
   authorisation granted at all.
3. Separately, grant authorisation, then change the option's price before
   calling `execute()`.

**Expected**:
- Step 2: `status = ABANDONED`, `abandonment_reason = "not_authorised"`.
- Step 3: `status = ABANDONED`, `abandonment_reason = "price_changed"`,
  and no order is created.

---

## Scenario 2 — Replacement Secured Before Original Released (US2, FR-003–005, FR-008–009)

**Goal**: Confirm the replacement is created, paid, and independently
ticketing-confirmed before the superseded booking's cancellation is ever
initiated, and the journey's current-order pointer only updates after
that confirmation.

**Steps**:
1. Seed a journey with an existing (superseded) order, a `Recommendation`,
   and a granted authorisation at the verified price.
2. Call `execute()`.
3. Inspect the `RecoveryExecution` row and `journeys.current_order_no`.

**Expected**:
- `replacement_outcome = SUCCEEDED`, `replacement_order_no` set.
- `current_order_no` equals the replacement's order_no only after this
  call — never observably set to the replacement before its ticketing was
  confirmed.
- A `CancellationAttempt` exists for the superseded `order_no`, created
  only after the replacement's ticketing confirmation.

---

## Scenario 3 — Partial Outcome Surfaced, Never Concealed (US3, FR-006–007)

**Goal**: Confirm a cancellation failure after a successful replacement is
recorded and surfaced explicitly.

**Steps**:
1. Repeat Scenario 2's setup.
2. Force the cancellation reconciliation query to still show a fully
   ticketed superseded booking (i.e., cancellation did not take).

**Expected**: `replacement_outcome = SUCCEEDED`,
`cancellation_outcome = FAILED`, `status = COMPLETED` (not `ABANDONED` —
the recovery itself succeeded; only cancellation did not), and this exact
state is queryable, not folded into a generic failure.

---

## Scenario 4 — Never Leave The Traveller Without a Confirmed Booking (Edge Cases, FR-008)

**Goal**: Confirm a replacement-creation or payment failure leaves the
superseded booking untouched.

**Steps**:
1. Repeat Scenario 2's setup.
2. Force `BookingService.create_order` (or `.submit_payment`) to fail.

**Expected**: `status = ABANDONED`,
`abandonment_reason` in (`replacement_creation_failed`,
`replacement_payment_failed`), `cancellation_outcome = NOT_ATTEMPTED`, and
no `CancellationAttempt` row exists — the superseded booking was never
touched.

---

## Scenario 5 — Duplicate Trigger Refused, Final Position Reported (US3, FR-012, FR-014)

**Goal**: Confirm a second `execute()` call against the same
`recommendation_id` is refused, and a successful recovery states the
final position in objective terms.

**Steps**:
1. Repeat Scenario 2's setup and call `execute()` once, successfully.
2. Call `execute()` again with the same `recommendation_id`.

**Expected**: Step 2 raises `RecoveryAlreadyAttemptedError` — no second
`RecoveryExecution` row, no second replacement order. Step 1's
`final_position_description` names the objective element the recovery
restored (e.g. "latest_arrival now satisfied"), not a raw flight fact.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_recovery_execution_service.py \
                  --tb=short --html=reports/report_011.html
```

**Expected**: All tests pass, with recorded/constructed responses for
`BookingService`/`VerificationService`/`AuthorisationPolicyEngine` calls
(no live sandbox call in CI). The existing `test_booking_service.py`
(005), `test_verification_service.py` (004),
`test_authorisation_policy_engine.py` (010), and
`test_impact_evaluation_service.py` (009) suites continue to pass
unmodified.

---

## References

- Internal service contract: [`contracts/recovery_execution_service.md`](contracts/recovery_execution_service.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions, including the two disclosed gaps this feature works
  around (no verified cancellation endpoint; no 009→010 bridge):
  [`research.md`](research.md)
- The recommendation this feature consumes: spec 009's `Recommendation`
- The authorisation this feature checks but never requests: spec 010's
  `AuthorisationPolicyEngine.enforce_authorised()`
