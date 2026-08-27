# Feature Specification: Flight Search

**Feature Branch**: `002-flight-search`

**Created**: 2026-08-28

**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Search for Flights from a Confirmed Objective (Priority: P1)

The agent holds a confirmed journey with origin, destination, departure date, and traveller count.
It submits a search to the external provider using exactly those values and the objective's
currency. The provider returns a set of options. The system records each option in full,
capturing the identifier needed to act on it, the pricing timestamp, the expiry time, the
leg structure, and the scarcity signals. The search is debited against the journey's call budget.

**Why this priority**: Everything else — filtering, scoring, verification, booking — depends on
having real options in hand. Without a successful search there is nothing downstream to act on.

**Independent Test**: Given a confirmed journey (SIN → LHR, 2026-09-05, 1 adult, USD), call
search; assert at least one option is recorded with a non-empty `fid`, a non-null `expire_at`,
a `refreshed_at` timestamp, a `legs` list, and `seat_count`/`risk_sellout` captured. Assert
the journey's call budget is decremented by 1.

**Acceptance Scenarios**:

1. **Given** a confirmed journey with origin `ICN`, destination `NRT`, date `2026-09-05`,
   1 adult, currency `USD`,
   **When** the agent triggers a search,
   **Then** the system submits a request containing `fromCity=ICN`, `toCity=NRT`,
   `fromDate=20260905`, `adultNum=1`, `currency=USD`, and returns a `SearchResult` with
   `option_count ≥ 1` and `carriers` listing at least one carrier code.

2. **Given** a successful search returning 30 options,
   **When** the result is recorded,
   **Then** every option has `fid` preserved byte-for-byte, `expire_at` set from the
   provider's `expireTime`, `refreshed_at` set from `refreshTime`, `is_multi_leg` correct
   for each, and `seat_count` and `risk_sellout` recorded per leg.

3. **Given** a search is triggered,
   **When** the provider returns a response,
   **Then** the full raw response is persisted to durable storage before any further
   processing occurs.

4. **Given** the journey has a call budget of N,
   **When** a search completes (success or empty result),
   **Then** the remaining call budget is N − 1.

---

### User Story 2 — Handle Empty and No-Option Results (Priority: P2)

The provider may return a valid response containing zero options (no flights match the
requested parameters). The system must handle this without error, record the outcome, and
report clearly that no options were found.

**Why this priority**: An empty result is operationally distinct from an error. The agent
must be able to report "no flights found" to the traveller and decide whether to adjust
parameters, rather than treating silence as a failure.

**Independent Test**: Given a confirmed journey for a route that returns zero routings, call
search; assert the system completes without exception, records `option_count = 0`, and the
`SearchResult` carries a `no_options` flag or equivalent indicator.

**Acceptance Scenarios**:

1. **Given** the provider returns `{ "routings": [], "status": 0 }`,
   **When** the system processes the response,
   **Then** it returns a `SearchResult` with `option_count = 0` and no error is raised.

2. **Given** an empty-result search,
   **When** the call budget is checked,
   **Then** the budget is still decremented — an empty result is still a billable search.

---

### User Story 3 — Respect Rate Limits and Call Budget (Priority: P2)

The provider enforces a request rate limit on `search.do`. If the system exceeds it, the
provider returns a rate-limit rejection with a retry interval. The system must honour that
interval and must not submit a retry before it has elapsed. The journey's call budget caps
the total number of searches.

**Why this priority**: Rate-limit violations degrade the shared provider account and may
result in suspension. Call budget enforcement prevents runaway search loops.

**Independent Test**: Simulate a rate-limit rejection (HTTP 429 with `retryAfter`); assert
the system does not retry before the specified interval; assert the budget is still
decremented for the rejected call.

**Acceptance Scenarios**:

1. **Given** the provider returns HTTP 429 with `retryAfter: 5`,
   **When** the system receives the rejection,
   **Then** no retry is issued before 5 seconds have elapsed, and the outcome is recorded
   in the audit trail.

2. **Given** the journey's call budget has reached zero,
   **When** a search is requested,
   **Then** the system refuses to submit the request and reports that the call budget is
   exhausted.

---

### Edge Cases

- What happens when the provider returns `status ≠ 0` with HTTP 200? The system treats a
  non-zero `status` field as a failure regardless of the HTTP status code.
- What if `expireTime` is already in the past when the response arrives? The option is
  recorded with its `expire_at` timestamp and immediately flagged as expired; remaining
  usable time is zero or negative.
- What if `refreshTime` or `expireTime` is missing from an option? The option is recorded
  with `null` for the missing field and surfaced as incomplete in the audit trail.
