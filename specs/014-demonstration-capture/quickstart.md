# Quickstart: End-to-End Demonstration Capture (014)

## Prerequisites

- Backend and frontend dev environments already set up (`backend/.venv`,
  `frontend/node_modules`)
- `DISRUPTION_INJECTOR_ENABLED=true` and `DISRUPTION_INJECTOR_TOKEN=<token>`
  set in the backend environment the capture runs against (feature 008's
  existing fail-closed defaults)
- Live sandbox credentials configured for a live-sandbox run; none needed
  for a recorded-events run (research.md R4)

---

## Scenario 1 — Unattended Primary Run, Verified at Every Step (US1, FR-001, FR-004, FR-007, FR-008)

**Goal**: Confirm the full pipeline runs unattended end to end and stops
immediately on the first unmet expectation, never continuing past it.

**Steps**:
1. `python -m scripts.capture_runner --scenario primary`
2. Inspect the exit status and the step-by-step log.

**Expected**:
- Exit status `0`; every step from objective parsing through recovery
  completion is logged as passed.
- Re-running immediately succeeds again without any manual reset
  (NFR-003) — each invocation creates its own fresh journey
  (research.md R6).
- Forcing one assertion to fail (e.g. temporarily disabling the
  disruption injector) makes the script stop at that exact step with a
  non-zero exit status — it does not continue into later steps.

---

## Scenario 2 — Operator-Console Recording, Paced for a Viewer (US2, FR-002, FR-005, FR-006, FR-012)

**Goal**: Confirm a legible video is produced from a verified run, with
the three emphasised moments held long enough to read.

**Steps**:
1. Complete Scenario 1 successfully.
2. Run the operator-console Playwright capture spec against that run's
   `journey_id`.
3. Review the resulting video file.

**Expected**:
- One video file covering the full replay, named with the producing
  `journey_id`.
- The rejection of the option satisfying the numeric constraints, the
  objective-violated statement, and the authorisation gate are each held
  on screen for a deliberate pause.
- Playback pace is legible — not a blur of machine-speed updates.

---

## Scenario 3 — Reproduce Footage From Recorded Events, No Network (US3, FR-010, FR-011)

**Goal**: Confirm a recording can be regenerated from a stored capture
alone, with no live provider access.

**Steps**:
1. `python -m scripts.capture_export export --journey-id <id> --out backend/tests/fixtures/demo_captures/<id>.json`
2. With network access disabled, `python -m scripts.capture_export load --file backend/tests/fixtures/demo_captures/<id>.json`
3. Run the operator-console Playwright capture spec against the newly
   loaded journey.

**Expected**: The resulting recording shows the same sequence of steps
and the same three emphasised moments as the original — zero network
calls made during the load or the replay.

---

## Scenario 4 — Handheld Traveller Recording of the Same Journey (US4, FR-003)

**Goal**: Confirm a second recording shows the traveller-facing surface,
not the operator console, for the same underlying journey.

**Steps**:
1. Complete Scenario 1 or load a capture per Scenario 3.
2. Run the traveller-view Playwright capture spec (handheld viewport)
   against that same `journey_id`.

**Expected**: The recording shows `TravellerConsole` (objective in plain
language, current state, the authorisation tap when relevant) — not the
operator console's event log or call-budget panel — at a handheld
viewport size, and traces to the same `journey_id` as the operator
recording (SC-003).

---

## Scenario 5 — Refusal Path, Isolated From the Approval Run (US5, FR-009, FR-014)

**Goal**: Confirm refusing authorisation results in zero spend and a
durable record, on its own independent journey.

**Steps**:
1. `python -m scripts.capture_runner --scenario refusal`
2. Inspect the resulting journey's orders/payments and its event log.

**Expected**: Exit status `0`; zero `Order`/`PaymentAttempt` rows exist
for this journey after the refusal step; an `AUTHORISATION_OUTCOME` event
with `outcome == "refused"` is present; this journey's `journey_id`
differs from any primary-run journey — no shared booking or session
(FR-014).

---

## Running the Test Suite

```bash
cd backend && .venv/bin/python -m pytest tests/ --tb=short --html=reports/report_014.html
cd frontend && npx playwright test
```

**Expected**: All tests pass, including the new capture-runner assertion
tests and the new/extended Playwright specs. Existing suites for every
prior feature continue to pass unmodified.

---

## References

- Internal contract: [`contracts/capture_runner.md`](contracts/capture_runner.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- Reference sequence and expected values:
  `.antabay/demo-sequence-diagram.md`, `.antabay/demo-scenario.md`
