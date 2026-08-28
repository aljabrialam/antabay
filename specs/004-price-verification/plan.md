# Implementation Plan: Price Verification and Offer Staleness

**Branch**: `004-price-verification` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-price-verification/spec.md`

## Summary

Before any order is created for a selected flight option, verify it against Atlas's `verify.do` and act only on what that response says: read `priceChange.isPriceChange` rather than compare fares, retire the offer-level freshness window in favour of a `sessionId`-bounded session window, record the per-offer passenger requirements and `maxSeats` ceiling, and return to search if the option is no longer available. Re-verification is triggered proactively — before a declared safety margin, not at the documented expiry.

## Technical Context

**Language/Version**: Python 3.11 (backend only — this feature has no frontend surface)

**Primary Dependencies**: httpx (existing Atlas HTTP client pattern from `journey/services/flight_search.py`), SQLAlchemy 2.0, Pydantic 2.0

**Storage**: Same SQLite/SQLAlchemy store as the rest of the journey system — one new `verifications` table; the existing `held_identifiers` table is reused (not extended) to track both freshness windows this feature introduces

**Testing**: pytest, pytest-recording (VCR cassettes) for Tier 1 E2E against a recorded `verify.do` response — same pattern as `tests/contract/test_flight_search_contract.py`

**Target Platform**: Backend service (no new deployable surface)

**Performance Goals**: Re-verification decision must be evaluable without an additional Atlas call (i.e., purely from locally held freshness data) so the safety-margin check (FR-010) never itself costs call budget

**Constraints**: `verify.do` shares its 60 QPM call-budget allowance with `getOffers.do` (per `.antabay/atlas-capability-map.md` §6); every verify call MUST decrement the journey's call budget the same way `search.do` already does

**Scale/Scope**: One verification (plus any re-verifications triggered by the safety margin) per selected option per journey; no batch verification

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | `routingIdentifier` (input) and `sessionId` (output) both flow through `atlas.identifiers.OpaqueId` — no construction, parsing, or mutation; `verify.do` is already `verified` in `atlas/allowlist.py` | PASS |
| II. Verification After Action | This feature *is* the independent-read gate before order creation; an accepted price/availability is never assumed from the selection step alone | PASS |
| III. Separation of Reasoning and Authority | FR-004 (price change invalidates prior authorisation) is a deterministic rule keyed on `priceChange.isPriceChange`, not a model judgement | PASS |
| VI. State Outside the Agent | Verification outcomes persist to a new `verifications` table; freshness windows persist to the existing `held_identifiers` table — nothing lives only in process memory | PASS |
| VII. Operational Discipline | Verify calls counted against the shared verify/getOffers budget (FR-011); re-verification is proactive relative to a safety margin, not reactive to failure (NFR-001) | PASS |
| VIII. End-to-End Traceability | Every FR below maps to a contract or unit test in Phase 1/tasks; see data-model.md validation rules | PASS |
| IX. Test-First Development | Tasks phase will require each test written and failing before its implementation, per this repo's established TDD gate | REQUIRED (enforced at /speckit-tasks + /speckit-implement) |
| XI. Two-Tier E2E Testing | Tier 1 cassette recorded from the already-captured ZE605 verify response documented in the capability map (§7a) — no new live sandbox call needed to seed it | PASS |
| XIV. Auditability | NFR-002 requires the full verify response persisted regardless of which fields are acted on | PASS |

**Post-Phase 1 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/004-price-verification/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── verify_do.md            ← Phase 1 output — external Atlas contract this feature consumes
│   └── verification_service.md ← Phase 1 output — internal service interface this feature exposes
└── tasks.md              ← /speckit.tasks output (not yet created)
```

### Source Code

```text
backend/                                  ← existing Python package
├── atlas/
│   ├── allowlist.py                      ← verify.do already present, verified (no change)
│   └── identifiers.py                    ← OpaqueId, reused as-is (no change)
├── journey/
│   ├── models/
│   │   ├── journey.py                    ← extend: JourneyState gains VERIFIED; two new
│   │   │                                     allowed transitions (SEARCHING→VERIFIED,
│   │   │                                     VERIFIED→SEARCHING)
│   │   └── verification.py               ← new: VerificationResult, PriceChange,
│   │                                          PassengerRequirement dataclasses
│   ├── services/
│   │   └── verification_service.py       ← new: VerificationService.verify(),
│   │                                          .needs_reverification()
│   └── storage/
│       ├── tables.py                     ← extend: add `verifications` table
│       └── repository.py                 ← extend: save_verification(), get_latest_verification()
├── alembic/versions/ (or journey/migrations/versions/, matching existing convention)
│   └── xxxx_add_verifications.py         ← new migration
└── tests/
    ├── unit/
    │   └── test_verification_service.py  ← new
    ├── integration/
    │   └── test_verification_persistence.py ← new
    ├── contract/
    │   └── test_verify_contract.py       ← new, VCR-recorded
    └── fixtures/atlas/cassettes/verification/
        └── verify_ze605.yaml             ← new cassette, transcribed from the already-
                                              captured ZE605 response in the capability map
```

**Structure Decision**: This feature extends the existing single-package `backend/journey` structure used by 001–003 and 006 — no new project or service boundary. It adds one model module, one service module, one storage table, and their tests; it does not touch `frontend/` (no UI surface — spec 004 is Out of Scope for that; 006's console will render verification's *effects*, such as the session clock, once this feature emits them, but that wiring is not part of this plan).

## Complexity Tracking

No constitution violations requiring justification.
