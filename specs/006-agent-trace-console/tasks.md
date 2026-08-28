# Tasks: Agent Trace and Journey Console

**Input**: Design documents from `specs/006-agent-trace-console/`

**Feature**: 006-agent-trace-console | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**TDD gate (Constitution Principle IX)**: Every test task MUST be written and confirmed FAILING before the corresponding implementation task begins. Tests failing with `ImportError` or `ModuleNotFoundError` satisfy the gate.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the frontend project and wire the backend FastAPI app entry point. Both are blocking prerequisites for all user stories.

- [x] T001 Scaffold Vite React TypeScript project at `frontend/` using `npm create vite@latest frontend -- --template react-ts` from repo root
- [x] T002 Add frontend dependencies to `frontend/package.json`: `@microsoft/fetch-event-source` (package renamed from @azure); devDependencies: `vitest`, `@vitest/ui`, `jsdom`, `@playwright/test`, `@vitejs/plugin-react`
- [x] T003 Configure Vite dev proxy in `frontend/vite.config.ts`: proxy `/api` and `/journeys` to `http://localhost:8000` with `changeOrigin: true`
- [x] T004 Configure Playwright in `frontend/playwright.config.ts`: `webServer.command = "npm run dev"`, `webServer.url = "http://localhost:5173"`, `testDir = "./e2e"`
- [x] T005 Configure Vitest in `frontend/vite.config.ts`: `test.environment = "jsdom"`, `test.globals = true`
- [x] T006 Create FastAPI app entry point `backend/journey/api/__init__.py` (empty)
- [x] T007 Create `backend/journey/api/main.py` with `FastAPI()` app instance and health check route `GET /health`
- [x] T008 Create `backend/journey/api/routers/__init__.py` (empty)
- [x] T009 [P] Create frontend TypeScript type definitions in `frontend/src/types/events.ts`: `JourneyEvent`, `EventType`, `ConsoleState`, `HeldIdentifier`, `AuthorisationRequest`, `TravellerObjective`, `Provenance`, `JourneyStateSequence` interfaces
- [x] T010 [P] Add `pytest-asyncio` and `anyio` to `backend/pyproject.toml` dev dependencies for async SSE testing

**Checkpoint**: `cd backend && uvicorn journey.api.main:app --port 8000` starts without error; `curl http://localhost:8000/health` returns 200. Frontend scaffolded with correct dependencies.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `journey_events` table, repository methods, event service, and SSE router skeleton — everything all three user stories build on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T011 Add `journey_events` table to `backend/journey/storage/tables.py`: columns `event_id` (String PK), `journey_id` (String FK → journeys), `sequence` (Integer), `event_type` (String), `payload_json` (Text), `simulated` (Integer), `recorded_at` (String); add `UniqueConstraint("journey_id", "sequence")`
- [x] T012 Create Alembic migration `backend/alembic/versions/xxxx_add_journey_events.py` adding the `journey_events` table
- [x] T013 Create `backend/journey/models/events.py` with `JourneyEvent` dataclass and Pydantic payload models for all 12 event types: `ExternalCallPayload`, `DecisionPayload`, `StateChangePayload`, `IdentifierIssuedPayload`, `IdentifierExpiredPayload`, `CallBudgetUpdatedPayload`, `AuthorisationRequestedPayload`, `AuthorisationOutcomePayload`, `OptionRejectedPayload`, `ObjectiveViolatedPayload`, `ObjectiveSetPayload`, `ReplayStartedPayload`, `ReplayEndedPayload`
- [x] T014 Add `append_event()` and `get_events_from_sequence()` methods to `backend/journey/storage/repository.py`; `append_event` uses `MAX(sequence)+1` within a transaction to enforce monotonic ordering; `get_events_from_sequence(journey_id, from_sequence)` returns rows ordered by `sequence ASC`
- [x] T015 Create `backend/journey/services/event_service.py` with `EventService` class: `append(journey_id, event_type, payload, simulated) -> JourneyEvent`; `stream_events(journey_id, last_sequence) -> AsyncGenerator[JourneyEvent]` (polls DB every 0.5 s for new rows, yields them); `replay_events(journey_id, speed) -> AsyncGenerator[JourneyEvent]` (reads full sequence, yields with scaled delays)
- [x] T016 Create `backend/journey/api/routers/events.py` with empty stubs for three routes: `GET /journeys/{journey_id}/events`, `GET /journeys/{journey_id}/events/replay`, `POST /journeys/{journey_id}/authorisation/{request_id}`; register router on `main.py`
- [x] T017 Create `backend/journey/__init__.py` re-exports for `JourneyEvent` and `EventService`
- [x] T018 Create reducer skeleton `frontend/src/reducer/consoleReducer.ts` with `ConsoleState` initial state and empty `switch` returning state unchanged for all unknown actions; export `consoleReducer` and `initialState`
- [x] T019 Create `useEventStream` hook skeleton `frontend/src/hooks/useEventStream.ts`: accepts `journeyId` string, returns `{ state, connectionStatus }`; dispatches `CONNECTION_STATUS` actions only (no SSE connection yet)
- [x] T020 Create `useExpiryClocks` hook skeleton `frontend/src/hooks/useExpiryClocks.ts`: sets up `setInterval` 1 s tick and dispatches `CLOCK_TICK` to the reducer; no-op if no identifiers held

