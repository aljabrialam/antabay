# Quickstart: Agent Trace and Journey Console (006)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- Node.js 20+, `npm install` in `frontend/`
- `@playwright/test` installed: `npx playwright install --with-deps`
- Backend running: `cd backend && uvicorn journey.api.main:app --reload --port 8000`
- Frontend dev server running: `cd frontend && npm run dev` (serves at `localhost:5173`)

---

## Scenario 1 — Live Journey Observation (US1, FR-001–007, FR-013–019)

**Goal**: Confirm the console renders live events as the agent acts.

**Step 1** — Seed a test journey with events:
```bash
cd backend
python -m pytest tests/integration/test_event_stream.py::test_seed_live_journey -v
```
This inserts a `journey_id` into the DB and writes a sequence of `journey_events` rows.

**Step 2** — Open the console in a browser:
```
http://localhost:5173/journey/{journey_id}
```

**Expected state**:
- Objective panel shows hard constraints and preferences in distinct styles.
- Journey state stepper shows completed, current, and pending stages.
- Event log shows all events in order.
- Expiry clocks count down and show spent state when expired.
- Call budget visible.
- Provenance bar visible with environment and model name.

**Step 3** — Inject a new event via the test helper:
```bash
python -m pytest tests/integration/test_event_stream.py::test_inject_decision_event -v
```

**Expected**: The event appears in the console within 1 second without any user refresh.

---

## Scenario 2 — Authorisation Gate (US2, FR-008–009, FR-015–016)

**Goal**: Confirm the auth gate appears and both outcomes are recorded.

**Step 1** — Inject an `authorisation_requested` event:
```bash
python -m pytest tests/integration/test_event_stream.py::test_inject_auth_request -v
```

**Expected**:
- Auth request panel appears with action, cost, objective effect, and rule ID.
- Panel carries visual emphasis (hold amber).
- Approve and refuse buttons are visible.

**Step 2** — Approve:
```bash
curl -X POST http://localhost:8000/journeys/{journey_id}/authorisation/{request_id} \
  -H "Content-Type: application/json" \
  -d '{"outcome": "approved"}'
```

**Expected**:
- `authorisation_outcome` event appears in the event log showing the rule ID.
- Auth request panel disappears.

**Step 3** — Repeat with `"outcome": "refused"` and confirm refusal is recorded.

---

## Scenario 3 — Replay (US3, FR-012, NFR-004–005)

**Goal**: Confirm a recorded stream replays without external calls and at adjustable pace.

**Step 1** — Load a fixture stream:
```bash
# The fixture is in backend/tests/fixtures/journey_events_001.json
python -m pytest tests/integration/test_replay.py::test_load_fixture_stream -v
```

**Step 2** — Open the replay console:
```
http://localhost:5173/journey/{fixture_journey_id}/replay
```

**Expected**:
- Replay label is permanently visible.
- Events play back in recorded order.
- No network calls leave localhost (verify with browser DevTools Network tab — no Atlas API calls).

**Step 3** — Adjust speed to 4×:
```
Set the speed control to 4
```
**Expected**: Events play back faster; relative timing is preserved.

**Step 4** — Run replay as a Playwright fixture test:
```bash
cd frontend
npx playwright test e2e/replay.spec.ts --reporter=html
```

---

## Scenario 4 — Reconnection (NFR-006, Edge Cases)

**Goal**: Confirm the console resumes from the correct event after a dropped stream.

**Step 1** — Open the console against a live journey.

**Step 2** — Kill and restart the backend process.

**Expected**:
- Console shows a `reconnecting` status briefly.
- On reconnect, only events after the last received `sequence` appear — no duplication.

---

## Running the Full Test Suite

```bash
# Backend unit + integration
cd backend && python -m pytest --tb=short --html=reports/report.html

# Frontend unit
cd frontend && npm run test

# E2E (requires both servers running)
cd frontend && npx playwright test --reporter=html
```

**Expected**: All tests pass. Playwright report and screenshots in `frontend/playwright-report/`.

---

## References

- SSE endpoint contract: [`contracts/sse_stream.md`](contracts/sse_stream.md)
- UI component contract: [`contracts/frontend_components.md`](contracts/frontend_components.md)
- Data model: [`data-model.md`](data-model.md)
- Visual reference: [`.antabay/console-mockup.html`](../../.antabay/console-mockup.html)
