---
description: "Task list for Atlas Capability Contract (feature 000)"
---

# Tasks: Atlas Capability Contract

**Input**: Design documents from `specs/000-atlas-capability-contract/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Testing approach**: Test-First (Constitution IX). Every test task MUST be written and confirmed failing before its paired implementation task begins.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All file paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Create the `backend/atlas/` package skeleton and test infrastructure so all story phases can begin cleanly.

- [x] T001 Create `backend/atlas/__init__.py` as empty public re-export module
- [x] T002 [P] Create `backend/atlas/models/__init__.py` as empty package marker
- [x] T003 [P] Create `backend/tests/contract/` directory with `backend/tests/contract/__init__.py`
- [x] T004 [P] Create `backend/tests/unit/` directory with `backend/tests/unit/__init__.py`
- [x] T005 Create `backend/tests/contract/conftest.py` wiring cassette directory to `fixtures/atlas/cassettes/` via `pytest-recording`
- [x] T006 [P] Create `fixtures/atlas/cassettes/` directory placeholder (`.gitkeep`)
- [x] T007 Add `pydantic>=2.0`, `mypy`, `pytest`, `pytest-recording`, `pytest-html`, `httpx` to `backend/pyproject.toml` (or `requirements-dev.txt` if pyproject.toml absent)

**Checkpoint**: Package skeleton exists; `pytest backend/tests/` runs (zero tests collected, no errors).

---

## Phase 2: Foundational — OpaqueId and OrderStatus

**Purpose**: `OpaqueId` and `OrderStatus` are used by every model. They must exist before any model can be written.

⚠️ **CRITICAL**: No model or story work can begin until this phase is complete.

- [x] T008 Write failing unit tests for `OpaqueId` in `backend/tests/unit/test_identifiers.py`: equality, inequality, `str()` passthrough, absence of `__getitem__`, `__add__`, `__mod__` (FR-004)
- [x] T009 Implement `OpaqueId` frozen dataclass in `backend/atlas/identifiers.py` — private `_value: str` field; `__eq__`, `__hash__`, `__str__` only; no other dunder or string methods (FR-004)
- [x] T010 Confirm `test_identifiers.py` passes; confirm Mypy reports error when test code attempts `opaque_id[0:4]`
- [x] T011 [P] Write failing unit tests for `OrderStatus` IntEnum normalisation in `backend/tests/unit/test_models_base.py`: string `"1"` → `PAID_NOT_TICKETED`; integer `2` → `TICKETED`; unknown integer preserved (FR-006)
- [x] T012 [P] Implement `OrderStatus` IntEnum with `_missing_` fallback in `backend/atlas/models/_base.py` (FR-006)
- [x] T013 Confirm `test_models_base.py` passes

**Checkpoint**: `OpaqueId` and `OrderStatus` tests green; Mypy passes on both modules.

---

## Phase 3: User Story 1 — Endpoint Allowlist Enforcement (Priority: P1)

**Goal**: Any call to an endpoint not in the verified allowlist fails at build time (Mypy import error).

**Independent Test**: `mypy backend/atlas/` passes with `search.do` referenced; fails when `suggestFlight.do` is referenced; `pytest tests/contract/test_allowlist.py` green.

### Tests for User Story 1 ⚠️ Write and confirm failing FIRST

- [x] T014 [US1] Write failing contract tests in `backend/tests/contract/test_allowlist.py`: verified endpoint symbols are importable; `suggestFlight.do` symbol does not exist; unverified endpoints have `verification_status == "unverified"` (FR-001, FR-002, SC-001, SC-002)

### Implementation for User Story 1

- [x] T015 [US1] Implement `AllowedEndpoint` dataclass and `ENDPOINT_ALLOWLIST` frozenset in `backend/atlas/allowlist.py` — 6 verified entries + 9 unverified stubs, each with `name`, `path`, `verification_status` (FR-001)
- [x] T016 [US1] Export public allowlist symbols from `backend/atlas/__init__.py` (FR-002)
- [x] T017 [US1] Confirm `test_allowlist.py` passes; run `mypy backend/atlas/allowlist.py --strict` and confirm zero errors

**Checkpoint**: Allowlist tests green. `mypy` rejects any import of a non-existent endpoint symbol.

---

## Phase 4: User Story 2 — Typed Request and Response Shapes (Priority: P2)

**Goal**: Every verified endpoint has a Pydantic model with `extra="forbid"`. Accessing an undeclared field raises a Mypy error at check time.

**Independent Test**: `pytest tests/contract/test_models.py` green; `mypy backend/atlas/models/` --strict zero errors; accessing `routing.fare_code` produces a Mypy attribute error.

### Tests for User Story 2 ⚠️ Write and confirm failing FIRST

- [ ] T018 [P] [US2] Write failing contract tests for search models in `backend/tests/contract/test_models.py`: parse `fixtures/atlas/sel_tyo_search.json`; assert `routing.fid` is `OpaqueId`; assert `routing.adult_price` is `Decimal`; assert extra field raises `ValidationError` (FR-003, SC-002)
- [ ] T019 [P] [US2] Write failing contract tests for verify models in `backend/tests/contract/test_models.py`: parse `fixtures/atlas/sel_tyo_verify.json`; assert `session_id` is `OpaqueId`; assert `routing.expire_time` is `None`; assert `price_change.is_price_change` is `bool` (FR-003)
- [ ] T020 [P] [US2] Write failing contract tests for webhook model in `backend/tests/contract/test_models.py`: parse `fixtures/atlas/webhook_order_ticketed.json`; assert `data.order_status` is `OrderStatus.TICKETED` (integer `2` normalised); assert `status == -1` does not block parse (FR-003, FR-006, SC-006)

### Implementation for User Story 2

- [ ] T021 [P] [US2] Implement `Segment`, `BaggageElement`, `FareRule`, `Rule`, `BookingRequirementField`, `BookingRequirement` Pydantic models in `backend/atlas/models/search.py` (FR-003)
- [ ] T022 [P] [US2] Implement `Routing`, `SearchRequest`, `SearchResponse` Pydantic models in `backend/atlas/models/search.py` — `OpaqueId` for `fid` and `routing_identifier`; `Decimal` for monetary fields; `extra="forbid"` (FR-003)
- [ ] T023 [P] [US2] Implement `PriceChange`, `VerifyRequest`, `VerifyResponse` Pydantic models in `backend/atlas/models/verify.py` — `OpaqueId` for `session_id`; `extra="forbid"` (FR-003)
- [ ] T024 [P] [US2] Implement `Passenger`, `Contact`, `PaxTicketInfo`, `OrderRequest`, `OrderResponse` Pydantic models in `backend/atlas/models/order.py` — `OpaqueId` for `order_no`, `pnr_code`, `duplicate_orders`; `tkt_limit_time` as `datetime`; `extra="forbid"` (FR-003)
- [ ] T025 [P] [US2] Implement `PayRequest`, `PayResponse` Pydantic models in `backend/atlas/models/pay.py` — `OpaqueId` for `order_no`; `extra="forbid"` (FR-003)
- [ ] T026 [P] [US2] Implement `QueryOrderRequest`, `QueryOrderResponse` Pydantic models in `backend/atlas/models/query.py` — `order_status` field uses `OrderStatus` with string→int coercion validator; `OpaqueId` for `order_no`; `extra="forbid"` (FR-003, FR-006)
- [ ] T027 [US2] Implement `WebhookData`, `WebhookEvent` Pydantic models in `backend/atlas/models/webhook.py` — `order_status` field uses `OrderStatus` directly (integer from webhook); `OpaqueId` for `order_no`; `extra="forbid"`; webhook `status` field stored as-is (not gated on `== 0`) (FR-003, FR-006)
- [ ] T028 [US2] Export all model symbols from `backend/atlas/__init__.py`
- [ ] T029 [US2] Confirm all model tests in `test_models.py` pass; run `mypy backend/atlas/models/ --strict` and confirm zero errors

**Checkpoint**: All three fixture files parse successfully into typed models. `routing.fare_code` access fails Mypy.

---

## Phase 5: User Story 3 — Identifier Integrity (Priority: P2)

**Goal**: `OpaqueId` is used consistently across all models; no string-manipulation of identifiers is possible.

**Independent Test**: `pytest tests/unit/test_identifiers.py` green (already from Phase 2); Mypy rejects any subscript, concatenation, or format operation on an `OpaqueId` value.

### Tests for User Story 3 ⚠️ Write and confirm failing FIRST

- [ ] T030 [US3] Extend `backend/tests/unit/test_identifiers.py`: add round-trip test — create `OpaqueId` from a raw string, store it, retrieve it, confirm byte-for-byte identity with the original; add passthrough test confirming `str(opaque_id)` equals the original string (FR-004, SC-002)
- [ ] T031 [US3] Add Mypy negative test comment in `backend/tests/unit/test_identifiers.py` documenting that `opaque_id[0:4]` and `opaque_id + "suffix"` produce Mypy errors (to be verified manually during review)

### Implementation for User Story 3

- [ ] T032 [US3] Verify all `OpaqueId` usages in models from Phase 4 are correct — `fid`, `routing_identifier`, `session_id`, `order_no`, `pnr_code`, `ticket_nos`, `airline_pnrs`, `duplicate_orders` are all typed as `OpaqueId`, not `str` (FR-004)
- [ ] T033 [US3] Confirm `test_identifiers.py` full suite passes; run `mypy backend/atlas/identifiers.py --strict` zero errors

**Checkpoint**: All identifier fields are `OpaqueId`; Mypy gate enforced.

---

## Phase 6: User Story 4 — Canonical Price Calculation (Priority: P3)

**Goal**: One function computes the total price; no other code path sums the three fare components.

**Independent Test**: `pytest tests/contract/test_pricing.py` green; CI grep check fails if the three field names are summed outside `pricing.py`.

### Tests for User Story 4 ⚠️ Write and confirm failing FIRST

- [ ] T034 [US4] Write failing contract tests in `backend/tests/contract/test_pricing.py`: `canonical_total_price(Decimal("66.43"), Decimal("23.96"), Decimal("0.00"))` returns `CanonicalPrice(amount=Decimal("90.39"), currency="USD")`; function is importable only from `backend/atlas/pricing`; `CanonicalPrice` has no arithmetic operators (FR-005, SC-003)

### Implementation for User Story 4

- [ ] T035 [US4] Implement `CanonicalPrice` frozen dataclass and `canonical_total_price()` function in `backend/atlas/pricing.py` — `amount: Decimal`, `currency: Literal["USD"]`; no arithmetic operators on `CanonicalPrice` (FR-005)
- [ ] T036 [US4] Add ruff noqa-style CI grep rule (or ruff custom check) to `backend/pyproject.toml` that fails if `adult_price.*adult_tax` or `adultPrice.*adultTax` appears outside `pricing.py` (FR-005, SC-003)
- [ ] T037 [US4] Export `canonical_total_price`, `CanonicalPrice` from `backend/atlas/__init__.py`
- [ ] T038 [US4] Confirm `test_pricing.py` passes; run `mypy backend/atlas/pricing.py --strict` zero errors

**Checkpoint**: Price test green with `90.39`. CI grep check rejects out-of-module price arithmetic.

---

## Phase 7: User Story 5 — Error Classification and Rate-Limit Discipline (Priority: P3)

**Goal**: Every Atlas error code is classified; duplicate-booking returns the existing order reference; rate-limit hold is respected.

**Independent Test**: `pytest tests/contract/test_errors.py tests/contract/test_budget.py` green.

### Tests for User Story 5 ⚠️ Write and confirm failing FIRST

- [ ] T039 [P] [US5] Write failing contract tests in `backend/tests/contract/test_errors.py`: `classify(0)` → SUCCESS; `classify(318)` → `ReconcilableOutcome` with non-empty `duplicate_orders`; `classify(800)` → TERMINAL; `classify(900)` → TERMINAL; `classify(9999)` → TERMINAL (FR-007, FR-008, SC-004)
- [ ] T040 [P] [US5] Write failing contract tests in `backend/tests/contract/test_budget.py`: budget exhausted → raises `BudgetExhausted`; rate-limit hold with future `retry_after` → raises `RateLimitHold`; `retry_after=None` → indefinite hold, raises `RateLimitHold`; hold with past `retry_after` → call proceeds (FR-010, FR-011, SC-005)

### Implementation for User Story 5

- [ ] T041 [P] [US5] Implement `ErrorCode` IntEnum, `ErrorDisposition` enum, `ReconcilableOutcome` dataclass, and `classify()` function in `backend/atlas/errors.py` — codes 0, 318, 800, 900; unknown default terminal; `classify(318)` returns `ReconcilableOutcome` populated from `duplicate_orders` parameter (FR-007, FR-008)
- [ ] T042 [P] [US5] Implement `BudgetExhausted` exception, `RateLimitHold` dataclass, and `CallBudget` class in `backend/atlas/budget.py` — `check_and_record()` raises `BudgetExhausted` when limit reached; `apply_hold()` stores hold; hold with `retry_after=None` is indefinite; hold with past `retry_after` is cleared (FR-010, FR-011)
- [ ] T043 [US5] Export `ErrorCode`, `ErrorDisposition`, `ReconcilableOutcome`, `classify`, `CallBudget`, `RateLimitHold`, `BudgetExhausted` from `backend/atlas/__init__.py`
- [ ] T044 [US5] Confirm `test_errors.py` and `test_budget.py` both pass; run `mypy backend/atlas/errors.py backend/atlas/budget.py --strict` zero errors

**Checkpoint**: Error and budget tests green. `classify(318)` surfaces existing order reference. Rate-limit hold blocks retry.

---

## Phase 8: Cross-Cutting — Telemetry and Freshness

**Purpose**: `CallRecord` (FR-009) and `FreshnessWindow` (FR-012) are infrastructure shared across all stories. They have no story dependency but are written last to avoid blocking the story phases.

### Tests ⚠️ Write and confirm failing FIRST

- [ ] T045 [P] Write failing unit tests in `backend/tests/unit/test_telemetry.py`: `CallRecord` has `endpoint`, `outcome`, `elapsed_ms`, `journey_id`, `recorded_at` fields; records are immutable (no mutation after creation) (FR-009)
- [ ] T046 [P] Write failing unit tests in `backend/tests/unit/test_freshness.py`: `from_offer()` with past `expire_time` → `is_usable()` returns `False`; `from_offer()` with future `expire_time` → `is_usable()` returns `True`; `from_session()` → `expires_at=None` → `is_usable()` returns `False`; `from_ticket()` with future `tkt_limit_time` → `is_usable()` returns `True` (FR-012)

### Implementation

- [ ] T047 [P] Implement `CallRecord` frozen dataclass in `backend/atlas/telemetry.py` — five fields; no mutation; `recorded_at` defaults to UTC now on construction (FR-009)
- [ ] T048 [P] Implement `FreshnessWindow` frozen dataclass with `clock_type` discriminator, `issued_at`, `expires_at`, `is_usable(now)` method, and three factory class methods (`from_offer`, `from_session`, `from_ticket`) in `backend/atlas/freshness.py` (FR-012)
- [ ] T049 Export `CallRecord`, `FreshnessWindow` from `backend/atlas/__init__.py`
- [ ] T050 Confirm `test_telemetry.py` and `test_freshness.py` pass; run `mypy backend/atlas/telemetry.py backend/atlas/freshness.py --strict` zero errors

**Checkpoint**: All unit tests green. `FreshnessWindow` correctly rejects expired-on-receipt offers.

---

## Phase 9: CI Gate and Full Suite

**Purpose**: Wire Mypy strict and pytest into CI; confirm full test suite green; generate HTML report.

- [ ] T051 Create `.github/workflows/contract.yml` (or equivalent CI config) running `mypy backend/atlas/ --strict` and `pytest backend/tests/ --html=reports/contract.html --self-contained-html` on every push to any branch
- [ ] T052 Run full test suite locally: `pytest backend/tests/ -v --html=reports/contract.html --self-contained-html` — confirm all tests pass; commit HTML report path to `.gitignore`
- [ ] T053 Run `mypy backend/atlas/ --strict` — confirm zero errors across all modules
- [ ] T054 [P] Verify Tier 1 / Tier 2 fixture parity: run `pytest backend/tests/contract/ --record-mode=new_episodes` against live sandbox (requires `ATLAS_CLIENT_ID` + `ATLAS_CLIENT_SECRET`); commit any new cassettes to `fixtures/atlas/cassettes/`
- [ ] T055 [P] Generate traceability confirmation: for each FR-001 through FR-012 and NFR-001 through NFR-003, confirm at least one test in the suite references the requirement (cross-check against `data-model.md` traceability matrix)

**Checkpoint**: CI passes on every push. Mypy strict clean. All 12 FRs and 3 NFRs have test coverage. Tier 1 cassettes committed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **blocks all model and story work**
- **US1 — Allowlist (Phase 3)**: Depends on Phase 2
- **US2 — Typed Models (Phase 4)**: Depends on Phase 2 (needs `OpaqueId`, `OrderStatus`)
- **US3 — Identifier Integrity (Phase 5)**: Depends on Phase 4 (verifies model field types)
- **US4 — Canonical Price (Phase 6)**: Depends on Phase 4 (uses `Decimal` from models)
- **US5 — Error/Budget (Phase 7)**: Depends on Phase 2 (`OpaqueId` in `ReconcilableOutcome`)
- **Cross-Cutting (Phase 8)**: Depends on Phase 4 (FreshnessWindow uses OrderResponse)
- **CI Gate (Phase 9)**: Depends on all phases complete

### Parallel Opportunities Within Phases

```bash
# Phase 4 — all model files are independent:
Task T021  backend/atlas/models/search.py (Segment, Rule, sub-models)
Task T022  backend/atlas/models/search.py (Routing, SearchRequest, SearchResponse)
Task T023  backend/atlas/models/verify.py
Task T024  backend/atlas/models/order.py
Task T025  backend/atlas/models/pay.py
Task T026  backend/atlas/models/query.py
# T027 (webhook.py) depends on T026 (OrderStatus already in query.py)

