# Contract: Flight Search Service

## Service: `FlightSearchService`

**Module**: `backend/journey/services/flight_search.py`

---

### Method: `search(journey_id, now) -> SearchResult`

Submits a one-way search to Atlas `search.do` using the confirmed objective from the
journey record, persists the raw response and all mapped options, decrements the call
budget, appends an audit entry, and returns a `SearchResult`.

**Pre-conditions**:
- `journey_id` must reference an existing `JourneyRecord` in state `OBJECTIVE_CONFIRMED`
  or `SEARCHING`
- The journey's `call_budget` must be > 0
- The journey's confirmed objective must have non-null `origin`, `destination`,
  `pax_count`, and (optionally) `budget_currency`

**Post-conditions**:
- A `SearchRecord` row is written with the full raw response in a **separate, committed
  transaction before option mapping begins** — a mapping failure does not roll back the
  raw record (NFR-001)
- Zero or more `FlightOption` + `Leg` rows are written in a second transaction
- `journeys.call_budget` is decremented atomically in the same transaction as the
  `SearchRecord` write
- An audit entry of type `OBSERVATION` is appended to the journey audit trail in the
  same transaction as the `SearchRecord` write
- A `SearchResult` is returned

**Raises**:
- `JourneyNotFoundError` — journey_id does not exist
- `BudgetExhaustedError` — `call_budget` is already 0
- `RateLimitError(retry_after_seconds: int)` — Atlas returned 429; no retry has occurred
- `AtlasSearchError(status_code, atlas_status, message)` — non-zero `atlas_status` or
  non-2xx HTTP response that is not a rate limit

**Signature**:

```python
def search(self, journey_id: str, now: datetime) -> SearchResult
```

`now` is always injected by the caller; never read from the system clock inside this method.

---

### Method: `get_options(journey_id, search_id) -> list[FlightOption]`

Returns all `FlightOption` records for a given search invocation.

**Raises**: `SearchRecordNotFoundError` if `search_id` does not exist for the journey.

**Signature**:

```python
def get_options(self, journey_id: str, search_id: str) -> list[FlightOption]
```

---

## Errors

| Exception | When raised |
|-----------|-------------|
| `JourneyNotFoundError` | `journey_id` not in DB |
| `BudgetExhaustedError` | `call_budget == 0` before submission |
| `RateLimitError` | HTTP 429; carries `retry_after_seconds` |
| `AtlasSearchError` | Non-zero `atlas_status` or unexpected HTTP error |
| `SearchRecordNotFoundError` | `search_id` not found for journey |
