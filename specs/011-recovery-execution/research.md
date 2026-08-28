# Research: Recovery Execution

## R1 — No cancellation endpoint exists anywhere; void.do is a disclosed, provisional gap

**Finding**: Grepping the entire backend and `.antabay/atlas-capability-map.md` finds
zero cancellation implementation. The capability map's own architectural
note (§2) says: *"No flight-change endpoint exists in the API
Reference... Recovery must therefore be rebook plus void/refund of the
original."* — naming the mechanism, but `void`/`refund` is listed among
endpoints **"documented but not yet exercised"**: no request/response
shape has ever been captured against the sandbox for it, unlike
`search.do`/`verify.do`/`order.do`/`pay.do`/`queryOrderDetails.do`, all of
which have verified field lists in the map.

**Decision**: Build the cancellation pipeline as a first-class,
independently-verified two-step process (attempt, then reconciliation
query) — following the exact shape of every other mutating call in this
codebase (`{cid, orderNo, requestSource}` request; `status`/`msg`
response) — against a `void.do` endpoint, but explicitly flag this call's
request/response shape as **provisional, pending a Tier 2 capture**
(Constitution XI). This is disclosed here, in code comments at the call
site, and in the quickstart — not hidden. This mirrors the precedent
feature 008 already set for `schedule.changed`'s envelope shape (also
provisional, also explicitly flagged) and features 007/009's precedent of
shipping honest, structurally-correct plumbing around a piece the
capability map itself acknowledges is unverified, rather than blocking
the whole feature on a sandbox capture this session cannot perform.

**Success predicate (also provisional)**: Since no captured cancellation
response exists, "cancellation confirmed" is defined as the mirror image
of feature 012's own `TicketingSuccessCondition`: an independent
`queryOrderDetails.do` call against the superseded order_no no longer
returns non-empty `paxTicketInfos[].ticketNos` for every passenger — i.e.,
the previously-confirmed ticketing state is no longer present. This reuses
an already-verified field (`paxTicketInfos`) rather than guessing at a
new, cancellation-specific field the map has never captured.

**Alternatives considered**: Refuse to build cancellation at all pending a
real sandbox capture. Rejected: FR-005/FR-006/FR-007 are core,
demonstrable requirements of this feature (Constitution XVIII); shipping
the full replace-then-cancel sequence with cancellation's one unverified
edge clearly flagged serves the project better than omitting a required
capability entirely.

## R2 — No bridge exists from a Recommendation to an authorisation request

**Finding**: Feature 009 produces a `Recommendation` (option_id,
verification_id, cost_relative_description, rationale, constraint flags)
and stops. Feature 010's `AuthorisationPolicyEngine` has zero references
to `Recommendation` anywhere. Both 009's and 011's own specs explicitly
place "obtaining/requesting authorisation" out of their scope — this
bridge is unowned by any existing or currently-planned feature.

**Decision**: Feature 011 does not build this bridge either (per its own
Out of Scope — it "consumes an authorisation decision already granted").
Production code only ever calls `AuthorisationPolicyEngine.enforce_authorised()`
(the check-only path), never `.evaluate()`/`.request_if_required()`. The
correlation key used is `action_id = recommendation_id` — a deterministic,
stable choice consistent with 010's own data-model.md rule ("a genuinely
different action... MUST use a new [action_id]"): a given `Recommendation`
is exactly one candidate action, so its own id is the natural, stable
`action_id`. Tests construct the "authorisation already granted for this
exact recommendation" precondition directly (via `EventService.append` for
`AUTHORISATION_REQUESTED`/`AUTHORISATION_OUTCOME`, matching `action_id`
and `cost_amount` to the recommendation under test) — the same pattern
008 used for a stub confirmation handler to prove its own plumbing without
building the capability that would register one for real.

**Current cost_amount for the authorisation check**: `Recommendation` has
no `cost_amount: Decimal` field — only a display string. FR-002's own
fresh re-verification (immediately before executing) is what supplies the
authoritative current price (`VerificationResult` → the option's
`adult_price + adult_tax`), which is passed to `enforce_authorised()`.
This one call therefore serves two requirements at once: it is FR-002's
required fresh verification, and its resulting price is exactly what
`enforce_authorised()`'s built-in exact-cost-match check (already voiding
a stale grant on mismatch — feature 010's own `AUTHORISATION_VOIDED`
mechanism) needs — no separate price-comparison logic is written in 011.

## R3 — Replacement booking reuses `BookingService` end to end, unmodified

**Decision**: `BookingService.create_order(journey_id, option_id, now)` →
`.submit_payment(journey_id, order_no, now)` → `.confirm_ticketing(journey_id, order_no, now)`
(feature 005) is called directly, unmodified, for the replacement — the
same three-call pipeline the traveller's original booking already went
through. This is the literal meaning of "creation of a replacement
booking" (spec Reference): not a parallel implementation, the same one.
`confirm_ticketing`'s returned `TicketingQuery.confirmed: bool` is
FR-004's "independent query" — feature 012's `PostActionVerifier` is not
needed here since 005 already has its own query-based confirmation for
exactly this purpose.

