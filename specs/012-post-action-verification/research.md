# Research: Post-Action Verification

## R1 — Shape of the general gate: `SuccessCondition` protocol

**Decision**: An action type registers with the gate by providing a
`SuccessCondition` with two responsibilities:

```text
classify(query_result) -> one of: Success, Failure, Inconclusive, NotFound
has_discrepancy(action_response, query_result) -> bool
reconciliation_bound() -> a bound (max attempts or max duration)
```

`Inconclusive` and `NotFound` are reported separately by the condition —
the *gate*, not the condition, decides what each becomes over time (see
R2). The gate itself never inspects `query_result`'s shape; only the
registered condition understands what a given action type's query
response looks like.

**Rationale**: FR-003 requires every action type to define its own
observable success condition, with no default or borrowed one — a single
shared `classify()` signature lets the gate stay action-agnostic (it
never hardcodes what "ticketed" or "refunded" means) while still
enforcing the same reconciliation, discrepancy, and audit discipline
uniformly. Splitting `Inconclusive` from `NotFound` is required by the
spec's own Clarifications: a query that simply failed to execute and a
query that cleanly reported absence are resolved differently at the
bound (Q2), so the gate needs to tell them apart without needing to
understand any specific action's data.

**Alternatives considered**:
- *One `classify()` return type covering only Success/Failure/Unresolved*:
  rejected — collapses the not-found/inconclusive distinction the spec's
  own Clarifications require the gate to treat differently at the bound.
- *Let each condition implement its own bound-and-retry loop*: rejected —
  this is exactly the ad hoc duplication (per action type) this feature
  exists to eliminate; the gate owns the loop, the condition only
  classifies and declares its bound.

## R2 — Bound handling: `Inconclusive` stays unresolved, `NotFound` becomes failure

**Decision**: The gate tracks, per unresolved outcome being reconciled,
whether every reconciliation query so far has returned `NotFound`
specifically. When the condition's declared bound (R1) is reached:
- if every query attempt was `NotFound`: the outcome resolves to
  `FAILURE`.
- otherwise (at least one attempt was `Inconclusive`, or the sequence was
  mixed): the outcome remains `UNRESOLVED`.

**Rationale**: Directly implements the spec's Clarifications Q2. A
consistent, clean not-found result is treated as increasingly trustworthy
the longer it persists (ruling out transient provider-side propagation
delay); a genuinely inconclusive result (the query itself failed, or
returned something uninterpretable) never becomes more trustworthy just
by recurring, so it cannot resolve to a definite failure on its own.

**Alternatives considered**: None beyond what the spec's clarification
already decided — this section exists to record the resulting
gate-level bookkeeping (a per-outcome "all-not-found-so-far" flag),
which the spec itself doesn't need to know about but the implementation
does.

## R3 — Concurrency ordering by observed timestamp (FR-011)

**Decision**: Every `VerificationAttempt` carries an `observed_at`
timestamp (when its query's result was obtained, not when the
`VerificationAttempt` row was written or when gate processing finished).
When the gate is about to apply an attempt's classification to journey
state, it compares that attempt's `observed_at` against the most recent
`observed_at` already applied for the same affected record; the later
timestamp wins. An attempt that loses this comparison is still persisted
in full (FR-009) — only its effect on state is superseded.

**Rationale**: Directly implements the spec's Clarifications answer.
Comparing timestamps already carried on the persisted rows means no
distributed lock or sequencing service is needed — the ordering decision
is a pure read of two already-fetched records at the moment state would
be updated, matching the plan's stated Performance Goal.

**Alternatives considered**:
- *First-to-finish-processing wins*: explicitly rejected by the spec's
  own clarification — a slower call that observed the record earlier
  must not be allowed to overwrite a faster call that observed it later,
  or vice versa; only the observation instant matters.

## R4 — Discrepancy detection is a per-condition responsibility, not a generic diff

**Decision**: `SuccessCondition.has_discrepancy(action_response,
query_result)` is implemented per action type, not as a generic
structural diff between two arbitrary objects.

