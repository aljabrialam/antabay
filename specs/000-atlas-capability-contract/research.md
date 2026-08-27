# Research: Atlas Capability Contract

**Feature**: 000-atlas-capability-contract
**Date**: 2026-08-28

All technical questions resolved from the verified capability map
(`.antabay/atlas-capability-map.md`, verified 2026-08-15), the Antabay
architecture document (`.antabay/architecture.md`), and the constitution.
No live searches were required — all decisions are grounded in observed
sandbox data.

---

## Decision 1: Schema enforcement mechanism

**Decision**: Pydantic v2 models with `extra = "forbid"` as the schema
representation; Mypy strict mode as the build-time enforcement gate.

**Rationale**:
- Pydantic `extra = "forbid"` causes a `ValidationError` if any field not
  declared in the model is present in the parsed input, and raises a `TypeError`
  at model construction time if a required field is absent. This satisfies
  FR-003 (typed shapes) and partially satisfies FR-002 (unverified fields
  rejected).
- Mypy strict mode (`--strict`) rejects attribute access on types that do
  not declare the attribute. Combined with Pydantic's generated stubs, any
  attempt to read `routing.fareCode` (not declared) produces a Mypy error at
  CI time, satisfying NFR-001 (build failure, not runtime failure).
- Pydantic is already the idiomatic schema library for Python/FastAPI
  projects; no new dependency class is introduced.

**Alternatives considered**:
- *dataclasses + manual validation*: Does not give Mypy the attribute map
  needed for static field-access checks. Rejected.
- *TypedDict*: Gives Mypy attribute checking but no runtime validation and no
  `extra = "forbid"` equivalent. Rejected.
- *JSON Schema / jsonschema library*: Runtime only; does not satisfy NFR-001.
  Rejected.

---

## Decision 2: Opaque identifier representation

**Decision**: A `NewType`-derived or single-field frozen dataclass wrapper
`OpaqueId` that carries the raw string but exposes no string manipulation
methods and provides no constructor from components.

**Rationale**:
- Atlas identifiers (`routingIdentifier`, `sessionId`, `orderNo`, `fid`) are
  opaque by the API's own documentation. The observed format of
  `routingIdentifier` is a large base64-encoded blob; `orderNo` includes a
  date and sequence but must never be parsed.
- A wrapper type satisfies FR-004: no slice, split, concatenate, or format
  method is available. The only operations are equality comparison and
  passthrough to the HTTP client.
- `NewType` is the lightest option but does not prevent string operations
  (Mypy does not block `str` methods on a `NewType("OpaqueId", str)`).
  A frozen dataclass with a single `_value: str` field and no `__str__`
  passthrough is therefore preferred.

**Alternatives considered**:
- *Plain `str`*: Does not make construction/mutation structurally impossible.
  Rejected.
- *`NewType`*: Mypy treats it as `str` for method calls. Insufficient.
  Rejected.

---

## Decision 3: Canonical price implementation

**Decision**: A module-level function `canonical_total_price(adult_price,
adult_tax, transaction_fee)` in `backend/atlas/pricing.py`. No other
arithmetic involving these three fields is permitted anywhere in the codebase.
The Mypy-enforced import structure (only `pricing.py` imports the price fields)
backs this up; a linting rule (ruff custom rule or a simple grep-based CI
check) fails the build if the three field names are added together outside
this module.

**Rationale**:
- Formula confirmed in capability map section 5:
  `total_per_adult = adultPrice + adultTax + transactionFeePerPax`
- Confirmed by observed values: 66.43 + 23.96 + 0.00 = 90.39 USD (ZE605).
- Centralising the formula prevents drift. The grep/ruff check enforces FR-005
  at build time.

**Alternatives considered**:
- *Inline arithmetic in each caller*: Violates FR-005 directly. Rejected.
- *Class method on `Routing`*: Couples pricing to the search model; pricing
  is also needed post-verify and post-order. Rejected.

---

## Decision 4: Error classification table

**Decision**: An `ErrorCode` enum and a `CLASSIFICATION` dict in
`backend/atlas/errors.py`. Verified codes from the capability map:
`0` (success), `318` (reconcilable — duplicate), `800` (terminal — bad state),
`900` (terminal — auth). Unknown codes default to `terminal`.

**Rationale**:
- The classification is static and fully determined by the capability map.
  An enum + dict is the simplest structure that satisfies FR-007 and FR-008
  and is inspectable in tests without live API calls.
