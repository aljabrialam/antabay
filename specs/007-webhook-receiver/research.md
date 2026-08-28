# Research: Event Reception and Reconciliation

## R1: Reuse 012's verification gate for confirmation, rather than building a second one

**Decision**: An inbound `order.ticketed` notification is confirmed by
calling `PostActionVerifier.verify(journey_id, action_type="ticketing",
affected_record_id=order_no, query_fn=<queries queryOrderDetails.do>, now,
action_response=<the notification's raw `data` payload>)`, using a
`PostActionVerifier` instance this feature owns, registered with 012's
existing `TicketingSuccessCondition`.

**Rationale**: 012 already solved every hard problem FR-004/FR-006/FR-012
and this spec's ordering Clarification require: `TicketingSuccessCondition.classify()`
derives truth only from the query result, never the caller-supplied
`action_response` (FR-006, for free); `has_discrepancy()` already compares
the untrusted claim against the confirmed result and records disagreement
as a `VerificationAttempt.has_discrepancy` flag (satisfies FR-012
directly); and `_should_apply()`'s observed-timestamp comparison already
implements the exact ordering rule this spec's Clarifications session
explicitly chose to adopt from 012. Treating the notification's `data`
payload as `action_response` is a natural fit — 012's contract never
required that value to come from *our own* prior action; it only requires
it to be "whatever the action claimed," which an external notification's
claim satisfies just as well as our own write's response would.

**Alternatives considered**: A second, webhook-specific verification/
discrepancy mechanism — rejected outright as a Principle XVI violation
once 012's existing contract was checked against this feature's actual
needs and found sufficient without modification.

---

## R2: The confirmation query is new, small glue code — not a reuse of `BookingService._query_order()`

**Decision**: This feature implements its own minimal call to
`queryOrderDetails.do` (`_ATLAS_QUERY_URL` in `booking_service.py`, same
endpoint, same request shape) as the `query_fn` passed to `verify()`. It
does not import or call `BookingService._query_order()`.

**Rationale**: `_query_order()` is a private method tightly coupled to
`BookingService`'s own `httpx.Client`, its own `TicketingQuery`
persistence, and its own state-transition side effects (it transitions the
journey to `MONITORING` directly) — none of which this feature wants
duplicated or triggered a second time. 012 already established the
precedent of treating "call the query endpoint" as glue code each
consumer supplies via `query_fn`, deliberately not a shared library
function — `test_ticketing_success_condition.py`'s own fixtures reuse only
the *response shape*, not any code path. This feature follows the same
pattern: the endpoint contract (already proven in production, per the
capability map) is reused; `BookingService`'s specific orchestration is
not.

**Alternatives considered**: Extracting `_query_order()` into a shared
utility both `BookingService` and this feature call — rejected as
out-of-scope refactoring of existing, working, tested code that neither
012 nor this feature's spec asks for.

---

## R3: One throttle satisfies both FR-009 (duplicate tolerance) and FR-013 (confirmation-query bounding)

**Decision**: Before triggering a confirmation query for a newly-associated
notification, check two sources for recent activity on this order
reference within the confirmation budget window: (a) whether a
`VerificationAttempt` already exists with `observed_at` inside the window,
and (b) whether a prior `InboundNotification` for the same order already
has `confirmation_triggered=True` with `received_at` inside the window. If
either is true, the notification is persisted and associated as normal,
but no new confirmation query is triggered.

**Implementation note (found during `/speckit-implement`, T041)**: checking
only (a) is not sufficient. `confirm()` runs as a FastAPI background task
— it does not execute synchronously inside `receive()` — so a burst of
`receive()` calls arriving faster than the *first* `confirm()` completes
would find no `VerificationAttempt` yet for any of them and all slip
through unthrottled. Source (b) closes this gap: `receive()` persists
`confirmation_triggered` synchronously, before `confirm()` ever runs, so
each subsequent `receive()` call in the same burst sees the prior one's
flag immediately, regardless of whether its `confirm()` has completed.