**Checkpoint**: `python -m pytest backend/tests/ -k "not vcr"` still passes (no regressions). Frontend TypeScript compiles without errors (`npm run build` in `frontend/`).

---

## Phase 3: User Story 1 — Live Journey Observation (Priority: P1) 🎯 MVP

**Goal**: A person watching the console during a live journey sees objective, journey state, every external call, every decision, expiry clocks, call budget, and provenance — all updating in real time via SSE, no manual refresh.

**Independent Test**: Open `http://localhost:5173/journey/{id}` against a running backend with seeded events; confirm new events appear within 1 s; confirm expiry clocks count down; confirm spent clocks remain visible.

### Tests for User Story 1

> **Write these tests FIRST — verify they FAIL before any implementation**

- [ ] T021 [P] [US1] Write contract test `backend/tests/contract/test_sse_contract.py`: assert `GET /journeys/{id}/events` returns `Content-Type: text/event-stream`; assert each event line parses to `{ id, event, data }` with valid JSON data; assert 404 for unknown journey_id (contracts/sse_stream.md)
- [ ] T022 [P] [US1] Write integration test `backend/tests/integration/test_event_stream.py`: `TestLiveStream` class — seed journey + events via `append_event`; open SSE stream with `httpx.AsyncClient stream=True`; assert events arrive in sequence order; assert `Last-Event-ID` reconnection skips already-delivered events (FR-006, NFR-006)
- [ ] T023 [P] [US1] Write unit test `backend/tests/unit/test_event_service.py`: `TestAppendEvent` — assert sequence starts at 1, increments monotonically, raises on duplicate; `TestStreamEvents` — assert async generator yields only rows after `last_sequence` (FR-011)
- [ ] T024 [P] [US1] Write Vitest unit test `frontend/src/reducer/consoleReducer.test.ts`: assert `EXTERNAL_CALL` appends to log; `STATE_CHANGE` updates `journeyState`; `IDENTIFIER_ISSUED` adds to `heldIdentifiers`; `IDENTIFIER_EXPIRED` marks identifier spent; `CALL_BUDGET_UPDATED` updates `callBudget`; `CLOCK_TICK` decrements `time_remaining_seconds`; `OBJECTIVE_SET` populates `objective` with `hard_constraints` and `preferences` (FR-001, FR-002, FR-003, FR-007)
- [ ] T025 [P] [US1] Write Vitest unit test `frontend/src/hooks/useEventStream.test.ts`: mock `@azure/fetch-event-source`; assert hook dispatches correct reducer actions for each SSE event type; assert `connectionStatus` transitions `connecting → live` (FR-006)
- [ ] T026 [US1] Write Playwright E2E test `frontend/e2e/live_observation.spec.ts`: `TestLiveObservation` — seed journey via backend fixture; open console URL; assert `[data-testid="objective-panel"]` visible with hard constraints and preferences; assert `[data-testid="event-log"]` receives new event within 1 s of injection; assert `[data-testid="expiry-clock"]` counts down using `page.clock`; assert spent clock carries `[data-testid="expiry-clock-spent"]` and remains visible; assert `[data-testid="call-budget"]` visible; assert `[data-testid="provenance-bar"]` visible (FR-001–FR-007, FR-013–FR-014, FR-017–FR-019, SC-001–SC-002)
- [ ] T027 [US1] Confirm T021–T026 all FAIL with `ImportError`, `AttributeError`, or missing element errors — document failure reason in a comment above each test class

### Implementation for User Story 1

