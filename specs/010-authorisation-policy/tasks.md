# Tasks: Authorisation Policy Engine

**Input**: Design documents from `specs/010-authorisation-policy/`

**Feature**: 010-authorisation-policy | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `NotImplementedError`, `ImportError`, or `AttributeError` satisfy the gate.

**Scope boundary (Constitution Principle XVI, plan.md Constitution Check)**: This feature does not modify `journey/api/routers/events.py`, `journey/services/event_service.py`'s existing methods, or `journey/services/booking_service.py`. It reuses feature 006's existing `AUTHORISATION_REQUESTED`/`AUTHORISATION_OUTCOME` event vocabulary and `POST /journeys/{id}/authorisation/{request_id}` endpoint unmodified, and it does not wire its enforcement primitive into any action-executing caller — see research.md R5.

**Fixed rule set (NFR-003)**: The four rules (`AUTH-MONEY`, `AUTH-CANCEL`, `AUTH-IRREVERSIBLE`, `AUTH-CONSTRAINT`) are hardcoded in the engine, not dependency-injected or configurable — unlike feature 012's per-action-type registration pattern, these four categories are universal and fixed by design, so no task in this file introduces a way to add, remove, or override one.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the target files/modules this feature will create do not already exist under conflicting names, and that the existing 006 infrastructure this feature depends on is present and passing.

- [x] T001 Confirmed: `tests/contract/test_auth_contract.py` + `tests/integration/test_auth_gate.py` — 7 passed
- [x] T002 [P] Confirmed: neither `journey/models/authorisation_policy.py` nor `journey/services/authorisation_policy_engine.py` exists yet