**Rationale**: What counts as "disagreement" is action-specific — for
ticketing, it's the action's response implying success while the query
shows no ticket numbers; a generic field-by-field diff between an
`order.do` response and a `queryOrderDetails.do` response would flag
enormous incidental noise (different field sets entirely) that has
nothing to do with FR-005's intent. This mirrors R1's reasoning: the gate
enforces that a discrepancy check happens and is recorded, but does not
and cannot know what a meaningful discrepancy looks like for an
arbitrary future action type.

**Alternatives considered**:
- *Generic dict diff*: rejected for the reason above.

## R5 — Cross-surface type normalisation (FR-008) lives in the condition, not the gate

**Decision**: Normalising a status value reported in different types by
different surfaces (the one proven instance: `orderStatus` as a string
from `queryOrderDetails.do` vs. an integer from the `order.ticketed`
webhook) is the responsibility of whichever `SuccessCondition` receives
values from both surfaces — not a generic type-coercion utility in the
gate itself.

**Rationale**: The gate has no way to know which fields, across which two
surfaces, represent "the same" status for an arbitrary action type — that
knowledge is inherently condition-specific, same reasoning as R4. A
shared helper function (e.g. `normalise_status(value) -> str`) is a
reasonable convenience for conditions to use, but the gate does not call
it automatically on inputs it does not understand.

**Alternatives considered**:
- *Gate-level automatic normalisation of any field appearing in both an
  action response and a query result*: rejected — the gate would need to
  guess which fields are "the same status" across two arbitrarily-shaped
  objects, which is exactly the kind of invented behaviour Principle I
  forbids.

## R6 — Reportable outcome is absence, not a placeholder (spec Clarifications Q4)

**Decision**: `PostActionVerifier.reportable_outcome(record_id)` returns
`None` until a `VerificationAttempt` for that record has resolved to
`SUCCESS` or `FAILURE`. There is no `PENDING` value in the returned type.

**Rationale**: Directly implements the spec's Clarifications answer.
Keeps the gate's public surface minimal — a caller checks for `None`
exactly as it would for any other "not yet available" fact — and leaves
whatever renders status to the traveller (out of scope here) free to
interpret that absence however it chooses.

**Alternatives considered**: None beyond what the clarification already
decided.

## R7 — Proving the general gate against 005's already-verified ticketing case, without refactoring 005

**Decision**: `journey/services/conditions/ticketing_condition.py`
implements a `TicketingSuccessCondition` reproducing 005's own rule
(every passenger's `ticketNos` non-empty confirms ticketing; a non-null
`errorCode` is a terminal failure) as a `SuccessCondition`. Its test
(`test_ticketing_success_condition.py`) is exercised against plain
constructed query-result objects mirroring the exact shapes already
proven by 005's cassette-backed tests (`TestConfirmTicketingAllPassengers`,
`TestConfirmTicketingPartialResult`, `TestConfirmTicketingTerminalError`)
— not against a new cassette, since the underlying provider contract is
already verified and unchanged. `BookingService.confirm_ticketing()`
itself is not modified to call through this new gate.

**Rationale**: FR-004 calls the ticketing rule "the canonical,
previously-confirmed instance" — proving the general mechanism reproduces
that exact, already-trusted behaviour is the most direct way to validate
the abstraction without re-deriving trust in the underlying Atlas
contract a second time. Not refactoring `BookingService` keeps this
feature's scope to what it specifies (the general policy) rather than
also taking on "migrate an existing, already-shipped, already-tested
feature to a new internal API," which is a separate capability
(Constitution Principle XVI) that risks regressing 005's own test suite
for no requirement in this spec.

**Alternatives considered**:
- *Refactor `BookingService` to call through the new gate in this same
  feature*: rejected per Constitution Principle XVI and this spec's own
  Out of Scope ("the actions themselves"). A future feature can make that
  change deliberately, as its own single capability, once this gate
  exists to migrate to.