- [ ] T028 [US1] Implement `GET /journeys/{journey_id}/events` SSE endpoint in `backend/journey/api/routers/events.py`: read `Last-Event-ID` header; call `EventService.stream_events()`; yield each `JourneyEvent` as `ServerSentEvent(id=str(sequence), event=event_type, data=payload_json)` using `fastapi.sse.EventSourceResponse` (FR-006, NFR-006)
- [ ] T029 [US1] Implement `EventService.stream_events()` in `backend/journey/services/event_service.py`: async generator polling `repository.get_events_from_sequence()` every 500 ms; yields new rows; terminates on journey end state
- [ ] T030 [US1] Implement `EventService.append()` in `backend/journey/services/event_service.py`: atomically computes `MAX(sequence)+1`, inserts row, returns `JourneyEvent`; raises `ValueError` if `journey_id` does not exist
- [ ] T031 [US1] Add `objective_set` event type handling: add `ObjectiveSetPayload` to `backend/journey/models/events.py`; append `objective_set` event when journey starts (in `append()` helper for journey creation flow)
- [ ] T032 [US1] Implement `consoleReducer` cases in `frontend/src/reducer/consoleReducer.ts` for all US1 actions: `EXTERNAL_CALL`, `DECISION`, `STATE_CHANGE`, `IDENTIFIER_ISSUED`, `IDENTIFIER_EXPIRED`, `CALL_BUDGET_UPDATED`, `CLOCK_TICK`, `OBJECTIVE_SET`, `CONNECTION_STATUS`; enforce append-only log with 500-entry cap
- [ ] T033 [US1] Implement `useEventStream` hook in `frontend/src/hooks/useEventStream.ts`: open `fetchEventSource` to `/journeys/{id}/events`; parse each SSE event and dispatch to reducer; handle `onopen` / `onerror` / reconnect with `Last-Event-ID`
- [ ] T034 [US1] Implement `useExpiryClocks` hook in `frontend/src/hooks/useExpiryClocks.ts`: `setInterval` 1 s tick; dispatch `CLOCK_TICK`; clear on unmount
- [ ] T035 [P] [US1] Implement `ObjectivePanel` component in `frontend/src/components/ObjectivePanel.tsx`: renders `hard_constraints` with `data-testid="objective-hard-constraint"` and `preferences` with `data-testid="objective-preference"` in visually distinct styles (FR-001)
- [ ] T036 [P] [US1] Implement `JourneyStateStepper` component in `frontend/src/components/JourneyStateStepper.tsx`: ordered sequence of stages; completed / current / pending visual states; `data-testid="journey-state-stepper"` and `data-testid="journey-state-step"` (FR-017)
- [ ] T037 [P] [US1] Implement `ExpiryClockPanel` component in `frontend/src/components/ExpiryClockPanel.tsx`: renders each `HeldIdentifier`; `data-testid="expiry-clock"` with time remaining and proportional indicator; `data-testid="expiry-clock-spent"` for spent state; spent clocks remain visible (FR-003, FR-014)
- [ ] T038 [P] [US1] Implement `EventLog` and `EventItem` components in `frontend/src/components/EventLog.tsx` and `EventItem.tsx`: scrollable log; `data-testid="event-log"` / `data-testid="event-item"`; simulated events carry `data-testid="event-item-simulated"` and simulation violet `#6B3FA0`; provider values wrapped in `data-testid="provider-value"` monospace span (FR-004, FR-005, FR-010, FR-019)
- [ ] T039 [P] [US1] Implement `CallBudget` component in `frontend/src/components/CallBudget.tsx`: `data-testid="call-budget"` showing remaining integer (FR-007)
- [ ] T040 [P] [US1] Implement `ProvenanceBar` component in `frontend/src/components/ProvenanceBar.tsx`: persistent footer; `data-testid="provenance-bar"`; shows environment, reasoning model, simulation indicator; palette ink `#141A21` on paper `#E4E2DC` (FR-018)
- [ ] T041 [US1] Wire all US1 components into `frontend/src/App.tsx`: render `ObjectivePanel`, `JourneyStateStepper`, `ExpiryClockPanel`, `CallBudget`, `EventLog`, `ProvenanceBar`; pass reducer state via React Context; apply flight-strip visual reference palette
- [ ] T042 [US1] Run `python -m pytest backend/tests/contract/test_sse_contract.py backend/tests/integration/test_event_stream.py backend/tests/unit/test_event_service.py -v` — all must pass; run `cd frontend && npm run test` and `npx playwright test e2e/live_observation.spec.ts` — all must pass

