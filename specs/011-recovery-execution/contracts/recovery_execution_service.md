# Contract: RecoveryExecutionService

No new HTTP endpoint — execution is triggered by whatever hosts the agent
loop calling this service directly once a recommendation is authorised
(the same "no endpoint of its own" shape as feature 009). Outcomes surface
through the existing event stream (feature 006).

## `RecoveryExecutionService.execute`

```python
def execute(self, recommendation_id: str, now: datetime) -> RecoveryExecution:
```

**Behaviour** (in order):

1. Look up the `Recommendation` by `recommendation_id`
   (`RecommendationNotFoundError` if unknown).
2. Refuse a second attempt: if a `RecoveryExecution` already exists for
   this `recommendation_id`, raise `RecoveryAlreadyAttemptedError`
   (FR-014, research.md R5) — checked before anything else runs.
3. Insert a `RecoveryExecution` row, `status = IN_PROGRESS`.
4. Fresh re-verification (FR-002, research.md R2):
   `VerificationService.verify(journey_id, recommendation.option_id, now)`.
   If the outcome is not `VERIFIED`, mark `ABANDONED` with
   `abandonment_reason = "price_changed"` (on `PRICE_CHANGED`) or
   `"alternative_unavailable"` (on `UNAVAILABLE`/other), persist, return.
5. Authorisation check (FR-001, research.md R2):
   `AuthorisationPolicyEngine.enforce_authorised(journey_id, action_id=recommendation_id, current_cost_amount=<fresh total from step 4>)`.
   If `False`, mark `ABANDONED` with `abandonment_reason = "not_authorised"`,
   persist, return.
6. Capture `superseded_order_no = get_order_no_for_journey(journey_id)`
   (research.md R3) before any replacement-booking call.
7. `BookingService.create_order(journey_id, option_id, now)`. If
   `outcome != CREATED`, mark `ABANDONED`,
   `abandonment_reason = "replacement_creation_failed"`,
   `replacement_outcome = FAILED`, `cancellation_outcome = NOT_ATTEMPTED`,
   persist, return — the superseded booking is untouched (FR-008).
8. `BookingService.submit_payment(journey_id, order.order_no, now)`. If
   `outcome != SUCCESS`, same as step 7 but
   `abandonment_reason = "replacement_payment_failed"`.
9. `BookingService.confirm_ticketing(journey_id, order.order_no, now)`
   (FR-004, research.md R3). If `.confirmed` is not `True`, treat as step
   7/8's failure case (`replacement_creation_failed`-equivalent — the
   replacement never became a real booking the traveller can rely on).
10. Replacement confirmed: `replacement_order_no` set,
    `replacement_outcome = SUCCEEDED`. `set_current_order(journey_id, order.order_no)`
    (FR-009, research.md R4).
11. Initiate cancellation of `superseded_order_no` (FR-005, research.md
    R1): best-effort `void.do` call, persisted as a `CancellationAttempt`,
    then an independent `queryOrderDetails.do` reconciliation query
    (FR-006). `cancellation_outcome = SUCCEEDED` if
    `confirmed_cancelled` is `True`, else `FAILED` — recorded and
    surfaced either way (FR-007), never concealed.
12. Build `final_position_description` in objective terms (FR-012),
    mark `status = COMPLETED` regardless of the cancellation outcome
    (FR-010, research.md R6 — the journey was never out of `MONITORING`
    to begin with), persist, return.

**Postconditions**: Exactly one `RecoveryExecution` row exists for this
`recommendation_id`, in a terminal status. The traveller holds at least
one confirmed booking in every outcome (FR-008): either the original
(any abandonment or replacement-failure path) or the replacement (any
path that reaches step 10), never neither.

## Audit trail (FR-011)

Every step above appends an event (new `EventType` members,
data-model.md is silent on these since they belong to
`journey/models/events.py` — see plan.md's Project Structure), including
the specific `recommendation_id` and, transitively via the authorisation
check's own event log, the authorisation that permitted the attempt.
