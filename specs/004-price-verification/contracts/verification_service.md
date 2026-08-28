# Contract: Verification Service (internal, exposed)

**Feature**: 004-price-verification
**Type**: Internal service interface — consumed by whatever orchestrates
the journey (the agent loop / a future order-creation feature), not by an
external caller
**Consumed by**: The order-creation step (out of scope for this feature —
this contract is what that future step will call), and by FR-010's
proactive re-verification trigger

---

## Operation: Verify

**Preconditions**: A `flight_options` row exists for the journey with a
held, non-expired offer `routingIdentifier`.

**Inputs**: `journey_id`, `option_id`.

**Behaviour**:
1. Reads the option's `routingIdentifier` from storage — never from a
   caller-supplied value that could diverge from what search returned
   (FR-002).
2. Decrements the journey's call budget before calling `verify.do`
   (FR-011), matching the existing `search.do` pattern.
3. Persists a `VerificationResult` row regardless of outcome (NFR-002).
4. On `VERIFIED` or `PRICE_CHANGED`: creates the session `HeldIdentifier`
   row (FR-005, FR-006); transitions the journey to `VERIFIED` if it was
   `SEARCHING`.
5. On `PRICE_CHANGED` specifically: additionally signals that any
   authorisation held for this option is invalidated (FR-004) — the
   mechanism for *acting* on that invalidation (e.g. clearing an
   authorisation record) belongs to whichever feature owns authorisation
   state; this operation's responsibility ends at making the
   invalidating fact observable on the persisted result.
6. On `UNAVAILABLE`: transitions the journey back to `SEARCHING` (FR-009).
7. On `RATE_LIMITED` or `ERROR`: no journey state change; the caller
   decides whether/when to retry (existing `RateLimitError` /
   `AtlasSearchError`-equivalent pattern).

**Outputs**: The persisted `VerificationResult` (see data-model.md).

**Error conditions**:

| Condition | Behaviour |
|---|---|
| Journey's call budget already exhausted | Raises the existing `BudgetExhaustedError` before any HTTP call is made |
| `verify.do` returns HTTP 429 | Raises the existing `RateLimitError`, after persisting a `RATE_LIMITED` `VerificationResult` |
| Response body unparseable | Raises an error (mirroring `AtlasSearchError`), after persisting an `ERROR` `VerificationResult` with the raw bytes |
| Option's `routingIdentifier` cannot be found for `option_id` | Raises before any HTTP call — this is a caller error, not an Atlas condition |

## Operation: NeedsReverification

**Inputs**: `journey_id`, `now`, a configured safety margin (duration).

**Behaviour**: Reads the session `HeldIdentifier` row's `stale_at`. Returns
`true` if `stale_at - now <= safety_margin`; `false` otherwise. Makes no
Atlas call (see plan.md Performance Goals — this check must be evaluable
locally so it never itself consumes call budget).

**Outputs**: boolean.

**Error conditions**:

| Condition | Behaviour |
|---|---|
| No session `HeldIdentifier` exists for the journey (never verified, or already returned to `SEARCHING`) | Raises the existing `IdentifierNotFoundError` — asking "does this need re-verification" is meaningless before a first verification has happened |

---

## Relationship to FR-010

The orchestrator (out of scope for this feature) is expected to call
`NeedsReverification` before acting on a held, verified option, and call
`Verify` again if it returns `true` — rather than proceeding directly to
order creation on a session that is within the safety margin of its
documented expiry.
