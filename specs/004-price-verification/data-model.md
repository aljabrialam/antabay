# Data Model: Price Verification and Offer Staleness

## Entities

### VerificationResult

The persisted record of one call to `verify.do`. One row per attempt —
including re-verifications triggered by the safety margin (FR-010) — so
the audit trail (NFR-002) shows every attempt, not just the latest.

| Field | Type | Notes |
|---|---|---|
| `verification_id` | string (UUID) | Primary key |
| `journey_id` | string | FK → `journeys.journey_id` |
| `option_id` | string | FK → `flight_options.option_id` — the option verified |
| `requested_at` | datetime (ISO-8601 UTC) | |
| `responded_at` | datetime (ISO-8601 UTC) | |
| `raw_response_json` | text | Full, unmodified verify.do response body (NFR-002) |
| `status_code` | int | HTTP status |
| `atlas_status` | int \| null | Atlas's own `status` field; `null` only if the body was unparseable |
| `outcome` | enum | `VERIFIED` \| `PRICE_CHANGED` \| `UNAVAILABLE` \| `RATE_LIMITED` \| `ERROR` — see below |
| `session_id` | OpaqueId \| null | Set only when `outcome` is `VERIFIED` or `PRICE_CHANGED`; preserved unmodified (FR-005) |
| `max_seats` | int \| null | Set only when `outcome` is `VERIFIED` or `PRICE_CHANGED` (FR-008) |
| `price_change` | PriceChange \| null | Set only when the response includes a `priceChange` block |
| `passenger_requirements` | list[PassengerRequirementField] | Empty list is valid (edge case); recorded even when `outcome` is not a success, if present |
| `budget_before` | int | Journey call budget immediately before this call (FR-011) |
| `budget_after` | int | Journey call budget immediately after this call |

**`outcome` values**:

| Value | Meaning | Triggers |
|---|---|---|
| `VERIFIED` | `atlas_status == 0`, `priceChange.isPriceChange == false` (or `priceChange` absent) | Session freshness window begins (FR-006); journey may proceed |
| `PRICE_CHANGED` | `atlas_status == 0`, `priceChange.isPriceChange == true` | Same as `VERIFIED`, plus: any existing authorisation for the option is invalidated (FR-004) |
| `UNAVAILABLE` | `atlas_status != 0` and not a recognised price-change response (R3) | Journey returns to `SEARCHING` (FR-009) |
| `RATE_LIMITED` | HTTP 429 | No state change; caller retries after the declared interval (existing `RateLimitError` pattern, out of scope for the retry policy itself) |
| `ERROR` | Unparseable body or unexpected HTTP failure | No state change; distinguishable from `UNAVAILABLE` per the Edge Cases in spec.md |

**Validation rules**:
- `session_id`, `max_seats`, and `price_change` MUST be `null` unless `outcome` is `VERIFIED` or `PRICE_CHANGED`.
- `raw_response_json` MUST be persisted even when `outcome` is `RATE_LIMITED` or `ERROR` (NFR-002 does not carve out an exception for failure responses).
- The `routingIdentifier` sent in the request that produced this row MUST equal, byte-for-byte, the `routing_identifier` already stored on `flight_options` for `option_id` (FR-002).

### PriceChange

Mirrors the verify.do `priceChange` object exactly — no derived or computed fields.

| Field | Type |
|---|---|
| `is_price_change` | bool |
| `original_adult_price` | decimal |
| `new_adult_price` | decimal |
| `original_adult_tax` | decimal |
| `new_adult_tax` | decimal |
| `original_child_price` | decimal \| null |
| `new_child_price` | decimal \| null |
| `original_infant_price` | decimal \| null |
| `new_infant_price` | decimal \| null |

**Validation rule**: `is_price_change` is read directly from the response and is never computed by comparing `original_*` to `new_*` (FR-003) — the two are stored side by side for audit, not for the system's own determination.

### PassengerRequirementField

One entry per field the provider declares for this offer's booking. The set as a whole is `bookingRequirement.passenger` from the verify response.

| Field | Type |
|---|---|
| `field_name` | string (e.g. `name`, `birthday`, `cardNum`) |
| `type` | string |
| `required` | bool |
| `description` | string |
| `max_length` | int \| null |

**Validation rule**: The full set for a `VerificationResult` MUST be exactly what that response returned — no field added, removed, or defaulted from a prior verification or a fixed template (FR-007).

### Freshness Windows (reuses `HeldIdentifier`, spec 001 — no schema change)

Two rows, same table, distinguished by which identifier they hold:

| Row | `identifier_id` scope | Begins | `stale_after_seconds` source |
|---|---|---|---|
| Offer window | the option's `routingIdentifier` | at search | `expireTime` observed on the search response (existing behaviour, unchanged by this feature) |
| Session window | the verification's `sessionId` | at successful verify (`VERIFIED` or `PRICE_CHANGED`) | configured constant (R2) — Atlas does not return an explicit session expiry |

**Validation rule**: A session window row is created only on `VERIFIED`/`PRICE_CHANGED` outcomes; the offer window row is left as-is (not deleted) when the session window begins, preserving the audit trail of when each phase held (FR-006).

### JourneyState (extends spec 001's enum — one addition)

| Value | New? | Meaning |
|---|---|---|
| `VERIFIED` | **Yes** | A verify has succeeded (with or without a reported price change) for the journey's currently held option |

**New allowed transitions**:

| From | To | Trigger |
|---|---|---|
| `SEARCHING` | `VERIFIED` | `outcome` is `VERIFIED` or `PRICE_CHANGED` |
| `VERIFIED` | `SEARCHING` | `outcome` is `UNAVAILABLE` (FR-009) |

`VERIFIED` also inherits the existing `→ CANCELLED` and `→ ABANDONED` terminal transitions available to every non-terminal state.

**Not a transition**: a re-verification (FR-010) performed while already `VERIFIED` that itself succeeds does not change state — it only refreshes the session `HeldIdentifier` row's `issued_at`/`stale_at`.

## Relationships

```text
journeys (1) ──< verifications (many)
flight_options (1) ──< verifications (many)   -- re-verification = multiple rows, same option_id
verifications (1) ── PriceChange (0..1)        -- embedded/serialised, not a separate table
verifications (1) ──< PassengerRequirementField (many)  -- embedded/serialised, not a separate table
journeys (1) ──< held_identifiers (many)       -- existing relationship, reused for both windows
```

`PriceChange` and the `PassengerRequirementField` list are stored serialised within the `verifications` row (e.g. as part of the persisted response structure), not as separate tables — they have no independent lifecycle or query pattern of their own; they are always read alongside their owning `VerificationResult`.

## Safety Margin

Not a persisted entity — a configuration value (a duration) supplied to the re-verification check (FR-010, NFR-001). The check itself is a pure function of `now`, the session `HeldIdentifier.stale_at`, and this configured margin; it requires no additional Atlas call to evaluate (see plan.md Performance Goals).