**A concrete precondition this reuse imposes**: `create_order` requires a
fresh (non-stale) held session identifier and a prior `VerificationResult`
for the exact `option_id` (`get_latest_verification`). FR-002's own
fresh re-verification (R2) satisfies both: `VerificationService.verify()`
persists the `VerificationResult` `create_order` looks up, and — on a
`VERIFIED` outcome — issues a new `HeldIdentifier` session
(`verification_service.py`'s `_on_verified`), which becomes the freshest
session and is exactly what `create_order`'s own session lookup picks up.
No separate session-freshening step is written.

**Capturing the superseded order_no before it stops being "the" order**:
`JourneyRepository.get_active_journeys_with_order_reference()` resolves
"the" order for a journey by *most recent* `requested_at` — once the
replacement order exists, that method would resolve to the replacement,
not the superseded booking. `RecoveryExecutionService` therefore captures
the superseded `order_no` via `get_order_no_for_journey(journey_id)`
**before** calling `create_order`, and uses that captured value for every
subsequent cancellation step — never re-deriving "the old order" after
the replacement exists.

## R4 — An explicit `current_order_no` marker, not recency, decides "the journey's current booking"

**Finding**: Nothing in this codebase's existing schema lets a caller ask
"which order is the journey's *authoritative* current booking" separately
from "which order is most recent" — `get_active_journeys_with_order_reference()`
is a recency heuristic built for feature 007's polling needs, not an
authoritative pointer. FR-009 requires the journey's current booking to
update **only after** the replacement is confirmed (R3) — but the
replacement order exists (and would win any recency-based resolution)
from the moment `create_order` succeeds, before ticketing is confirmed.
Recency alone cannot express "created, but not yet current."

**Decision**: Add one new column, `journeys.current_order_no` (nullable
`String`), set for the first time by this feature via a new repository
method `set_current_order(journey_id, order_no)`, called only after
`confirm_ticketing` reports `confirmed=True` for the replacement (FR-009).
This does not retroactively backfill a value for the traveller's original
booking (out of this feature's scope — no existing caller reads this
column yet, so its absence for pre-011 journeys is harmless); it exists
solely to make FR-009's ordering an explicit, checkable fact rather than
an implicit, timing-dependent one.

## R5 — Duplicate-trigger protection reuses feature 010's own event log, not a new lock

**Decision**: FR-014 ("refuse a second execution attempt against an
already-consumed or in-progress authorisation") is implemented by
recording a `RecoveryExecution` row (data-model.md) keyed by
`recommendation_id` with a `status` field
(`IN_PROGRESS`/`COMPLETED`/`ABANDONED`) the moment execution begins, and
refusing a second `execute()` call for the same `recommendation_id` while
one already exists in any state — a single row per `recommendation_id`,
never replaced or re-created. This mirrors feature 007's own
"tolerate duplicates without duplicating any resulting action" precedent,
implemented the same lightweight way (a durable, checked-first record),
not a new locking primitive.

## R6 — Post-abandonment/failure return to monitoring is structural, not an explicit transition

**Finding**: `JourneyState.MONITORING`'s only outgoing edges in
`_ALLOWED_TRANSITIONS` are `CANCELLED`/`ABANDONED` — there is no
`MONITORING → <anything else>` edge for recovery execution to traverse
into, and `BookingService`/`VerificationService`'s own transition helpers
(`_transition_to_monitoring`, `_on_verified`) are both gated on the
journey already being in an earlier state (`VERIFIED`/`SEARCHING`), so
they silently no-op when called against a `MONITORING` journey — exactly
as feature 009's research.md R6 already found for its own reuse of
`FlightSearchService`/`VerificationService`.

**Decision**: The journey remains `MONITORING` throughout recovery
execution, in every outcome (success, abandonment, partial
replacement-succeeded-cancellation-failed). FR-010 ("return the journey
to monitoring once recovery is complete") is satisfied by construction —
there is nothing to explicitly transition back *from*, since nothing in
this reused pipeline moves the journey out of `MONITORING` in the first
place. This is stated explicitly, not left implicit, per the clarified
FR-010 wording (spec.md) that covers abandonment and partial outcomes
alongside full success.

## R7 — Concurrency: a further disruption does not interrupt an in-progress execution

**Decision**: No supersede/interrupt check is added to `execute()`. Per
the spec's own clarified Edge Cases, a further disruption confirmed while
recovery is already executing does not abandon the in-progress attempt —
the safety ordering (replacement secured before original released)
governs whatever step is currently in progress regardless of new
information arriving concurrently. This is the one place 011's design
deliberately does *not* mirror 009's "most recent wake wins" pattern
(research.md R8 there) — the two features have opposite concurrency
requirements by design, and both are stated explicitly in their own specs.
