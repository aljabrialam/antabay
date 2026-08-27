# Data Model: Flight Search

## Traceability Matrix

| Requirement | Entity / Field | Test |
|-------------|---------------|------|
| FR-001 | `SearchRequest.from_city`, `to_city`, `from_date`, `adult_num`, `currency` | `test_flight_search_service.py::test_search_params_from_objective` |
| FR-002 | `SearchRequest.currency` from `TravelObjective.budget_currency` | `test_flight_search_service.py::test_currency_from_objective` |
| FR-003 | `FlightOption.fid`, `routing_identifier` (TEXT NOT NULL, verbatim) | `test_flight_option.py::test_identifiers_preserved_verbatim` |
| FR-004 | `FlightOption.refreshed_at`, `expire_at` | `test_flight_option.py::test_freshness_timestamps_recorded` |
| FR-005 | `FlightOption.remaining_seconds(now)` computed from `expire_at - now` | `test_flight_option.py::test_remaining_seconds_uses_now_not_receipt` |
| FR-006 | `SearchResult.option_count`, `carriers` | `test_flight_search_service.py::test_result_summary_fields` |
| FR-007 | `FlightOption.is_multi_leg` = `len(legs) > 1` | `test_flight_option.py::test_multi_leg_detection` |
| FR-008 | `Leg.seat_count`, `Leg.risk_sellout` | `test_flight_option.py::test_scarcity_fields_recorded` |
| FR-009 | `JourneyRecord.call_budget` decremented atomically | `test_flight_search_service.py::test_budget_decremented` |
| FR-010 | `SearchResult.no_options = True` when `option_count == 0` | `test_flight_search_service.py::test_empty_result_no_exception` |
| FR-011 | No field augmentation; all values traced to raw response | `test_flight_option.py::test_no_field_enrichment` |
| NFR-001 | `SearchRecord.raw_response_json` written before mapping | `test_flight_search_persistence.py::test_raw_response_persisted` |
| NFR-002 | `RateLimitError` raised on 429; no retry before `retryAfter` | `test_flight_search_service.py::test_rate_limit_no_retry` |

---

## Entities

### SearchRequest

Parameters sent to Atlas `search.do`. Derived from `TravelObjective`; never authored.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `journey_id` | `str` | `JourneyRecord.journey_id` | Links result to journey |
| `from_city` | `str` | `TravelObjective.origin.value` | IATA city code |
| `to_city` | `str` | `TravelObjective.destination.value` | IATA city code |
| `from_date` | `str` | `TravelObjective.departure_date.value` | `YYYYMMDD` format required by Atlas — **requires `departure_date` field added to `TravelObjective` in Feature 002 (see Schema Changes)** |
| `adult_num` | `int` | `TravelObjective.pax_count.value` | `adultNum` in Atlas request |
| `currency` | `str` | `TravelObjective.budget_currency.value` | e.g. `"USD"` |
| `trip_type` | `str` | constant `"1"` | One-way only for this feature |

**Validation rules**:
- `from_city`, `to_city` must be non-empty strings
- `adult_num` must be ≥ 1
- `from_date` must match `YYYYMMDD` pattern

---

### FlightOption

One routing returned by Atlas `search.do`. All fields mapped directly from the provider
response; no inference or enrichment.

| Field | Type | Atlas source field | Notes |
|-------|------|-------------------|-------|
| `option_id` | `str` | generated UUID | Local identity only |
| `journey_id` | `str` | FK → `journeys` | |
| `search_record_id` | `str` | FK → `search_records` | |
| `fid` | `str` | `fid` | Preserved byte-for-byte |
| `routing_identifier` | `str` | `routingIdentifier` | Preserved byte-for-byte |
| `currency` | `str` | `currency` | As returned |
| `adult_price` | `Decimal` | `adultPrice` | |
| `adult_tax` | `Decimal` | `adultTax` | |
| `transaction_fee` | `Decimal` | `transactionFeePerPax` | |
| `refreshed_at` | `datetime` | `refreshTime` (ISO8601) | UTC |
| `expire_at` | `datetime` | `expireTime` (ISO8601) | UTC; authoritative freshness |
| `is_multi_leg` | `bool` | `len(fromSegments) > 1` | No inference |
| `separate_bookings` | `bool` | `separateBookings` | Recorded for downstream use |
| `legs` | `list[Leg]` | `fromSegments[]` | |
| `recorded_at` | `datetime` | injected `now` | When option was recorded by system |

**Computed (not persisted)**:
- `remaining_seconds(now: datetime) -> float` = `(expire_at - now).total_seconds()`
  — `now` always injected by caller, never read internally

**Validation rules**:
- `fid` and `routing_identifier` must be non-empty; option dropped if either is absent
- `expire_at` must be parseable ISO8601; if missing, option recorded with `expire_at=None`
  and flagged in audit trail

---

### Leg

A single flight segment within a `FlightOption`. All fields from `fromSegments[]` entry.

