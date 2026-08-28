# Contract: SSE Event Stream Endpoint

**Feature**: 006-agent-trace-console
**Type**: HTTP endpoint (Server-Sent Events)
**Consumed by**: Frontend React console (`@azure/fetch-event-source`)

---

## Endpoint

```
GET /journeys/{journey_id}/events
```

### Path Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `journey_id` | String (UUID) | Yes | The journey to stream events for |

### Request Headers

| Header | Required | Description |
|---|---|---|
| `Last-Event-ID` | No | If present, stream resumes from `sequence > Last-Event-ID`; otherwise streams from sequence 1 |

### Response

- **Content-Type**: `text/event-stream`
- **Cache-Control**: `no-cache`
- **X-Accel-Buffering**: `no`
- **Transfer-Encoding**: `chunked`

Each SSE event has the following fields:

```
id: {sequence}
event: {event_type}
data: {payload_json}

```

The `id` field is the per-journey monotonic `sequence` value (integer, starting at 1). The browser uses this as `Last-Event-ID` on reconnect.

### Keep-Alive

The endpoint emits a `: keep-alive` comment every 15 seconds when no events are pending, to prevent proxy timeouts.

### Error Cases

| Condition | Behaviour |
|---|---|
| `journey_id` not found | HTTP 404 before opening the stream |
| Stream interrupted | Client reconnects using `Last-Event-ID`; server resumes from that sequence |
| Journey ended | Stream closes normally after a `journey_ended` event |

---

## Replay Endpoint

```
GET /journeys/{journey_id}/events/replay?speed={multiplier}
```

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `speed` | Float | `1.0` | Speed multiplier applied to recorded inter-event intervals. Must be > 0. |

### Behaviour

- Reads the full `journey_events` sequence for `journey_id` from storage.
- Replays events with inter-event delays scaled by `1 / speed` relative to original `recorded_at` timestamps.
- Emits a `replay_started` event as the first event (with `source_journey_id` and `speed_multiplier`).
- Emits a `replay_ended` event as the final event.
- Makes **no calls** to any external service during replay (FR-012).
- If `speed <= 0`, returns HTTP 422.

### SSE format

Identical to the live stream endpoint.

---

## Authorisation Response Endpoint

```
POST /journeys/{journey_id}/authorisation/{request_id}
```

### Request Body (JSON)

```json
{
  "outcome": "approved" | "refused"
}
```

### Response

- **200 OK** — outcome recorded; an `authorisation_outcome` event appears in the SSE stream within 1 second (SC-003).
- **404** — `journey_id` or `request_id` not found.
- **409** — request already resolved.
- **422** — invalid `outcome` value.

---

## SSE Payload Schemas

### `external_call`
```json
{
  "endpoint": "string",
  "outcome": "string",
  "elapsed_ms": "integer"
}
```

### `decision`
```json
{
  "description": "string",
  "reason": "string"
}
```

### `state_change`
```json
{
  "from_state": "string",
  "to_state": "string"
}
```

### `identifier_issued`
```json
{
  "identifier_id": "string",
  "value": "string",
  "stale_after_seconds": "integer",
  "stale_at": "ISO-8601 UTC string"
}
```

### `identifier_expired`
```json
{
  "identifier_id": "string"
}
```

### `call_budget_updated`
```json
{
  "budget_remaining": "integer"
}
```

### `authorisation_requested`
```json
{
  "request_id": "string",
  "action": "string",
  "cost": "string",
  "objective_effect": "string",
  "rule_id": "string"
}
```

### `authorisation_outcome`
```json
{
  "request_id": "string",
  "outcome": "approved" | "refused",
  "rule_id": "string"
}
```

### `option_rejected`
```json
{
  "option_id": "string",
  "constraint_violated": "string",
  "satisfies_numeric_constraints": "boolean"
}
```

### `objective_violated`
```json
{
  "description": "string",
  "violated_constraints": ["string"]
}
```

### `replay_started`
```json
{
  "source_journey_id": "string",
  "speed_multiplier": "float"
}
```

### `replay_ended`
```json
{}
```
