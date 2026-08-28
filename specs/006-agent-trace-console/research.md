# Research: Agent Trace and Journey Console (006)

## Decision 1: SSE Backend Package

**Decision**: Use `fastapi.sse` (`EventSourceResponse` + `ServerSentEvent`) from FastAPI's native module (>=0.135.0). Do not use `sse-starlette`.

**Rationale**: FastAPI >= 0.135.0 ships SSE support natively. The native module auto-handles keep-alive pings (15 s), sets `Cache-Control: no-cache` and `X-Accel-Buffering: no` for proxy compatibility. `sse-starlette` predates native support and adds an unnecessary dependency.

**Alternatives considered**: `sse-starlette` — rejected (redundant given native support).

---

## Decision 2: Last-Event-ID Reconnection

**Decision**: Read `last_event_id: int | None = Header(default=None)` in the SSE endpoint. Assign a monotonically increasing `id` field to each `ServerSentEvent`. On reconnect, skip events where `id <= last_event_id` by querying `journey_events` from that sequence number onward.

**Rationale**: Native browser `EventSource` sends `Last-Event-ID` automatically on reconnect. The server-side `id` maps directly to the `sequence` column in `journey_events`, making catch-up trivial.

**Alternatives considered**: Stateful in-memory queues — rejected (violates Principle VI: State Outside the Agent).

---

## Decision 3: React SSE Consumer Library

**Decision**: Use `@azure/fetch-event-source` (formerly `@microsoft/fetch-event-source`).

**Rationale**: Native `EventSource` cannot send `Authorization` headers and offers no retry control. `@azure/fetch-event-source` uses the Fetch API, supports arbitrary headers, gives full control over reconnect logic, and pauses when the page is hidden. Preferred for any authenticated or production SSE consumer.

**Alternatives considered**: Native `EventSource` — rejected (no header support). `eventsource` npm package — rejected (Node-only polyfill, unnecessary in modern browsers).

---

## Decision 4: State Management

**Decision**: `useReducer` + React Context. Each SSE event type maps to a reducer `case`. State is a single immutable object: `{ log, journeyState, heldIdentifiers, callBudget, objective, pendingAuth, provenance }`.

**Rationale**: Single journey, ~20 event types, no user mutations except auth responses. Zustand/Redux are unjustified at this scale. `useSyncExternalStore` available as escape hatch if concurrent-mode tearing is observed.

**Alternatives considered**: Zustand — deferred (overkill for single journey); Redux — rejected (excessive boilerplate).

---

## Decision 5: Expiry Clock Implementation

**Decision**: `setInterval` (1 s tick) in a `useEffect`, writing remaining seconds to React state.

**Rationale**: CSS animations are not inspectable as discrete values. `requestAnimationFrame` is harder to control in tests. `setInterval` is fully controllable by Playwright's `page.clock` API (`page.clock.install()` + `page.clock.fastForward()`), enabling deterministic clock assertions without real waiting.

**Alternatives considered**: CSS animation — rejected (not Playwright-testable as a value); `requestAnimationFrame` — rejected (harder test control).

---

## Decision 6: Frontend Project Setup

**Decision**: Scaffold at `frontend/` under repo root using `npm create vite@latest frontend -- --template react-ts`. Vite dev proxy maps `/api` and `/events` to `http://localhost:8000`.

**Rationale**: Single frontend in a backend+frontend mono-repo; no workspace tooling needed. `frontend/antabay-console/` nesting only justified for multi-package workspaces.

**Alternatives considered**: `frontend/antabay-console/` nesting — deferred; CRA — rejected (unmaintained).

---

## Decision 7: Test Stack

**Decision**:
- **Backend SSE unit tests**: `httpx.AsyncClient` with `stream=True` via `async with client.stream(...)` + `aiter_lines()`. Extract async event generator as a standalone function and test it with `pytest.mark.asyncio` + `unittest.mock.AsyncMock`.
- **Frontend unit tests**: Vitest + `jsdom` (or `happy-dom`). Mock the SSE stream by directly dispatching events to the reducer.
- **E2E**: Playwright with `webServer` config pointing at Vite dev server (`localhost:5173`). Control SSE stream from a local in-process fixture server. Use `page.clock` for deterministic expiry-clock assertions.

**Rationale**: `page.route()` cannot stream SSE chunks in real time; a fixture server under test control is the correct pattern. `page.clock` makes countdown assertions deterministic and fast.

**Alternatives considered**: `page.route()` for SSE mocking — rejected (intercepts completed responses only).

---

## Decision 8: Append-Only Event Log

**Decision**: Model the event log as an array in reducer state. Reducer appends via spread: `log: [...state.log, action.payload]`. Cap at `MAX_LOG_ENTRIES` (e.g. 500) to bound memory.

**Rationale**: Spread creates a new array reference satisfying React's immutability requirement. A cap prevents unbounded memory growth for long-running journeys.

**Alternatives considered**: Mutable push — rejected (violates React immutability).

---

## Decision 9: journey_events Table Schema

**Decision**: New `journey_events` table with columns: `event_id` (String PK, UUID), `journey_id` (String FK), `sequence` (Integer, per-journey monotonic, used as SSE `id`), `event_type` (String), `payload_json` (Text), `simulated` (Integer 0/1), `recorded_at` (String ISO-8601 UTC).

**Rationale**: Dedicated table keeps streaming concerns separate from `audit_entries`. `sequence` maps directly to SSE `Last-Event-ID`. `simulated` flag satisfies FR-010 and Principle V (Honest Simulation). `payload_json` stores typed event data without schema migration for each new event type.

**Alternatives considered**: Reusing `audit_entries` — rejected (schema contortion, fragile SSE sequencing).
