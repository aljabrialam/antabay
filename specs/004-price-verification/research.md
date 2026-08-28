# Research: Price Verification and Offer Staleness

## R1 — Representing the two freshness windows (FR-006)

**Decision**: Reuse the existing `held_identifiers` table/model (from spec 001) for both the offer-level and session-level windows, rather than introducing a new freshness table. The offer's `routingIdentifier` row and the verified option's `sessionId` row are two separate `held_identifiers` rows for the same journey; the offer row is not deleted on verify success, it simply stops being consulted for freshness decisions once its counterpart `sessionId` row exists.

**Rationale**: `held_identifiers` already models exactly this shape — `value`, `issued_at`, `stale_after_seconds`, `stale_at`, plus `is_stale(now)` and a `JourneyStateService.check_identifier_freshness()` read path. Spec 001 built this generically ("an identifier held by the system that has a known expiry time"); FR-006 is a second consumer of that same primitive, not a new concept. Reusing it also means 006's console — which already renders `held_identifiers` as expiry clocks — gets the session clock for free once this feature starts writing rows to it.

**Alternatives considered**:
- *New `freshness_windows` table with an explicit `phase` column (OFFER/SESSION)*: rejected — duplicates a table that already exists for the same purpose, and the "phase" distinction is fully recoverable from which `identifier_id` a row belongs to (a routing identifier vs a session identifier) without a new column.
- *Single mutable row, overwritten on verify success*: rejected — destroys the audit trail of when the offer window ended and the session window began, which NFR-002 (persist verification responses in full) implies should be reconstructable, not just the current value.

## R2 — Session window duration when Atlas does not return an explicit session expiry

**Decision**: `stale_after_seconds` for the `sessionId` row is a configured constant (the documented "up to 2 hours" ceiling from the capability map), not a value read from the verify response — because `verify.do` does not return one. `routing.expireTime` is explicitly `null` in the verify response (per capability map §7a, "Freshness changes shape after verify"); there is no analogous explicit field for `sessionId`'s own expiry.

**Rationale**: FR-005/FR-006 require tracking *a* session-level window; the only number the capability map gives is Atlas's own documentation ceiling. Treating it as a configured value (rather than inventing a computed one) keeps this feature honest about what is actually known versus assumed — this is itself an instance of Principle I applied to a *duration*, not just an identifier.

**Alternatives considered**:
- *Derive session duration from the retired offer window's remaining time*: rejected — the two windows have no documented mathematical relationship; the capability map explicitly separates them ("The journey state machine therefore has two distinct freshness phases").
- *Treat session as never-expiring until a call fails*: rejected — directly contradicts FR-010's safety-margin re-verification, which requires a known upper bound to measure remaining time against.

## R3 — Detecting "no longer available" (FR-009)

**Decision**: Treat any non-success `verify.do` outcome that is *not* a reported price change as "no longer available," pending the exact status/message Atlas uses for this condition (not yet captured in the capability map — see its own §10, "Not yet verified"). The distinguishing signal already established by `FlightSearchService` for `search.do` (non-zero `status` field) is reused as the same shape of check for `verify.do`.

**Rationale**: The capability map documents `status: 0` as the success convention across every verified endpoint. A price change is a *successful* verify (`status: 0`, `priceChange.isPriceChange: true`) — it is not this condition. Everything else non-zero is treated conservatively as unavailability until a real sandbox capture narrows it further, consistent with how `search.do`'s non-zero status is already handled as an error condition in `FlightSearchService`.

**Alternatives considered**:
- *Wait for a live sandbox capture of this exact condition before specifying behaviour*: rejected — FR-009 is an explicit, prioritized requirement; the fallback behaviour (treat non-zero, non-price-change as unavailable, return to search) is safe in the conservative direction and does not need to be perfectly precise to satisfy "does not proceed to order creation on an option that cannot be confirmed."

## R4 — Passenger requirement storage shape (FR-007)

**Decision**: Persist `bookingRequirement.passenger` as-is (the full per-field `{type, required, description, maxLength}` structure Atlas returns), not mapped into fixed typed columns.

**Rationale**: The capability map is explicit that this schema is "returned per offer. Read it at runtime — do not hardcode a passenger form." A fixed set of typed columns would be exactly the hardcoding the source data warns against — different offers can return different required fields (spec 004's own edge case: zero required fields is valid).

**Alternatives considered**:
- *Typed columns for the currently-observed field set (`name`, `birthday`, `gender`, `nationality`, `passengerType`, `cardNum`, `cardType`, `cardIssuePlace`, `cardExpired`)*: rejected — freezes the schema to what one sandbox response happened to contain, contradicting FR-007's explicit "not a fixed set."

## R5 — Journey state additions

**Decision**: Add a single new `JourneyState.VERIFIED` value. Allowed transitions gain `SEARCHING → VERIFIED` (successful verify) and `VERIFIED → SEARCHING` (FR-009, unavailable). `VERIFIED` also inherits the existing terminal transitions (`→ CANCELLED`, `→ ABANDONED`). Re-verification (FR-010) while already `VERIFIED` is not itself a state transition — it is a repeated action that refreshes the session's `held_identifiers` row; only a failed re-verification transitions back to `SEARCHING`.

**Rationale**: `JourneyState` currently has no state representing "a verified, order-ready option is held" — `SEARCHING` covers everything from an empty search to a scored, selected-but-unverified option (spec 003's `scoring_runs.selected_option_id` does not itself move the journey out of `SEARCHING`). FR-009's "return to search" only makes sense as a real transition if verification success first moved the journey somewhere else.

**Alternatives considered**:
- *No new state; track "verified" only via the presence of a `verifications` row*: rejected — makes FR-009 unobservable as a state machine fact, and 006's journey-state stepper (which renders `JourneyState` as an ordered sequence) would have nothing to render for this step.
- *Separate `VERIFYING` (in-flight) state in addition to `VERIFIED`*: rejected — `verify.do` is a synchronous call in this codebase's existing pattern (`FlightSearchService.search()` is likewise synchronous, not a background job); there is no observable interval during which the journey is meaningfully "verifying" as opposed to "about to call" or "just called."

## R6 — Call budget accounting (FR-011)

**Decision**: Reuse `JourneyRepository.decrement_call_budget()` exactly as `FlightSearchService.search()` already does — decrement before the HTTP call, record `budget_before`/`budget_after` on the persisted verification row, raise the existing `BudgetExhaustedError` if the budget is already zero.

**Rationale**: This is the same shared-allowance accounting the capability map already documents for `verify.do` + `getOffers.do` (60 QPM combined); no new budget concept is needed, only a second caller of the existing mechanism.

**Alternatives considered**: None seriously considered — this is a direct precedent match, not a design choice.
