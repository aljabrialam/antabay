# Data Model: Disruption Injector

## InboundNotification (extended, owned by feature 007)

One new field, additive and backward-compatible (defaults to `False`, so
every existing and every real, provider-originated notification is
unaffected):

| Field | Type | Notes |
|---|---|---|
| `simulated` | `bool` | `True` only for notifications this feature delivered via `WebhookService.receive(..., simulated=True)`. Permanent once set — nothing in this feature or 007 ever flips it after creation (FR-003, NFR-001). |

No other `InboundNotification` field changes. `declared_event_type` for
every injection this feature produces is the schedule-change type
(anticipated as `"schedule.changed"`, following the dotted-string
convention §7c establishes and 007's own Assumptions already anticipate);
`order_reference` is always the targeted journey's real order number.

---

## WAKE_REQUESTED event (extended, owned by feature 006/007)

No new payload field — `WakeRequestedPayload` (007) is unchanged. What
changes is that `JourneyEvent.simulated` (006, already existing) is now
correctly threaded through from the triggering `InboundNotification`
rather than always defaulting to `False`, whenever `WebhookService.confirm()`
appends one (research.md R3).

---

## New entity: Injection Request (not persisted — a transient service call)

The input to `DisruptionInjectorService.inject()`. Not stored in its own
right; its only durable trace is the `InboundNotification` (with
`simulated=True`) it produces.

| Field | Type | Notes |
|---|---|---|
| `journey_id` | `str` | The target journey (FR-005). Must correspond to a real journey with a real order — see Validation. |
| `revised_arrival_time` | `datetime` | Operator-specified (FR-006). Carried into the constructed envelope's `data` object as the schedule-change claim's revised time. |

**Validation** (research.md R6):
- `journey_id` does not correspond to any existing journey →
  `JourneyNotFoundError`.
- `journey_id` corresponds to a real journey, but it has no order with a
  real `order_no` yet → `JourneyHasNoOrderError`.
- The injector's enabled/disabled state (FR-008) is currently disabled →
  `InjectorDisabledError`, checked before any of the above.

---

## New entity: Injector Control (an operational parameter, not a persisted row)

The enabled/disabled state (FR-008) and the operator-only access token
(NFR-002) are both read from environment configuration at startup
(research.md R5) — global, not scoped per-journey or per-environment
within the running process, per spec.md's own Assumption. Not a database
row; there is nothing here for a test to seed beyond setting environment
variables or constructing the service with explicit values for
testability.

---

## Constructed envelope shape (not a new schema — a value this feature builds, structurally derived from §7c)

```json
{
  "cid": "<client id>",
  "type": "schedule.changed",
  "status": 0,
  "data": {
    "orderNo": "<the targeted journey's real order_no>",
    "revisedArrivalTime": "<operator-specified time, ISO-8601>"
  }
}
```

This mirrors the one real captured envelope's top-level shape (`cid`,
`type`, `status`, `data`) exactly; only the `type` value and the `data`
object's contents are specific to a schedule change, following the same
dotted-string convention and object-nesting pattern the real capture
established (research.md, spec.md Input). `status` is included for
structural completeness but — per feature 007's own FR-006 (never
interpreted as a success/failure signal) — carries no meaning this or any
other feature reads.

---

## Lifecycle (for one injection)

```
DisruptionInjectorService.inject(journey_id, revised_arrival_time, now)
       │
       ▼
   injector enabled?
   │            │
  no           yes
   │            │
   ▼            ▼
InjectorDisabledError   journey exists?
                        │            │
                       no           yes
                        │            │
                        ▼            ▼
              JourneyNotFoundError   journey has a real order_no?
                                     │            │
                                    no           yes
                                     │            │
                                     ▼            ▼
                        JourneyHasNoOrderError   construct envelope
                                                       │
                                                       ▼
                                    WebhookService.receive(raw_body, now,
                                                            simulated=True)
                                                       │
                                                       ▼
                              (identical to any real notification from
                               here: association, throttle, confirmation-
                               triggering — all per 007's existing rules,
                               unaffected by `simulated`)
                                                       │
                                                       ▼
                          confirmation_triggered? → confirm() scheduled,
                          exactly as the router would (or currently
                          always False for schedule.changed — no
                          registered handler yet, research.md R4)
```
