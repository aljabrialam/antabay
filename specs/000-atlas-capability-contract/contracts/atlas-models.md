# Contract: Atlas Typed Models

**Feature**: 000-atlas-capability-contract
**Date**: 2026-08-28
**Source**: `.antabay/atlas-capability-map.md` §3–§9

This contract describes the interface each typed model exposes and the
invariants it enforces. Implementation lives in `backend/atlas/models/`.

---

## General Invariants (all models)

1. `extra = "forbid"` — any field not declared in the model causes a
   validation error. No extra field passes through silently.
2. Monetary fields use `Decimal`, not `float`.
3. Datetime fields are UTC-aware. Times in `YYYYMMDDHHMM` string form
   (segment dep/arr) are stored as strings; callers who need datetime
   semantics must parse them explicitly using the documented format.
4. `OpaqueId` fields are never `str`. Code that compares or constructs
   them as strings will not type-check.

---

## `canonical_total_price(adult_price, adult_tax, transaction_fee)` — `pricing.py`

**Signature** (conceptual):
```
canonical_total_price(
    adult_price: Decimal,
    adult_tax: Decimal,
    transaction_fee_per_pax: Decimal,
) -> CanonicalPrice
```

**Invariants**:
- This is the only callable that returns a `CanonicalPrice`.
- No other code path may add `adult_price + adult_tax + transaction_fee_per_pax`.
- A CI check (grep/ruff rule) fails the build if those three field names
  appear in a sum expression outside `pricing.py`.

**Known good input/output**:
```
adult_price=66.43, adult_tax=23.96, transaction_fee_per_pax=0.00
→ CanonicalPrice(amount=Decimal("90.39"), currency="USD")
```

---

## `OpaqueId` — `identifiers.py`

**Permitted operations**:
```
id == other_id          # equality
id != other_id          # inequality
str(id)                 # returns raw value for HTTP serialisation only
```

**Prohibited operations** (not available on the type):
- Subscript (`id[0:4]`)
- Concatenation (`id + suffix`)
- Format (`f"{id}-extra"`)
- Regex match
- Construction from components (`OpaqueId(prefix + seq + date)`)

---

## Error Classification — `errors.py`

**`classify(status_code: int) -> ErrorDisposition | ReconcilableOutcome`**

```
classify(0)    → ErrorDisposition.SUCCESS
classify(318)  → ReconcilableOutcome(error_code=DUPLICATE_BOOKING,
                                     duplicate_orders=[...])
classify(800)  → ErrorDisposition.TERMINAL
classify(900)  → ErrorDisposition.TERMINAL
classify(any_unknown) → ErrorDisposition.TERMINAL
```

**Invariants**:
- `DUPLICATE_BOOKING` MUST return `ReconcilableOutcome`, never
  `ErrorDisposition.RECONCILABLE`.
- `duplicate_orders` is always populated from the Atlas response field;
  callers MUST NOT retry when they receive `ReconcilableOutcome`.

---

## `orderStatus` Normalisation — `models/webhook.py` and `models/query.py`

Both surfaces produce `OrderStatus` (IntEnum) after parsing.

| Source | Raw type | Raw value observed | Normalised |
|--------|----------|--------------------|-----------|
| `queryOrderDetails.do` | `str` | `"1"` | `OrderStatus.PAID_NOT_TICKETED` |
| Webhook `data.orderStatus` | `int` | `2` | `OrderStatus.TICKETED` |

**Invariant**: Downstream code MUST only compare against `OrderStatus`
members. Comparisons against `"1"`, `"2"`, `1`, or `2` as literals will
not type-check.

---

## `FreshnessWindow` — `freshness.py`

**Factory functions**:
```
FreshnessWindow.from_offer(routing: Routing, received_at: datetime)
    → FreshnessWindow(clock_type="offer", issued_at=received_at,
                      expires_at=routing.expire_time)

FreshnessWindow.from_session(received_at: datetime)
    → FreshnessWindow(clock_type="session", issued_at=received_at,
                      expires_at=None)        # explicit field absent in response

FreshnessWindow.from_ticket(order_response: OrderResponse)
    → FreshnessWindow(clock_type="ticket", issued_at=received_at,
                      expires_at=order_response.tkt_limit_time)
```

**`is_usable(now: datetime) -> bool`**:
```
expires_at is None  → False  # unknown expiry = treat as expired
expires_at > now    → True
expires_at <= now   → False
```

**Invariant**: Any code acting on a held identifier MUST call
`freshness_window.is_usable(now)` and handle `False` before proceeding.

---

## `CallBudget` — `budget.py`

**`check_and_record(journey_id, endpoint, now) -> None | raises BudgetExhausted`**

Raises `BudgetExhausted` if the per-journey limit for the endpoint is reached.
Records the call regardless.

**`apply_hold(endpoint, retry_after: datetime | None) -> RateLimitHold`**

Records a rate-limit hold. While the hold is active, `check_and_record`
raises `RateLimitHold` before checking the budget.

**Invariant**: `retry_after = None` means indefinite hold; it MUST NOT be
treated as "no hold".

---

## `CallRecord` — `telemetry.py`

Every external HTTP call MUST produce one `CallRecord` before returning to the
caller. The record is append-only; existing records are never modified.

Fields: `endpoint`, `outcome` (Atlas status code), `elapsed_ms`, `journey_id`,
`recorded_at` (UTC).
