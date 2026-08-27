# Contract: Flight Option Model

## Dataclass: `FlightOption`

**Module**: `backend/journey/models/flight.py`

---

### Fields

| Field | Type | Nullable | Invariant |
|-------|------|----------|-----------|
| `option_id` | `str` | No | UUID assigned at creation |
| `journey_id` | `str` | No | FK to `JourneyRecord` |
| `search_record_id` | `str` | No | FK to `SearchRecord` |
| `fid` | `str` | No | Non-empty; preserved byte-for-byte from Atlas |
| `routing_identifier` | `str` | No | Non-empty; preserved byte-for-byte from Atlas |
| `currency` | `str` | No | As returned by Atlas |
| `adult_price` | `Decimal` | No | |
| `adult_tax` | `Decimal` | No | |
| `transaction_fee` | `Decimal` | No | |
| `refreshed_at` | `datetime \| None` | Yes | UTC; None if absent in response |
| `expire_at` | `datetime \| None` | Yes | UTC; None if absent in response |
| `is_multi_leg` | `bool` | No | `True` iff `len(legs) > 1` |
| `separate_bookings` | `bool` | No | From Atlas `separateBookings` |
| `legs` | `list[Leg]` | No | At least 1 entry |
| `recorded_at` | `datetime` | No | Injected `now`; never system clock |

---

### Method: `remaining_seconds(now: datetime) -> float`

Returns `(expire_at - now).total_seconds()`. Result may be negative if the option has
already expired.

**Pre-condition**: `expire_at` is not `None`. Raises `ValueError` if `expire_at is None`.

**`now` is always injected by the caller. This method MUST NOT read the system clock.**

---

### Method: `is_expired(now: datetime) -> bool`

Returns `True` when `remaining_seconds(now) <= 0`.

---

## Dataclass: `Leg`

| Field | Type | Nullable |
|-------|------|----------|
| `leg_id` | `str` | No |
| `option_id` | `str` | No |
| `segment_index` | `int` | No |
| `carrier` | `str` | No |
| `flight_number` | `str` | No |
| `dep_airport` | `str` | No |
| `dep_time` | `str` | No | `YYYYMMDDHHMM` local |
| `arr_airport` | `str` | No |
| `arr_time` | `str` | No | `YYYYMMDDHHMM` local |
| `duration_minutes` | `int` | No |
| `stop_cities` | `str` | No | Empty string if none |
| `cabin_class` | `str` | No |
| `seat_count` | `int` | No |
| `risk_sellout` | `bool` | No |
| `code_share` | `bool` | No |
| `aircraft_code` | `str` | No |
| `fare_family` | `str \| None` | Yes |

---

## Dataclass: `SearchResult`

| Field | Type | Notes |
|-------|------|-------|
| `search_id` | `str` | FK to `SearchRecord` |
| `option_count` | `int` | Number of valid options |
| `no_options` | `bool` | `True` when `option_count == 0` |
| `carriers` | `list[str]` | Unique carrier codes; derived from legs |
| `options` | `list[FlightOption]` | |

---

## Dataclass: `SearchRecord`

| Field | Type | Notes |
|-------|------|-------|
| `search_id` | `str` | UUID |
| `journey_id` | `str` | |
| `requested_at` | `datetime` | UTC |
| `responded_at` | `datetime` | UTC |
| `raw_response_json` | `str` | Verbatim Atlas response |
| `status_code` | `int` | HTTP status |
| `atlas_status` | `int` | Atlas `status` field |
| `option_count` | `int` | |
| `budget_before` | `int` | |
| `budget_after` | `int` | |
| `outcome` | `SearchOutcome` | enum: SUCCESS, EMPTY, RATE_LIMITED, ERROR |
