# Implementation Plan: Order Creation and Payment

**Branch**: `005-booking-path` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-booking-path/spec.md`

## Summary

Convert a verified, held session into a ticketed booking through three synchronous Atlas calls — `order.do`, `pay.do`, `queryOrderDetails.do` — treating each state-changing call (order creation, payment) as unconfirmed until an independent read proves otherwise. A duplicate-order rejection is read as confirmation, not failure. Payment success is never ticketing evidence; only a query showing non-empty ticket numbers for every passenger is. The journey moves to a new `MONITORING` state only at that point.

## Technical Context

**Language/Version**: Python 3.11 (backend only — no frontend surface for this feature)

**Primary Dependencies**: httpx (existing Atlas HTTP client pattern from `journey/services/flight_search.py` and `journey/services/verification_service.py`), SQLAlchemy 2.0, Pydantic 2.0

**Storage**: Same SQLite/SQLAlchemy store as the rest of the journey system — three new tables (`orders`, `payments`, `ticketing_queries`); the existing `held_identifiers` table is reused for the ticketing-deadline freshness window, the third such window after the offer and session windows from spec 002/004

**Testing**: pytest, pytest-recording (VCR cassettes) for Tier 1 E2E against recorded `order.do`/`pay.do`/`queryOrderDetails.do` responses — same pattern as `tests/contract/test_verify_contract.py`

**Target Platform**: Backend service (no new deployable surface)

**Performance Goals**: The ticketing-confirmation polling loop (FR-011) must terminate deterministically — every iteration re-evaluates against locally known state (the ticketing deadline) without needing an extra call beyond the query itself

**Constraints**: Unlike `verify.do`, the capability map documents no per-journey call-budget allowance for `order.do`/`pay.do`/`queryOrderDetails.do` — this feature does not decrement or check the journey's call budget for any of its three endpoints (see research.md R7)

**Scale/Scope**: One order, and typically one payment attempt, per verified option per journey; the ticketing query loop runs until confirmed, the ticketing deadline passes, or a terminal error — bounded by `tktLimitTime` (observed 30 minutes)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | `sessionId` (input) flows through unmodified; `order.do`/`pay.do`/`queryOrderDetails.do` are already `verified` in `atlas/allowlist.py`; no endpoint or field invented | PASS |
| II. Verification After Action | This feature's entire structure *is* Principle II applied to booking: order creation and payment are never trusted at face value; an independent query is the only accepted evidence of ticketing (NFR-001, FR-010) | PASS |
| III. Separation of Reasoning and Authority | No authorisation-policy logic lives here (explicitly Out of Scope); this feature assumes required authorisation already granted before it acts | PASS |
| IV. Human Authorisation | Not this feature's concern (Out of Scope) — but FR-004/FR-009's "never assume a false confirmation" discipline is the safety property authorisation policy depends on being true | PASS |
| VI. State Outside the Agent | `orders`, `payments`, `ticketing_queries` tables persist every attempt; `held_identifiers` persists the ticketing-deadline window — nothing lives only in process memory | PASS |
| VII. Operational Discipline | Duplicate-order rejection (FR-006) and payment-decline (FR-013) are both treated as stated, recorded, recoverable-or-terminal conditions, never silent or undefined | PASS |
| VIII. End-to-End Traceability | Every FR maps to a contract or unit test in Phase 1/tasks; see data-model.md validation rules | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XI. Two-Tier End-to-End Testing | Tier 1 cassette recorded from the already-captured order.do/pay.do/queryOrderDetails.do responses documented in the capability map (§7b, JKT→SUB, 2026-08-15) — no new live sandbox call needed to seed it | PASS |
| XII. Assertions Against Observable External State | Ticketing confirmation is asserted against `queryOrderDetails.do`'s own returned ticket numbers, never against what `order.do`/`pay.do` claimed | PASS |
| XIV. Auditability | NFR-002 requires order and payment responses persisted in full; this plan extends that to every ticketing query too, for the same audit reason | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/005-booking-path/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── order_pay_query_do.md   ← Phase 1 output — external Atlas contract consumed
│   └── booking_service.md      ← Phase 1 output — internal service interface exposed
└── tasks.md              ← /speckit.tasks output (not yet created)
```

### Source Code

```text
backend/                                  ← existing Python package
├── atlas/
│   ├── allowlist.py                      ← order.do, pay.do, queryOrderDetails.do
│   │                                          already present, verified (no change)
│   └── identifiers.py                    ← OpaqueId, reused as-is (no change)
├── journey/
│   ├── models/
│   │   ├── journey.py                    ← extend: JourneyState gains MONITORING;
│   │   │                                     one new allowed transition
│   │   │                                     (VERIFIED → MONITORING)
│   │   └── booking.py                    ← new: Order, PaymentAttempt, TicketingQuery
│   │                                          dataclasses, OrderOutcome/PaymentOutcome enums
│   ├── services/
│   │   └── booking_service.py            ← new: BookingService.create_order(),
│   │                                          .submit_payment(), .confirm_ticketing()
│   └── storage/
│       ├── tables.py                     ← extend: add orders, payments,
│       │                                     ticketing_queries tables
│       └── repository.py                 ← extend: save_order(), get_order_by_order_no(),
│                                              save_payment(), save_ticketing_query(),
│                                              get_ticketing_queries()
├── journey/migrations/versions/
│   └── xxxx_add_booking_tables.py        ← new migration
├── fixtures/atlas/cassettes/booking/     ← sibling to tests/, matching the
│   │                                        convention set by 002/004
│   ├── order_pay_query_jkt_sub.yaml      ← new cassette, transcribed from the
│   │                                         already-captured JKT→SUB response
│   │                                         sequence in the capability map
│   └── order_duplicate_318.yaml          ← new cassette, transcribed from the
│                                              observed 318 duplicate response
└── tests/
    ├── unit/
    │   └── test_booking_service.py       ← new
    ├── contract/
    │   └── test_booking_contract.py      ← new, VCR-recorded
```

**Structure Decision**: This feature extends the existing single-package `backend/journey` structure used by 000–004 and 006 — no new project or service boundary. It adds one model module, one service module, three storage tables, and their tests; it does not touch `frontend/` (the 006 console can render this feature's events once wired, but that wiring is not part of this plan — the same boundary 004 drew for the freshness-window rendering it produced).

## Complexity Tracking

No constitution violations requiring justification.
