# Quickstart: Flight Search Validation

## Prerequisites

```bash
cd backend
source .venv/bin/activate
export JOURNEY_DB_URL=sqlite:///./journey.db
# For Tier 2 (live sandbox) only:
export ATLAS_CLIENT_ID=<your-sandbox-client-id>
export ATLAS_CLIENT_SECRET=<your-sandbox-client-secret>
```

---

## Tier 1 — Recorded Tests (no network, runs on every push)

Uses the committed fixture `fixtures/atlas/sel_tyo_search.json` and VCR cassettes
recorded from a prior Tier 2 run.

```bash
pytest tests/unit/test_flight_option.py \
       tests/unit/test_flight_search_service.py \
       tests/integration/test_flight_search_persistence.py \
       -v
```

**Expected**: All unit and integration tests pass. No network calls made.

```bash
pytest tests/contract/test_flight_search_contract.py -v
```

**Expected**: VCR cassette replays Atlas `search.do` response; asserts 30 options returned,
`status == 0`, at least one carrier from `{7C, TW, ZE, LJ, RS, BX, ZG, MM}`.

---

## Tier 2 — Live Sandbox (requires credentials, run on demand)

```bash
pytest tests/contract/test_flight_search_contract.py \
       --record-mode=new_episodes \
       -v
```

**Expected**:
- HTTP 200 with `status: 0`
- `routings` array with ≥ 1 entry
- Each routing has non-empty `fid` and `routingIdentifier`
- `call_budget` on the test journey decremented by 1
- `search_records` table has one new row with `raw_response_json` populated

**Post-run**: Commit updated cassettes to `backend/fixtures/atlas/cassettes/flight_search/`.

---

## Validation Scenarios

### Scenario 1 — Successful search returns options

1. Create a journey with objective: origin `ICN`, destination `NRT`,
   departure `2026-09-05`, 1 adult, currency `USD`.
2. Call `FlightSearchService.search(journey_id, now=datetime.now(tz=utc))`.
3. Assert:
   - `result.option_count >= 1`
   - `result.no_options == False`
   - `result.carriers` is non-empty
   - All options have non-empty `fid` and `routing_identifier`
   - All options have `expire_at` not None
   - `journeys.call_budget` decremented by 1
   - `search_records` has 1 new row with `outcome == "SUCCESS"`
   - See [data-model.md](data-model.md) for full field list

### Scenario 2 — Empty result

1. Mock Atlas to return `{ "routings": [], "status": 0 }`.
2. Call `FlightSearchService.search(...)`.
3. Assert:
   - No exception raised
   - `result.option_count == 0`
   - `result.no_options == True`
   - Budget still decremented
   - `search_records` row with `outcome == "EMPTY"`

### Scenario 3 — Rate-limit rejection

1. Mock Atlas to return HTTP 429 with body `{ "retryAfter": 5 }`.
2. Call `FlightSearchService.search(...)`.
3. Assert:
   - `RateLimitError` raised with `retry_after_seconds == 5`
   - No second HTTP call made
   - Budget decremented (rejected call still counts)
   - Audit entry records the rate-limit event

### Scenario 4 — Multi-leg detection

1. Identify an option in the SEL→TYO fixture where `len(fromSegments) == 2`
   (both observed connecting options via Busan).
2. Assert `option.is_multi_leg == True`.
3. Assert `len(option.legs) == 2`.
4. Assert single-segment options have `is_multi_leg == False`.

### Scenario 5 — Budget exhaustion

1. Set `call_budget = 0` on the journey.
2. Call `FlightSearchService.search(...)`.
3. Assert `BudgetExhaustedError` raised; no HTTP call made.

---

## Reference

- Atlas search request/response schema: [`.antabay/atlas-capability-map.md`](../../.antabay/atlas-capability-map.md) §3–4
- Seed fixture: `backend/fixtures/atlas/sel_tyo_search.json`
- Data model: [data-model.md](data-model.md)
- Service contract: [contracts/flight-search.md](contracts/flight-search.md)
- Option/Leg/SearchResult contract: [contracts/flight-option.md](contracts/flight-option.md)
