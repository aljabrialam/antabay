# Contract: Disruption Injector (operator-only endpoint + internal service)

**Feature**: 008-disruption-injector
**Type**: One operator-only HTTP endpoint (the only endpoint in this
backend deliberately *not* meant to be publicly reachable) plus an
internal service interface that endpoint calls.

**Not part of this contract** (already exists, owned by features 006/007,
not touched here beyond the additive extensions in data-model.md):
`POST /webhooks/atlas`, `WebhookService.receive()`/`.confirm()`'s existing
behaviour for real notifications, `EventService.append()`,
`JourneyEvent.simulated`.

---

## Endpoint: `POST /operator/disruptions`

**Authentication**: A required header (e.g. `X-Operator-Token`) matching
an environment-configured value (research.md R5). Missing, empty, or
mismatched → `401 Unauthorized`. If the environment value itself is unset
at startup, every request is treated as unauthorised — fail closed, never
fail open.

**Request body**:
```json
{
  "journey_id": "<existing journey id>",
  "revised_arrival_time": "<ISO-8601 datetime>"
}
```

**Response**:
- `200 OK` — injection succeeded; body confirms the notification was
  delivered (does not need to expose internal identifiers beyond what's
  useful to the operator triggering a demo).
- `401 Unauthorized` — missing/wrong token, or the injector is disabled
  (research.md R5's fail-closed posture treats "disabled" and
  "unauthorised" as the same observable outcome from outside: nothing
  happens, no information is leaked about *why*).
- `404 Not Found` — `journey_id` does not correspond to any existing
  journey (`JourneyNotFoundError`).
- `409 Conflict` — the journey exists but has no real order yet
  (`JourneyHasNoOrderError`) — a state conflict, not a missing resource.
- `422 Unprocessable Entity` — malformed request body (standard FastAPI
  validation).

**Behaviour**:
1. Verify the operator token; if invalid, `401` — before touching
   anything else.
2. Call `DisruptionInjectorService.inject(journey_id, revised_arrival_time, now)`.
3. Translate `InjectorDisabledError` → `401`, `JourneyNotFoundError` →
   `404`, `JourneyHasNoOrderError` → `409`.
4. On success, `200`.

---

## Internal Service: `DisruptionInjectorService`

### `inject(journey_id: str, revised_arrival_time: datetime, now: datetime) -> InboundNotification`

**Behaviour** (data-model.md's lifecycle diagram in full):
1. If disabled (FR-008), raise `InjectorDisabledError` — before any
   lookup.
2. Look up the journey; if it does not exist, raise
   `JourneyNotFoundError`.
3. Look up the journey's most recent order's `order_no`; if none exists,
   raise `JourneyHasNoOrderError`.
4. Construct the schedule-change envelope (data-model.md) — structurally
   derived from the one real capture's convention, referencing the real
   `order_no`, carrying `revised_arrival_time`. No travel option, price,
   or availability value is read, invented, or altered (FR-007) — this
   service touches nothing about the journey beyond its identity and its
   real order reference.
5. Call `WebhookService.receive(raw_body, now, simulated=True)`
   (research.md R1, R2) — the identical logic path a real notification's
   arrival triggers.
6. If the resulting notification's `confirmation_triggered` is `True`,
   call `WebhookService.confirm(notification)` exactly as the webhook
   router would (today: always `False` for `schedule.changed`, since no
   handler is registered — research.md R4).

**Outputs**: The persisted `InboundNotification`, `simulated=True`.

**Error conditions**: `InjectorDisabledError`, `JourneyNotFoundError`,
`JourneyHasNoOrderError` (research.md R6) — checked in that order, each
independently testable in isolation.

---

## Relationship to feature 007

Step 5–6 above are not a reimplementation — they are direct calls into
`WebhookService`'s existing, unmodified logic (aside from the additive
`simulated` parameter on `receive()`, research.md R2). Every rule 007
already enforces (association, throttling, terminal-journey handling,
confirmation ordering) applies to an injected notification exactly as it
does to a real one, per this spec's own Clarifications and Assumptions.

## Relationship to feature 006

`WAKE_REQUESTED` events produced from an injected notification (if any —
currently never, in production, per research.md R4) carry
`simulated=True` via `EventService.append()`'s already-existing parameter.
No change to `journey/api/routers/events.py` or the SSE envelope shape —
`simulated` is already rendered there (006).
