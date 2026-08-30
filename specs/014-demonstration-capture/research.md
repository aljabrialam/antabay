# Research: End-to-End Demonstration Capture

## R1 — Orchestration is an in-process Python script, not a new HTTP endpoint

**Decision**: A new orchestration module drives the full pipeline by
calling existing services directly, in-process, in one linear sequence —
`ObjectiveParser` → `JourneyService.create_journey()` →
`FlightSearchService.search()` → `ScoringService.score()` →
`VerificationService.verify()` → `BookingService.create_order()` →
`.submit_payment()` → `.confirm_ticketing()` — exactly the same calls
`backend/scripts/seed_console_fixture.py` and every feature's own test
suite already make, just chained into one real run instead of stubbed
individually.

**Rationale**: No journey-creation HTTP endpoint exists anywhere in this
codebase (confirmed: `backend/journey/api/main.py` registers only the
events/webhooks/disruption-injector routers). Adding one would be new
public surface for a capability this feature does not own (spec.md's Out
of Scope: "this feature orchestrates and captures... it does not
reimplement or alter them"). Driving the same services test code already
calls, from a script instead of a test, needs no new production surface
at all.

**Alternatives considered**: A `POST /journeys` create-from-goal endpoint.
Rejected — it would be new business-facing API surface owned by no other
feature's spec, built solely to serve this one script.

## R2 — Video capture extends the existing Playwright scaffold, unmodified

**Finding**: `frontend/playwright.config.ts`, `frontend/e2e/*.spec.ts`,
and `frontend/e2e/seed.ts` already exist and are exercised today
(`auth_gate.spec.ts`, `live_observation.spec.ts`, `replay.spec.ts`).
`@playwright/test` is already a devDependency. This is not new
infrastructure to stand up — it is a scaffold to extend.

**Decision**: New Playwright spec files drive the capture; Playwright's
own per-test video recording (a context option, not a separate tool)
produces the video files. No new browser-automation framework, config
system, or dependency is introduced.

## R3 — The live run and the recorded footage are decoupled (confirms spec.md's own Assumption)

**Decision**: The orchestration script (R1) runs at real speed against
the live provider (or against a fixture-seeded journey for the recorded-
events path, R4) — fast enough to finish before the provider's own
freshness windows (a ~7m43s offer, a payment session) lapse. Once that
run is complete and every step's assertion has passed (R8), a *separate*
Playwright pass produces the recording by opening the existing
`GET /journeys/{id}/events/replay?speed=...` page — feature 006's
`EventService.replay_events` (`backend/journey/services/event_service.py`)
— and lets Playwright itself hold on the three emphasised moments with
explicit waits before continuing, rather than by pausing the live run or
slowing the replay's own global speed parameter to reading pace
throughout.

**Rationale**: This is precisely what `.antabay/demo-scenario.md` already
specifies as the project's intended approach, and is the only way to
satisfy FR-005/FR-006 (human-legible pacing and pauses) without violating
NFR (real provider state cannot be paused). `replay_events` already makes
zero external calls (confirmed: `backend/tests/integration/test_replay.py`
asserts no rows are written during replay) and already supports an
arbitrary speed multiplier — no new replay capability is needed, only a
Playwright script that drives it and captures video while doing so.

## R4 — Event Stream Capture and "canonical" reuse the existing fixture-file convention

**Finding**: `backend/scripts/seed_console_fixture.py`'s `replay`
scenario already does almost exactly what FR-011 requires: it reads a
JSON file of `{event_type, payload, simulated, recorded_at}` rows
(`backend/tests/fixtures/journey_events_001.json`) and re-inserts them
into a fresh journey via `EventService.append(...)`, preserving the
original `recorded_at` timestamps so `replay_events`'s pacing is
faithful to the original run. This is a working, precedented pattern for
"load a recorded event stream into a fresh database, then replay it" —
not something to invent from scratch.

**Decision**:
- **Export** (new): after an orchestrated run completes and passes every
  assertion, its full `journey_events` row set
  (`JourneyRepository.get_events_from_sequence(journey_id, 0)`) is
  serialised to a JSON file in the same shape `journey_events_001.json`
  already uses, under a new `backend/tests/fixtures/demo_captures/`
  directory, named by the run's `journey_id`.
- **Canonical designation** (FR-013, new): a single manifest file,
  `backend/tests/fixtures/demo_captures/canonical.json`, holding the
  file name of the currently-designated canonical capture. Promoting a
  capture to canonical is a deliberate, separate step — never an
  automatic side effect of a run completing (per the Clarifications
  session's own resolution).
- **Import for reproduction without the live provider** (FR-011,
  reused): extending `seed_console_fixture.py`'s existing `seed_replay()`
  logic to load an exported capture file (rather than only the one fixed
  fixture it loads today) into a fresh journey, which the existing
  `/replay` endpoint then drives exactly as R3 describes — no network
  call is made anywhere in this path.

**Alternatives considered**: A new database table for "capture" records.
Rejected — the event stream itself is already the durable record
(Constitution VI); a capture is a file-based export of what is already
persisted, not new business state, and belongs alongside the existing
fixture convention rather than as a new domain concept in `journeys.*`.

## R5 — A minimal traveller view is built, reusing the existing hook and reducer unmodified

**Finding**: Exactly one UI exists today — the operator console
(`frontend/src/App.tsx`, `JourneyConsole`). There is no traveller-facing
view, no router library, and no existing mobile/handheld layout
anywhere in the frontend. This was confirmed and the resulting scope
question — build a minimal traveller view, reuse the operator console at
phone size, or defer to a separate feature — was put to the user
directly; the decision was to build a minimal traveller view, scoped
narrowly.

**Decision**: A new `TravellerConsole` component consumes the exact same
`useEventStream` hook and `consoleReducer` the operator console already
uses — no new data-fetching or event-parsing logic. It renders a
simplified, phone-density layout: the objective in plain language, the
current journey state, the pending authorisation prompt (reusing
`AuthPanel` as-is, since "same journey on the traveller's phone, one tap"
is literally this component's own narrated purpose) — and omits the
operator-only panels (`EventLog`, `CallBudget`, `ExpiryClockPanel`,
`ProvenanceBar`). It is exposed at `/journey/{id}/traveller` (and
`/journey/{id}/traveller/replay`), extending `App.tsx`'s existing
hand-rolled path parsing rather than introducing a router library, which
nothing else in this small application currently uses.

**Alternatives considered**: Recording the operator console itself at a
handheld viewport. Rejected per the user's explicit decision — it would
satisfy FR-003's letter but not its intent (showing the traveller
surface the product actually has, at the density Constitution Principle
XX already calls for: "the operator surface and the traveller surface
MUST render from the same event stream at different densities").

## R6 — Journey isolation (FR-014) holds by construction

**Finding**: `JourneyService.create_journey()` already generates a fresh
UUID on every call (`backend/journey/services/journey_service.py`) — no
existing mechanism reuses a `journey_id` across separate creations.

**Decision**: No new isolation mechanism is built. The orchestration
script (R1) simply never reuses a `journey_id` across invocations — the
primary run and the refusal-path run are two separate script invocations,
each creating (and therefore owning) exactly one journey. FR-014 is
satisfied by this being the only way the script is written, not by an
additional runtime check.

## R7 — Disruption-before-ticketing ordering is enforced by the orchestrator's own sequencing

**Finding**: The clarify session raised, but left unresolved, whether the
disruption trigger must wait for ticketing confirmation. Feature 008's
own disruption injector has no such guard itself (by design — it is a
narrow, single-purpose trigger, per its own Single Capability boundary).

**Decision**: The orchestration script (R1) only calls
`POST /operator/disruptions` after `BookingService.confirm_ticketing()`
has reported `confirmed=True` (the journey has reached `MONITORING`) —
enforced by the script's own linear sequencing, not by a new check inside
the disruption injector. This resolves the deferred clarification
structurally: it is not possible for this feature's own orchestrated run
to fire the disruption early, because the step simply does not appear in
the script before that point.

## R8 — Assertions check structural expectations, not fixed live values

**Decision**: A new assertions module, used by the orchestration script
after each step, checks the *shape* of the outcome the scenario requires
— an eliminated candidate that satisfies the numeric constraints but is
excluded for the overnight-connection rule; a selected option that
satisfies every hard constraint; an impact evaluation reporting
`objective_satisfied is False` with `latest_arrival` among the violated
constraints; a recovery execution reporting `replacement_outcome ==
SUCCEEDED` — not fixed prices, flight numbers, or option IDs, consistent
with spec.md's own Edge Cases resolution for live-data drift. This is new
code with no existing precedent to extend; each check reads the same
return values/persisted records each underlying feature's own test suite
already asserts against, just chained into one pass/fail gate for the
whole run (FR-004).

## R10 — The disruption trigger and authorisation response call the service layer directly, not a self-directed HTTP round-trip

**Decision** (refined during implementation, superseding the earlier draft
of R1/contracts.md that described these as HTTP calls): the orchestration
script calls `DisruptionInjectorService.inject()` and
`EventService.record_auth_outcome()` directly, in-process — the exact
same code the `POST /operator/disruptions` and
`POST /journeys/{id}/authorisation/{request_id}` routers themselves call
(`backend/journey/api/routers/disruption_injector.py`,
`backend/journey/api/routers/events.py`) — rather than the script making
an HTTP request to a separately-running server.

**Rationale**: This is the codebase's own established convention with no
exception anywhere else in it: every feature composes another feature's
*service*, never its HTTP route. Feature 008's own injector calls
`WebhookService.receive()`/`.confirm()` directly, not via a self-HTTP-call
to `/webhooks/atlas`, even though a *real* provider notification would
arrive over HTTP. `backend/scripts/seed_console_fixture.py` calls
`EventService`/`JourneyService` directly for the same reason. FR-007's
"without manual intervention" and FR-008's "respond... as part of the
run" are about the absence of a *human* clicking a button — not a
mandate that the automation itself route through HTTP. Calling the
service layer directly also removes any need for the script to have a
separately-running server or network access for these two steps,
simplifying both production usage and testing (the orchestration logic
becomes fully testable against a local database with no live process to
stand up).

## R11 — The orchestration script builds the missing Recommendation → authorisation-request bridge, scoped to itself only

**Finding**: Feature 011's own research (R2) already established that no
code anywhere turns a feature 009 `Recommendation` into a feature 010
`ProposedAction`/`AuthorisationPolicyEngine.request_if_required()` call —
both features' specs place that bridge out of their own scope, and 011's
tests construct the "already granted" precondition directly rather than
building it. Something has to call `request_if_required()` for a real,
end-to-end demonstration run to ever produce a real
`AUTHORISATION_REQUESTED` event to respond to.

**Decision**: `capture_runner.py` builds this bridge itself, scoped
entirely to the orchestration script (not added to
`journey/services/authorisation_policy_engine.py` or any other
production module): it constructs a `ProposedAction` from the
`Recommendation` (`action_id = recommendation_id`, per feature 011's own
established correlation convention), calls
`AuthorisationPolicyEngine.request_if_required()`, then reads back the
resulting `AUTHORISATION_REQUESTED` event to recover its `request_id`
(the same lookup `AuthorisationPolicyEngine`'s own private
`_latest_request_for` performs internally, reimplemented locally rather
than exposed as new public API surface).

**Rationale**: This is genuinely required for the pipeline to run at
all — without it, there is no `request_id` for `record_auth_outcome()`
to resolve. Keeping it local to this one script, rather than adding it as
new production surface on 009 or 010, respects both features' own
explicit scope boundaries; if a future feature ever does own this bridge
for real, this script's local version can be deleted in favour of it.

## R12 — The wake trigger is scoped to this run's own journey, not a full sweep

**Finding**: `WebhookService.reconcile_active_journeys()` sweeps *every*
active journey in the database, not just one — confirmed during
implementation when a second orchestrated run in the same database
re-processed the first run's still-`MONITORING` journey too (`MONITORING`
is not one of `webhook_service.py`'s `_TERMINAL_STATES`). Since the
demonstration database is expected to accumulate multiple prior runs'
journeys over time (each run creates its own, per FR-014/research.md R6),
calling the broad sweep from the orchestration script would re-touch
every earlier run's journey on every new run — consuming unrelated Atlas
calls and corrupting the deterministic step sequence a mocked/replayed
run relies on.

**Decision**: The script appends its own `WAKE_REQUESTED` event for
exactly this run's journey — the same shape `confirm()`/
`reconcile_active_journeys()` already construct
(`{"order_reference": ..., "declared_event_type": ..., "classification":
"SUCCESS"}`) — via `EventService.append()`, then calls
`ImpactEvaluationService.evaluate_wake(journey_id, wake_event)` directly
with that event. This never touches any other journey in the database and
never waits on the live server's 300s reconciliation timer.

**Alternatives considered**: Running the full sweep and accepting that it
touches other journeys. Rejected — it would make the orchestration
script's own behaviour depend on however many prior runs happen to share
its database, breaking NFR-003's repeatability guarantee in practice even
though each run's *own* journey remains correctly isolated (FR-014).

## R9 — The refusal-path run stops at the authorisation outcome

**Decision**: The refusal-path run (User Story 5) is a separate
orchestration invocation that proceeds through disruption and impact
evaluation exactly like the primary run, submits `"refused"` to
`POST /journeys/{id}/authorisation/{request_id}` (the same existing
endpoint the primary run submits `"approved"` to — `backend/journey/api/
routers/events.py`), asserts zero spend and a durably recorded refusal,
and stops there — it does not continue into recovery execution, since
there is nothing left to execute once authorisation is refused.
