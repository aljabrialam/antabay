# Data Model: End-to-End Demonstration Capture

This feature adds no new database tables or columns. Everything it
introduces is either an in-memory result of a script run, or a file-based
artifact alongside the existing `backend/tests/fixtures/` convention
(research.md R4) — journey state itself remains exactly what features
001–012 already persist (Constitution VI: journey state lives in durable
storage, not in this feature's own tooling).

## Entities

### Demonstration Run Result (in-memory, produced by the orchestration script)

| Field | Type | Notes |
|---|---|---|
| `journey_id` | str | The fresh journey this run created (research.md R6) |
| `run_kind` | enum: `PRIMARY`, `REFUSAL_PATH` | Which scenario this invocation executed |
| `status` | enum: `PASSED`, `FAILED` | Whether every step's assertion held |
| `failed_step` | str \| None | Name of the first step whose assertion failed, if `status == FAILED` |
| `steps_completed` | list[str] | Ordered list of step names actually reached, for diagnosis |

Not persisted to the database — printed/logged by the script and used to
decide whether to proceed to export (research.md R4) or to the
video-capture pass (research.md R3).

### Captured Event Stream (file)

A JSON array, one object per event, in the exact shape
`backend/tests/fixtures/journey_events_001.json` already uses:

```json
[
  {
    "event_type": "objective_set",
    "payload": { "...": "..." },
    "simulated": false,
    "recorded_at": "2026-08-29T09:21:03+00:00"
  }
]
```

Stored under `backend/tests/fixtures/demo_captures/<journey_id>.json`
(research.md R4). One file per successfully-passed Demonstration Run
whose export was requested — not every run is exported, only ones worth
keeping as a candidate canonical capture.

### Capture Manifest (file)

`backend/tests/fixtures/demo_captures/canonical.json`:

```json
{
  "canonical_file": "<journey_id>.json",
  "promoted_at": "2026-08-29T10:00:00+00:00",
  "source_run_status": "PASSED"
}
```

Exactly one canonical file at a time (FR-013). Promotion is a deliberate,
separate step from exporting — never automatic on a run passing.

### Recording (video file, produced by Playwright)

| Field | Meaning |
|---|---|
| File name | Includes the producing run's `journey_id` and surface (`operator` / `traveller`) so footage traces back to a verified execution (FR-012) |
| Surface | `operator` (full console) or `traveller` (new minimal view, research.md R5) |
| Source | Either a live replay of a just-completed run, or a replay of an imported Captured Event Stream (research.md R3, R4) |
| Validity | A recording produced from a run whose result was `FAILED` is retained but named/marked so it is never mistaken for valid output (spec.md FR-012, Clarifications) |

## Integration points on existing modules

- **`backend/journey/services/event_service.py`**: `replay_events` and
  `record_auth_outcome` are called directly by the orchestration script
  (research.md R10), not modified.
- **`backend/journey/api/routers/events.py`**: the existing `/replay`
  route is opened over HTTP by the Playwright capture (research.md R3);
  `/authorisation/{request_id}` is not called over HTTP by this feature
  — the orchestration script calls `EventService.record_auth_outcome()`
  directly instead (research.md R10). No route is added or changed.
- **`backend/journey/services/disruption_injector_service.py`**:
  `DisruptionInjectorService.inject()` is called directly by the
  orchestration script (research.md R7, R10); unmodified.
- **`backend/scripts/seed_console_fixture.py`**: extended (not replaced)
  with an import path that can load an arbitrary exported capture file,
  not only the one fixed `journey_events_001.json` fixture it loads
  today (research.md R4).
- **`frontend/src/App.tsx`**: extended with a second path pattern
  (`/journey/{id}/traveller[/replay]`) alongside the existing
  `/journey/{id}[/replay]`, following the same hand-rolled parsing
  already used — no router library introduced (research.md R5).
