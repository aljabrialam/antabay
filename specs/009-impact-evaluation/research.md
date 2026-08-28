# Research: Objective Impact Evaluation and Alternative Discovery

## R1 — Wake trigger: reuse the reconciliation sweep, not `confirm()`

**Decision**: `ImpactEvaluationService` is invoked from `WebhookService`'s
existing `reconcile_active_journeys()` periodic sweep (`journey/services/webhook_service.py:161-188`),
via a new optional `on_wake` callback parameter on `WebhookService`, rather
than by adding a new "schedule.changed" entry to `_EVENT_TYPE_HANDLERS`.

**Rationale**: A concrete trace through the current code shows `confirm()`
can never fire `WAKE_REQUESTED` for a `schedule.changed` notification
today: `confirmation_triggered` (`webhook_service.py:74-81`) requires
`declared_event_type in _EVENT_TYPE_HANDLERS`, and that map contains only
`"order.ticketed"`. The disruption injector's own `inject()` already
guards on this (`if notification.confirmation_triggered: ... confirm()`),
so a simulated schedule-change notification is received and persisted,
but `confirm()` is never called for it — no `WAKE_REQUESTED` is produced
through that path. `reconcile_active_journeys()`, by contrast, fires
`WAKE_REQUESTED` for every active journey with an order on every sweep,
unconditionally of what notification (if any) is pending — this is
precisely what feature 007's FR-010 built it for ("independent of any
notification... delivery is not guaranteed"). It is the only trigger path
that actually reaches a journey after a schedule-change notification is
recorded.

**Alternatives considered**:
- *Register "schedule.changed" in `_EVENT_TYPE_HANDLERS` with a new
  `SuccessCondition`.* Rejected: this would require a way to confirm the
  claim against the provider's own interface (007 FR-004), and no
  verified Atlas endpoint returns current flight schedule data for a
  booked order (see R2) — building this condition would mean confirming
  only that the order still exists, not the schedule-change claim itself,
  which is no better than what the reconciliation sweep already achieves,
  at the cost of modifying 007's dispatch table (which both 007's and
  008's own specs explicitly leave to whichever feature needs it — this
  research makes the call that the sweep already suffices without that
  change).
- *Poll for unconsumed `WAKE_REQUESTED` events on an interval, independent
  of `WebhookService`.* Rejected as needless duplication: `WebhookService`
  already runs exactly this kind of interval loop (`_reconciliation_loop`
  in `journey/api/main.py:22-26`); a second, parallel polling loop would
  duplicate that scheduling logic for no benefit.

**Wiring**: `WebhookService.__init__` gains `on_wake: Callable[[str, JourneyEvent], None] | None = None`.
Both `confirm()` (line ~116-126) and `reconcile_active_journeys()` (line
~179-188) invoke it immediately after their existing `self._events.append(...,
EventType.WAKE_REQUESTED, ...)` call, passing the journey_id and the
appended `JourneyEvent`. This costs nothing when `on_wake` is `None`
(existing callers/tests are unaffected) and means `confirm()` will also
reach `ImpactEvaluationService` immediately, without waiting for the next
sweep, for any event type that does get a handler registered in future.
At composition time, `journey/api/main.py`'s `_reconciliation_loop` and
`journey/api/routers/webhooks.py`'s `get_webhook_service()` both construct
their own `WebhookService()` instance today (two separate instances) —
both must be given the same wiring: construct `ImpactEvaluationService`
once and pass `on_wake=impact_evaluation_service.evaluate_wake` into both.

## R2 — No endpoint exists to query a booked order's current flight schedule