**Checkpoint**: `python -m pytest backend/tests/contract/test_auth_contract.py backend/tests/integration/test_auth_gate.py -v` — both suites pass unmodified before any new code is written.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The model types and engine skeleton every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 [P] `backend/journey/models/authorisation_policy.py` created with `ProposedAction`, `Rule` (with `RULE_DESCRIPTIONS`), and `AuthorisationDecision` per data-model.md
- [x] T004 `backend/journey/services/authorisation_policy_engine.py` created with `AuthorisationPolicyEngine.evaluate()`/`request_if_required()`/`enforce_authorised()` raising `NotImplementedError`

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` — no regressions. `from journey.services.authorisation_policy_engine import AuthorisationPolicyEngine` succeeds.

---

## Phase 3: User Story 1 — Deterministic Classification of Every Proposed Action (Priority: P1) 🎯 MVP

**Goal**: Every proposed action is classified — permitted autonomously or requiring authorisation — without consulting a language model; the same action and context always produce the same classification; every decision names the specific rule(s) that produced it.

**Independent Test**: Evaluate the same `ProposedAction` repeatedly and confirm identical classifications. Evaluate an action triggering more than one rule and confirm every triggered rule is named. Inspect the decision path for any language-model dependency.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T005 [P] [US1] `TestEvaluateClassifiesBeforeAnyExecutionSignal` written
- [x] T006 [P] [US1] `TestEvaluateIsDeterministic` written
- [x] T007 [P] [US1] `TestNoLanguageModelConsulted` written (AST-based import scan)
- [x] T008 [P] [US1] `TestMultipleRulesAllNamedNotJustFirst` written
- [x] T009 [US1] Confirmed: T005/T006/T008 (and the US2 rule tests written alongside) failed with `NotImplementedError`; T007 passed immediately — a static import-scan true against the empty skeleton, not a TDD-gate violation

### Implementation for User Story 1

- [x] T010 [US1] `AuthorisationPolicyEngine.evaluate()` implemented — four hardcoded boolean checks, pure Python, no external call
- [x] T011 [US1] `python -m pytest backend/tests/unit/test_authorisation_policy_engine.py -v -k "ClassifiesBefore or Deterministic or NoLanguageModel or MultipleRules"` — 4 passed

**Checkpoint**: US1 complete. The engine classifies deterministically, without an LLM, and names every rule that fired.

---

## Phase 4: User Story 2 — Rules That Force Human Authorisation (Priority: P1)

**Goal**: Each of the four rules is proven, individually and in isolation, to force authorisation when its condition is met and to leave the classification unforced when it is not (NFR-004). This story adds test rigor over the engine US1 already implemented — it introduces no new production code, since the four rules are not independently togglable pieces of logic but a single fixed set evaluated together by design.

**Independent Test**: For each rule, construct one triggering and one non-triggering `ProposedAction`, evaluate both, and confirm the rule's effect in isolation from the other three.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T012 [P] [US2] `TestAuthMoneyRuleBothDirections` written
- [x] T013 [P] [US2] `TestAuthCancelRuleBothDirections` written
- [x] T014 [P] [US2] `TestAuthIrreversibleRuleBothDirections` written
- [x] T015 [P] [US2] `TestAuthConstraintRuleBothDirections` written
- [x] T016 [US2] Confirmed: all 8 (both-directions × 4 rules) failed with `NotImplementedError` before US1's `evaluate()` was implemented

### Implementation for User Story 2

- [x] T017 [US2] No new implementation needed — US1's `evaluate()` (T010) already satisfies every case; all 8 passed on the first run after T010
- [x] T018 [US2] `python -m pytest backend/tests/unit/test_authorisation_policy_engine.py -v -k "BothDirections"` — 8 passed

**Checkpoint**: US2 complete. Every rule is independently proven in both directions.

---

## Phase 5: User Story 3 — Authorisation Request, Response, and Enforcement (Priority: P1)

**Goal**: A requires-authorisation classification produces a correctly-shaped request on the existing (006) event stream; an unanswered or refused request blocks execution; a granted one permits it; no path exists to a "may proceed" answer other than a real recorded grant.

**Independent Test**: Trigger a requires-authorisation classification and confirm the request payload states the action, cost, and objective effect. Confirm `enforce_authorised()` returns `False` before any response, `False` after an explicit refusal, and `True` after a grant. Confirm the enforcement function's signature carries no parameter that could assert authorisation without a real grant.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T019 [P] [US3] `TestRequestIfRequiredAppendsAuthorisationRequestedEvent` written
- [x] T020 [P] [US3] `TestRequestIfRequiredSkipsEventWhenPermitted` written
- [x] T021 [P] [US3] `TestEnforceAuthorisedFalseWhenNoRequestExists` written
- [x] T022 [P] [US3] `TestEnforceAuthorisedFalseWhenUnanswered` written
- [x] T023 [P] [US3] `TestEnforceAuthorisedFalseWhenRefused` written
- [x] T024 [P] [US3] `TestEnforceAuthorisedTrueWhenApproved` written
- [x] T025 [P] [US3] `TestEnforceAuthorisedHasNoTrustMeParameter` written
- [x] T026 [US3] Confirmed: 6 of 7 failed with `NotImplementedError`; `TestEnforceAuthorisedHasNoTrustMeParameter` passed immediately (structural, true against the empty skeleton). **Design gap found while writing these tests**: the existing (006) `AuthorisationRequestedPayload` had no `action_id` field at all — only `request_id`/`action`/`cost`/`objective_effect`/`rule_id` — so `enforce_authorised()` had no way to look up "the current request for this action." Fixed by adding `action_id: str | None = None` to `AuthorisationRequestedPayload` in `journey/models/events.py` — additive and backward-compatible (defaults to `None`, so 006's existing fixtures in `test_auth_contract.py`/`test_auth_gate.py`, which never pass it, are unaffected). Also added `EventType.AUTHORISATION_VOIDED` + `AuthorisationVoidedPayload` at this point (pulled forward from T035, same file, same edit)
- [x] T026a Confirmed no regression: `python -m pytest backend/tests/ -k "not vcr"` — 285 passed after the `events.py` extension

### Implementation for User Story 3

- [x] T027 [US3] `AuthorisationPolicyEngine.request_if_required()` implemented — calls `evaluate()`, appends `AUTHORISATION_REQUESTED` (with `action_id`, `rule_id` joined by `+`) via the existing `EventService.append()` only when required
- [x] T028 [US3] `AuthorisationPolicyEngine.enforce_authorised()` implemented — reads the event stream, resolves no-request/unanswered/refused/approved via `_latest_request_for()`/`_outcome_for()` helpers; cost comparison deferred to US4 as planned
- [x] T029 [US3] `python -m pytest backend/tests/unit/test_authorisation_enforcement.py -v -k "RequestIfRequired or EnforceAuthorised"` — 7 passed

**Checkpoint**: US3 complete. Requests are correctly shaped and recorded on the existing stream; execution is blocked absent a real, recorded grant; the enforcement function structurally cannot be talked past.

---

## Phase 6: User Story 4 — Authorisation Scope and Staleness (Priority: P2)

**Goal**: A grant applies to exactly the one action it was requested for — never to a subsequent action, even of the same type or against the same booking — and is voided the moment its action's cost changes before execution.

**Independent Test**: Grant authorisation for one action, then check a different `action_id` at the same cost — confirm the grant does not apply. Change the granted action's cost before execution — confirm the grant is voided and a fresh request is required. Resubmit the identical action/cost unchanged — confirm no duplicate request is issued.

### Tests for User Story 4

> **Write these tests FIRST — verify they FAIL before any implementation**

- [x] T030 [P] [US4] `TestGrantDoesNotCarryToSubsequentAction` written
- [x] T031 [P] [US4] `TestCostChangeVoidsGrant` written (plus an idempotency assertion — re-checking an already-voided grant must not double-void)
- [x] T032 [P] [US4] `TestIdenticalResubmissionReusesExistingGrant` written
- [x] T033 [P] [US4] `TestFreshRequestIssuedAfterVoid` written
- [x] T034 [US4] Confirmed: `TestCostChangeVoidsGrant` and `TestIdenticalResubmissionReusesExistingGrant` failed before implementation; `TestGrantDoesNotCarryToSubsequentAction` and `TestFreshRequestIssuedAfterVoid` passed immediately against US3's implementation alone (US3's `enforce_authorised` already returns `False` for an unrelated `action_id`, and its `request_if_required` already appended a fresh event unconditionally, which happens to satisfy the "distinct request_id" assertion even before dedup exists) — not a TDD-gate violation, the same "already-true-against-the-prior-story's-code" pattern as T028 in 012. **Second design gap found here**: `AuthorisationRequestedPayload.cost` is a human-readable string (`"+USD 50.00"`) that cannot be compared against the raw `Decimal` `enforce_authorised()` receives. Fixed by adding a second field, `cost_amount: str | None = None` (the `Decimal` serialised as text) — additive and backward-compatible, same reasoning as `action_id`

### Implementation for User Story 4

- [x] T035 [US4] `EventType.AUTHORISATION_VOIDED` + `AuthorisationVoidedPayload` (`request_id`, `granted_cost`, `current_cost` — numeric strings, not currency-formatted, since `enforce_authorised()` only has a bare `Decimal` to work with) added to `events.py` (done together with T026's `action_id` fix, same file/same edit)
- [x] T036 [US4] `enforce_authorised()` extended: compares `cost_amount` against `current_cost_amount`; on mismatch, appends `AUTHORISATION_VOIDED` — guarded by `_voided_for()` so a repeated check against an already-voided grant never double-voids — then returns `False`
- [x] T037 [US4] `request_if_required()` extended: calls `enforce_authorised()` first: cost unchanged with a live approved grant → returns the decision with no new event; cost changed or nothing granted → falls through to a fresh `AUTHORISATION_REQUESTED`
- [x] T038 [US4] `python -m pytest backend/tests/unit/test_authorisation_enforcement.py -v -k "SubsequentAction or CostChange or Resubmission or FreshRequest"` — 4 passed

**Checkpoint**: US4 complete. Grants are scoped to exactly the action they were issued for and go stale the instant their terms change, without either silently persisting past their scope or being needlessly re-requested for an unchanged retry.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, quickstart validation, and NFR confirmation.

- [x] T039 [P] `python -m pytest backend/tests/ --tb=short --html=reports/report_010.html` — 306 passed, 4 pre-existing failures (`test_objective_parser.py`, unrelated `DASHSCOPE_API_KEY` dependency, predate this feature); `test_auth_contract.py`/`test_auth_gate.py` (006) confirmed passing unmodified both before and after this feature's `events.py` schema extension
- [x] T040 [P] Walked through all four quickstart.md scenarios — each maps directly to a passing test class already in the suite (Scenario 1 → `TestEvaluateClassifiesBeforeAnyExecutionSignal`/`TestEvaluateIsDeterministic`/`TestMultipleRulesAllNamedNotJustFirst`/`TestNoLanguageModelConsulted`; Scenario 2 → the four `*BothDirections` classes; Scenario 3 → `TestRequestIfRequiredAppendsAuthorisationRequestedEvent`/`TestEnforceAuthorisedFalseWhenUnanswered`/`TestEnforceAuthorisedFalseWhenRefused`/`TestEnforceAuthorisedTrueWhenApproved`; Scenario 4 → `TestGrantDoesNotCarryToSubsequentAction`/`TestCostChangeVoidsGrant`/`TestFreshRequestIssuedAfterVoid`) — no discrepancy found
- [x] T041 [P] NFR-002 confirmed via a new test, `TestRuleDescriptionsAreReadable` — every `Rule` has a `RULE_DESCRIPTIONS` entry, a non-trivial sentence, no code-facing jargon
- [x] T042 [P] NFR-003 confirmed via a new test, `TestNoPublicMethodAcceptsAnOutcomeAssertion` — `evaluate()` takes only `action`, `request_if_required()` takes only `journey_id`/`action`; combined with T025's existing check on `enforce_authorised()`, all three public methods are covered
- [x] T043 `backend/journey/__init__.py` updated to export `AuthorisationPolicyEngine`, `ProposedAction`, `Rule`, `AuthorisationDecision` — no naming collision found (unlike 012's `VerificationOutcome` precedent); all four names were free
- [x] T044 `mypy journey` run before and after (via `git stash -u` baseline): 13 pre-existing errors in `scoring_service.py`/`repository.py`, identical in both runs. **4 real new errors were found and fixed** in `authorisation_policy_engine.py` along the way: `evaluate()`'s `classification` local needed an explicit `Literal[...]` annotation (mypy widened the ternary to `str`); three call sites (`_outcome_for`, `Decimal(...)`, `_voided_for`) needed `cast(str, ...)` around values pulled from `JourneyEvent.payload: dict[str, object]`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2/US3/US4
- **US2 (Phase 4)**: Depends on US1's `evaluate()` (T010) — purely additive test coverage, no new production code
- **US3 (Phase 5)**: Depends on Phase 2 and US1's `evaluate()` (T010) — `request_if_required()` calls `evaluate()` directly
- **US4 (Phase 6)**: Depends on US3's `request_if_required()`/`enforce_authorised()` (T027, T028) — extends both
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4

### User Story Dependencies

- **US1** has no dependency on US2/US3/US4, and is the true MVP — the classification mechanism alone is independently demonstrable.
- **US2** is a pure test-rigor addition on US1; it introduces no new production code path.
- **US3** builds request/response/enforcement on top of US1's classification — cannot exist without it.
- **US4** refines US3's enforcement with scope and staleness rules — cannot exist without US3.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement the story's specific logic
3. Confirm tests PASS

### Parallel Opportunities

- T002 (Setup) has no dependency on T001
- T003 (Foundational) — T004 depends on it
- Within US1: T005–T008 (tests) all parallel
- Within US2: T012–T015 (tests) all parallel
- Within US3: T019–T025 (tests) all parallel
- Within US4: T030–T033 (tests) all parallel
- T039–T042 (Polish) all parallel

---

## Parallel Example: User Story 3 Tests

```bash
# T019-T025 all write to the same new test file but assert independent
# scenarios with no shared mutable state (each constructs its own tmp_path
# DB) — safe to parallelize:
T019: TestRequestIfRequiredAppendsAuthorisationRequestedEvent
T020: TestRequestIfRequiredSkipsEventWhenPermitted
T021: TestEnforceAuthorisedFalseWhenNoRequestExists
T022: TestEnforceAuthorisedFalseWhenUnanswered
T023: TestEnforceAuthorisedFalseWhenRefused
T024: TestEnforceAuthorisedTrueWhenApproved
T025: TestEnforceAuthorisedHasNoTrustMeParameter
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T004)
3. Complete Phase 3: US1 tests (T005–T009) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T010)
5. Run T011 gate — all tests must pass
6. **STOP and VALIDATE**: The engine classifies deterministically, without an LLM, and names every rule that fired — the separation-of-reasoning-and-authority boundary exists and is provable, even before request/response/enforcement is built

### Incremental Delivery

1. Setup + Foundational → model vocabulary and skeleton ready
2. US1 → the classification mechanism itself, deterministic and LLM-free
3. US2 → every rule proven individually, in both directions
4. US3 → requires-authorisation classifications become real requests on the existing 006 stream, and execution is structurally blocked absent a real grant
5. US4 → grants are scoped correctly and go stale the instant their terms change
6. Polish → full regression + quickstart walkthrough + NFR confirmation + type-check

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files, or independent test cases with no shared mutable state, with no incomplete dependency — safe to parallelize
- No task in this file modifies `journey/api/routers/events.py`, `journey/services/event_service.py`'s existing methods, or `journey/services/booking_service.py` — see the Scope Boundary note at the top
- The four rules are fixed and hardcoded by design (NFR-003) — no task introduces a registration mechanism, config flag, or injection point for them, unlike feature 012's deliberately-pluggable `SuccessCondition` pattern
- `enforce_authorised()` MUST NOT gain a parameter that lets a caller assert an outcome rather than identify what to check — this is a structural, not just documented, guarantee (NFR-003, T025)
