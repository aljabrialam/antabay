# Contract: Demonstration Capture Runner

This feature introduces no new HTTP endpoint. It calls existing services
in-process and two existing HTTP endpoints (disruption injection,
authorisation outcome) that features 008 and 006/010 already expose. The
contract below is the orchestration script's own interface, and the two
existing endpoints it depends on, in place of an API contract.

## `capture_runner` — orchestration script

```text
python -m scripts.capture_runner --scenario {primary|refusal}
```

**Behaviour, `--scenario primary`** (in order):

1. Parse the reference goal (`.antabay/demo-scenario.md`'s stated
   objective) via `ObjectiveParser`; create a fresh journey via
   `JourneyService.create_journey()` (research.md R1, R6).
2. `FlightSearchService.search()`; assert at least one option satisfies
   every hard constraint (research.md R8).
3. `ScoringService.score()`; assert the selected option satisfies every
   hard constraint, and that at least one eliminated candidate satisfied
   the numeric constraints (arrival, budget) but was excluded on the
   overnight-connection rule (FR-005's first emphasised moment).
4. `VerificationService.verify()` → `BookingService.create_order()` →
   `.submit_payment()` → `.confirm_ticketing()`; assert `confirmed is
   True` before proceeding (research.md R7 — this is the ordering gate).
5. `DisruptionInjectorService.inject()` (feature 008, called directly —
   research.md R10) with the reference revised arrival time; assert the
   injected notification was accepted.
6. Trigger the wake-driven impact evaluation (feature 009) immediately
   and scoped to only this journey (research.md R12) — the script appends
   its own `WAKE_REQUESTED` event via `EventService.append()` and calls
   `ImpactEvaluationService.evaluate_wake(journey_id, wake_event)`
   directly, never sweeping every active journey in the database and
   never waiting on the live server's 300s reconciliation timer. Assert
   `objective_satisfied is False` and `latest_arrival` is among the
   violated constraints (FR-005's second emphasised moment).
7. Assert a `Recommendation` was produced and trace it to a `VERIFIED`
   result (feature 009's own NFR-001).
8. `EventService.record_auth_outcome()` with `outcome="approved"`
   (feature 006/010, called directly — research.md R10; FR-005's third
   emphasised moment, FR-008); assert the outcome was recorded.
9. `RecoveryExecutionService.execute()` (feature 011); assert
   `status == COMPLETED` and `replacement_outcome == SUCCEEDED`.
10. On every assertion holding: export the run's full event stream
    (research.md R4) to
    `backend/tests/fixtures/demo_captures/<journey_id>.json`. On any
    assertion failing: stop immediately, report the failed step, and do
    not export.

**Behaviour, `--scenario refusal`** (research.md R9):

Steps 1–7 identical, against its own separate fresh journey
(research.md R6). Step 8 calls `record_auth_outcome(..., outcome=
"refused")` instead. Assert zero spend occurred (no new
`Order`/`PaymentAttempt` created for this journey after the refusal) and
that the refusal was durably recorded (an `AUTHORISATION_OUTCOME` event
with `outcome == "refused"` exists). The script stops here — no step 9.

**Exit status**: `0` only if every assertion for the requested scenario
held; non-zero otherwise, with the failed step named on stderr.

## Existing services this script depends on (called directly, unmodified — research.md R10)

- `DisruptionInjectorService.inject(journey_id, revised_arrival_time, now)`
  — the same call `POST /operator/disruptions` makes internally.
- `EventService.record_auth_outcome(journey_id, request_id, outcome)` —
  the same call `POST /journeys/{id}/authorisation/{request_id}` makes
  internally.
- `ImpactEvaluationService.evaluate_wake(journey_id, wake_event)`, given a
  locally-constructed `WAKE_REQUESTED` event for just this journey
  (research.md R12) — triggers impact evaluation immediately and scoped
  to this run alone, instead of waiting on the live 300s reconciliation
  timer or sweeping every active journey in the database.

A real operator using the actual HTTP endpoints (curl, the frontend) gets
the identical outcome — these are the same underlying calls, just
invoked directly rather than through their own HTTP layer, consistent
with how every other feature in this codebase composes another
feature's service rather than calling its own routes.

## `capture_export` — event stream export/import

```text
python -m scripts.capture_export export --journey-id <id> --out <path>
python -m scripts.capture_export promote --file <path>
python -m scripts.capture_export load --file <path>
```

- `export`: writes the journey's full event stream to `<path>` in the
  shape `data-model.md`'s Captured Event Stream describes.
- `promote`: updates `canonical.json` to point at `<path>` — a
  deliberate, separate step (FR-013; never automatic on a run passing).
- `load`: creates a fresh journey and re-inserts `<path>`'s events into
  it (extending `seed_console_fixture.py`'s existing `seed_replay`
  logic, research.md R4), for reproducing footage without the live
  provider (FR-011).

## Video capture (Playwright, extends the existing `frontend/e2e/` scaffold)

Two new spec files, each opening the existing replay page for one
surface and recording video for the duration:

- Operator: `GET /journey/{id}/replay?speed=...` (existing route)
- Traveller: `GET /journey/{id}/traveller/replay?speed=...` (new route,
  research.md R5)

Each spec holds on the three emphasised moments with an explicit wait on
the corresponding DOM state (the rejection entry, the objective-violated
statement, the authorisation panel) before letting the replay continue,
satisfying FR-005/FR-006 without slowing the underlying replay's own
global speed.
