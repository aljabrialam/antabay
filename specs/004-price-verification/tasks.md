# Tasks: Price Verification and Offer Staleness

**Input**: Design documents from `specs/004-price-verification/`

**Feature**: 004-price-verification | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `ImportError` or `AttributeError` satisfy the gate.

**Fixture discipline (Constitution Principle XI)**: Only one Tier 1 cassette exists for this feature — `verify_ze605.yaml`, transcribed from the real capture in `.antabay/atlas-capability-map.md` §7a (`isPriceChange: false`, success). The price-changed and unavailable response paths are **not yet captured from a live sandbox run**, so they are exercised with plain Python dict fixtures in unit tests, not disguised as VCR cassettes. Do not fabricate a cassette for either — that would violate "recordings MUST be captured from Tier 2 runs and MUST NOT be handwritten." Replace the dict fixtures with a real cassette once one is captured.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Schema and fixture groundwork used by every story.

- [x] T001 [P] Add `verifications` table to `backend/journey/storage/tables.py`: columns `verification_id` (String PK), `journey_id` (String FK → journeys), `option_id` (String FK → flight_options), `requested_at`/`responded_at` (String, ISO-8601), `raw_response_json` (Text), `status_code` (Integer), `atlas_status` (Integer, nullable), `outcome` (String), `session_id` (String, nullable), `max_seats` (Integer, nullable), `price_change_json` (Text, nullable), `passenger_requirements_json` (Text), `budget_before`/`budget_after` (Integer)
- [x] T002 Migration `backend/journey/migrations/versions/g7b863k29l46_add_verifications.py` created, `down_revision = 'f6a752j18i35'`
- [x] T003 [P] `backend/tests/fixtures/atlas/cassettes/verification/verify_ze605.yaml` created — `sessionId`/`fid`/`routingIdentifier` use the repo's existing `<REDACTED>` convention (matching `search_sel_tyo.yaml`'s own redaction of opaque identifiers) rather than a fabricated-looking real value; all 9 observed `bookingRequirement.passenger` fields, `maxSeats: 7`, `isPriceChange: false`, `adultPrice 66.43`/`adultTax 23.96` all present per the capability map capture

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 224 passed, 6 deselected. No regressions.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model types, storage methods, state-machine extension, and service skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 [P] `backend/journey/models/verification.py` created with `PriceChange`, `PassengerRequirementField`, `VerificationOutcome`, `VerificationResult` exactly per data-model.md, plus `invalidates_authorisation: bool` on `VerificationResult` (T016's field, declared here since it's part of the same dataclass)
- [x] T005 `JourneyState.VERIFIED` added; `_ALLOWED_TRANSITIONS` extended with `SEARCHING → VERIFIED` and `VERIFIED → {SEARCHING, CANCELLED, ABANDONED}`
- [x] T006 `get_flight_option(option_id) -> FlightOption | None` (not originally named in this task, but required for `verify()` to look up `routing_identifier` — no such single-option lookup existed before this feature), `save_verification()`, and `get_latest_verification()` added to `backend/journey/storage/repository.py`
- [x] T007 `AtlasVerifyError` and `OptionUnavailableError` added to `backend/journey/errors.py` (`OptionUnavailableError` is defined but not currently raised — outcome classification uses the `UNAVAILABLE` enum value instead, matching how `search.do`'s errors are surfaced via `SearchOutcome` rather than always raising)
- [x] T008 `VerificationService` skeleton created with `SESSION_WINDOW_SECONDS` module constant (research.md R2) alongside it

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — 224 passed. `from journey.services.verification_service import VerificationService` succeeds.

---

## Phase 3: User Story 1 — Verify Before Commitment (Priority: P1) 🎯 MVP

**Goal**: Before any order is created, the selected option is verified with Atlas; the identifier is forwarded unmodified; the price-change signal is read from the provider, never computed; a reported price change invalidates any prior authorisation; every call is counted against the shared call budget.

**Independent Test**: Call `VerificationService.verify()` for a held option against the `verify_ze605.yaml` cassette and confirm the request's `routingIdentifier` matches the option's stored value byte-for-byte, the outcome is `VERIFIED`, and `budget_after == budget_before - 1`. Feed a price-changed response dict through the same parsing path and confirm the outcome is `PRICE_CHANGED` with an invalidation signal set.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T009 [P] [US1] `backend/tests/contract/test_verify_contract.py` written against `verify_ze605.yaml`. **Deviation**: the identifier-integrity assertion originally planned here was moved entirely to T011. vcrpy's `vcr` fixture exposes the cassette's *stored* request object (`cassette.py`: "Use stored ... request, not the raw incoming request"), not what the test run actually sent, so it cannot prove what `verify()` put on the wire — an `httpx.MockTransport` (T011) can and does.
- [x] T010 [P] [US1] `TestVerifyPriceChanged` added to `backend/tests/unit/test_verification_service.py`, feeding a plain dict through a new `VerificationService._parse_response()` (a pure-classification helper split out of `verify()` specifically so US1/US3's response-shape behaviour is unit-testable without HTTP mocking for every permutation — not originally named in this task but required to test it as described)
- [x] T011 [P] [US1] `TestVerifyIdentifierIntegrity` added, using `httpx.MockTransport` to capture the real request body and assert it equals the seeded option's `routing_identifier`
- [x] T012 [P] [US1] `TestVerifyCallBudget` added (both the decrement/record case and the pre-HTTP-call `BudgetExhaustedError` case, asserting zero HTTP calls were made)
- [x] T013 [US1] Confirmed: all of T009–T012 failed with `NotImplementedError` (`verify()`/`needs_reverification()`) or `AttributeError` (`_parse_response` not yet existing) before implementation

### Implementation for User Story 1

- [x] T014 [US1] `VerificationService.verify()` implemented: looks up the option via the new `get_flight_option()`, decrements budget via the existing shared mechanism, POSTs to `verify.do`, handles 429 and unparseable-body paths
- [x] T015 [US1] Outcome classification implemented inside `_parse_response()`: `status == 0` + falsy/absent `isPriceChange` → `VERIFIED`; `status == 0` + truthy `isPriceChange` → `PRICE_CHANGED`; anything else → `UNAVAILABLE`
- [x] T016 [US1] `invalidates_authorisation` set `True` only on `PRICE_CHANGED` in `_parse_response()`
- [x] T017 [US1] `SEARCHING → VERIFIED` transition implemented in `_on_verified()`, guarded on the journey's current state
- [x] T018 [US1] `save_verification()` called on every code path (success/price-changed/unavailable via `_parse_response()`'s result, plus the 429 and unparseable-body paths built via a separate `_build_result()` helper)
- [x] T019 [US1] `python -m pytest backend/tests/contract/test_verify_contract.py backend/tests/unit/test_verification_service.py -v -k "PriceChanged or IdentifierIntegrity or CallBudget or contract"` — 6 passed

**Checkpoint**: US1 complete. A selected option can be verified; identifier integrity, price-change reading, invalidation signalling, and budget accounting are all correct and tested.

---

## Phase 4: User Story 2 — Freshness Window Handoff (Priority: P2)

**Goal**: Once verification succeeds, the offer-level freshness window is retired and a session-level window (bounded by `sessionId`) begins, tracked separately. The system re-verifies once the held session's remaining time falls inside a declared safety margin.

**Independent Test**: Run a successful verify and confirm a new `held_identifiers` row exists for the returned `sessionId` alongside the untouched offer-window row for the original `routingIdentifier`. Call `needs_reverification()` with `now` inside and outside the configured margin and confirm the boolean flips correctly.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T020 [P] [US2] `TestSessionFreshnessWindow` added to `backend/tests/integration/test_verification_persistence.py`. **Note**: exercised against a mocked `httpx` response (matching the `_verified_response()` fixture shape), not the VCR cassette — the seed helper also had to be extended to pre-seed the offer-window `held_identifiers` row and transition the journey to `SEARCHING` first, mirroring what 002-flight-search would already have done in the real flow; without that, there is no offer-window row to assert "remains untouched" against
- [x] T021 [P] [US2] `TestNeedsReverification` added, covering both the inside/outside-margin boolean and the `IdentifierNotFoundError` case
- [x] T022 [US2] Confirmed: both failed with `NotImplementedError` before implementation

### Implementation for User Story 2

- [x] T023 [US2] Session-window creation implemented in `_on_verified()`, called from `verify()` on `VERIFIED`/`PRICE_CHANGED`
- [x] T024 [US2] `needs_reverification()` implemented: finds the session identifier via `_find_session_identifier()` (the most-recently-issued `held_identifiers` row — valid because this service is the only writer of session rows and always creates them after the offer row already exists) and compares `stale_at - now` against the margin
- [x] T025 [US2] `python -m pytest backend/tests/integration/test_verification_persistence.py backend/tests/unit/test_verification_service.py -v -k "SessionFreshnessWindow or NeedsReverification"` — 4 passed

**Checkpoint**: US2 complete. The two freshness windows are tracked distinctly and re-verification triggers proactively ahead of the documented expiry (NFR-001).

---

## Phase 5: User Story 3 — Runtime Requirements Capture (Priority: P2)

**Goal**: Passenger field requirements and the maximum bookable quantity are read from each verification response and recorded as-is — never a fixed template, never carried over from a previous verification.

**Independent Test**: Verify two options against response fixtures with different `bookingRequirement.passenger` field sets and confirm each produces its own distinct, exactly-matching `passenger_requirements` list, with `max_seats` matching each response's own `maxSeats`.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T026 [P] [US3] `TestPassengerRequirementsCapture` added
- [x] T027 [P] [US3] `TestPassengerRequirementsEmptySet` added
- [x] T028 [P] [US3] `TestMaxSeatsCapture` added, using two `_parse_response()` calls with different `maxSeats` values on the same option to prove no leakage between calls
- [x] T029 [US3] Confirmed: all three failed with `AttributeError` (`_parse_response` not yet existing) before implementation

### Implementation for User Story 3

- [x] T030 [US3] Passenger-requirement extraction implemented inline in `_parse_response()` (not a separate `_extract_passenger_requirements()` function as originally named — folded into the same response-classification pass since both read from the same `response_json` and there was no benefit to a separate function call boundary): maps each key of `bookingRequirement.passenger` to a `PassengerRequirementField`; empty/absent `bookingRequirement` or `passenger` yields `[]`, never a substituted default
- [x] T031 [US3] `max_seats` capture implemented in the same pass: `None` unless outcome is `VERIFIED`/`PRICE_CHANGED`
- [x] T032 [US3] `python -m pytest backend/tests/unit/test_verification_service.py -v -k "PassengerRequirements or MaxSeats"` — 3 passed

**Checkpoint**: US3 complete. Passenger requirements and bookable quantity are always read fresh from the response that produced them.

---

## Phase 6: User Story 4 — Unavailable Option Recovery (Priority: P3)

**Goal**: When verification reports the selected option is no longer available, the journey returns to the search state rather than proceeding or getting stuck.

**Independent Test**: Feed a non-zero-status, non-price-change response dict through `verify()` for a journey currently `VERIFIED`, and confirm the journey's state becomes `SEARCHING` and the outcome is `UNAVAILABLE`.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T033 [P] [US4] `TestUnavailableRecovery` added: verifies successfully first (reaching `VERIFIED`), then re-verifies against a 404-style unavailable response
- [x] T034 [US4] Confirmed: failed with `NotImplementedError` before implementation

### Implementation for User Story 4

- [x] T035 [US4] `VERIFIED → SEARCHING` transition implemented in `_on_unavailable()`, called from `verify()` on `UNAVAILABLE`, guarded on the journey currently being `VERIFIED`
- [x] T036 [US4] `python -m pytest backend/tests/integration/test_verification_persistence.py -v -k UnavailableRecovery` — 1 passed

**Checkpoint**: US4 complete. An unavailable option no longer leaves the journey stuck on a dead verification.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and audit trail confirmation across all four stories.

- [x] T037 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_004.html` — 241 passed (224 baseline + 17 new), 4 pre-existing failures unrelated to this feature (`test_objective_parser.py` needs `DASHSCOPE_API_KEY`, not set in this environment). Report at `backend/reports/report_004.html`.
- [x] T038 [P] Walked through all four quickstart.md scenarios — each is now directly exercised by an automated test: Scenario 1 → `test_verify_contract.py` + `TestVerifyIdentifierIntegrity`/`TestVerifyCallBudget`; Scenario 2 → `TestSessionFreshnessWindow`/`TestNeedsReverification`; Scenario 3 → `TestPassengerRequirementsCapture`/`TestMaxSeatsCapture`; Scenario 4 → `TestUnavailableRecovery`
- [x] T039 [P] NFR-002 gap found and closed: `RATE_LIMITED` and `ERROR` outcomes were not exercised by any test task in this file. Added `TestVerifyRateLimited` and `TestVerifyError` to `test_verification_service.py`, asserting `raw_response_json` is persisted and non-empty (including the raw unparseable bytes verbatim) on both paths. All 5 outcome types are now confirmed to persist their full response.
- [x] T040 `backend/journey/__init__.py` now exports `VerificationService`, `VerificationResult`, `VerificationOutcome`, `PriceChange`, `PassengerRequirementField`
- [x] T041 `mypy journey` run. Two real errors introduced by this feature were found and fixed: (1) `repository.py` referenced `VerificationResult` in signatures without a `TYPE_CHECKING` import; (2) `_find_session_identifier` was typed to accept/return `Any`, making `needs_reverification()`'s boolean return silently `Any` — retyped to `JourneyRecord`/`HeldIdentifier`. Confirmed via a stashed-diff baseline that all remaining errors (`scoring_service.py`, `repository.py`'s untyped-`dict` warnings) predate this feature and are unrelated to it.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on Phase 2 and on US1's `verify()` existing (it hooks into the same method's success path) — but is independently testable once that hook point exists
- **US3 (Phase 5)**: Depends on Phase 2 and on US1's `verify()` existing (same reason as US2) — independently testable
- **US4 (Phase 6)**: Depends on Phase 2 and on US1's outcome classification (T015) already producing `UNAVAILABLE` — independently testable
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4.
- **US2**, **US3**, and **US4** are each additive to the single `verify()` method US1 delivers — they do not depend on each other, and each has its own test file/class that can be verified failing and then passing in isolation, but all three require US1's `verify()` skeleton (T014–T015) to exist first because there is only one method to extend, not three independent ones. This mirrors the shared-endpoint pattern already used in spec 006 (US2's auth endpoint was additive to US1's SSE stream).

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic in `verification_service.py` / `repository.py` / `journey.py`
3. Confirm tests PASS

### Parallel Opportunities

- T001, T003 (Setup) can run in parallel; T002 depends on T001
- T004, T005, T007 (Foundational) can run in parallel; T006 depends on T004; T008 depends on T004+T006
- Within US1: T009–T012 (tests) all parallel; T014 must land before T015–T018 (sequential, same file)
- Within US2: T020–T021 (tests) parallel
- Within US3: T026–T028 (tests) parallel
- US2, US3, and US4's test-writing (T020–T021, T026–T028, T033) can all happen in parallel with each other once US1's T014–T015 exist, even though their implementation tasks touch the same file sequentially

---

## Parallel Example: Foundational Phase

```bash
# T004, T005, T007 touch different files — safe to parallelize:
T004: backend/journey/models/verification.py
T005: backend/journey/models/journey.py
T007: backend/journey/errors.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T008)
3. Complete Phase 3: US1 tests (T009–T013) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T014–T018)
5. Run T019 gate — all tests must pass
6. **STOP and VALIDATE**: A selected option can be verified end-to-end with correct identifier integrity, price-change reading, and budget accounting
7. This is the commitment-safety gate itself — demo-ready as the core capability

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → verify-before-commit gate working → the core safety property is enforced
3. US2 → freshness-window handoff + proactive re-verification working
4. US3 → passenger requirements and quantity always read fresh
5. US4 → unavailable options recover cleanly to search
6. Polish → full regression + quickstart walkthrough + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files with no incomplete dependency — safe to parallelize
- Only `verify_ze605.yaml` is a real VCR cassette; price-changed and unavailable scenarios use plain dict fixtures in unit tests until a live sandbox capture of those conditions exists (Constitution Principle XI — see the Fixture Discipline note at the top of this file)
- `routingIdentifier` and `sessionId` both flow through `atlas.identifiers.OpaqueId` — no task in this file should introduce string concatenation, slicing, or parsing of either value
- `verify.do` is already `verified` in `backend/atlas/allowlist.py` — no allowlist change is part of this feature
- The session window's duration is a configured constant (research.md R2), not parsed from the response — do not add a task that tries to read a session expiry field from `verify.do`, because none exists
