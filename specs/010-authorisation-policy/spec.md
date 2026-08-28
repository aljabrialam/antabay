# Feature Specification: Authorisation Policy Engine

**Feature Branch**: `010-authorisation-policy`

**Created**: 2026-08-28

**Status**: Draft

**Input**: Cross-cutting policy definition, not tied to a single external
endpoint. Directly instantiates Constitution Principle III (Separation of
Reasoning and Authority — "a deterministic policy engine MUST decide
whether an action requires human authorisation... Authority MUST NOT be
delegated to a model") and Principle IV (Human Authorisation for
High-Impact Actions — "spending money, cancelling or voiding a ticket,
committing to an itinerary, or acting outside a stated constraint... MUST
NOT be inferred from absence of objection").

---

## Business Context

**Business Goal**: Decide, deterministically, whether a proposed action
may be executed autonomously or requires explicit human authorisation.

**Business Value**: The system spends the traveller's money and cancels
the traveller's tickets. The boundary of its authority must be a rule that
cannot be reasoned around, argued with, or persuaded. This is what makes
autonomous operation safe enough to permit at all.

**Business Actors**:
- Traveller — the sole party who can grant an Authorisation Request; silence
  or absence from this actor is treated as refusal
- Agent — the sole party who proposes actions for classification and who is
  bound by the resulting decision

**Business Capability**: Authority Control

**Reference**: `.specify/memory/constitution.md` Principles III and IV.
This feature is the general policy engine those principles describe;
feature 005 (Order Creation and Payment) is the first capability whose
actions will be submitted to it for classification.

---

## Clarifications

### Session 2026-08-28

- Q: A compensating/cleanup action taken automatically after a technical failure (e.g. voiding a partial hold before it becomes a stray live hold or an unwanted charge) would trigger FR-004/FR-005 exactly like any other action. Does this engine carve out a structural exception for compensating actions, or hold them to the same gate as everything else? → A: No exception — a compensating action is evaluated by the same four rules as any other proposed action; if it cancels, voids, spends money, or is irreversible, it still requires authorisation.
- Q: Does FR-003 ("spends money") trigger on any outgoing charge regardless of a larger simultaneous or subsequent refund, or should a net-savings action be exempt? → A: Gross outflow, always — any action with a nonzero outgoing cost triggers FR-003, regardless of whether a larger refund accompanies it; the rule looks only at the one proposed action's own charge, never at another action's outcome.
- Q: When a traveller's refusal renders the stated objective unachievable, is detecting/reporting that this feature's concern, or entirely out of scope? → A: Entirely out of scope — this engine only records the refusal; detecting objective-unachievability is the concern of whatever feature evaluates the objective (e.g., scoring), which this feature does not know about (Out of Scope).
- Q: Do two actions requiring authorisation at the same time need any additional rule about ordering or mutual exclusion, beyond FR-014's existing per-action scoping? → A: No new rule needed — each request is independently scoped and resolved by its own `(action_id, cost)` pair; nothing about concurrency changes how any one request is evaluated, requested, or enforced.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Deterministic Classification of Every Proposed Action (Priority: P1)

Before any proposed action executes, it is submitted to the policy engine
and classified as either permitted to run autonomously or requiring
explicit human authorisation. The engine reaches this decision without
consulting a language model, and the same proposed action evaluated
against the same journey context always produces the same classification.
Every decision names the specific rule that produced it.

**Why this priority**: This is the mechanism itself. No action can be
gated, no authorisation requested, and no audit trail written until every
proposed action passes through this decision point first.

**Independent Test**: Submit a proposed action to the engine and confirm a
classification is returned before execution is permitted. Submit the same
action and journey context repeatedly and confirm the classification never
varies. Confirm the decision path never invokes a language model. Confirm
each decision names the specific rule that determined it.

**Acceptance Scenarios**:

1. **Given** a proposed action, **When** it is submitted for evaluation,
   **Then** a classification — permitted autonomously or requiring
   authorisation — is produced before the action is allowed to execute.

2. **Given** the same proposed action and the same journey context,
   **When** it is evaluated any number of times, **Then** the
   classification produced is identical every time.

3. **Given** any evaluation performed by this engine, **When** the
   decision path is inspected, **Then** no language model was consulted to
   reach it.

4. **Given** any classification produced by this engine, **When** the
   decision is recorded, **Then** it is accompanied by the specific rule
   identifier that determined it, not a general explanation.

---

### User Story 2 — Rules That Force Human Authorisation (Priority: P1)

A fixed, enumerated set of conditions always forces a proposed action into
the requires-authorisation classification, regardless of any other
argument for proceeding: the action spends money, the action cancels or
voids a booking, the action cannot be reversed, or the action would breach
a hard constraint the traveller has stated. Each of these rules can be
tested on its own, in isolation, confirming both that it correctly forces
authorisation when it applies and that it does not force authorisation
when it does not apply.

**Why this priority**: This is the actual content of the boundary the
business goal describes. Without an enumerated, individually testable rule
set, "deterministic" and "cannot be reasoned around" are just claims, not
properties anyone can verify.

**Independent Test**: For each rule, construct a proposed action that
triggers it and confirm the classification is requires-authorisation.
Construct a proposed action that does not trigger it and confirm the
classification is not forced to requires-authorisation by that rule.
Repeat for every rule independently.

**Acceptance Scenarios**:

1. **Given** a proposed action that spends money, **When** it is
   evaluated, **Then** it is classified as requiring authorisation.

2. **Given** a proposed action that cancels or voids a booking, **When**
   it is evaluated, **Then** it is classified as requiring authorisation.

3. **Given** a proposed action that cannot be reversed, **When** it is
   evaluated, **Then** it is classified as requiring authorisation.

4. **Given** a proposed action that would breach a hard constraint the
   traveller has stated, **When** it is evaluated, **Then** it is
   classified as requiring authorisation.

5. **Given** a proposed action that triggers none of the four rules,
   **When** it is evaluated, **Then** it is classified as permitted
   autonomously.

6. **Given** a proposed action that triggers more than one rule
   simultaneously, **When** it is evaluated, **Then** it is classified as
   requiring authorisation and every rule that applied is identifiable
   from the decision record, not only the first one matched.

---

### User Story 3 — Authorisation Request, Response, and Enforcement (Priority: P1)

When an action requires authorisation, the traveller is presented with a
request stating the proposed action, its cost relative to the traveller's
current position, and its effect on the traveller's stated objective. If
the traveller does not respond, that is treated exactly as a refusal — not
as a pending state, and not as consent. Every decision — granted, refused,
or never answered — is written to the journey's audit trail. No action for
which authorisation was required is ever allowed to execute unless
authorisation for it was actually granted.

**Why this priority**: A classification with no enforcement behind it is
advisory, not a boundary. This story is what makes the classification from
User Story 1 and the rules from User Story 2 actually binding.

**Independent Test**: Trigger a requires-authorisation classification and
confirm the presented request states the action, its relative cost, and
its objective effect. Simulate no response and confirm the action does not
execute and a refusal is recorded. Simulate an explicit refusal and
confirm the same. Simulate a grant and confirm the action is then
permitted to execute, and that the grant is recorded. Attempt to force
execution of a requires-authorisation action without a recorded grant and
confirm it is prevented.

**Acceptance Scenarios**:

1. **Given** an action classified as requiring authorisation, **When** the
   authorisation request is presented, **Then** it states the proposed
   action, its cost relative to the traveller's current position, and its
   effect on the traveller's objective.

2. **Given** an authorisation request has been presented, **When** no
   response is received, **Then** the outcome is recorded as a refusal,
   not as an unresolved or pending state.

3. **Given** an authorisation request has been refused or not responded
   to, **When** execution of that action is attempted, **Then** execution
   is prevented.

4. **Given** an authorisation request has been granted, **When** execution
   of that specific action is attempted, **Then** execution is permitted.

5. **Given** any authorisation decision — granted, refused, or unanswered
   — **When** it is reached, **Then** it is recorded in the journey audit
   trail.

6. **Given** no authorisation was ever recorded for an action that
   required it, **When** execution is attempted by any path, **Then**
   execution is prevented.

---

### User Story 4 — Authorisation Scope and Staleness (Priority: P2)

An authorisation grant applies to exactly the one proposed action it was
requested for — never to a later action, even one of the same type or
directed at the same booking. If the cost of the authorised action changes
after the grant was given but before it executes, that prior grant is
voided and authorisation must be sought again on the new terms.

**Why this priority**: Without this, a single grant could be stretched to
cover actions the traveller never actually saw or agreed to — quietly
reintroducing exactly the failure mode Principle IV exists to prevent.
This is a refinement of User Story 3's enforcement, not a new capability,
which is why it follows rather than leads.

**Independent Test**: Grant authorisation for one proposed action, then
submit a second, subsequent action of the same type; confirm the second
action is evaluated on its own and the prior grant does not apply to it.
Separately, grant authorisation for an action, change its cost before
execution, and confirm the prior grant is voided and a fresh authorisation
request is required.

**Acceptance Scenarios**:

1. **Given** authorisation was granted for one specific proposed action,
   **When** a subsequent action is proposed — even one of the same type or
   against the same booking — **Then** the prior grant does not apply to
   it, and it is evaluated and, if required, authorised independently.

2. **Given** authorisation was granted for a proposed action at a stated
   cost, **When** that action's cost changes before it executes, **Then**
   the prior grant is voided and the action may not execute on the strength
   of it.

3. **Given** a prior grant has been voided by a cost change, **When** the
   action is still to proceed, **Then** a new authorisation request
   reflecting the changed cost is required before execution.

---

### Edge Cases

- A proposed action triggers more than one of the four forcing rules at
  once (for example, it spends money and would also breach a hard
  constraint). The classification is still simply
  requires-authorisation — there is no escalated tier above it — but the
  decision record identifies every rule that matched, not only one, so the
  audit trail and the authorisation request presented are not silently
  incomplete about why.
- A proposed action's cost is genuinely zero or unknown at evaluation time
  (for example, its price has not yet been confirmed). A cost that cannot
  yet be stated is not evidence that no money will be spent; the rule for
  money-spending actions applies to the action's classification, not to
  whether a specific number happens to be available at evaluation time.
- The traveller responds after the point at which absence was already
  treated as refusal. The original refusal decision and its recorded
  timestamp stand; a late response does not retroactively convert it into
  a grant. Any further action to execute the same underlying intent must
  be freshly proposed and freshly authorised.
- The same proposed action is resubmitted after a technical failure (for
  example, a transient error prevented the previous attempt from
  executing) rather than because the traveller changed anything. Whether
  this counts as the "one specific action" the original grant already
  covered, or as a new action requiring a fresh grant, is decided by
  whether anything material to the decision — the action itself, its cost,
  or the journey context — has changed since the grant; an identical
  resubmission with nothing changed is not a new action for this purpose.
- A compensating or cleanup action is proposed automatically to recover
  from a technical failure (for example, voiding a partial hold before it
  becomes a stray live hold or an unwanted charge) — as distinct from the
  resubmission case above, this is a genuinely new action, not a retry of
  the one that failed. It receives no exception: it is evaluated by the
  same four rules as any other proposed action, and if it cancels, voids,
  spends money, or is irreversible, it still requires authorisation, even
  though it exists only to limit damage from a prior failure.
- A hard constraint is added or changed by the traveller after an
  authorisation was already granted but before the action executes. This
  is treated the same way as a cost change (User Story 4): the prior grant
  no longer reflects the current terms and is voided, requiring
  re-evaluation against the current constraint set.
- Two proposed actions requiring authorisation are pending at the same
  time. No additional ordering or mutual-exclusion rule applies beyond
  FR-014's existing per-action scoping — each request is independently
  scoped and resolved by its own action and cost, and concurrency between
  them is not, on its own, a condition this feature treats specially.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST evaluate every proposed action before it is
  executed. No path exists by which an action executes without first
  passing through this evaluation.

- **FR-002**: The system MUST classify every evaluated action as either
  permitted to execute autonomously or as requiring human authorisation.
  No third classification exists.

- **FR-003**: The system MUST classify a proposed action as requiring
  human authorisation if it spends money, regardless of the amount. This
  is evaluated on the action's own gross outgoing cost alone — a larger
  refund or credit occurring simultaneously or subsequently, even one
  confirmed in the same request, does not exempt the action from this
  rule.

- **FR-004**: The system MUST classify a proposed action as requiring
  human authorisation if it cancels or voids a booking.

- **FR-005**: The system MUST classify a proposed action as requiring
  human authorisation if it cannot be reversed.

- **FR-006**: The system MUST classify a proposed action as requiring
  human authorisation if it would breach a hard constraint the traveller
  has stated.

- **FR-007**: The system MUST reach every classification decision without
  consulting a language model at any point in the decision path.

- **FR-008**: The system MUST produce, with every classification decision,
  the identifier of the specific rule that determined it. When more than
  one rule applies to the same proposed action, the system MUST identify
  every rule that applied, not only the first matched.

- **FR-009**: The system MUST present, for every action classified as
  requiring authorisation, a request stating the proposed action, its cost
  relative to the traveller's current position, and its effect on the
  traveller's stated objective.

- **FR-010**: The system MUST treat the absence of a response to an
  authorisation request as a refusal of that request, recorded as such —
  never as a pending or unresolved state, and never as consent.

- **FR-011**: The system MUST record every authorisation decision —
  granted, refused, or unanswered — in the journey's audit trail.

- **FR-012**: The system MUST prevent execution of any action for which
  authorisation was required and was not granted, through every path by
  which that action's execution could otherwise be attempted.

- **FR-013**: The system MUST void a prior authorisation grant when the
  cost of the authorised action changes after the grant was given and
  before the action executes, and MUST require a fresh authorisation
  request reflecting the new cost before the action may proceed.

- **FR-014**: The system MUST treat an authorisation grant as applying to
  exactly one specific proposed action, and MUST NOT carry that grant
  forward to authorise a subsequent action — including a subsequent action
  of the same type or directed at the same booking. An identical
  resubmission of the same action, with nothing material changed since the
  grant, is not a subsequent action for this purpose.

### Non-Functional Requirements

- **NFR-001**: The classification decision MUST be deterministic — the
  same proposed action evaluated against the same journey context MUST
  always produce the same classification.

- **NFR-002**: The rule set MUST be readable by a non-engineer, without
  requiring familiarity with the system's implementation.

- **NFR-003**: No configuration, prompt, or input MUST be capable of
  causing an action that requires authorisation to execute without it
  having been granted.

- **NFR-004**: Every rule MUST be individually testable in isolation, in
  both the direction that grants autonomous execution and the direction
  that forces authorisation.

### Key Entities

- **Proposed Action**: The candidate action submitted for classification
  before execution. Carries whatever the applicable rules need to decide
  it — at minimum, whether it spends money and how much, whether it
  cancels or voids a booking, whether it can be reversed, and whether it
  would breach a stated hard constraint.

- **Rule**: One of the fixed, enumerated, individually testable conditions
  (FR-003 through FR-006) that forces the requires-authorisation
  classification when it applies. Rules are the unit both of decision and
  of test.

- **Authorisation Decision**: The engine's output for one Proposed
  Action — permitted autonomously or requires authorisation — together
  with the identifier of every Rule that determined it (FR-008).

- **Authorisation Request**: What is presented to the traveller when a
  Proposed Action's Authorisation Decision requires it. States the
  proposed action, its cost relative to the traveller's current position,
  and its effect on the traveller's objective (FR-009).

- **Authorisation Grant**: The traveller's affirmative response to one
  specific Authorisation Request. Scoped to exactly the one Proposed
  Action it answers (FR-014); voided if that action's cost changes before
  execution (FR-013).

- **Authorisation Refusal**: The recorded outcome of an Authorisation
  Request that was explicitly declined or that received no response
  (FR-010). Functionally identical in its effect on execution regardless
  of which of the two produced it.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every proposed action exercised in the test suite receives a
  classification before any execution is permitted — 100%, no exceptions.

- **SC-002**: Every proposed action in the test suite that spends money,
  cancels or voids a booking, is irreversible, or would breach a stated
  hard constraint is classified as requiring authorisation — 100%, in
  both single-rule and multiple-rule-triggered scenarios.

- **SC-003**: Every proposed action in the test suite that triggers none
  of the four rules is classified as permitted autonomously — zero
  false positives forcing unnecessary authorisation.

- **SC-004**: The same proposed action and journey context, evaluated
  repeatedly in the test suite, produces an identical classification
  every time — 100% of repeated evaluations.

- **SC-005**: Every classification decision in the test suite is
  accompanied by the specific rule identifier(s) that produced it — 100%,
  with no decision left unattributed to a rule.

- **SC-006**: Zero instances in the test suite of an action requiring
  authorisation executing without a recorded grant for that specific
  action.

- **SC-007**: Every non-response scenario in the test suite is recorded as
  a refusal, never as a pending, unresolved, or granted state — 100%.

- **SC-008**: Every authorisation decision produced in the test suite —
  granted, refused, or unanswered — has a corresponding entry in the
  journey audit trail — 100%.

- **SC-009**: Every test scenario in which an authorised action's cost
  changes before execution results in the prior grant being voided and a
  fresh authorisation request being required — 100%, zero instances of a
  stale grant being honoured.

- **SC-010**: Every rule in the enumerated set has at least one passing
  test confirming it forces authorisation when triggered, and at least one
  passing test confirming it does not when not triggered — 100% of rules,
  both directions.

---

## Out of Scope

- Executing the proposed action itself, once permitted or authorised
- Searching for alternative options or scoring them
- The user interface that presents the authorisation request to the
  traveller — this feature defines what must be stated in that request,
  not how it is rendered
- Verifying, after execution, whether an authorised action actually
  produced its claimed effect (that is Post-Action Verification's
  concern, not this feature's)
- Detecting or reporting that a refusal has rendered the traveller's
  stated objective unachievable — this feature's responsibility ends at
  recording the refusal; whatever evaluates the objective against
  available options (scoring) is the only thing positioned to know
  whether it can still be satisfied

---

## Assumptions

- Feature 005's `BookingService` (order creation, payment, ticketing) is
  the first concrete source of Proposed Actions this engine will
  classify, but this specification defines the general policy any current
  or future action-producing feature must submit to — it does not modify
  005 directly.
- "Cannot be reversed" (FR-005) means no compensating action exists that
  would fully restore the state prior to the action executing — not
  merely that reversing it would be inconvenient or costly.
- A cost that is genuinely unknown or not yet confirmed at evaluation time
  does not exempt an action from FR-003; an action that will spend an
  as-yet-unconfirmed amount of money is still classified as
  money-spending, per the Edge Cases entry addressing this.
- Any nonzero change to an authorised action's cost — not only a change
  past some materiality threshold — voids the prior grant under FR-013,
  consistent with the "cannot be reasoned around" posture this feature is
  built to enforce.
- The window within which a response to an Authorisation Request is
  awaited before its absence is treated as refusal (FR-010) is a concern
  of whatever feature manages that request's lifecycle and timing, not of
  this policy engine, which only defines that absence — however it comes
  to be established — means refusal.
- "The traveller's current position" (FR-009) means the journey's current
  committed spend and held identifiers at the moment the request is
  presented, consistent with how those are already tracked by features
  001 and 004.
