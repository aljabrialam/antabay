# Data Model: Event Reception and Reconciliation

## InboundNotification

The raw, untrusted record of one notification, persisted before anything
else happens to it (FR-002). New table: `webhook_notifications`.

| Field | Type | Notes |
|---|---|---|
| `notification_id` | `str` | Generated on receipt. |
| `received_at` | `datetime` | When the endpoint accepted it — precedes acknowledgement (FR-001). |
| `declared_event_type` | `str` | The raw `type` field, e.g. `"order.ticketed"` (FR-005). Not validated against a known set — routing failing to find a handler is a normal, inert outcome (research.md R5), not a rejected notification. |
| `order_reference` | `str \| None` | Extracted from the payload (e.g. `data.orderNo`). `None` if the payload omits it or is malformed. |
| `raw_payload_json` | `str` | The full, unmodified body, exactly as received (FR-002). |
| `journey_id` | `str \| None` | Set once associated (FR-008) via `order_reference`; `None` if no known journey matched, or the payload had no usable order reference. |
| `associated` | `bool` | Explicit flag, not merely `journey_id is not None`, so a discard is unambiguous even before any lookup logic changes in the future. |
| `confirmation_triggered` | `bool` | Whether this specific notification triggered its own confirmation query, or was absorbed into an existing one already inside the confirmation budget window (FR-013) — see the Throttle Record below. |

**Validation**: `notification_id`, `received_at`, `declared_event_type`
(may be an empty string if the payload is malformed, but the field itself
always exists), and `raw_payload_json` are always present — persistence
(FR-002) happens unconditionally, even for a payload with no other
extractable field.

---

## Confirmation (reused, not redefined)

This feature does not define its own confirmation/verification entity. An
`order.ticketed` notification's confirmation is a `VerificationAttempt`
row (feature 012), created by calling this feature's own
`PostActionVerifier` instance (registered with 012's
`TicketingSuccessCondition`) with:

| `verify()` parameter | Value |
|---|---|
| `journey_id` | Resolved via `order_reference` → `InboundNotification.journey_id` |
| `action_type` | `"ticketing"` |
| `affected_record_id` | The order reference |
| `query_fn` | This feature's own call to `queryOrderDetails.do` (research.md R2) |
| `action_response` | The notification's raw `data` payload — the untrusted claim |
| `now` | Current time |

Everything FR-004 (confirm before acting), FR-006 (never trust the
notification's own status), FR-012 (record a discrepancy), and this
spec's adopted ordering rule require is satisfied by 012's existing
`VerificationAttempt` shape and `PostActionVerifier` behaviour — see
research.md R1.

---

## Confirmation Budget Window (throttle)

Not a new persisted entity — implemented as a query against two existing
sources: 012's `verification_attempts` table (a completed confirmation's
`observed_at`), and this feature's own `webhook_notifications` table (a
prior notification's `confirmation_triggered` flag and `received_at`). If
either shows recent activity for this order reference within the window,
this notification does not trigger a new confirmation query (FR-013); if
neither does, it triggers one. Checking both sources — not just completed
`VerificationAttempt` rows — is necessary because `confirm()` runs as a
background task; see research.md R3's implementation note.

This single check is also what satisfies FR-009 (duplicate tolerance) —
research.md R3.

---

## WakeSignal (new `EventType.WAKE_REQUESTED`)

A durable, minimal fact recorded via the existing (006) `EventService`
once a confirmation for a journey resolves to `SUCCESS` or `FAILURE`
(FR-011). New payload model, `WakeRequestedPayload`, in
`journey/models/events.py`'s existing registry (additive, same pattern as
010's `AUTHORISATION_VOIDED`).

| Field | Type | Notes |
|---|---|---|
| `order_reference` | `str` | Which order this confirmation concerned. |
| `declared_event_type` | `str` | The notification type that triggered this confirmation, or `"reconciliation_sweep"` if it was sweep-triggered rather than notification-triggered. |
| `classification` | `str` | The resolved `VerificationOutcome` value (`"SUCCESS"` or `"FAILURE"`) — never issued for `"UNRESOLVED"` (FR-011's "only after... confirmed"). |

---

## Reconciliation Sweep (behaviour, not a persisted entity)

`WebhookService.reconcile_active_journeys(now)`: for every journey with a
known order reference and a non-terminal state, triggers the same
confirmation path described above (as if a notification had arrived for
it), independent of whether any notification for it exists at all
(FR-010). Reuses the same confirmation-budget-window throttle, so a sweep
and a recent notification-triggered confirmation for the same journey
don't double up either.

---

## Lifecycle (for one inbound notification)

`receive()` (local-only) runs entirely before the HTTP response is sent.
`confirm()` (makes the network call) is scheduled as a background task
*after* the response — this split is what satisfies NFR-001.

```
receive() ──► persist InboundNotification (FR-002)
                    │
                    ▼
       order_reference present & known?
          │                    │
         no                   yes
          │                    │
          ▼                    ▼
   associated=False    associated=True, journey_id set
   (discarded)                 │
                                ▼
                   declared_event_type has a registered handler?
                       │                        │
                      no                       yes (today: "order.ticketed")
                       │                        │
                       ▼                        ▼
                    inert                journey non-terminal?
              (research.md R5)               │           │
                                             no          yes
                                              │            │
                                              ▼            ▼
                                          inert    within confirmation budget
                                                    window for this order?
                                                       │           │
                                                      yes          no
                                                       │            │
                                                       ▼            ▼
                                          confirmation_triggered=False   confirmation_triggered=True
                                          (absorbed into existing attempt)
                    │                                                        │
                    ▼                                                        ▼
     ═══════════ acknowledge (FR-001, NFR-001) — response sent here ═══════════
                                                                              │
                                                          (background task, after response)
                                                                              ▼
                                                                     confirm() calls
                                                                     PostActionVerifier
                                                                     .verify()
                                                                     (FR-004, FR-006,
                                                                     FR-012, research R1)
                                                                              │
                                                        ┌─────────────────────┼─────────────────────┐
                                                        ▼                     ▼                     ▼
                                                    SUCCESS               FAILURE              UNRESOLVED
                                                        │                     │                     │
                                                        ▼                     ▼                     ▼
                                                 WAKE_REQUESTED        WAKE_REQUESTED           no wake
                                                 (FR-011)              (FR-011)                 (FR-011)
```