- `318` is handled specially: the `ReconcilableError` return value includes
  the `duplicate_orders` list from the response (FR-008).

**Alternatives considered**:
- *Exception hierarchy*: Overcomplicates a lookup table. Rejected.
- *String constants*: Not type-safe; Mypy cannot exhaustiveness-check them.
  Rejected.

---

## Decision 5: Call budget and rate-limit enforcement

**Decision**: A `CallBudget` class in `backend/atlas/budget.py` that tracks
per-journey, per-endpoint call counts against declared limits, and a
`RateLimitHold` state that records the `retryAfter` timestamp (defaulting to
`None` for indefinite hold when absent).

**Rationale**:
- Observed rate limits (capability map section 6): `search.do` 10 QPS;
  `verify.do` + `getOffers.do` share 60 QPM; `seatAvailability.do` +
  `getLuggage.do` share 60 QPM.
- The budget is checked before every call, not after. A refused call is
  recorded (FR-010) and a `BudgetExhausted` error raised.
- `retryAfter` absence → indefinite hold satisfies FR-011's edge case.

**Alternatives considered**:
- *Decorator-based rate limiter*: Implies retry loops. Constitution VII and
  FR-011 prohibit retry loops. Rejected.
- *External rate-limit library*: Introduces third-party dependency with its
  own retry semantics. Rejected.

---

## Decision 6: Freshness window representation

**Decision**: A `FreshnessWindow` dataclass in `backend/atlas/freshness.py`
with `issued_at: datetime`, `expires_at: datetime | None`, and a `clock_type`
discriminator (`offer | session | ticket`). Three factory functions derive
instances from the three observed clocks.

**Rationale**:
- Three distinct clocks (capability map section 7b):
  - Offer: `expireTime` (ISO8601) — observed 7m43s to 31m, may arrive
    pre-aged
  - Session: `sessionId` window (~2h, no explicit field in response)
  - Ticket: `tktLimitTime` (observed 30m)
- `refreshTime` and `expireTime` are `null` in the verify response; the
  factory handles this by using the documented session TTL as a conservative
  bound.
- `expires_at = None` signals an unknown expiry (e.g. session clock when no
  explicit timestamp is present); callers must treat this as "expiry unknown,
  proceed with caution".

**Alternatives considered**:
- *Single `expires_at` field without clock type*: Loses the three-clock
  semantics required for the journey state machine. Rejected.

---

## Decision 7: `orderStatus` normalisation

**Decision**: Ingest-time normalisation in `backend/atlas/models/webhook.py`
and `backend/atlas/models/query.py`. Both surfaces produce `OrderStatus`
(an `IntEnum`) after parsing. The REST surface casts the string `"1"` to
`int`; the webhook surface receives the integer `2` directly.

**Rationale**:
- Observed divergence (capability map section 7c): webhook delivers integer
  `2`; `queryOrderDetails.do` delivers string `"1"`. Downstream state machine
  code must never branch on raw type — only on the normalised `OrderStatus`
  value.
- `IntEnum` is the natural Python type: it compares as an integer, prints as
  a name, and Mypy rejects comparisons with bare strings.
- Partial known mapping: `1` = paid/not-ticketed, `2` = ticketed. Unknown
  values are preserved as their integer representation (not rejected) so that
  future Atlas enum additions do not crash the receiver.

**Alternatives considered**:
- *String normalisation (cast integer to string)*: Makes future comparisons
  error-prone. Rejected.
- *Ignore the divergence, let callers handle it*: Violates FR-006. Rejected.

---

## Decision 8: Fixture management

**Decision**: `pytest-recording` (VCR.py-compatible cassettes) stored under
`fixtures/atlas/cassettes/`. Existing raw JSON responses in
`fixtures/atlas/*.json` are the seeds; cassettes are generated by running
the Tier 2 test suite once against the live sandbox and then committed.

**Rationale**:
- Three verified raw fixtures already exist:
  `sel_tyo_search.json`, `sel_tyo_verify.json`,
  `webhook_order_ticketed.json`.
- `pytest-recording` in `--record-mode=none` (CI default) replays cassettes
  without live calls, satisfying SC-007 (no live sandbox connection needed
  in CI). `--record-mode=new_episodes` triggers Tier 2 capture.
- Handwritten fixtures are prohibited by NFR-003 and constitution XI.

**Alternatives considered**:
- *responses / httpretty mocking*: Requires maintaining mock data manually.
  Prohibited. Rejected.
- *Live calls in CI*: Consumes sandbox balance, hits rate limits. Rejected.