**Checkpoint**: US1 complete. Observer can watch a live journey end-to-end in the browser. SSE stream delivers events in real time. Expiry clocks count down and spent clocks remain visible.

---

## Phase 4: User Story 2 — Authorisation Gate (Priority: P2)

**Goal**: When the agent raises an authorisation request, the console presents it with full detail and visual emphasis; the observer can approve or refuse; both outcomes are recorded and appear in the event stream.

**Independent Test**: Inject an `authorisation_requested` event; confirm the auth panel appears with hold amber emphasis; approve via the button; confirm `authorisation_outcome` appears in the event log with the rule ID.

### Tests for User Story 2

> **Write these tests FIRST — verify they FAIL before any implementation**

- [ ] T043 [P] [US2] Write contract test `backend/tests/contract/test_auth_contract.py`: assert `POST /journeys/{id}/authorisation/{req_id}` with `{"outcome":"approved"}` returns 200; assert 409 on duplicate; assert 404 for unknown IDs; assert 422 for invalid outcome value (contracts/sse_stream.md)
- [ ] T044 [P] [US2] Write integration test `backend/tests/integration/test_auth_gate.py`: seed `authorisation_requested` event; POST approval; assert `authorisation_outcome` event appears in SSE stream within 1 s with matching `rule_id`; repeat for refusal (FR-008, FR-009, SC-003)
- [ ] T045 [P] [US2] Write Vitest unit test `frontend/src/reducer/consoleReducer.test.ts` (append to existing): `AUTH_REQUESTED` sets `pendingAuth` and appends emphasised log entry; `AUTH_OUTCOME` clears `pendingAuth` and appends log entry with rule ID (FR-008, FR-009, FR-015, FR-016)
- [ ] T046 [US2] Write Playwright E2E test `frontend/e2e/auth_gate.spec.ts`: inject `authorisation_requested` event; assert `[data-testid="auth-request-panel"]` visible with action, cost, objective effect, rule ID; assert `[data-testid="event-item-emphasised"]` present; click `[data-testid="auth-approve-button"]`; assert panel disappears; assert `authorisation_outcome` event in log with rule ID; repeat with refuse button (FR-008, FR-009, FR-015, FR-016, SC-003)
- [ ] T047 [US2] Confirm T043–T046 all FAIL — document failure reason in a comment above each test class

### Implementation for User Story 2

- [ ] T048 [US2] Implement `POST /journeys/{journey_id}/authorisation/{request_id}` endpoint in `backend/journey/api/routers/events.py`: validate `outcome`; check request exists and is pending (409 if already resolved); call `EventService.record_auth_outcome()`; return 200 (FR-009)
- [ ] T049 [US2] Add `record_auth_outcome(journey_id, request_id, outcome, rule_id)` to `backend/journey/services/event_service.py`: appends `authorisation_outcome` event; validates pending state; raises `ConflictError` if already resolved
- [ ] T050 [US2] Add `AUTH_REQUESTED` and `AUTH_OUTCOME` reducer cases to `frontend/src/reducer/consoleReducer.ts`: `AUTH_REQUESTED` sets `pendingAuth` and appends emphasised log entry; `AUTH_OUTCOME` clears `pendingAuth` and appends log entry
- [ ] T051 [US2] Implement `AuthPanel` component in `frontend/src/components/AuthPanel.tsx`: renders when `pendingAuth !== null`; shows action, cost, objective effect, rule ID; approve and refuse buttons post to `/journeys/{id}/authorisation/{req_id}`; `data-testid="auth-request-panel"`, `auth-approve-button"`, `"auth-refuse-button"`; hold amber `#B0700F` background (FR-008, FR-015, FR-016)
- [ ] T052 [US2] Add `event-item-emphasised` rendering logic to `EventItem.tsx`: apply violation red `#9E2B1C` for `option_rejected` (when `satisfies_numeric_constraints=true`) and `objective_violated`; apply hold amber `#B0700F` for `authorisation_requested`; all other events uniform ink `#141A21` (FR-015)
- [ ] T053 [US2] Run `python -m pytest backend/tests/contract/test_auth_contract.py backend/tests/integration/test_auth_gate.py -v` and `cd frontend && npx playwright test e2e/auth_gate.spec.ts` — all must pass

**Checkpoint**: US2 complete. Authorisation gate is live. Approve and refuse both record outcomes. Three emphasis classes are correctly enforced.

