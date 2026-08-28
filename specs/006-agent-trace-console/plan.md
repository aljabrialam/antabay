# Implementation Plan: Agent Trace and Journey Console

**Branch**: `006-agent-trace-console` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/006-agent-trace-console/spec.md`

## Summary

Build a real-time browser console that renders the agent's full observable behaviour — external calls, decisions, expiry clocks, authorisation gates, and journey state — as a stateless SSE-driven React UI. The backend adds a `journey_events` table, an SSE streaming endpoint, a replay endpoint, and an authorisation response endpoint. The frontend is a new React + TypeScript + Vite project at `frontend/`. Replay of recorded event streams is indistinguishable from live operation in appearance.

## Technical Context

**Language/Version**: Python 3.11 (backend) · TypeScript 5.x / React 18 (frontend)

**Primary Dependencies**:
- Backend: FastAPI ≥ 0.135.0 (native `fastapi.sse`), SQLAlchemy 2.0, Alembic, httpx
- Frontend: React 18, Vite 5, `@azure/fetch-event-source`, Vitest, Playwright

**Storage**: SQLite (dev) / same durable store as existing journey system — new `journey_events` table; no new storage service

**Testing**:
- Backend: pytest, httpx AsyncClient streaming, pytest-html
- Frontend: Vitest + jsdom (unit), Playwright (E2E) with `page.clock` for deterministic clock tests

**Target Platform**: Browser (React SPA) + deployed FastAPI backend

**Performance Goals**: Authorisation request visible within 1 s of agent raising it (SC-003); event appears in console without manual refresh (FR-006)

**Constraints**: SSE only (no WebSocket); `Last-Event-ID` reconnection; no polling; interface holds no state (FR-013); replay makes zero external calls (FR-012)

**Scale/Scope**: Single journey at a time; ~20 event types; append-only event log capped at 500 entries in reducer state

## Constitution Check

| Principle | Gate | Status |
|---|---|---|
| I. Truth Over Fluency | Provider values rendered verbatim via `provider-value` typeface; no inference | PASS |
| III. Separation of Reasoning and Authority | Auth decision sent via POST to backend; UI only presents, never decides | PASS |
| IV. Human Authorisation | Auth panel requires explicit Approve/Refuse; silence never advances | PASS |
| V. Honest Simulation | `simulated` flag on every event; `simulation_active` in provenance bar; replay labelled | PASS |
| VI. State Outside the Agent | Frontend holds no state; all state derived from event stream (FR-013) | PASS |
| IX. Test-First Development | Tests written and confirmed failing before implementation in every phase | REQUIRED |
| XIII. Deterministic Automation | `page.clock` for expiry assertions; fixture server for SSE; no arbitrary sleeps | PASS |
| XIV. Auditability | Every event persisted to `journey_events` before being streamed | PASS |
| XVIII. Demonstrability | Console is the visual artefact; recording at 50% resolution is acceptance test (NFR-001) | PASS |
| XX. Visual Discipline | Exactly 3 emphasis classes; palette fixed; expiry clocks permanently visible | PASS |

**Post-Phase 0 re-check**: All gates pass. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/006-agent-trace-console/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   ├── sse_stream.md    ← Phase 1 output
│   └── frontend_components.md ← Phase 1 output
└── tasks.md             ← /speckit.tasks output (not yet created)
```

### Source Code

```text
backend/                          ← existing Python package
├── journey/
│   ├── api/
│   │   ├── main.py               ← FastAPI app (new or extend existing)
│   │   └── routers/
│   │       └── events.py         ← SSE + replay + auth endpoints (new)
│   ├── models/
│   │   └── events.py             ← JourneyEvent, event payload types (new)
│   ├── services/
│   │   └── event_service.py      ← append_event(), stream_events(), replay_events() (new)
│   └── storage/
│       ├── tables.py             ← add journey_events table (extend)
│       └── repository.py        ← add event persistence methods (extend)
├── alembic/
│   └── versions/
│       └── xxxx_add_journey_events.py  ← migration (new)
└── tests/
    ├── unit/
    │   └── test_event_service.py       ← new
    ├── integration/
    │   ├── test_event_stream.py        ← SSE endpoint tests (new)
    │   └── test_replay.py             ← replay endpoint tests (new)
    ├── contract/
    │   └── test_sse_contract.py        ← SSE payload schema tests (new)
    └── fixtures/
        └── journey_events_001.json     ← canonical fixture stream (new)

frontend/                         ← new Vite React TypeScript project
├── index.html
├── vite.config.ts                ← proxy /api and /events to :8000
├── playwright.config.ts          ← webServer: Vite dev server
├── package.json
├── tsconfig.json
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── types/
    │   └── events.ts             ← JourneyEvent, ConsoleState types
    ├── reducer/
    │   └── consoleReducer.ts     ← useReducer reducer + action types
    ├── hooks/
    │   ├── useEventStream.ts     ← @azure/fetch-event-source SSE hook
    │   └── useExpiryClocks.ts    ← setInterval clock tick hook
    ├── components/
    │   ├── ObjectivePanel.tsx    ← FR-001
    │   ├── JourneyStateStepper.tsx ← FR-017
    │   ├── EventLog.tsx          ← FR-004, FR-005, FR-015, FR-016
    │   ├── EventItem.tsx         ← individual event row
    │   ├── ExpiryClockPanel.tsx  ← FR-003, FR-014
    │   ├── CallBudget.tsx        ← FR-007
    │   ├── AuthPanel.tsx         ← FR-008, FR-009, FR-015
    │   └── ProvenanceBar.tsx     ← FR-018, FR-019
    └── e2e/
        ├── live_observation.spec.ts   ← US1 E2E
        ├── auth_gate.spec.ts          ← US2 E2E
        └── replay.spec.ts             ← US3 E2E
```

## Complexity Tracking

No constitution violations requiring justification. The new `frontend/` project is required by the feature scope (React SPA is the specified technology); it is not optional complexity.
