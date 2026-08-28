# Quickstart: Disruption Injector (008)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- No external sandbox access needed — this feature makes no provider call
  of its own; it delegates entirely to feature 007's already-tested
  confirmation glue
- Features 006 (`EventService`/`JourneyEvent.simulated`) and 007
  (`WebhookService`) must already be present (they are, in `master`)
- An operator token configured via environment variable for the contract
  tests that exercise access control

---

## Scenario 1 — Produce a Conforming Notification (US1, FR-001, FR-005–007)

**Goal**: Confirm the constructed envelope conforms to the observed
structure, references the target journey's real order, carries the
specified revised time, and touches no travel data.

**Steps**:
1. Seed a journey with a real order (`order_no` set).
2. Call `DisruptionInjectorService.inject(journey_id, revised_arrival_time, now)`.
3. Inspect the resulting `InboundNotification.raw_payload_json`.

**Expected**:
- The envelope's top-level shape matches `cid`/`type`/`status`/`data`,
  the same shape as the one real capture.
- `data.orderNo` equals the seeded journey's real `order_no`, unmodified.
- The revised arrival time specified in step 2 appears exactly as given.
- No other travel-related field (price, availability, flight option) is
  present anywhere in the envelope.

---

## Scenario 2 — Delivery, Marking, and Independence (US2, FR-002–003, NFR-001)

**Goal**: Confirm delivery reuses 007's own logic, the result is marked
simulated permanently, and a real notification for the same order is
unaffected.

**Steps**:
1. Inject a notification for a journey with a real order.
2. Inspect the persisted `InboundNotification`.
3. Separately, deliver a real, provider-originated `order.ticketed`
   notification for the *same* order via `WebhookService.receive()`
   directly (as feature 007's own router would).
4. Compare the two stored records.

**Expected**:
- Step 2: `simulated=True`, and this remains true on every subsequent
  read.
- Step 3–4: the real notification's `confirmation_triggered`,
  association, and any resulting confirmation are exactly what they
  would be had the simulated one never existed — no cross-contamination
  (Clarifications).

---

## Scenario 3 — Simulation Visibility Downstream (US3, FR-004)

**Goal**: Confirm the `simulated` flag reaches any event this feature's
plumbing produces — proven structurally, since no schedule-change
handler exists yet to exercise this in production (research.md R4).

**Steps**:
1. Temporarily register a stub confirmation handler for
   `"schedule.changed"` (test-only — not a production capability this
   feature builds).
2. Inject a notification against a journey using that stub.
3. Confirm the stub resolves and inspect any resulting event.

**Expected**: The resulting event carries `simulated=True`, proving the
plumbing (research.md R3) works correctly once any real handler is
eventually registered — without this feature having built that handler.

---

## Scenario 4 — Operator-Only, Disableable (US4, FR-008, NFR-002)

**Goal**: Confirm the endpoint is unreachable without the correct token,
and inert while disabled.

**Steps**:
1. `POST /operator/disruptions` with no token, then with a wrong token.
2. Disable the injector; `POST /operator/disruptions` with the correct
   token.
3. Re-enable the injector; repeat.

**Expected**:
- Step 1: `401 Unauthorized` in both cases, no notification produced.
- Step 2: `401 Unauthorized` (or an equivalent no-effect outcome),
  regardless of a correct token — disabled means inert.
- Step 3: behaves exactly as Scenario 1.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_disruption_injector_service.py \
                  tests/contract/test_disruption_injector_contract.py \
                  --tb=short --html=reports/report_008.html
```

**Expected**: All tests pass, with no network access required. The
existing `test_webhook_service.py`/`test_webhook_reconciliation.py`/
`test_webhook_contract.py` (007) and `test_auth_contract.py`/
`test_auth_gate.py` (006) suites continue to pass unmodified, confirming
this feature's additive extensions did not disturb what it builds on.

---

## References

- Internal service contract: [`contracts/disruption_injector.md`](contracts/disruption_injector.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- The one real captured envelope this feature's structure derives from:
  `.antabay/atlas-capability-map.md` §7c
- The reception path this feature delivers through: spec 007,
  `journey/services/webhook_service.py`