---

## Phase 5: User Story 3 — Simulation and Replay (Priority: P3)

**Goal**: An observer can replay a previously recorded event stream at a controllable speed multiplier; the console appears identical to live operation; a persistent replay label is visible; no external calls are made; simulated events in live operation carry distinct visual marking.

**Independent Test**: Record a fixture stream; load into replay endpoint; confirm events play in order at 2× speed; confirm no network calls leave localhost; confirm replay label visible; confirm simulated events carry simulation violet marking.

### Tests for User Story 3

> **Write these tests FIRST — verify they FAIL before any implementation**

- [ ] T054 [P] [US3] Write contract test `backend/tests/contract/test_replay_contract.py`: assert `GET /journeys/{id}/events/replay` streams `replay_started` as first event and `replay_ended` as last; assert events arrive in sequence order; assert `speed=0` returns 422; assert no Atlas API calls during replay (FR-012, contracts/sse_stream.md)
- [ ] T055 [P] [US3] Write integration test `backend/tests/integration/test_replay.py`: load fixture `backend/tests/fixtures/journey_events_001.json`; call replay endpoint at `speed=4.0`; assert all events received in order; assert inter-event timing is scaled; assert `replay_started.speed_multiplier == 4.0`; assert no DB writes occur during replay (FR-012)
- [ ] T056 [P] [US3] Write Vitest unit test for replay state: append to `frontend/src/reducer/consoleReducer.test.ts` — `REPLAY_STARTED` sets `replayActive = true`; `REPLAY_ENDED` sets `replayActive = false`; `replayActive = true` causes `[data-testid="replay-label"]` to render (NFR-004)
- [ ] T057 [US3] Write Playwright E2E test `frontend/e2e/replay.spec.ts`: load fixture journey; open replay URL; assert `[data-testid="replay-label"]` visible throughout; assert events appear in order; adjust `[data-testid="replay-speed-control"]` to 4×; assert faster playback; assert no external network requests; assert simulated events have `[data-testid="event-item-simulated"]` with simulation violet (FR-010, FR-012, NFR-004, NFR-005, SC-004, SC-006)
- [ ] T058 [US3] Confirm T054–T057 all FAIL — document failure reason in a comment above each test class

### Implementation for User Story 3

- [ ] T059 [US3] Implement `EventService.replay_events()` in `backend/journey/services/event_service.py`: reads full `journey_events` sequence for `journey_id`; yields synthetic `replay_started` event first; yields each stored event with `asyncio.sleep(delta / speed)` where `delta` is the difference between consecutive `recorded_at` timestamps; yields synthetic `replay_ended` event last; makes no external calls (FR-012)
- [ ] T060 [US3] Implement `GET /journeys/{journey_id}/events/replay` endpoint in `backend/journey/api/routers/events.py`: read `speed` query param (default 1.0, reject ≤ 0 with 422); call `EventService.replay_events()`; stream via `EventSourceResponse` identically to live endpoint
- [ ] T061 [US3] Create fixture file `backend/tests/fixtures/journey_events_001.json`: JSON array of 10–15 `JourneyEvent` dicts covering all event types including at least one `simulated=1` event, one `authorisation_requested`, one `option_rejected` with `satisfies_numeric_constraints=true`, one `identifier_issued`, one `identifier_expired`
- [ ] T062 [US3] Add `REPLAY_STARTED`, `REPLAY_ENDED` reducer cases to `frontend/src/reducer/consoleReducer.ts`; add `replayActive` to state
- [ ] T063 [US3] Add replay label rendering to `frontend/src/components/ProvenanceBar.tsx`: when `replayActive = true`, show `data-testid="replay-label"` persistently (NFR-004)
- [ ] T064 [US3] Add replay speed control to `frontend/src/App.tsx`: `data-testid="replay-speed-control"` numeric input; on change, close current SSE connection and reopen replay endpoint with new `speed` param (FR-012)
- [ ] T065 [US3] Run `python -m pytest backend/tests/contract/test_replay_contract.py backend/tests/integration/test_replay.py -v` and `cd frontend && npx playwright test e2e/replay.spec.ts` — all must pass

**Checkpoint**: US3 complete. Replay is indistinguishable from live in appearance. Speed multiplier works. Replay label is persistent. Simulated events carry simulation violet.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Visual conformance, legibility at 50% resolution, NFR validation, and test suite wiring.

