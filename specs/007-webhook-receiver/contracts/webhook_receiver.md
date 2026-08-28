# Contract: Webhook Receiver (public endpoint + internal service)

**Feature**: 007-webhook-receiver
**Type**: One public HTTP endpoint (this backend's first genuinely public,
unauthenticated surface) plus an internal service interface consumed by
that endpoint and by the periodic reconciliation sweep.

---

## Endpoint: `POST /webhooks/atlas`

**Authentication**: None — deliberately. The channel is unauthenticated by
the provider's own design (FR-003); this endpoint does not invent
authentication the provider does not send, since there is nothing to
verify a signature against.

**Request**: Raw JSON body, shape observed in
`.antabay/atlas-capability-map.md` §7c:
```json
{
  "cid": "<client id>",
  "type": "order.ticketed",
  "status": -1,
  "data": { "orderNo": "...", "orderStatus": 2, "paxTicketInfos": [...] }
}
```
No schema is enforced strictly enough to reject a malformed body — a body
that fails to parse as JSON, or lacks `type`/`data.orderNo`, is still
accepted and persisted (FR-002), just with those fields recorded as
absent/empty (data-model.md's `InboundNotification`).

**Response**: `200 OK`, returned as soon as persistence (FR-002)
completes — never delayed by the confirmation query (FR-001, NFR-001).
Body is a minimal acknowledgement; its content carries no meaning the
provider is expected to act on (this is not a bidirectional protocol).

**Behaviour**:
1. Parse the body (tolerantly — see above).
2. Call `WebhookService.receive(raw_body, received_at)` — persistence,
   routing, association, and the throttle check only (all local, no
   network call to the provider; see below).
3. Schedule `WebhookService.confirm(notification)` as a background task —
   it runs *after* the response is sent, and its outcome (including any
   exception) has no bearing on the response already returned.
4. Return `200 OK`.

**Error conditions**: None that produce a non-`200` response for a
malformed or unrecognised payload — per FR-001/NFR-001, acknowledgement is
unconditional. A `5xx` is only possible if step 2 itself (a local database
write) fails — a genuine infrastructure fault, not a payload-shape
problem. A failure in the step-3 background task (e.g. the provider is
unreachable) never surfaces as an HTTP error, since the response has
already been sent — this is exactly why NFR-001 requires the split
between step 2 and step 3.

---

## Internal Service: `WebhookService`

`receive()` and `confirm()` are deliberately separate methods — the
endpoint calls `receive()` synchronously (fast, local-only) before
responding, then schedules `confirm()` to run afterward (FR-001,
NFR-001). This split is the whole reason acknowledgement never depends on
the confirmation step's outcome or timing.

### `receive(raw_body: bytes, received_at: datetime) -> InboundNotification`

**Behaviour** (local-only — no network call to the provider):
1. Persist an `InboundNotification` row from `raw_body` (FR-002) —
   unconditionally, before anything below.
2. Extract `order_reference` from the parsed body, if present and
   well-formed.
3. Look up a journey by `order_reference` (reusing
   `JourneyRepository.get_order_by_order_no()`). If none matches, mark
   `associated=False` and stop (FR-008) — the notification remains
   persisted, nothing further happens.
4. Look up a registered handler for `declared_event_type`. If none is
   registered, stop (FR-005, research.md R5) — inert, not an error.
5. If the associated journey is in a terminal state, stop (spec.md Edge
   Cases) — still persisted and associated, no confirmation or wake.
6. Check the confirmation budget window for this `order_reference`
   (FR-013), via the existing `JourneyRepository.get_verification_attempts()`
   (012). If a recent attempt already exists inside the window, mark
   `confirmation_triggered=False` and stop — this notification is
   absorbed into it; this is also how FR-009's duplicate tolerance is
   satisfied (research.md R3). Otherwise mark `confirmation_triggered=True`.

**Outputs**: The persisted `InboundNotification`, with
`confirmation_triggered` telling the caller (the endpoint) whether to
schedule `confirm()` at all.

### `confirm(notification: InboundNotification) -> None`

**Behaviour** (the one step that makes a network call — never on the
acknowledgement path):
1. Call the registered handler's confirmation path — for
   `order.ticketed`, `PostActionVerifier.verify(...)` per data-model.md —
   with the notification's `data` payload as `action_response`.
2. If the resulting classification is `SUCCESS` or `FAILURE`, append a
   `WAKE_REQUESTED` event (FR-011). If `UNRESOLVED`, do not.

Only called when `receive()` returned `confirmation_triggered=True`.

**Outputs**: None (side effects only — the `VerificationAttempt` and,
conditionally, the `WAKE_REQUESTED` event).

### `reconcile_active_journeys(now: datetime) -> None`

**Behaviour**: For every journey with a known order reference in a
non-terminal state, performs the same throttle check as `receive()`
step 6, then calls `confirm()`-equivalent logic directly (no
`InboundNotification` exists for a sweep-triggered confirmation;
`declared_event_type` is recorded as `"reconciliation_sweep"` in the
resulting `WAKE_REQUESTED` event, per data-model.md). Independent of
whether any notification has ever been received for that journey
(FR-010). This method itself makes network calls (via the same
confirmation path) and is therefore never called from the request/response
cycle of the endpoint — only from the periodic sweep loop (research.md R6).

**Outputs**: None (side effects only, same as `confirm()`).

---

## Relationship to feature 012

This feature's confirmation step is 012's `PostActionVerifier.verify()`,
called with a `PostActionVerifier` instance this feature owns (registered
with 012's existing `TicketingSuccessCondition`, action_type
`"ticketing"`). It does not modify `journey/services/verification_gate.py`
or `journey/services/conditions/ticketing_condition.py`. Discrepancy
recording (FR-012) and confirmation ordering (this spec's Clarifications)
are inherited, not reimplemented — see research.md R1.

## Relationship to feature 006

The wake signal is a new `EventType.WAKE_REQUESTED` case added to the
existing event vocabulary and payload registry in
`journey/models/events.py` (additive, same pattern 010 used for
`AUTHORISATION_VOIDED`). This feature does not modify
`journey/api/routers/events.py` or `EventService`'s existing methods.

## Relationship to feature 005

The confirmation query calls the same `queryOrderDetails.do` endpoint
`BookingService._query_order()` calls, at the same request shape, but as
independent glue code — not a shared function, not an import from
`booking_service.py` (research.md R2).