# Phase 7 — errors and budget are independent:
Task T039 + T041  errors.py test + impl
Task T040 + T042  budget.py test + impl

# Phase 8 — telemetry and freshness are independent:
Task T045 + T047  telemetry test + impl
Task T046 + T048  freshness test + impl
```

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2
- **US2 (P2)**: Independent after Phase 2; US3 validates US2's identifier usage
- **US3 (P2)**: Depends on US2 completion
- **US4 (P3)**: Independent after Phase 2; uses `Decimal` type from US2 models
- **US5 (P3)**: Independent after Phase 2

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (OpaqueId + OrderStatus)
3. Complete Phase 3 (Allowlist)
4. **STOP AND VALIDATE**: Run `mypy backend/atlas/ --strict`; run `pytest tests/contract/test_allowlist.py -v`
5. Demonstrate: `mypy` rejects `suggestFlight.do` import; accepts `search.do`

### Incremental Delivery

1. Setup + Foundational → skeleton ready
2. US1 → Allowlist gate active — **primary safety guarantee delivered**
3. US2 → Typed models for all verified endpoints
4. US3 → Identifier integrity verified (validates US2)
5. US4 → Canonical price enforced
6. US5 → Error classification + rate-limit discipline
7. Cross-Cutting + CI Gate → full suite wired

---

## Notes

- `[P]` = different files, no incomplete dependencies — safe to run in parallel
- `[USn]` maps directly to user stories in `specs/000-atlas-capability-contract/spec.md`
- Every test task MUST be confirmed failing before its paired implementation task (Constitution IX)
- Commit after each task — one task, one commit, one demonstrable capability (Constitution XV, XVI)
- Do not hand-write fixtures; run Tier 2 (`--record-mode=new_episodes`) to capture (Constitution XI, NFR-003)
- Existing fixtures at `fixtures/atlas/sel_tyo_search.json`, `sel_tyo_verify.json`, `webhook_order_ticketed.json` are the seeds for cassette capture