**Finding**: `queryOrderDetails.do` (the only "current order state" query
in this codebase — `webhook_service.py:132-137`, `booking_service.py:277-306`)
returns ticketing/payment/status fields only (`.antabay/atlas-capability-map.md`
§7b's verified field list: `orderStatus, ticketStatus, paxTicketInfos[],
payTime, createdTime, updatedTime, tktLimitTime, ...`) — no departure/arrival
time or segment data. `depTime`/`arrTime` exist only on `search.do`/`verify.do`
routing segments (searchable options), never on a booked order's query
response. The capability map is explicit (§2): "No flight-change endpoint
exists in the API Reference... Schedule Change event's `type` string and
`data` shape [are] not yet verified — do not build against."

**Decision**: The evaluation compares the objective against the specific
value the schedule-change notification itself claims
(`data.revisedArrivalTime` on the `schedule.changed` envelope — see R3),
not against an independently re-queried value, because no capability to
re-query that specific value exists. What *is* independently confirmed is
that the order itself still exists and is valid — the same
`queryOrderDetails.do` check `reconcile_active_journeys()` already
performs as part of firing the wake in the first place (R1). This is a
disclosed limitation, not a shortcut: Constitution Principle I (Truth
Over Fluency) prohibits fabricating data or calling an undocumented
endpoint; it does not require verification depth beyond what the
published API actually supports. Feature 007's own FR-003 already
establishes the discipline this leans on: notifications are untrusted
assertions, confirmed only to the extent the provider's own interface
allows.

## R3 — Extracting the claimed new value

**Decision**: On wake, look up the journey's order's notifications via
`JourneyRepository.get_notifications_for_order(order_reference)`
(`repository.py:882-892`, already ordered by `received_at`), take the most
recent one with `declared_event_type == "schedule.changed"`, and parse its
`raw_payload_json` (`json.loads(...)["data"]["revisedArrivalTime"]`) — the
exact key the disruption injector already constructs
(`disruption_injector_service.py:55-58`, mirroring
`.antabay/atlas-capability-map.md` §7c's real captured envelope shape).
If no such notification exists (the wake was a routine sweep with nothing
new to report), evaluation still runs (per FR-002, every element is
checked) but finds the objective unchanged and satisfied — User Story 2.

**Rationale**: `InboundNotification.raw_payload_json` is 007's own
"persist every inbound notification in full" (FR-002) field — no new
storage is needed, only a read of what 007 already persists.

## R4 — Evaluating objective elements

**Decision**: For each populated field on `TravelObjective`
(`journey/models/objective.py`), compare its current value against the
claimed new state. Today, the only field a `schedule.changed` claim can
affect is `latest_arrival` (a `ConstrainedField[str]`). A violation exists
when `latest_arrival.constraint_type == ConstraintType.HARD` and the
claimed `revisedArrivalTime` is later than `latest_arrival.value`. Per
the spec's own Assumptions, a `SOFT` (preference) `latest_arrival` being
exceeded does not constitute a violation (User Story 2, Acceptance
Scenario 3 — treated as satisfied). Other objective fields
(`origin`, `destination`, `departure_date`, `budget_amount`, `pax_count`)
are unaffected by a schedule-change claim and are evaluated as
unchanged/still-satisfied — this keeps FR-002's "every element checked"
literal without inventing checks the current claim shape cannot inform.

**Extensibility note**: This mapping (claim field → objective field) is
deliberately narrow because only one claim shape (`schedule.changed` /
`revisedArrivalTime`) exists in the codebase today (R2). The evaluation
function's design (see data-model.md) keeps this mapping in one place so
a future claim shape (e.g. a cancellation notice) can add a case without
restructuring the evaluation flow.

## R5 — Alternative search reuses `FlightSearchService.search()` unmodified

**Decision**: `FlightSearchService.search(journey_id, now)` already builds
its request from `journey.objective` (`flight_search.py:198-211` —
origin/destination/departure_date/pax_count/budget_currency), not from any
mutable per-call objective argument. Alternative search for feature 009 is
therefore simply calling this same method again with the same
`journey_id` — no new search variant, no objective mutation, is needed.
This is the literal meaning of "search for alternatives" here: a fresh
live search against the same stated trip parameters, since what changed
is the *booked* flight's schedule, not the traveller's origin/destination/
dates.

**Alternatives considered**: A parallel `search(objective, ...)` overload
taking an explicit objective. Rejected as unnecessary — the traveller's
objective does not change during impact evaluation (Out of Scope; that is
a hypothetical future capability, not this feature's).

## R6 — Scoring and verification reuse, and recommendation order

**Decision**: `ScoringService().score(journey.objective, search_result.options, now)`
is called unmodified (FR-007). The resulting `ScoringRun.scored_options`
(ranked, ties handled per existing rules) are then verified in rank order
via `VerificationService.verify(journey_id, option.option_id, now)`
(FR-008) — the first one whose `VerificationResult.outcome ==
VerificationOutcome.VERIFIED` is the recommendation (FR-010); if a
candidate comes back `PRICE_CHANGED` or `UNAVAILABLE`, the next-ranked
survivor is tried. This directly satisfies NFR-001 ("every alternative
presented MUST come from a verified provider response") — nothing is ever
recommended off `ScoringRun` alone. If the full ranked list is exhausted
with no `VERIFIED` result (or `ScoringRun.selected_option is None` — a
full tie, or `no_satisfying_option` — no survivor at all), FR-012's
no-alternative report is produced.

**State machine note**: Neither call disturbs the journey's `MONITORING`
state. `_ALLOWED_TRANSITIONS` (`journey/models/journey.py:33-58`) has no
`MONITORING → SEARCHING` edge, and `VerificationService.verify()`'s own
transition calls (`_on_verified`/`_on_unavailable`) are gated on the
journey already being `SEARCHING`/`VERIFIED` — since it is `MONITORING`,
both are silent no-ops rather than raising `InvalidTransitionError`. This
is the correct behaviour: evaluating and recommending an alternative is
not the same as committing to it, so the journey correctly remains
`MONITORING` throughout (feature 011's eventual recovery execution is
what would cause a real, intentional transition).

**Alternatives considered**: Verify only the top-ranked option and stop.
Rejected: this would silently produce a no-alternative report whenever the
single best-scored option happens to have gone stale between search and
verification, even when a close second-ranked option is still bookable —
inconsistent with the spec's intent that a search "concludes" (User Story
3, Acceptance Scenario 6) only once nothing viable is found, not after one
verification attempt.

## R7 — Call budget: no new mechanism

**Decision**: No new budget field or table. `FlightSearchService.search()`
and `VerificationService.verify()` each already call
`JourneyRepository.decrement_call_budget()` internally
(`flight_search.py:46`, `verification_service.py:46`) before their
respective Atlas calls. Feature 009's FR-013/SC-010 are satisfied simply
by calling these existing methods — a second caller of an existing
mechanism, exactly as feature 004's own research.md (R6) already
established for verification. If `BudgetExhaustedError` is raised by
either call during alternative search, it is caught and folded into the
same no-alternative report (FR-012) — per the spec's own Assumptions, the
traveller-facing outcome does not distinguish budget exhaustion from "no
alternative found."

## R8 — Concurrency: "most recent wins" without a lock table

**Decision**: No lock table, no journey-level mutex. Each `evaluate_wake()`
invocation is stamped with the sequence number of the `WAKE_REQUESTED`
event that triggered it. At each checkpoint between steps (after search,
after scoring, before recommending/reporting), the evaluation re-reads
`JourneyRepository.get_events_from_sequence(journey_id, since=triggering_sequence + 1)`
for a newer `WAKE_REQUESTED` on the same journey; if one exists, the
current evaluation is marked `SUPERSEDED` (data-model.md) and returns
immediately without producing a recommendation or violation report — the
newer wake (already queued as its own callback invocation, or the next
sweep) evaluates fresh state from scratch. This directly implements the
clarified FR-002 behaviour ("abandoned and restarted from scratch")
without introducing a locking primitive foreign to this codebase's
existing synchronous, single-process style — the same "most recent
observed wins" pattern 007's own confirmation-budget-window logic already
uses (`_within_confirmation_budget_window`).

## R9 — Past-departure and terminal-journey short-circuit

**Decision**: `evaluate_wake()`'s first step after loading the journey
(FR-001) is a departure-time check: if `journey.objective.departure_date`
(or, once available, a more specific departure timestamp) has already
passed relative to `now`, no further evaluation step runs and no
`ImpactEvaluation` record beyond a minimal "inert — past departure" marker
is produced. This mirrors 007's own existing terminal-journey check
(`_TERMINAL_STATES` in `webhook_service.py`) but is evaluated
independently here since a journey can still be `MONITORING` (non-terminal
state) while its departure date has nonetheless passed.

## R10 — New durable state: two tables, four new event types

**Decision**: Two new tables (`impact_evaluations`, `recommendations` —
see data-model.md) record every evaluation attempt and its outcome,
following this codebase's established pattern of one table per
audit-relevant record (e.g. `search_records`, `scoring_runs`,
`verifications`). Four new `EventType` members are added to
`journey/models/events.py` (`IMPACT_EVALUATION_COMPLETED`,
`ALTERNATIVE_RECOMMENDED`, `NO_ALTERNATIVE_FOUND`,
`IMPACT_EVALUATION_SUPERSEDED`), each with a registered Pydantic payload
model, following the exact `_PAYLOAD_MODELS` registration convention
already used for all 15 existing event types. The pre-existing but
never-produced `OBJECTIVE_VIOLATED` and `OBJECTIVE_SET` event types
(`events.py:20-29`) are also put into real use here: `OBJECTIVE_VIOLATED`
is appended when FR-002/FR-004 determine a violation (carrying the
quantified extent), and satisfied-objective determinations use a new
lightweight event rather than overloading `OBJECTIVE_SET` (which, by its
existing payload shape, describes setting an objective, not re-confirming
one already set) — see data-model.md for the exact payload shapes.