- What if the provider returns options in a currency different from the one requested?
  The currency field is recorded as returned; no conversion is performed and the discrepancy
  is noted.
- What if `fid` or `routingIdentifier` is absent from an option? The option is rejected
  from the result set and the omission recorded in the audit trail.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST search for travel options using the origin, destination,
  departure date, and traveller count taken verbatim from the confirmed objective.
- **FR-002**: The system MUST include the objective's currency in every search request.
- **FR-003**: The system MUST record, for every returned option, the identifier required
  to act on it (`fid` and `routingIdentifier`), preserved unmodified, byte-for-byte.
- **FR-004**: The system MUST record, for every returned option, the time it was priced
  (`refreshTime`) and the time it becomes unusable (`expireTime`).
- **FR-005**: The system MUST compute remaining usable time from the current clock at the
  moment of processing, not from the time of receipt; offers already partially aged must
  reflect the actual time remaining.
- **FR-006**: The system MUST report the total number of options returned and the set of
  carrier codes represented in the result.
- **FR-007**: The system MUST distinguish single-leg options (one segment) from multi-leg
  options (more than one segment in `fromSegments`).
- **FR-008**: The system MUST record, for every returned option, the available seat count
  and the provider's sell-out risk indicator per segment.
- **FR-009**: The system MUST decrement the journey's call budget by one for every search
  submitted, regardless of whether options are returned or the request is rejected.
- **FR-010**: The system MUST handle a provider response containing zero options without
  raising an error, and MUST indicate that no options were returned.
- **FR-011**: The system MUST NOT modify, enrich, supplement, or infer any value in a
  returned option; every recorded field must be traceable to the provider response.

### Non-Functional Requirements

- **NFR-001**: The raw provider response for every search MUST be persisted in full before
  any processing occurs, for audit purposes and for use as Tier 1 test fixtures.
- **NFR-002**: The system MUST respect the provider's documented request rate (10 QPS on
  `search.do`) and MUST NOT retry after a rate-limit rejection before the instructed
  `retryAfter` interval has elapsed.

### Key Entities

- **SearchRequest**: The parameters submitted to the provider — origin, destination, date,
  adult count, currency. Derived from the confirmed objective; not independently authored.
- **FlightOption**: A single routing returned by the provider. Carries the action
  identifier (`fid`, `routingIdentifier`), pricing metadata (`refreshed_at`, `expire_at`,
  `currency`, `adult_price`, `adult_tax`, `transaction_fee`), leg structure (`legs`,
  `is_multi_leg`), and scarcity signals (`seat_count`, `risk_sellout` per segment).
- **Leg**: A single flight segment within a routing. Carries carrier, flight number,
  departure and arrival airports and times (local), duration, stop cities, cabin class,
  seat count, and `riskSellout`.
- **SearchResult**: The output of a single search invocation. Carries `option_count`,
  `carriers`, the list of `FlightOption` records, and a `no_options` flag when
  `option_count = 0`.
- **SearchRecord**: The persisted audit record for a search, holding the raw provider
  response, the timestamp of the call, the journey's call budget before and after, and
  the outcome (success, empty, rate-limited, error).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every flight option returned by the provider is recorded in full with no
  fields omitted, modified, or supplemented, verifiable by comparing the stored record
  against the raw persisted response.
- **SC-002**: The remaining usable time on any option is accurate to within one second of
  the true remaining window, measured from the moment of processing.
- **SC-003**: A rate-limit rejection never causes a retry submission before the instructed
  interval; confirmed by audit trail inspection.
- **SC-004**: The call budget is decremented by exactly one for every search attempt,
  regardless of outcome; confirmed by unit test across all outcome types.
- **SC-005**: An empty result is returned as a valid `SearchResult` with `option_count = 0`
  and no exception path exercised, confirmed by test against a provider response with an
  empty `routings` array.
- **SC-006**: Multi-leg options (more than one entry in `fromSegments`) are always
  distinguished from single-leg options in the recorded result.

## Assumptions

- The external provider is the Atlas API (`search.do` endpoint), sandbox environment,
  as verified in `.antabay/atlas-capability-map.md`.
- `tripType` is always `"1"` (one-way) for this feature; return-trip search is out of scope.
- Currency is always taken from the confirmed objective; the sandbox requires `USD` and
  that constraint is met by the objective model.
- The confirmed objective always provides at minimum origin, destination, departure date,
  and adult count; the system does not handle a search with any of these absent.
- The journey's call budget is an integer counter already present in the journey record
  from Feature 001; this feature decrements it but does not define its initial value.
- `separateBookings` is recorded as part of the `FlightOption` for downstream use but is
  not acted upon in this feature.
- Scoring, ranking, filtering, and presentation of results are explicitly out of scope.
