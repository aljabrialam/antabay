# Quickstart: Order Creation and Payment (005)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- A journey already `VERIFIED` (spec 004's output) with a session
  `held_identifiers` row not yet expired
- The Tier 1 cassette
  `fixtures/atlas/cassettes/booking/order_pay_query_jkt_sub.yaml`,
  transcribed from the JKT→SUB capture in
  `.antabay/atlas-capability-map.md` §7b (no live sandbox call needed to
  run these scenarios)

---

## Scenario 1 — Create Order From a Verified Session (US1, FR-001–005)

**Goal**: Confirm the session identifier is forwarded unmodified, the
passenger form matches the verified requirements, and the order/booking
references and ticketing deadline are recorded correctly.

**Steps**:
1. Call `BookingService.CreateOrder` for a journey with a held, unexpired
   session, replaying the cassette's `order.do` interaction.
2. Inspect the persisted `Order`.

**Expected**:
- The request's `sessionId` equals the session held from verification,
  byte-for-byte.
- `outcome == CREATED`.
- `order_no == "TESTA20260815172246746"`, `booking_reference == "TZKZYA"`
  (the JKT→SUB capture's observed values).
- A ticketing-deadline `held_identifiers` row exists, bounded by the
  response's `tktLimitTime`.
- No code path anywhere treats `booking_reference` as ticketing evidence.

---

## Scenario 2 — Payment Only After Order Exists (US2, FR-008, FR-009, FR-013)

**Goal**: Confirm payment is gated on order existence and that success
doesn't confirm ticketing.

**Steps**:
1. Attempt `BookingService.SubmitPayment` for a journey with no created
   order — confirm it refuses.
2. Run Scenario 1, then call `SubmitPayment` for the resulting `order_no`.
3. Replay a cassette variant where `pay.do` returns a decline, and attempt
   `SubmitPayment` a second time for the same `order_no`.

**Expected**:
- Step 1 raises before any HTTP call.
- Step 2's `PaymentAttempt.outcome == SUCCESS`; the journey's state is
  unchanged (still `VERIFIED`, not `MONITORING`).
- Step 3's second attempt is refused — no second `PaymentAttempt` row is
  created for the same `order_no` after a decline (FR-013).

---

## Scenario 3 — Independent Ticketing Confirmation (US3, FR-010–012)

**Goal**: Confirm ticketing is only accepted from an independent query,
requires every passenger's ticket numbers, and the journey moves to
`MONITORING` only then.

**Steps**:
1. Run Scenarios 1–2.
2. Call `BookingService.ConfirmTicketing` against a query response where
   `ticketNos` is still empty for all passengers — confirm no transition.
3. Call it again against a response where only some passengers have
   ticket numbers — confirm still no transition.
4. Call it again against a response where every passenger has non-empty
   `ticketNos` — confirm the journey transitions to `MONITORING`.

**Expected**:
- Steps 2–3 leave `JourneyState` at `VERIFIED`.
- Step 4 transitions it to `MONITORING`, and the `TicketingQuery` row from
  that call has `confirmed == True`.

---

## Scenario 4 — Duplicate Order Reconciliation (US4, FR-006, FR-007)

**Goal**: Confirm a duplicate rejection — whether from a genuine duplicate
attempt or from retrying after an uncertain outcome — is reconciled by
reading and querying the referenced order, never by reporting failure or
creating a second order.

**Steps**:
1. Replay a cassette variant where `order.do` returns a duplicate
   rejection (`status: 318`, `duplicateOrders: ["<existing orderNo>"]`).
2. Call `BookingService.CreateOrder`.

**Expected**:
- The `Order` row's `outcome == DUPLICATE_REJECTED`.
- `queryOrderDetails.do` is called for the referenced `orderNo`.
- The journey resumes from that queried order's real state — no second
  order-creation attempt is made, and no failure is reported to the
  caller.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/contract/test_booking_contract.py \
                  tests/unit/test_booking_service.py \
                  tests/integration/test_booking_persistence.py \
                  --tb=short --html=reports/report_005.html
```

**Expected**: All tests pass. Tier 1 (cassette-backed) tests require no
network access and no live sandbox credentials.

---

## References

- External contract: [`contracts/order_pay_query_do.md`](contracts/order_pay_query_do.md)
- Internal service contract: [`contracts/booking_service.md`](contracts/booking_service.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- Source of truth: `.antabay/atlas-capability-map.md` §7b
