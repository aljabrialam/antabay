# Implementation Plan: Disruption Injector

**Branch**: `008-disruption-injector` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-disruption-injector/spec.md`

## Summary

Build an operator-only trigger that constructs a schedule-change
notification conforming to the one real captured envelope's structural
convention (`.antabay/atlas-capability-map.md` §7c), targets an existing
journey's real order, and delivers it through feature 007's own
`WebhookService.receive()`/`.confirm()` — the identical logic path a real
notification would go through, called directly rather than duplicated.
This feature extends 007's `InboundNotification` and `webhook_notifications`
table with one new field, `simulated: bool`, additively (mirroring the
extension pattern 010 and 007 itself already established), and threads
that flag into any `WAKE_REQUESTED` event 007 produces, reusing feature
006's already-existing `simulated` field on `JourneyEvent` rather than
inventing a second simulation-marking mechanism. No schedule-change
confirmation handler exists yet in 007 (per 007's and this spec's own
Assumptions), so an injected notification is honestly received, persisted,
and marked simulated today, but currently produces no downstream
confirmed event — the plumbing this feature adds ensures FR-004 holds
automatically once a schedule-change handler is eventually registered,
without this feature needing to build that handler itself (Out of Scope).

## Technical Context

**Language/Version**: Python 3.11 (backend only — the injector's own
trigger surface is a narrow, operator-only HTTP endpoint; no new frontend
work)

**Primary Dependencies**: None new. Reuses `WebhookService` (007),
`EventService`/`JourneyEvent.simulated` (006), and `JourneyRepository`
(existing). No new external dependency for the operator-only access
control — a shared-secret token check against an environment variable,
consistent with this project's existing configuration style (env-var-driven
operational parameters, e.g. 007's reconciliation interval).

**Storage**: Same SQLite/SQLAlchemy store. One additive column,
`simulated` (boolean, default `0`), on 007's existing `webhook_notifications`
table — not a new table. No other schema changes; 012's `verification_attempts`
and 006's `journey_events` (already carrying `simulated`) are read/written
through their existing, unmodified interfaces.

**Testing**: pytest. No VCR cassette — this feature makes no external
provider call of its own (it only ever calls into `WebhookService`, which
already has its own, separately-tested confirmation-query glue). Tests
exercise the injector service directly (target validation, envelope
construction, delivery) and the trigger endpoint's access control
(missing/wrong token, disabled state) against constructed scenarios,
matching the pattern already established for 007's own unit/contract
tests.

**Target Platform**: Backend service. One new HTTP endpoint — this
backend's first endpoint that is deliberately *not* meant to be publicly
reachable (007's webhook endpoint is public by design; this one is the
opposite).

**Performance Goals**: Not applicable beyond what 007's own `receive()`/
`confirm()` already require — this feature adds no new hot path.

**Constraints**: MUST NOT introduce a second, parallel delivery mechanism
into feature 007's reception logic — "the same reception path" (FR-002)
means calling `WebhookService.receive()`/`.confirm()` directly, the same
methods a real notification's arrival at `POST /webhooks/atlas` triggers,
not a duplicated or shortcut version of that logic. MUST NOT allow any
configuration or code path to cause a downstream event to appear
unmarked when it derives from an injected notification (FR-004, NFR-001).
MUST default to disabled/inert if its own required configuration (the
operator token) is absent — fail closed, not fail open, consistent with
NFR-002's strictness.

**Scale/Scope**: One `InboundNotification` (with `simulated=True`) per
injection, delivered through the identical logic 007 already has. No
change to 007's confirmation-query volume, throttle, or reconciliation
behaviour for real notifications — Clarifications already establish full
behavioural independence between simulated and real notifications for the
same order.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| V. Honest Simulation | This feature *is* Principle V made concrete for schedule-change events: simulated notifications are labelled at reception, permanently in storage, and (via 006's existing `simulated` field) in every interface that already renders it; no travel option, price, or availability is ever fabricated (FR-007) | PASS |
| I. Truth Over Fluency | The injector never invents travel data — it only asserts a schedule-change claim against a real, existing order, and that claim is subject to the same untrusted-until-confirmed discipline (007) as any other notification | PASS |
| VI. State Outside the Agent | The `simulated` marking is a durable, persisted fact (the `webhook_notifications` column), not an in-memory flag threaded through a request | PASS |
| VII. Operational Discipline | The injector fails closed (disabled) if its access-control configuration is absent, rather than defaulting to an open, reachable state | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit/contract test in Phase 1/tasks | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XIV. Auditability | Every injected notification is persisted through 007's existing, already-auditable `InboundNotification` record, now carrying an explicit, permanent simulated marker | PASS |
| XVI. Single Capability Principle | This feature does not build a schedule-change confirmation handler (that remains 007's or a future feature's separate concern), and does not build a general-purpose authentication system (a narrow, single-purpose operator-token check is sufficient for this one endpoint) | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/008-disruption-injector/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── disruption_injector.md   ← Phase 1 output — the endpoint contract and internal service interface
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/                                          ← existing Python package
├── journey/
│   ├── models/
│   │   └── webhook.py                            ← extend: InboundNotification
│   │                                                  gains `simulated: bool`
│   ├── services/
│   │   ├── disruption_injector_service.py        ← new: DisruptionInjectorService —
│   │   │                                              .inject(journey_id, revised_arrival_time, now)
│   │   └── webhook_service.py                    ← extend: receive() gains
│   │                                                  `simulated: bool = False`;
│   │                                                  confirm()/reconcile_active_journeys()
│   │                                                  thread `simulated` into any
│   │                                                  WAKE_REQUESTED event
│   ├── storage/
│   │   ├── tables.py                             ← extend: webhook_notifications
│   │   │                                              gains `simulated` column
│   │   └── repository.py                         ← extend: save_notification()/
│   │                                                  _row_to_notification() handle
│   │                                                  `simulated`; new
│   │                                                  get_order_no_for_journey()
│   ├── errors.py                                 ← extend: JourneyNotFoundError,
│   │                                                  JourneyHasNoOrderError,
│   │                                                  InjectorDisabledError
│   └── api/
│       └── routers/
│           └── disruption_injector.py            ← new: POST /operator/disruptions,
│                                                      gated by a shared operator token
├── journey/migrations/versions/
│   └── xxxx_add_simulated_to_webhook_notifications.py  ← new migration
└── tests/
    ├── unit/
    │   └── test_disruption_injector_service.py   ← new — target validation,
    │                                                  envelope construction, delivery,
    │                                                  simulated-marking propagation
    └── contract/
        └── test_disruption_injector_contract.py  ← new — the trigger endpoint's
                                                        access control and disabled state
```

**Structure Decision**: This feature extends the existing single-package
`backend/journey` structure used by every prior feature — no new project
or service boundary. It adds one new service module, one new router, and
extends three existing files additively (`webhook.py`, `webhook_service.py`,
`tables.py`/`repository.py`) — the same "extend, don't duplicate" pattern
010 and 007 itself already established for cross-feature integration. It
does not modify `journey/services/verification_gate.py`,
`journey/services/conditions/ticketing_condition.py`, or
`journey/api/routers/webhooks.py`'s existing route.

## Complexity Tracking

No constitution violations requiring justification.