- [ ] T066 [P] Audit all components against `.antabay/console-mockup.html` palette: verify paper `#E4E2DC`, strip `#FAF9F7`, ink `#141A21`, rule `#C2BEB5`, hold amber `#B0700F`, violation red `#9E2B1C`, confirmation blue `#1B5A87`, simulation violet `#6B3FA0` are applied correctly; no colour used decoratively (NFR-002)
- [ ] T067 [P] Generate Playwright screenshot of full console during a live journey and review at 50% size; confirm all text is readable and all visual indicators distinguishable; fix any elements that fail (NFR-001, SC-005)
- [ ] T068 [P] Verify NFR-003: walk through a complete journey using only three human interactions (submit objective, approve authorisation, start replay); document the interaction sequence in `specs/006-agent-trace-console/quickstart.md`
- [ ] T069 [P] Add `pytest-anyio` and configure `asyncio_mode = "auto"` in `backend/pyproject.toml` `[tool.pytest.ini_options]` to remove `@pytest.mark.asyncio` boilerplate from SSE tests
- [ ] T070 [P] Run full backend test suite `python -m pytest --tb=short --html=reports/report_006.html` and confirm no regressions against earlier features
- [ ] T071 [P] Run full frontend test suite `cd frontend && npm run test && npx playwright test --reporter=html` and confirm all pass with screenshots and traces in `frontend/playwright-report/`
- [ ] T072 Update `backend/journey/__init__.py` to export `EventService` and `JourneyEvent`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 — no dependency on US1 or US3
- **US3 (Phase 5)**: Depends on Phase 2 — no dependency on US1 or US2
- **Polish (Phase 6)**: Depends on US1 + US2 + US3

### User Story Dependencies

- **US1** and **US2** and **US3** are all independently testable after Phase 2 completes. They touch different endpoints and different reducer cases. US2 reuses the SSE stream from US1 but does not depend on US1 being complete — the auth endpoint is additive.

### Within Each User Story

1. Write all test tasks for the story → confirm FAIL
2. Implement backend model / service / endpoint
3. Implement frontend reducer cases
4. Implement frontend components
5. Wire into App and confirm tests PASS

### Parallel Opportunities

- T001–T010 (Setup): T009, T010 can run in parallel with T001–T008
- T011–T020 (Foundational): T011–T013 can run in parallel; T014 depends on T011; T015 depends on T014; T016 depends on T015; T018–T020 can run in parallel
- Within US1: T021–T025 (tests) all parallel; T035–T040 (components) all parallel after T032–T034
- Within US2: T043–T045 (tests) all parallel; T050–T051 parallel
- Within US3: T054–T056 (tests) all parallel; T062–T064 parallel after T059–T060

---

## Parallel Example: User Story 1 Tests

```bash
# All US1 test tasks can be written in parallel (different files):
T021: backend/tests/contract/test_sse_contract.py
T022: backend/tests/integration/test_event_stream.py
T023: backend/tests/unit/test_event_service.py
T024: frontend/src/reducer/consoleReducer.test.ts
T025: frontend/src/hooks/useEventStream.test.ts
T026: frontend/e2e/live_observation.spec.ts
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T010)
2. Complete Phase 2: Foundational (T011–T020)
3. Complete Phase 3: US1 tests (T021–T027) — confirm all FAIL
4. Complete Phase 3: US1 implementation (T028–T041)
5. Run T042 gate — all tests must pass
6. **STOP and VALIDATE**: Observer can watch a live journey in the browser
7. Demo-ready at this point

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → live observation working → Demo 1
3. US2 → authorisation gate working → Demo 2
4. US3 → replay + simulation marking → Demo 3 (final demo artefact)
5. Polish → visual conformance + full test reports

---

## Notes

- TDD gate: every `[US*]` test task MUST fail before its implementation tasks begin (Constitution Principle IX)
- `[P]` marks tasks that write to different files with no incomplete dependency — safe to parallelize
- `page.clock` in Playwright enables deterministic expiry clock assertions without real waiting
- Replay endpoint synthesises `replay_started` / `replay_ended` events in memory — do not persist them to `journey_events`
- The `sequence` column has a `UniqueConstraint("journey_id", "sequence")` — the repository `append_event()` must use `MAX(sequence)+1` inside a transaction, not an application-level counter
- Provider values in `EventItem` must use the monospace typeface token, not inferred or substituted (Principle I)
- Silence on the auth panel MUST NOT advance the journey — the backend POST is the only path to resolution (Principle IV)
