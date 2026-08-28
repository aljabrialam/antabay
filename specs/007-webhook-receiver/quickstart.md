# Quickstart: Event Reception and Reconciliation (007)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- No external sandbox access needed for the primary test suite — tests
  exercise the endpoint and service against constructed webhook envelopes
  (matching the real captured shape in `.antabay/atlas-capability-map.md`
  §7c) and a stubbed confirmation query, the same pattern feature 012
  already established
- Feature 012 (`PostActionVerifier`, `TicketingSuccessCondition`) and
  feature 006 (`EventService`, `JourneyEvent`) must already be present
  (they are, in `master`) — this feature is built directly on both

---

## Scenario 1 — Untrusted Notification Ingestion (US1, FR-001–002, NFR-001)

**Goal**: Confirm acknowledgement never waits on confirmation, and every
notification is persisted in full first.

**Steps**:
1. POST a well-formed `order.ticketed` envelope to `/webhooks/atlas` with
   a confirmation query stubbed to hang or fail.
2. Measure response time and inspect the stored `InboundNotification`.

**Expected**:
- Step 1 returns `200 OK` promptly, regardless of the stubbed
  confirmation's behaviour.
- Step 2 shows the exact raw body persisted, with `received_at` before
  the confirmation attempt (if any) was made.

---

## Scenario 2 — Confirm Before Acting (US2, FR-003–004, FR-006)

**Goal**: Confirm the notification's own claim is never trusted, and its
status field is never read as success/failure.

**Steps**:
1. POST an `order.ticketed` envelope whose `data.orderStatus` implies
   ticketed, but stub the confirmation query to return empty `ticketNos`
   for every passenger.
2. Repeat with the envelope's top-level `status` field set to a value that
   would look like failure if it were ever interpreted directly.

**Expected**:
- Step 1: the resulting `VerificationAttempt` classifies as not-yet-
  ticketed (per `TicketingSuccessCondition`), matching the query, not the
  claim.
- Step 2: classification is unaffected by the `status` field's value —
  only the query result and `TicketingSuccessCondition`'s own rule matter.

---

## Scenario 3 — Correct Routing and Association (US3, FR-005, FR-007–008)

**Goal**: Confirm routing by declared type, association by order
reference, and discarding of unknown orders.

**Steps**:
1. POST an envelope with an `orderNo` matching no known journey.
2. POST an envelope with a `type` no handler is registered for.
3. POST an `order.ticketed` envelope whose confirmed `orderStatus` is an
   integer while the stubbed query result reports the equivalent status as
   a string.

**Expected**:
- Step 1: notification persisted, `associated=False`, no journey affected.
- Step 2: notification persisted, `associated` reflects a real journey if
  one matched, but no confirmation or wake follows.
- Step 3: no discrepancy from the type mismatch alone — normalised before
  comparison (inherited from 012's `TicketingSuccessCondition.has_discrepancy()`).

---

## Scenario 4 — Duplicate Tolerance, Throttling, and Reconciliation (US4, FR-009–010, FR-013)

**Goal**: Confirm a burst of notifications for one journey collapses into
a bounded number of confirmation queries, and that reconciliation covers
journeys independently of notification history.

**Steps**:
1. POST the identical `order.ticketed` envelope five times in quick
   succession.
2. POST five distinct-looking `order.ticketed` envelopes for the same
   `orderNo` in quick succession.
3. Call `reconcile_active_journeys()` for a journey with a known order
   reference that has never received any notification.

**Expected**:
- Step 1 and Step 2 both result in exactly one triggered confirmation
  query for that `orderNo` within the confirmation budget window — the
  other four each time are absorbed, not duplicated (research.md R3).
- Step 3 produces a confirmation query for that journey regardless of its
  empty notification history.

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/unit/test_webhook_service.py \
                  tests/unit/test_webhook_reconciliation.py \
                  --tb=short --html=reports/report_007.html
```

**Expected**: All tests pass, with no network access required. The
existing 012 (`test_verification_gate.py`, `test_ticketing_success_condition.py`)
and 006 (`test_auth_contract.py`, `test_auth_gate.py` and other event-stream
tests) suites continue to pass unmodified, confirming this feature did not
disturb the mechanisms it builds on.

---

## References

- Internal service contract: [`contracts/webhook_receiver.md`](contracts/webhook_receiver.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- The real captured event this feature is grounded in:
  `.antabay/atlas-capability-map.md` §7c
- The verification mechanism this feature reuses rather than
  reimplementing: spec 012, `journey/services/verification_gate.py`