**Rationale**: A duplicate notification and a burst of distinct
notifications for the same journey present the identical problem at this
feature's boundary — "don't multiply confirmation queries for the same
underlying question asked repeatedly in a short window" — and the webhook
envelope (per the captured example in the capability map) carries no
unique event/message ID to dedupe on directly. Rather than building a
separate content-hash dedup key for FR-009 and a separate counter for
FR-013, one throttle keyed by `(order_no, confirmation budget window)`
satisfies both: exact duplicates collapse trivially (same order_no, same
window), and a flood of distinct-looking notifications collapses just as
well, since the thing being protected — provider call volume for that
journey — is identical in both cases.

**Alternatives considered**: A separate payload-hash-based dedup table for
FR-009 — rejected as solving a narrower problem with more moving parts
than FR-013's throttle already covers; every duplicate scenario in
spec.md's User Story 4 is also a "burst for one journey" scenario.

---

## R4: The wake signal is a new, minimal `JourneyEvent` type — this feature does not build an agent runner

**Decision**: Once a confirmation resolves to `SUCCESS` or `FAILURE` (per
012's `VerificationOutcome`) for a notification-triggered or
sweep-triggered confirmation, this feature appends a new
`EventType.WAKE_REQUESTED` event via the existing (006) `EventService`,
carrying the order reference, the notification's declared event type, and
the resolved classification. Nothing in this codebase currently consumes
this event — there is no agent runner/loop implemented yet.

**Rationale**: Constitution Principle VI requires journey continuity to
live in durable storage, not in a process's memory — a `JourneyEvent` is
exactly that. Reusing 006's already-proven event mechanism (extended
additively by 010 for its own `AUTHORISATION_VOIDED` case) is consistent
with this project's established pattern for "record a durable fact,"
rather than inventing a second notification/queue mechanism for this one
purpose. What eventually polls or subscribes for `WAKE_REQUESTED` events
and does something with them is explicitly out of scope for this feature
("recovery," "evaluating objective impact" — spec.md Out of Scope) and for
this plan.

**Alternatives considered**: A dedicated `pending_wakes` table with its
own consumption/ack semantics — rejected as over-engineering a signal this
feature is not itself responsible for consuming; a plain, queryable event
is sufficient for whatever does consume it later, and keeps this feature's
footprint to "record the fact," per Principle XVI.

---

## R5: Unrecognised event types need no special-case logic — 012's "no default" pattern already covers it

**Decision**: Routing (FR-005) is a lookup against a small, explicit
handler registry (today: only `order.ticketed`). A `type` with no
registered handler falls through to exactly the behaviour spec.md's Edge
Cases already define: acknowledged, persisted, inert. No `if type ==
"schedule.changed": ...` placeholder is added in anticipation of feature
008, since no confirmation mechanism for a schedule-change claim is
documented anywhere in the capability map yet (§2: "No flight-change
endpoint exists in the API Reference").

**Rationale**: This mirrors 012's `UnregisteredActionTypeError` precedent
exactly — no default handler exists, and adding one type doesn't require
touching the registry's fallback behaviour for every other type. When
feature 008 (or whatever eventually defines a schedule-change confirmation
mechanism) is built, it registers a new handler; this feature's dispatch
logic does not change.

**Alternatives considered**: Pre-building a stub handler for
`schedule.changed` now — rejected as speculative; spec.md's Out of Scope
already excludes "simulating events" (008's job), and there is no
confirmation query to wire it to yet.

---

## R6: The periodic reconciliation sweep is an in-process async loop, not a new scheduler dependency

**Decision**: `WebhookService.reconcile_active_journeys(now)` is a plain,
directly-callable, testable method. Its periodic invocation is a small
`asyncio` loop task started during the FastAPI app's lifespan, sleeping
for the confirmation-adjacent reconciliation interval between sweeps —
the same style of loop `EventService.stream_events()` already uses for its
own polling (`POLL_INTERVAL_SECONDS`).

**Rationale**: This project has no job-queue or external scheduler
dependency today (`pyproject.toml` confirms this), and the backend is
already a single, long-lived FastAPI process (Constitution's Technology
Standards: "Deployed backend holding long-lived connections"). Introducing
a new scheduling framework for one periodic sweep would be a
disproportionate new dependency; an in-process loop matches an existing,
proven pattern in this exact codebase.

**Alternatives considered**: An external cron entry invoking a one-shot
CLI/script — rejected as adding a second deployment artifact and
operational surface for a need this project's own existing pattern
(long-lived process, in-process polling loop) already satisfies without
one.
