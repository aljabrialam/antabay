# Quickstart: Price Verification and Offer Staleness (004)

## Prerequisites

- Python 3.11, `pip install -e ".[dev]"` in `backend/`
- A journey already in `SEARCHING` state with at least one `flight_options`
  row (i.e., spec 002's flight search has already run) — see spec
  002/003's own quickstarts for how to produce one
- The Tier 1 cassette `fixtures/atlas/cassettes/verification/verify_ze605.yaml`,
  transcribed from the ZE605 capture in
  `.antabay/atlas-capability-map.md` §7a (no live sandbox call needed to
  run these scenarios)

---

## Scenario 1 — Verify Before Commitment (US1, FR-001–004, FR-011)

**Goal**: Confirm a selected option is verified, its identifier reaches
the provider unmodified, and the price-change signal is read rather than
computed.

**Steps**:
1. Select an option from a journey's `flight_options` (its
   `routing_identifier` is what search returned, untouched).
2. Call the verification service's `Verify` operation for that
   `journey_id`/`option_id`, replaying `verify_ze605.yaml`.
3. Inspect the persisted `VerificationResult`.

**Expected**:
- The cassette's recorded request shows `routingIdentifier` equal,
  byte-for-byte, to the option's stored `routing_identifier`.
- `outcome` is `VERIFIED` (the ZE605 capture has
  `priceChange.isPriceChange: false`).
- `budget_after == budget_before - 1`.
- Re-running Scenario 1 against a cassette variant with
  `isPriceChange: true` produces `outcome: PRICE_CHANGED`, and the result
  signals that any existing authorisation for the option is invalidated
  (FR-004) — see contracts/verification_service.md step 5.

---

## Scenario 2 — Freshness Window Handoff (US2, FR-005, FR-006, FR-010)

**Goal**: Confirm the offer window is retired and a session window begins,
and that the safety margin triggers re-verification.

**Steps**:
1. Run Scenario 1 to produce a `VERIFIED` result.
2. Read the journey's `held_identifiers`.
3. Call `NeedsReverification` with `now` set just inside the configured
   safety margin of the session's `stale_at`.

**Expected**:
- Two `held_identifiers` rows exist: the original offer-window row
  (`routingIdentifier`, unchanged) and a new session-window row
  (`sessionId`, `stale_after_seconds` equal to the configured session
  duration — see research.md R2).
- `NeedsReverification` returns `true` once `now` is inside the margin,
  `false` well before it.
- The journey's state is `VERIFIED` (was `SEARCHING` before Scenario 1).

---

## Scenario 3 — Runtime Requirements Capture (US3, FR-007, FR-008)

**Goal**: Confirm passenger requirements and bookable quantity are read
from the response, not assumed.

**Steps**:
1. Run Scenario 1.
2. Read the persisted `VerificationResult.passenger_requirements` and
   `.max_seats`.

**Expected**:
- `max_seats == 7` (the ZE605 capture's `maxSeats`).
- `passenger_requirements` matches the cassette's
  `bookingRequirement.passenger` field set exactly — no field added or
  removed relative to the response.
- Replaying a second cassette with a different field set produces a
  different `passenger_requirements` list, proving no fixed template is
  in play.

---

## Scenario 4 — Unavailable Option Recovery (US4, FR-009)

**Goal**: Confirm an unavailable verification returns the journey to
search.

**Steps**:
1. Run Scenario 1 to reach `VERIFIED`.
2. Call `Verify` again against a cassette recording a non-zero `status`
   that is not a price-change response.

**Expected**:
- `outcome` is `UNAVAILABLE`.
- The journey's state transitions from `VERIFIED` back to `SEARCHING`.
- No order-creation call is made or attempted (out of scope for this
  feature to test directly, but observable as: no such call exists in the
  scenario's call trace).

---

## Running the Test Suite

```bash
cd backend
python -m pytest tests/contract/test_verify_contract.py \
                  tests/unit/test_verification_service.py \
                  tests/integration/test_verification_persistence.py \
                  --tb=short --html=reports/report_004.html
```

**Expected**: All tests pass. Tier 1 (cassette-backed) tests require no
network access and no live sandbox credentials.

---

## References

- External contract: [`contracts/verify_do.md`](contracts/verify_do.md)
- Internal service contract: [`contracts/verification_service.md`](contracts/verification_service.md)
- Data model: [`data-model.md`](data-model.md)
- Design decisions: [`research.md`](research.md)
- Source of truth: `.antabay/atlas-capability-map.md` §7a
