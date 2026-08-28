# Implementation Plan: Event Reception and Reconciliation

**Branch**: `007-webhook-receiver` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/007-webhook-receiver/spec.md`

## Summary

Build the endpoint that receives Atlas's unauthenticated webhook
notifications, persists every one before acting, and confirms each claim
against the provider before treating anything as true — the concrete
instance of Constitution Principle II (Verification After Action) applied
to an *external, untrusted trigger* rather than the agent's own action.
Rather than building a second verification/discrepancy/ordering mechanism,
this feature reuses feature 012's `PostActionVerifier` and
`TicketingSuccessCondition` outright: an inbound `order.ticketed`
notification is fed to `PostActionVerifier.verify()` as the untrusted
`action_response`, and 012's already-proven discrepancy detection
(FR-005/012) and concurrency-ordering (FR-011/012) become this feature's
FR-012 and the ordering rule adopted in this spec's Clarifications,
without reimplementing either. This feature adds only what 012 does not
already provide: the ingestion endpoint itself, raw persistence before
acknowledgement, order-reference routing/association, per-journey
confirmation-query throttling (FR-013, which doubles as FR-009's
duplicate-tolerance mechanism), the periodic reconciliation sweep
(FR-010), and the durable wake signal (FR-011).

## Technical Context

**Language/Version**: Python 3.11 (backend only — no new frontend surface)

**Primary Dependencies**: `httpx` (already a project dependency, used for
the confirmation query against `queryOrderDetails.do` — the same endpoint
005's `BookingService._query_order()` calls, reused at the contract level
only; this feature does not import from `booking_service.py`). FastAPI's
native `BackgroundTasks` (no new dependency) schedules the confirmation
step to run after the acknowledgement response is sent — the mechanism
that makes NFR-001 (ack never depends on confirmation) an enforced
property of the endpoint, not just a documented intention. No new external
dependency for periodic scheduling either — the reconciliation sweep is a
plain async loop task started at FastAPI app startup, consistent with the
polling pattern `EventService.stream_events()` already uses
(`POLL_INTERVAL_SECONDS`); this project has no job-queue/scheduler
dependency today and this feature does not introduce one.

**Storage**: Same SQLite/SQLAlchemy store. One new table,
`webhook_notifications` (raw persistence, FR-002). No new verification
table — this feature registers `TicketingSuccessCondition` with its own
`PostActionVerifier` instance and writes to 012's existing
`verification_attempts` table. One new `EventType` on the existing (006)
`journey_events` table: `WAKE_REQUESTED`, the durable wake signal (FR-011).

**Testing**: pytest. Tier 1 (recorded-cassette) tests are not applicable
to the confirmation query itself — 012's `test_ticketing_success_condition.py`
already proves that classification logic against real captured fixture
shapes; this feature's own tests exercise ingestion, persistence,
routing/association, throttling, and the reconciliation sweep against
constructed webhook envelopes (matching the real captured shape in
`.antabay/atlas-capability-map.md` §7c) and a stubbed confirmation query,
the same pattern 012's own unit tests use.

**Target Platform**: Backend service. One new public HTTP endpoint (the
webhook receiver) — the first genuinely public, unauthenticated surface
this backend exposes.

**Performance Goals**: Acknowledgement (FR-001, NFR-001) must return as
soon as raw persistence (FR-002) completes — a single local database
write — and MUST NOT wait on the confirmation query's network round-trip
to the provider.

**Constraints**: No configuration or code path may skip FR-002's
persist-before-act ordering (NFR-002's spirit applied to ingestion) or
treat a notification's own status/claim as sufficient without a real
confirmation query (FR-003, FR-004, FR-006). This feature MUST NOT modify
`journey/services/booking_service.py` or `journey/services/verification_gate.py`
— it registers its own condition instance with its own `PostActionVerifier`,
consistent with how every other consumer of 012's gate is expected to.

**Scale/Scope**: One `webhook_notifications` row per inbound notification,
regardless of outcome. At most one live confirmation query per journey per
confirmation budget window (FR-013), regardless of notification volume in
that window. The reconciliation sweep iterates journeys with a known order
reference in a non-terminal state.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | The raw notification is persisted as an untrusted record, never as a fact; only a confirmed query result is ever treated as true (FR-002, FR-003, FR-004) | PASS |
| II. Verification After Action | This feature applies the exact discipline Principle II describes, to an external trigger instead of the agent's own write — confirmation always precedes any state change (FR-004) | PASS |
| VI. State Outside the Agent | Every notification, confirmation (via 012's `VerificationAttempt`), and wake signal is persisted durably; nothing about "what happened" lives only in a request handler's memory | PASS |
| VII. Operational Discipline | FR-013 treats provider call volume as a bounded, tracked resource per journey — a forged or duplicate flood cannot turn into unbounded confirmation-query volume; a failed confirmation degrades to the periodic reconciliation safety net (FR-010), never a silent drop or an unbounded retry loop | PASS |
| VIII. End-to-End Traceability | Every FR maps to a unit test in Phase 1/tasks | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XII. Assertions Against Observable External State | Confirmation is 012's gate verbatim — classification is derived only from the query result, never from the notification's own claim (FR-006, inherited from 012's NFR-001) | PASS |
| XIV. Auditability | Every notification (FR-002), every confirmation and discrepancy (via 012's audit trail), and every wake signal (new `WAKE_REQUESTED` event) is recorded | PASS |
| XVI. Single Capability Principle | This feature reuses 012's verification gate rather than rebuilding discrepancy detection or concurrency-ordering a second time; it does not build the (not-yet-existing) agent runner that would consume the wake signal — only the signal itself | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/007-webhook-receiver/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md         ← Phase 1 output
├── quickstart.md         ← Phase 1 output
├── contracts/
│   └── webhook_receiver.md   ← Phase 1 output — the endpoint contract and internal service interfaces
└── tasks.md              ← /speckit-tasks output (not yet created)
```

