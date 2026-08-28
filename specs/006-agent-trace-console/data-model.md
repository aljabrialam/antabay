# Data Model: Agent Trace and Journey Console (006)

## Entity: JourneyEvent (persisted as `journey_events` table row)

Represents a single observable occurrence emitted by the agent during a journey. This is the atomic unit of the event stream.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `event_id` | String (UUID) | PK, not null | Stable identifier across replays |
| `journey_id` | String | FK → `journeys.journey_id`, not null | Scopes the event to a single journey |
| `sequence` | Integer | not null, per-journey monotonic from 1 | Used as SSE `Last-Event-ID` |
| `event_type` | String | not null | See Event Types below |
| `payload_json` | Text | not null | JSON-encoded typed payload |
| `simulated` | Integer (0/1) | not null, default 0 | 1 = event is simulated (Principle V) |
| `recorded_at` | String | not null, ISO-8601 UTC | Wall-clock time the event was recorded |

**Validation rules**:
- `sequence` values within a `journey_id` MUST be unique and contiguous starting from 1.
- `payload_json` MUST be a valid JSON object conforming to the schema for `event_type`.
- `simulated` MUST be 0 for events sourced from the live Atlas API; 1 for events injected by the simulation trigger.

---

## Event Types

| `event_type` | Payload Fields | Visual Emphasis (FR-015) |
|---|---|---|
| `external_call` | `endpoint`, `outcome`, `elapsed_ms` | None (uniform) |
| `decision` | `description`, `reason` | None (uniform) |
| `state_change` | `from_state`, `to_state` | None (uniform) |
| `identifier_issued` | `identifier_id`, `value`, `stale_after_seconds`, `stale_at` | None (uniform) |
| `identifier_expired` | `identifier_id` | None (uniform) |
| `call_budget_updated` | `budget_remaining` | None (uniform) |
| `authorisation_requested` | `request_id`, `action`, `cost`, `objective_effect`, `rule_id` | **Emphasised** (FR-015 class 3) |
| `authorisation_outcome` | `request_id`, `outcome` (`approved`/`refused`), `rule_id` | None (uniform) |
| `option_rejected` | `option_id`, `constraint_violated`, `satisfies_numeric_constraints` | **Emphasised** if `satisfies_numeric_constraints=true` (FR-015 class 1) |
| `objective_violated` | `description`, `violated_constraints` | **Emphasised** (FR-015 class 2) |
| `replay_started` | `source_journey_id`, `speed_multiplier` | None (uniform) |
| `replay_ended` | — | None (uniform) |

---

## Entity: EventStream (logical, not a separate table)

An ordered view over all `journey_events` rows for a given `journey_id`, sorted by `sequence` ascending. The SSE endpoint streams this view live; the replay endpoint replays it from a stored recording.

| Attribute | Value |
|---|---|
| Identity | `journey_id` |
| Ordering | `sequence` ASC |
| Persistence | `journey_events` table |
| Append-only | Yes — no updates or deletes |

---

## Entity: ExpiryIdentifier (derived, held in frontend reducer state)

Not persisted separately — reconstructed from `identifier_issued` and `identifier_expired` events in the event stream.

| Field | Type | Source |
|---|---|---|
| `identifier_id` | String | `identifier_issued.identifier_id` |
| `value` | String | `identifier_issued.value` |
| `stale_at` | ISO-8601 string | `identifier_issued.stale_at` |
| `spent` | Boolean | `true` when `identifier_expired` event received |
| `time_remaining_seconds` | Integer | Computed: `stale_at - now`, updated by 1 s clock tick |

**Rules**:
- A spent identifier MUST remain visible with a spent state (FR-014).
- If `stale_at` is absent from the `identifier_issued` payload, the clock is rendered as incomplete (not hidden).

---

## Entity: AuthorisationRequest (derived, held in frontend reducer state)

Reconstructed from `authorisation_requested` and `authorisation_outcome` events.

| Field | Type | Notes |
|---|---|---|
| `request_id` | String | Matches `authorisation_requested.request_id` |
| `action` | String | Human-readable description of the proposed action |
| `cost` | String | Full cost statement |
| `objective_effect` | String | Effect on the traveller's objective |
| `rule_id` | String | Policy rule that raised the request (FR-016) |
| `status` | `pending` / `approved` / `refused` | Transitions on `authorisation_outcome` event |

**Rules**:
- A `pending` request MUST receive visual emphasis (FR-015 class 3).
- Silence MUST NOT constitute approval (Principle IV).

---

## Entity: TravellerObjective (derived, held in frontend reducer state)

Sourced from the journey record; surfaced to the console via a `journey_started` or `objective_set` event (subset of `state_change`).

| Field | Type | Notes |
|---|---|---|
| `hard_constraints` | List of `{ field, value }` | Visually distinct from preferences (FR-001) |
| `preferences` | List of `{ field, value }` | Visually distinct from hard constraints (FR-001) |

---

## Entity: Provenance (derived, held in frontend reducer state)

Persistent footer content (FR-018). Sourced from `state_change` events or a dedicated `provenance_set` event type.

| Field | Type | Notes |
|---|---|---|
| `environment` | String | e.g. `sandbox` |
| `reasoning_model` | String | e.g. `qwen-turbo` |
| `simulation_active` | Boolean | `true` if any `simulated=1` event is in the current stream |

---

## Relationships

```
journeys (existing)
  └── journey_events (new, FK journey_id)
        └── EventStream (logical view, ordered by sequence)
              ├── ExpiryIdentifier (derived in frontend)
              ├── AuthorisationRequest (derived in frontend)
              ├── TravellerObjective (derived in frontend)
              └── Provenance (derived in frontend)
```

---

## Schema Change Summary

| Change | Table | Type |
|---|---|---|
| Add `journey_events` table | `journey_events` | New table |
| No changes to existing tables | — | — |
