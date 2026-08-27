# Implementation Plan: Atlas Capability Contract

**Branch**: `000-atlas-capability-contract` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/000-atlas-capability-contract/spec.md`

## Summary

Establish a single, enforced boundary around all Atlas API interactions in the
Antabay backend. The boundary is implemented as a Python package
(`backend/atlas/`) that exposes typed models for every verified endpoint,
opaque-identifier wrappers, a canonical price function, an error-classification
table, a call-budget enforcer, and a freshness-window tracker. Any call to an
endpoint outside the verified allowlist, or any read of an unverified field,
must fail at import time (Mypy strict) — not at runtime. Contract tests run on
every push against recorded sandbox fixtures.

## Technical Context

**Language/Version**: Python 3.11 (backend, per constitution)

**Primary Dependencies**:
- `pydantic` v2 — typed schemas and validated models; unknown fields rejected
  via `model_config = ConfigDict(extra="forbid")`
- `mypy` (strict) — static type checker; enforces no unverified field access
  at CI time
- `pytest` + `pytest-recording` (VCR cassettes) — contract tests against
  recorded fixtures
- `httpx` — HTTP client for Atlas calls (supports both sync and async)

**Storage**: N/A — this feature defines data shapes; state persistence is a
separate feature

**Testing**: pytest; HTML report generation enabled; fixtures captured from
Tier 2 sandbox runs

**Target Platform**: Linux server (deployed backend), also runs on CI runner

**Project Type**: Internal library package within the backend monolith
(`backend/atlas/`)

**Performance Goals**: Build-time enforcement (Mypy) must complete in under
60 seconds on a standard CI runner for the full backend package

**Constraints**:
- Zero runtime cost for schema validation on the critical path; Pydantic model
  parsing is the only acceptable overhead
- No third-party agent framework (constitution XVII)
- Fixtures MUST be captured from live sandbox runs; handwritten fixtures
  are prohibited (constitution XI, spec NFR-003)

**Scale/Scope**: Covers 5 exercised endpoints + 1 webhook event shape.
Unexercised endpoints (getOffers, seatAvailability, getLuggage, refunds, void,
webhook registration, incident, balance) are listed in the allowlist but their
Pydantic models are marked `status = "unverified"` and must not be imported
by production code paths.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I — Truth Over Fluency | All Atlas fields come from captured API responses. No field may be present in a model unless it appears in the capability map. | ✅ PASS — models are derived from `.antabay/atlas-capability-map.md` |
| I — Truth Over Fluency | Endpoints must be in the published API reference before they are called. | ✅ PASS — allowlist enforced at import time via Mypy |
| I — Truth Over Fluency | Opaque identifiers must not be constructed, parsed, or mutated. | ✅ PASS — `OpaqueId` wrapper type provides no mutation API |
| VII — Operational Discipline | Rate limits are design constraints. | ✅ PASS — `CallBudget` enforcer is a first-class entity, not an afterthought |
| VII — Operational Discipline | Held identifiers re-verified before documented expiry. | ✅ PASS — `FreshnessWindow` tracks issued-at and expires-at; FR-012 |
| VIII — End-to-End Traceability | Every requirement has acceptance criteria mapped to tests. | ✅ PASS — all 12 FRs have acceptance scenarios; traceability in data-model |
| IX — Test-First Development | Tests written before implementation. | ✅ PASS — tasks order: write failing test → implement → confirm green |
| X — Testing Pyramid | ~70% unit, ~20% integration, ~10% E2E. | ✅ PASS — this feature is primarily unit + contract (no UI surface) |
| XI — Two-Tier E2E Testing | Tier 1 uses recorded fixtures; Tier 2 uses live sandbox. | ✅ PASS — pytest-recording cassettes; Tier 2 trigger is manual / daily CI job |
| XI — Two-Tier E2E Testing | Fixtures captured from Tier 2 runs, never handwritten. | ✅ PASS — NFR-003 enforced; existing fixtures in `fixtures/atlas/` are the seed |
| XII — Assertions Against Observable External State | Tests assert on what the external system reports. | ✅ PASS — contract tests replay real responses and assert on parsed model fields |
| XIII — Deterministic Automation | No arbitrary sleeps; order-independent tests. | ✅ PASS — tests use recorded responses; no live calls in CI |
| XV — AI-Assisted Development Under Human Review | Human review required before commit. | ✅ PASS — each task is one commit; human verifies before merge |
| XVI — Single Capability Principle | One task = one commit = one demonstrable capability. | ✅ PASS — tasks are broken down to individual model/function/test units |
| XVII — Built With Qoder | All files generated via Qoder CLI. | ✅ PASS — no hand-written patches |
| XXI — Scope Freeze | Scope froze 2026-08-20; this is hardening work. | ✅ PASS — contract enforcement is a hardening requirement, not a new feature |

No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/000-atlas-capability-contract/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── atlas-allowlist.md
│   └── atlas-models.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── atlas/                        # NEW — spec 000 contract package
│   ├── __init__.py               # public re-exports; nothing else
│   ├── allowlist.py              # FR-001, FR-002: verified endpoint registry
│   ├── models/
│   │   ├── search.py             # FR-003: SearchRequest, SearchResponse, Routing
│   │   ├── verify.py             # FR-003: VerifyRequest, VerifyResponse
│   │   ├── order.py              # FR-003: OrderRequest, OrderResponse
│   │   ├── pay.py                # FR-003: PayRequest, PayResponse
│   │   ├── query.py              # FR-003: QueryOrderRequest, QueryOrderResponse
│   │   └── webhook.py            # FR-003, FR-006: WebhookEvent (normalised orderStatus)
│   ├── identifiers.py            # FR-004: OpaqueId wrapper; no construction API
│   ├── pricing.py                # FR-005: canonical_total_price(); only price entry point
│   ├── errors.py                 # FR-007, FR-008: ErrorCode enum + classification table
│   ├── telemetry.py              # FR-009: CallRecord dataclass + recorder
│   ├── budget.py                 # FR-010, FR-011: CallBudget + retryAfter enforcement
│   └── freshness.py              # FR-012: FreshnessWindow; three clock types
│
└── tests/
    ├── contract/                 # Tier 1 — recorded fixtures, run on every push
    │   ├── conftest.py           # cassette directory wiring
    │   ├── test_allowlist.py     # SC-001, SC-002
    │   ├── test_models.py        # SC-002, SC-006
    │   ├── test_pricing.py       # SC-003
    │   ├── test_errors.py        # SC-004
    │   └── test_budget.py        # SC-005
    └── unit/
        ├── test_identifiers.py   # FR-004
        ├── test_freshness.py     # FR-012
        └── test_telemetry.py     # FR-009

fixtures/
└── atlas/
    ├── sel_tyo_search.json       # EXISTING — seed for Tier 1 cassettes
    ├── sel_tyo_verify.json       # EXISTING
    └── webhook_order_ticketed.json  # EXISTING
```

**Structure Decision**: Single-project web-application backend. The Atlas
contract lives as `backend/atlas/`, a plain Python package importable by
any other backend module. Tests live under `backend/tests/` split into
`contract/` (Tier 1, recorded) and `unit/`. No frontend files are touched
by this feature.

## Complexity Tracking

> No violations — section left blank per template rules.
