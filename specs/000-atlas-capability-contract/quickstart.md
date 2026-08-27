# Quickstart: Validating the Atlas Capability Contract

**Feature**: 000-atlas-capability-contract
**Date**: 2026-08-28

This guide describes how to verify that the contract enforcement layer is
working correctly. It covers both local validation and the CI gate.

---

## Prerequisites

- Python 3.11 installed
- Project dependencies installed (`pip install -e ".[dev]"` from `backend/`)
- `ATLAS_CLIENT_ID` and `ATLAS_CLIENT_SECRET` set in environment (Tier 2
  only — not needed for Tier 1)
- Existing fixtures present at `fixtures/atlas/`:
  - `sel_tyo_search.json`
  - `sel_tyo_verify.json`
  - `webhook_order_ticketed.json`

---

## Tier 1: Contract tests against recorded fixtures (no live calls)

These run on every push. No sandbox credentials required.

```bash
cd backend
pytest tests/contract/ -v --html=reports/contract.html --self-contained-html
```

**Expected outcome**: All tests pass. HTML report at `backend/reports/contract.html`.

**What the tests prove**:

| Test file | What passes | Requirement |
|-----------|------------|-------------|
| `test_allowlist.py` | `search.do` accepted; `suggestFlight.do` rejected | FR-001, FR-002 |
| `test_models.py` | `routing.fid` accepted; `routing.fareCode` raises; `orderStatus` normalised from both sources | FR-003, FR-006 |
| `test_pricing.py` | `canonical_total_price(66.43, 23.96, 0.00)` returns `90.39` | FR-005 |
| `test_errors.py` | `318` → `ReconcilableOutcome` with `duplicate_orders`; `900` → terminal | FR-007, FR-008 |
| `test_budget.py` | Rate-limit hold respected; no retry before `retryAfter` | FR-010, FR-011 |
| `test_identifiers.py` | `OpaqueId` stores and returns value unchanged; no mutation API | FR-004 |
| `test_freshness.py` | Offer window expired-on-receipt detected; three clock types tracked | FR-012 |
| `test_telemetry.py` | `CallRecord` produced for every call with endpoint, outcome, elapsed_ms | FR-009 |

---

## Build-time enforcement check (Mypy)

```bash
cd backend
mypy atlas/ --strict
```

**Expected outcome**: Zero errors.

To verify enforcement works, temporarily add a reference to an unknown
field (e.g. `routing.fare_code`) in any file under `backend/atlas/` and
re-run. Mypy must report an attribute error. Revert the change.

---

## Tier 2: Live sandbox run (captures new fixtures)

Run on demand or at least daily. Requires sandbox credentials.

```bash
cd backend
ATLAS_CLIENT_ID=... ATLAS_CLIENT_SECRET=... \
  pytest tests/contract/ -v --record-mode=new_episodes \
  --html=reports/contract-tier2.html --self-contained-html
```

**Expected outcome**: All tests pass against live Atlas sandbox. New VCR
cassettes written to `fixtures/atlas/cassettes/`. Commit the cassettes.

**When to run Tier 2**:
- After any change to `backend/atlas/models/`
- After any update to `.antabay/atlas-capability-map.md`
- If Tier 1 and Tier 2 results diverge (re-capture is mandatory per
  Constitution XI)
- At least once daily in the scheduled CI job

---

## Demonstrating the contract live (three-minute recording checklist)

To demonstrate this feature in a recording:

1. **Show the allowlist rejection**: Run `mypy atlas/` with a planted unknown
   endpoint reference. Show the error. Revert.

2. **Show the field rejection**: Run `mypy atlas/` with a planted unknown
   field access (`routing.fare_code`). Show the error. Revert.

3. **Show the price test passing**: Run `pytest tests/contract/test_pricing.py -v`.
   Show the green result and the assertion `90.39`.

4. **Show the duplicate-booking test passing**: Run
   `pytest tests/contract/test_errors.py -v -k "318"`. Show the reconcilable
   outcome and the surfaced order reference.

5. **Show the rate-limit hold test passing**: Run
   `pytest tests/contract/test_budget.py -v -k "rate_limit"`. Show that no
   retry is initiated before the hold expires.

**On screen during the recording**:
- Terminal showing `mypy` error on invalid field access
- Terminal showing `pytest` green across all contract tests
- The HTML test report open in a browser

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Mypy error on valid field | Model not yet imported in `__init__.py` | Add re-export to `backend/atlas/__init__.py` |
| Fixture not found | Cassette not generated yet | Run Tier 2 once to capture |
| `extra = "forbid"` ValidationError on a known field | Field name snake_case mismatch | Check `alias` or `model_config` in the Pydantic model |
| `orderStatus` comparison fails | Comparing `OrderStatus` to raw `int` or `str` | Use `OrderStatus.TICKETED`, not `2` or `"2"` |
