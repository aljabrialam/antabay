# Research: Flight Search

## Decision 1 — HTTP Client

**Decision**: Use `httpx` (synchronous mode) for Atlas `search.do` calls.

**Rationale**: Already a declared dependency in `backend/pyproject.toml`. Synchronous mode
matches the rest of the Feature 001 service layer (no async event loop). The Feature 001
pattern uses plain function calls; introducing async here would require threading through
the entire call stack for no gain at this scope.

**Alternatives considered**:
- `requests` — not in the dependency tree; no advantage over httpx.
- `httpx` async — adds complexity without benefit at current scale.

---

## Decision 2 — Raw Response Persistence Format

**Decision**: Persist raw Atlas response as a JSON string column in a `search_records` table,
written in the same SQLAlchemy transaction that writes `flight_options`.

**Rationale**:
- NFR-001 requires the raw response to be persisted before any processing. A single
  transaction guarantees atomicity: if processing fails, the raw record is still committed
  on rollback of the outer work, or both succeed together if wrapped correctly.
- Storing as a JSON string (not a separate file) keeps the entire journey record in one
  store, consistent with Constitution VI (state outside the agent, in durable storage).
- The existing `fixtures/atlas/sel_tyo_search.json` already captures the seed response
  shape; the persisted format mirrors it exactly.

**Alternatives considered**:
- File system storage — breaks the "single durable store" principle; harder to query.
- Separate SQLite table per response — that is what `search_records` is; no change needed.

---

## Decision 3 — Remaining Usable Time Computation

**Decision**: Compute `remaining_seconds = (expire_at - now).total_seconds()` at the
moment `FlightOption` is constructed, where `now` is injected by the caller (never read
internally), matching the Feature 001 pattern for `HeldIdentifier.is_stale(now)`.

**Rationale**:
- FR-005 requires remaining time to be computed from current clock, not from receipt.
  Injecting `now` keeps the computation deterministic and testable (no internal clock reads).
- Atlas observed data: one offer had 14 minutes left at time of receipt (Section 6 of
  capability map). The delta between receipt and processing can be non-trivial.

**Alternatives considered**:
- Computing from `refreshTime` — wrong; FR-005 explicitly requires current clock.
- Storing as a float column — redundant; derivable from `expire_at` and `now` at any time.

---

## Decision 4 — Rate-Limit Enforcement

**Decision**: `FlightSearchService` tracks the timestamp of its last successful `search.do`
call. Before each call it enforces a minimum inter-call gap of 100ms (= 10 QPS). On a 429
response, it reads `retryAfter` from the response body and raises a `RateLimitError`
carrying the interval; it does NOT sleep or retry internally.

**Rationale**:
- Constitution VII: rate limits are design constraints, not error conditions. The service
  layer should surface the constraint, not hide it.
- The caller (agent loop) decides whether to wait; the service must not block the event loop
  with an arbitrary sleep.
- Raising `RateLimitError` with the interval lets the caller record it in the audit trail
  and schedule a retry at the right time.

**Alternatives considered**:
- Internal sleep + retry — violates "no arbitrary sleeps" (Constitution XIII) and hides
  the rate-limit event from the audit trail.
- Leaky-bucket token counter — correct but over-engineered; a simple last-call timestamp
  suffices for 10 QPS.

---

## Decision 5 — Multi-Leg Detection

**Decision**: `is_multi_leg = len(fromSegments) > 1`. No inference or enrichment.

**Rationale**:
- FR-007 requires distinguishing single-leg from multi-leg; the capability map (Section 4)
  confirms `fromSegments` length is the signal. The two observed connecting options both
  had `len(fromSegments) == 2`.
- Retaining all `fromSegments` as `Leg` records preserves the raw data per FR-011.

---

## Decision 6 — Call Budget Storage

**Decision**: Add a `call_budget` integer column to the `journeys` table via Alembic
migration. `FlightSearchService` decrements it atomically (UPDATE with a WHERE clause
checking `call_budget > 0`). Initial value is set at journey creation (Feature 001 creates
the journey; a sensible default is 20 searches per journey).

**Rationale**:
- FR-009 requires every search to be counted against the journey's call budget.
- An atomic UPDATE prevents races if two agents query simultaneously.
- Feature 001's `JourneyRecord` already has the journey in SQLite; adding a column is the
  minimal change.

**Alternatives considered**:
- Counting via audit trail entries — readable but requires a COUNT query for enforcement,
  which is not atomic.
- Separate budget table — unnecessary indirection.

---

## Decision 7 — Identifier Preservation

**Decision**: `fid` and `routingIdentifier` are stored as `TEXT NOT NULL` columns with no
normalisation, trimming, or encoding. They are read from the response and written verbatim.

**Rationale**: Constitution I and FR-003 are unambiguous. Any transformation — even
whitespace trimming — violates the byte-for-byte requirement. The storage layer uses raw
string assignment with no Python str methods applied to these fields.

---

## Decision 8 — Options with Missing Required Identifiers

**Decision**: Any routing missing `fid` or `routingIdentifier` is dropped from
`FlightOption` records. The omission is logged as an audit entry on the journey. The
`SearchResult` reflects only valid options.

**Rationale**: An option without its action identifier cannot be acted on. Recording it
would create a phantom option that silently fails at verify time. Dropping it at ingest
is safer and auditable.

---

## Decision 9 — Currency Scope

**Decision**: The search request always sends `currency` from the confirmed objective.
Fares are returned in whatever currency Atlas uses (USD in sandbox). The currency field
is recorded as-is on each `FlightOption`; no conversion is performed.

**Rationale**: FR-002 requires the request to use the objective's currency. FR-011
prohibits modifying returned data. The capability map (Section 6) warns explicitly about
the currency mixing hazard; the correct response is to record faithfully and let downstream
features handle conversion with explicit rates.
