# Contract: ImpactEvaluationService

This feature exposes no new HTTP endpoint — it is triggered internally by
`WebhookService`'s existing wake mechanism (research.md R1), and its
outcomes surface to the traveller/operator through the existing event
stream (feature 006's SSE/journey console), the same way every other
feature's decisions already do. The contract below is the internal
service interface, in place of an API contract.

## `ImpactEvaluationService.evaluate_wake`

```python
def evaluate_wake(self, journey_id: str, wake_event: JourneyEvent) -> ImpactEvaluation:
```

**Preconditions**: `wake_event.event_type == EventType.WAKE_REQUESTED` and
`wake_event.journey_id == journey_id`.

**Behaviour** (in order):

1. Insert an `ImpactEvaluation` row with `status = IN_PROGRESS`,
   `triggering_event_id = wake_event.event_id`,
   `triggering_sequence = wake_event.sequence` (FR-001).
2. Load the journey fresh via `JourneyRepository.get_journey(journey_id)`
   (FR-001 — full rehydration; no state is taken from the caller beyond
   the event itself).
3. If the journey's departure has passed relative to `now`: mark the
   evaluation `INERT_PAST_DEPARTURE`, persist, return (research.md R9).
4. Look up the claimed change via
   `get_notifications_for_order(order_reference)` and extract
   `revisedArrivalTime` if a `schedule.changed` notification exists
   (research.md R3).
5. Evaluate every objective element (research.md R4). If satisfied: append
   `IMPACT_EVALUATION_SATISFIED`, mark `COMPLETED`, `objective_satisfied =
   True`, persist, return (User Story 2, FR-005).
6. If violated: append `OBJECTIVE_VIOLATED` with the quantified extent
   (FR-003, FR-004). Check for a newer `WAKE_REQUESTED` (research.md R8);
   if found, mark `SUPERSEDED`, append `IMPACT_EVALUATION_SUPERSEDED`,
   return.
7. Search for alternatives: `FlightSearchService.search(journey_id, now)`
   (FR-006, research.md R5). On `BudgetExhaustedError`, skip to step 9
   with `no_alternative_reason = "budget_exhausted"`.
8. Score (`ScoringService.score`) and verify in rank order
   (`VerificationService.verify`) until one comes back `VERIFIED`
   (research.md R6), re-checking for a newer wake between each verify
   call (research.md R8; supersede as in step 6 if found).
9. If a verified alternative was found: build the `Recommendation`
   (relative cost, one-sentence rationale, constraint-breach check against
   `TravelObjective`'s `HARD` fields — FR-009, FR-010, FR-011), persist,
   append `ALTERNATIVE_RECOMMENDED`, mark `COMPLETED`. Otherwise: mark
   `COMPLETED` with `objective_satisfied = False`,
   `no_alternative_reason` set, append `NO_ALTERNATIVE_FOUND` (FR-012).
10. Return the final `ImpactEvaluation`.

**Postconditions**: Exactly one `ImpactEvaluation` row exists for this
`wake_event`, in a terminal status (`COMPLETED`, `SUPERSEDED`, or
`INERT_PAST_DEPARTURE`) except in the case the caller's own process is
interrupted mid-evaluation (crash-safety/resumption is not handled by
this feature — Out of Scope, matches this feature's own scope boundary
around execution, which is feature 011's concern).

## `WebhookService.__init__` (extended)

```python
def __init__(
    self,
    repository: JourneyRepository | None = None,
    http_client: httpx.Client | None = None,
    event_service: EventService | None = None,
    on_wake: Callable[[str, JourneyEvent], object] | None = None,
) -> None:
```

No change to `receive()`. `confirm()` and `reconcile_active_journeys()`
each call `self._on_wake(journey_id, event)` immediately after appending
`WAKE_REQUESTED`, only if `on_wake` is not `None`.
