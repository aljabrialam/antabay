# Quickstart: Authorisation Policy Engine (010)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- No external sandbox access needed — this feature makes no external call
  of any kind (FR-007); its tests exercise the engine directly and, for
  the enforcement lifecycle, against a file-backed SQLite journey store
- Feature 006 must already be present (it is, in `master`) — this feature
  reads and writes through its `EventService`/`JourneyEvent` mechanism

---

## Scenario 1 — Deterministic Classification (US1, FR-001–002, FR-007–008)

**Goal**: Confirm every proposed action gets classified before execution,
the classification never varies, no LLM is consulted, and the decision
names the rule(s) that produced it.

**Steps**:
1. Construct a `ProposedAction` that triggers no rule (`cost_amount=0`,
   `cancels_or_voids_booking=False`, `is_reversible=True`,
   `breaches_hard_constraint=False`).
2. Call `AuthorisationPolicyEngine.evaluate()` on it 100 times.
3. Construct a `ProposedAction` that triggers `AUTH-MONEY` and
   `AUTH-CONSTRAINT` simultaneously.
4. Call `evaluate()` on it once.

**Expected**:
- Step 2: all 100 results are `classification = permitted_autonomously`,
  `matched_rules = []` — identical every time.
- Step 4: `classification = requires_authorisation`,
  `matched_rules = ["AUTH-MONEY", "AUTH-CONSTRAINT"]` — both rules named,
  not just one.
- Inspecting `evaluate()`'s implementation and imports confirms no
  language-model client is imported or called anywhere in the module.

---

## Scenario 2 — The Four Rules, Independently, Both Directions (US2, FR-003–006, NFR-004)

**Goal**: Confirm each rule fires when its condition is met and does not
fire when it isn't — tested in isolation from the other three.

**Steps**: For each rule, construct one `ProposedAction` that triggers
only that rule (all other fields at their non-triggering default) and one
that triggers none, and call `evaluate()` on each.

**Expected**: Each rule's triggering case classifies as
`requires_authorisation` with exactly that rule in `matched_rules`; its
non-triggering case classifies as `permitted_autonomously`.

---

## Scenario 3 — Request, Response, and Enforcement (US3, FR-009–012)

**Goal**: Confirm a requires-authorisation classification produces a
correctly-shaped request on the existing event stream, that silence and
explicit refusal both block execution, and that a grant permits it.

**Steps**:
1. Call `RequestIfRequired()` for an action that triggers `AUTH-MONEY`.
2. Read the resulting `AUTHORISATION_REQUESTED` event's payload.
3. Call `EnforceAuthorised()` before any response — confirm `False`.
4. Call the existing `EventService.record_auth_outcome(..., "refused")`
   for that request, then call `EnforceAuthorised()` again.
5. Repeat from step 1 with a fresh `action_id`, but call
   `record_auth_outcome(..., "approved")` instead, then call
   `EnforceAuthorised()`.

**Expected**:
- Step 2: payload states the action's description, cost, and objective
  effect, and carries `rule_id = "AUTH-MONEY"`.
- Step 3: `False` (unanswered).
- Step 4: `False` (explicitly refused).
- Step 5: `True` (granted, cost unchanged).

---

## Scenario 4 — Authorisation Scope and Staleness (US4, FR-013–014)

**Goal**: Confirm a grant does not leak to a subsequent action, and a
cost change voids a prior grant.

**Steps**:
1. Grant authorisation for `action_id="a1"` at `cost_amount=50`.
2. Call `EnforceAuthorised(action_id="a2", current_cost_amount=50)` — a
   different action, same cost.
3. Call `EnforceAuthorised(action_id="a1", current_cost_amount=75)` — same
   action, changed cost.
4. Read the resulting event stream.

**Expected**:
- Step 2: `False` — `a1`'s grant does not apply to `a2`.
- Step 3: `False`, and a new `AUTHORISATION_VOIDED` event now exists for
  `a1`'s original request, recording `granted_cost` and `current_cost`.
- A fresh `RequestIfRequired()` call for `a1` at the new cost issues a new
  authorisation request rather than reusing the voided one.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_authorisation_policy_engine.py \
                  tests/unit/test_authorisation_enforcement.py \
                  --tb=short --html=reports/report_010.html
```

**Expected**: All tests pass, with no network access and no language-model
call required. The existing `test_auth_contract.py` and `test_auth_gate.py`
suites (feature 006) continue to pass unmodified, confirming this feature
did not disturb the request/response surface it builds on.

---

## References

- Internal service contract: [`contracts/authorisation_policy.md`](contracts/authorisation_policy.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- The existing infrastructure this generalises on top of: `journey/services/event_service.py`'s `record_auth_outcome()`, `journey/api/routers/events.py`'s `respond_authorisation()`, both from feature 006