| Field | Type | Atlas source field | Notes |
|-------|------|-------------------|-------|
| `leg_id` | `str` | generated UUID | |
| `option_id` | `str` | FK → `flight_options` | |
| `segment_index` | `int` | `segmentIndex` | Ordering within option |
| `carrier` | `str` | `carrier` | IATA carrier code |
| `flight_number` | `str` | `flightNumber` | |
| `dep_airport` | `str` | `depAirport` | IATA airport code |
| `dep_time` | `str` | `depTime` | `YYYYMMDDHHMM` local airport time |
| `arr_airport` | `str` | `arrAirport` | IATA airport code |
| `arr_time` | `str` | `arrTime` | `YYYYMMDDHHMM` local airport time |
| `duration_minutes` | `int` | `duration` | |
| `stop_cities` | `str` | `stopCities` | comma-separated or empty |
| `cabin_class` | `str` | `cabinClass` | |
| `seat_count` | `int` | `seatCount` | Scarcity signal |
| `risk_sellout` | `bool` | `riskSellout` | Provider's sell-out risk flag |
| `code_share` | `bool` | `codeShare` | |
| `aircraft_code` | `str` | `aircraftCode` | |
| `fare_family` | `str` | `fareFamily` | May be null |

---

### SearchRecord

Audit record for one invocation of `search.do`. Written atomically with the
`FlightOption` records.

| Field | Type | Notes |
|-------|------|-------|
| `search_id` | `str` | UUID |
| `journey_id` | `str` | FK → `journeys` |
| `requested_at` | `datetime` | UTC; when the HTTP request was sent |
| `responded_at` | `datetime` | UTC; when the raw response was received |
| `raw_response_json` | `str` | Full Atlas response, verbatim |
| `status_code` | `int` | HTTP status code |
| `atlas_status` | `int` | `response.status` field (0 = success) |
| `option_count` | `int` | Number of valid `FlightOption` records produced |
| `budget_before` | `int` | `call_budget` before decrement |
| `budget_after` | `int` | `call_budget` after decrement |
| `outcome` | `str` | enum: `SUCCESS`, `EMPTY`, `RATE_LIMITED`, `ERROR` |

---

### SearchResult

In-memory value object returned by `FlightSearchService.search()`. Not persisted directly
(the `SearchRecord` and `FlightOption` rows are the durable form).

| Field | Type | Notes |
|-------|------|-------|
| `search_id` | `str` | FK to `SearchRecord` |
| `option_count` | `int` | |
| `no_options` | `bool` | `True` when `option_count == 0` |
| `carriers` | `list[str]` | Unique carrier codes across all options |
| `options` | `list[FlightOption]` | |

---

## Schema Changes to Existing Tables

### `journeys` table — new column

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `call_budget` | `INTEGER NOT NULL` | `20` | Decremented per search; enforced atomically |

Migration: `backend/journey/migrations/versions/XXXX_add_call_budget_to_journeys.py`

### `TravelObjective` model — new field (Feature 001 extension)

`TravelObjective` must gain a `departure_date: ConstrainedField[str] | None` field.
Atlas requires a `fromDate` (`YYYYMMDD`) which is the **departure date**, distinct from
`latest_arrival` (the deadline). A search without a departure date cannot be submitted.

This field is added to:
- `backend/journey/models/objective.py` — `TravelObjective` dataclass
- The `ObjectiveParser` DashScope prompt schema (`_build_tool_schema`)
- The `_OBJECTIVE_FIELDS` list in `objective_parser.py`

Migration: no DB column change required — the objective is stored as JSON in
`journeys.objective_json`; the new field will be present in new journeys and absent
(treated as `None`) in existing ones.

### Search currency resolution rule

When `TravelObjective.budget_currency` is `None`, the search request uses `"USD"` as
the default currency (Atlas sandbox requires it and it is the only observed sandbox
currency). This default is recorded in the `SearchRecord` so it is auditable. A future
feature may make this configurable.

---

## New Tables

### `search_records`

```
search_id TEXT PK
journey_id TEXT NOT NULL REFERENCES journeys(journey_id)
requested_at TEXT NOT NULL
responded_at TEXT NOT NULL
raw_response_json TEXT NOT NULL
status_code INTEGER NOT NULL
atlas_status INTEGER NOT NULL
option_count INTEGER NOT NULL
budget_before INTEGER NOT NULL
budget_after INTEGER NOT NULL
outcome TEXT NOT NULL
```

### `flight_options`

```
option_id TEXT PK
journey_id TEXT NOT NULL REFERENCES journeys(journey_id)
search_record_id TEXT NOT NULL REFERENCES search_records(search_id)
fid TEXT NOT NULL
routing_identifier TEXT NOT NULL
currency TEXT NOT NULL
adult_price TEXT NOT NULL          -- stored as TEXT to preserve Decimal precision
adult_tax TEXT NOT NULL
transaction_fee TEXT NOT NULL
refreshed_at TEXT                  -- nullable: may be absent
expire_at TEXT                     -- nullable: may be absent
is_multi_leg INTEGER NOT NULL      -- 0/1
separate_bookings INTEGER NOT NULL -- 0/1
recorded_at TEXT NOT NULL
```

### `legs`

```
leg_id TEXT PK
option_id TEXT NOT NULL REFERENCES flight_options(option_id)
segment_index INTEGER NOT NULL
carrier TEXT NOT NULL
flight_number TEXT NOT NULL
dep_airport TEXT NOT NULL
dep_time TEXT NOT NULL
arr_airport TEXT NOT NULL
arr_time TEXT NOT NULL
duration_minutes INTEGER NOT NULL
stop_cities TEXT NOT NULL          -- empty string if none
cabin_class TEXT NOT NULL
seat_count INTEGER NOT NULL
risk_sellout INTEGER NOT NULL      -- 0/1
code_share INTEGER NOT NULL        -- 0/1
aircraft_code TEXT NOT NULL
fare_family TEXT                   -- nullable
```
