# Quickstart: Objective Impact Evaluation and Alternative Discovery (009)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- Features 002 (`FlightSearchService`), 003 (`ScoringService`), 004
  (`VerificationService`), 006 (`EventService`), 007 (`WebhookService`),
  and 008 (`DisruptionInjectorService`) must already be present (they are,
  in `master`)
- No new external sandbox access beyond what 002/004 already require —
  this feature makes no Atlas call that isn't already made through those
  reused services

---

## Scenario 1 — Wake, Rehydrate, Evaluate (US1, FR-001–004)

**Goal**: Confirm evaluation reconstructs the journey from durable
storage and states a violation in objective terms, quantified.

**Steps**:
1. Seed a journey with a `MONITORING` state, a `HARD` `latest_arrival`
   objective constraint, and a real order.
2. Inject a schedule change via
   `DisruptionInjectorService.inject(journey_id, revised_arrival_time, now)`
   where `revised_arrival_time` is after `latest_arrival`.
3. Invoke `WebhookService(...).reconcile_active_journeys(now)` with
   `ImpactEvaluationService.evaluate_wake` wired as `on_wake`.
4. Inspect the resulting `ImpactEvaluation` row and the appended
   `OBJECTIVE_VIOLATED` event.

**Expected**:
- The evaluation reads `journey.objective` fresh from the repository —
  no reliance on any journey instance held before the wake.
- `objective_satisfied = False`, `violated_constraints = ["latest_arrival"]`,
  `violation_extent` states the specific overage (e.g. minutes late).
- The event's payload names the objective element, not the raw flight fact.

---

## Scenario 2 — No Action When Satisfied (US2, FR-005)

**Goal**: Confirm an improving or neutral change triggers no search.

**Steps**:
1. Repeat Scenario 1's setup, but inject a `revised_arrival_time` earlier
   than the original (an improvement).
2. Trigger the wake as in Scenario 1, step 3.

**Expected**: `objective_satisfied = True`, `IMPACT_EVALUATION_SATISFIED`
appended, no `SearchRecord`/`ScoringRun`/`VerificationResult` created for
this evaluation.

---

## Scenario 3 — Search, Score, Verify, Recommend (US3, FR-006–011)

**Goal**: Confirm a violation drives a full alternative-discovery cycle
using the existing services unmodified, ending in exactly one verified
recommendation.

**Steps**:
1. Repeat Scenario 1's setup (a genuine violation).
2. Seed the sandbox/recorded search response with at least one option
   that would satisfy the objective.
3. Trigger the wake.
4. Inspect the resulting `Recommendation`.

**Expected**:
- `FlightSearchService.search()` and `ScoringService.score()` are called
  with the journey's unmodified original objective (research.md R5–R6).
- The recommended option's `Recommendation.verification_id` traces to a
  `VerificationResult` with `outcome == VERIFIED` — never recommended off
  the search/score result alone.
- `cost_relative_description` is relative (e.g. `"+$18"`), never an
  absolute price.
- `rationale` is one sentence.
- The journey's `call_budget` decremented by exactly the number of
  search/verify calls made.

---

## Scenario 4 — No Alternative, Reported Plainly (US3, FR-012)

**Goal**: Confirm a violation with no viable alternative produces an
explicit report, and that budget exhaustion and freshness-lapse both fold
into the same reported outcome.

**Steps**:
1. Repeat Scenario 1's setup, but seed the search response with zero
   options that satisfy the objective (or exhaust the journey's
   `call_budget` before search, or contrive every candidate's
   verification to lapse before recommendation).
2. Trigger the wake for each variant.

**Expected**: Each variant produces a `NO_ALTERNATIVE_FOUND` event and an
`ImpactEvaluation` with `objective_satisfied = False` and no
`Recommendation` row — the traveller-facing report is identical across
all three causes (`no_alternative_reason` differs internally only).

---

## Scenario 5 — Concurrency and Boundaries (Edge Cases, FR-002)

**Goal**: Confirm a second wake interrupts an in-progress evaluation, and
a past-departure journey stays inert.

**Steps**:
1. Start an evaluation for a journey (Scenario 1 setup), then — before it
   reaches a terminal status — append a second `WAKE_REQUESTED` event for
   the same journey with a higher sequence number.
2. Separately, trigger a wake for a journey whose `departure_date` has
   already passed.

**Expected**:
- Step 1: the first evaluation's row ends `SUPERSEDED`; the second
  produces its own fresh, independent `COMPLETED` evaluation.
- Step 2: the evaluation row is `INERT_PAST_DEPARTURE`; no search, score,
  or verification call is made.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_impact_evaluation_service.py \
                  tests/contract/test_impact_evaluation_wiring.py \
                  --tb=short --html=reports/report_009.html
```

**Expected**: All tests pass, with recorded/cassette-backed responses for
`FlightSearchService`/`VerificationService` calls (no live sandbox call in
CI). The existing `test_webhook_service.py`/`test_webhook_reconciliation.py`
(007), `test_disruption_injector_service.py` (008), `test_flight_search.py`
(002), `test_scoring_service.py` (003), and `test_verification_service.py`
(004) suites continue to pass unmodified.

---

## References

- Internal service contract: [`contracts/impact_evaluation_service.md`](contracts/impact_evaluation_service.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions, including the wake-trigger gap this feature resolves:
  [`research.md`](research.md)
- The trigger this feature subscribes to: spec 007's
  `WebhookService.reconcile_active_journeys()`/`confirm()`
- The claim source this feature reads: spec 008's `schedule.changed`
  envelope (`data.revisedArrivalTime`)