### Source Code

```text
backend/                                        ← existing Python package
├── journey/
│   ├── models/
│   │   ├── webhook.py                          ← new: InboundNotification,
│   │   │                                            NotificationOutcome
│   │   └── events.py                           ← extend: add EventType.WAKE_REQUESTED
│   │                                                + WakeRequestedPayload
│   ├── services/
│   │   └── webhook_service.py                  ← new: WebhookService —
│   │                                                .receive() (local-only,
│   │                                                on the ack path),
│   │                                                .confirm() (network call,
│   │                                                scheduled as a background
│   │                                                task, never on the ack
│   │                                                path — this split is what
│   │                                                satisfies NFR-001),
│   │                                                .reconcile_active_journeys()
│   ├── storage/
│   │   ├── tables.py                           ← extend: add webhook_notifications table
│   │   └── repository.py                       ← extend: save_notification(),
│   │                                                get_notifications_for_order(),
│   │                                                get_active_journeys_with_order()
│   └── api/
│       └── routers/
│           └── webhooks.py                     ← new: POST /webhooks/atlas
├── journey/migrations/versions/
│   └── xxxx_add_webhook_notifications.py       ← new migration
└── tests/
    └── unit/
        ├── test_webhook_service.py             ← new — ingestion, persistence,
        │                                            routing/association, throttling
        └── test_webhook_reconciliation.py      ← new — the periodic sweep
```

**Structure Decision**: This feature extends the existing single-package
`backend/journey` structure used by 000–006, 010, and 012 — no new project
or service boundary. It adds one new model module, one new service module,
one storage table, one new API router (the feature's only public,
unauthenticated endpoint), and their tests. It registers `TicketingSuccessCondition`
(012) with its own `PostActionVerifier` instance rather than importing or
modifying `booking_service.py` or `verification_gate.py` — see Constitution
Check, Principle XVI.

## Complexity Tracking

No constitution violations requiring justification.
