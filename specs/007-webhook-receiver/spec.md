# Feature Specification: Event Reception and Reconciliation

**Feature Branch**: `007-webhook-receiver`

**Created**: 2026-08-28

**Status**: Draft

**Input**: `.antabay/atlas-capability-map.md` section 7c — a real
`order.ticketed` webhook event captured live on 2026-08-15 via a Cloudflare
quick tunnel. That capture is the ground truth behind four of this
feature's requirements: the event type is a dotted string in a `type`
field (FR-005); the webhook's own `status` field carried `-1` on a
*successful* event, proving it cannot be read as a success/failure signal
(FR-006); `orderStatus` arrived as an integer in the webhook but a string
from `queryOrderDetails.do`, proving cross-surface fields need normalising
(FR-007); and the webhook carries no signature, HMAC, or shared secret —
only a non-secret `cid` — making every inbound notification forgeable by
anyone who learns the URL (FR-003, FR-004, and both Non-Functional
Requirements).

---

## Business Context

**Business Goal**: Receive change notifications from the travel provider,
establish whether each one is true, and wake the agent when it is.

**Business Value**: This is what makes the product continuous rather than
transactional. It is also the point of highest risk: the notification
channel is unauthenticated and delivery is not guaranteed.

**Business Actors**:
- Travel provider — sends inbound notifications over an unauthenticated
  channel, with no delivery guarantee
- Agent — is woken by this feature once a notification's claim has been
  independently confirmed, and does not otherwise interact with the
  notification channel directly

**Business Capability**: Event Ingestion

**Reference**: `.antabay/atlas-capability-map.md` section 7c. Feature 008
(not yet specified) is expected to inject simulated events of the same
envelope shape into this same receiver, per that section's own note —
this feature is the receiver those events, and every real one, arrive
through.

---

## Clarifications

### Session 2026-08-28

- Q: Two notifications (or a notification and a periodic reconciliation sweep) for the same journey are confirmed independently and could resolve out of order — nothing currently says which result governs if they'd produce conflicting journey states. Should this feature adopt feature 012's existing "most recent observed timestamp governs" rule, or does it need something different? → A: Adopt feature 012's rule directly — the confirmation whose query observed the provider's state most recently governs, regardless of which one finished processing first. Consistent with this spec's own Assumption that FR-004's confirmation *is* 012's verification discipline, applied to an external trigger.
- Q: When a notification's claim and its confirmation actively disagree (not merely unconfirmed yet, but contradicted), should this be recorded as a distinct discrepancy — mirroring feature 012's existing concept — or is the confirmed truth governing sufficient on its own? → A: Record it. A discrepancy is recorded whenever a notification's claim and its confirmation disagree, mirroring feature 012's Discrepancy concept.
- Q: A notification arrives for a journey while the agent is actively mid-action on that same journey — should confirmation run immediately regardless, or be deferred until the in-flight action settles? → A: Confirmation always runs immediately — it is read-only and safe to run concurrently; reconciling a confirmed fact against in-flight agent work is the agent's concern once woken, not this feature's.
- Q: The channel is unauthenticated, so a third party can submit forged notifications freely, and each one that passes the order-reference check triggers a confirmation query against the provider's tracked call budget. Should this feature bound confirmation-query volume per journey against a flood, or leave that to a separate, future rate-limiting feature? → A: Bound it here — a burst of notifications for the same journey within a short window collapses into a bounded number of confirmation queries, regardless of how many distinct notifications arrived.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Untrusted Notification Ingestion (Priority: P1)

The system accepts inbound notifications at a publicly reachable endpoint
and acknowledges receipt immediately, before any attempt is made to
establish whether the notification is true. Every notification is
persisted in full — exactly as received — before anything else happens to
it.

**Why this priority**: Nothing else in this feature can happen until a
notification has actually been accepted and preserved. Acknowledging
before verifying is also what makes the endpoint reliable from the
provider's side: a slow or failed verification step must never look like
a failed delivery.

**Independent Test**: Send a notification to the endpoint and confirm an
acknowledgement is returned before any confirmation query could plausibly
have completed. Inspect storage afterward and confirm the exact
notification received is present in full, independent of what happened to
it next.

**Acceptance Scenarios**:

1. **Given** a notification arrives at the endpoint, **When** it is
   received, **Then** an acknowledgement is returned without waiting for
   any confirmation of the notification's claim.

2. **Given** any notification is accepted, **When** it is processed at
   all, **Then** its full, unmodified content has already been persisted
   before any routing or confirmation step begins.

3. **Given** the confirmation step for a notification later fails, times
   out, or is never reached, **When** this is checked against the
   acknowledgement already sent, **Then** the acknowledgement is
   unaffected — it was never contingent on that outcome.

---

### User Story 2 — Confirm Before Acting (Priority: P1)

No notification is ever trusted on its own word. Every notification is
treated as an unauthenticated, untrusted assertion, and its claim is
confirmed against the provider's own interface before any journey state
changes. The notification's own status value is never read as a
success/failure signal. The agent is woken only once confirmation has
actually happened.

**Why this priority**: This is the actual trust boundary the whole feature
exists to enforce — the "point of highest risk" the business value names
directly. Every other story in this feature exists in service of getting
a notification safely to this checkpoint.

**Independent Test**: Send a notification asserting an outcome, and
confirm that no journey state changes and the agent is not woken until an
independent query of the provider's interface has confirmed the claim.
Send a notification whose own status field would suggest failure while
the independent query shows success (or vice versa), and confirm the
independent query's result — never the notification's own status field —
is what governs.

**Acceptance Scenarios**:

1. **Given** a notification asserts that something happened, **When** the
   system considers acting on it, **Then** the provider's own interface is
   queried independently and its response — not the notification's
   assertion — determines what is treated as true.

2. **Given** a notification carries a status value, **When** the system
   evaluates what happened, **Then** that status value is never read as
   evidence of success or failure, regardless of what it appears to say.

3. **Given** a notification's claim has not yet been confirmed, **When**
   anything downstream might act on it, **Then** no journey state has
   changed and the agent has not been woken.

4. **Given** a notification's claim has been confirmed by an independent
   query, **When** confirmation completes, **Then** the agent is woken for
   the affected journey.

5. **Given** a notification's claim and its confirmation disagree about
   what happened, **When** confirmation completes, **Then** the confirmed
   truth governs journey state, and the disagreement itself is recorded as
   a discrepancy — not silently dropped now that the "true" answer is
   known.

---

### User Story 3 — Correct Routing and Association (Priority: P1)

Each notification is routed according to the event type it declares, and
is associated with exactly one journey via the order reference it
carries. A notification whose order reference matches no known journey is
discarded rather than acted on. Field types that differ between a
notification and the provider's query interface for the same underlying
value are normalised before being compared or used.

**Why this priority**: A confirmation step (User Story 2) is only
meaningful if it is confirming the right thing, about the right journey.
Misrouted or misattributed notifications would either silently do nothing
useful or — worse — get confirmed and applied against the wrong journey.

**Independent Test**: Send notifications of different declared event types
and confirm each is handled according to its own type. Send a notification
whose order reference matches no known journey and confirm it is discarded
with no journey affected. Send a notification carrying a field in a
different type than the query interface reports the same value in, and
confirm both are treated as equal once normalised.

**Acceptance Scenarios**:

1. **Given** a notification declares an event type, **When** it is
   processed, **Then** it is routed according to that declared type.

2. **Given** a notification carries an order reference, **When** it is
   processed, **Then** it is associated with the one journey that
   reference identifies.

3. **Given** a notification's order reference matches no known journey,
   **When** this is discovered, **Then** the notification is discarded and
   no journey is affected.

4. **Given** a field is reported by a notification in one data type and by
   the query interface in a different type for the same underlying value,
   **When** the two are compared, **Then** they are normalised to a common
   type first and treated as equal.

---

### User Story 4 — Duplicate Tolerance and Independent Reconciliation (Priority: P2)

Receiving the same notification more than once never produces more than
one resulting action. A burst of many notifications for the same
journey — whether duplicates, distinct legitimate notifications, or a
forged flood exploiting the channel's lack of authentication — never
triggers more than a bounded number of confirmation queries against the
provider for that journey. Separately from — and regardless of — whatever
notifications do or don't arrive, active journeys are periodically
reconciled against the provider on their own schedule, because delivery of
any given notification is never guaranteed.

**Why this priority**: This is what makes the first three stories reliable
in practice rather than only in the case where the channel behaves
perfectly. It is explicitly a P2 because it is a resilience layer on top
of a mechanism (Stories 1–3) that must exist first.

**Independent Test**: Send the identical notification more than once and
confirm only one resulting action occurs, however many times it arrives.
Send a burst of many distinct notifications for one journey in a short
window and confirm the resulting confirmation-query volume against the
provider stays bounded, not one-per-notification. Confirm an active
journey for which no notification has ever arrived is still checked
against the provider on the periodic schedule, independent of any
notification history.

**Acceptance Scenarios**:

1. **Given** the same notification is received more than once, **When**
   each is processed, **Then** at most one resulting action is ever
   produced, regardless of how many times it arrived.

2. **Given** an active journey exists, **When** its periodic reconciliation
   comes due, **Then** it is checked against the provider independently of
   whether any notification has ever been received for it.

3. **Given** a notification for an active journey was sent by the provider
   but never arrived, **When** that journey's next periodic reconciliation
   occurs, **Then** whatever change the missed notification would have
   reported is still discovered.

4. **Given** many notifications for the same journey arrive within a short
   window — whether duplicates, distinct notifications, or a forged flood
   — **When** they are processed, **Then** the number of confirmation
   queries triggered against the provider for that journey stays bounded,
   never one query per notification received.

---

### Edge Cases

- A notification arrives whose order reference matches a journey that has
  already reached a terminal state. It is still persisted in full (User
  Story 1's guarantee is unconditional), but no confirmation query or
  agent wake follows for a journey that is no longer active.
- A notification declares an event type the system does not recognise
  (the only type verified in production so far is `order.ticketed`;
  others are expected to arrive over time, following the same dotted-string
  convention, per the capability map). It is still acknowledged and
  persisted in full — an unrecognised type is inert, not an error — but no
  routing, confirmation, or wake follows, since there is no defined
  handling for it.
- A notification's payload is malformed, or omits the order reference
  entirely, so it cannot be associated with any journey by the normal
  means. It is still persisted in full; from there it is treated the same
  as a notification matching no known journey (User Story 3) — discarded,
  with no journey affected.
- A notification's claim actively contradicts what its confirmation query
  finds (as opposed to simply not being confirmed yet) — for example, a
  forged or stale notification asserting an outcome the provider's own
  interface shows never happened. The confirmed truth still governs
  (FR-004), but the disagreement is recorded as a discrepancy (FR-012)
  rather than disappearing once the correct answer is known.
- A notification arrives for a journey while the agent is actively
  performing a state-changing action on that same journey. Confirmation
  runs immediately regardless — it is a read-only query, not a write, so
  running it concurrently with the agent's own in-flight action carries no
  risk of corruption on this feature's side. Reconciling a confirmed fact
  against whatever the agent is mid-way through is the agent's
  responsibility once woken, not something this feature defers for.
- The confirmation query itself fails, times out, or the provider is
  unreachable at the moment a notification is being confirmed. No journey
  state changes and the agent is not woken from this notification, and no
  special retry is required of this path specifically — the periodic
  reconciliation (User Story 4) independently covers the same journey
  regardless.
- Two notifications for the same journey — of the same or different
  declared event types — are being processed at close to the same time.
  Each is confirmed independently against the provider's interface; this
  feature does not assume they arrive, or must be confirmed, in any
  particular order relative to each other. If their confirmations would
  produce conflicting journey states, the one whose query observed the
  provider's state most recently governs, regardless of which one finished
  local processing first (feature 012's rule, adopted here).
- A periodic reconciliation sweep and a notification's own confirmation
  query for the same journey happen to run at close to the same time. Both
  are independent queries of the same underlying truth; neither is
  privileged over the other by source — the same most-recent-observed rule
  resolves them if they would conflict, exactly as it does between two
  notification-triggered confirmations.
- A third party, exploiting the channel's lack of authentication, submits
  a large volume of forged notifications for a single journey in a short
  window. Each still passes acknowledgement (FR-001) and full persistence
  (FR-002) individually, but the resulting confirmation-query volume for
  that journey is bounded (FR-013) rather than growing one-for-one with
  the flood — protecting the journey's, and the system's, provider call
  budget from being exhausted by an unauthenticated sender.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept inbound notifications at a publicly
  reachable endpoint and MUST acknowledge receipt promptly, without
  waiting for the notification's claim to be confirmed.

- **FR-002**: The system MUST persist every inbound notification in full,
  exactly as received, before taking any other action on it.

- **FR-003**: The system MUST treat every inbound notification as an
  untrusted assertion, on the basis that the channel carries no
  authentication of any kind.

- **FR-004**: The system MUST confirm the claim made by a notification
  against the provider's own interface, independently, before changing
  any journey state on the strength of that notification. When more than
  one confirmation for the same journey (from separate notifications, or
  from a notification and a periodic reconciliation sweep, per FR-010)
  would produce conflicting journey states, the confirmation whose query
  observed the provider's state most recently MUST govern, regardless of
  which one finished local processing first.

- **FR-005**: The system MUST route each notification according to the
  event type it declares. This feature MUST NOT assume the set of event
  types is fixed or fully known in advance.

- **FR-006**: The system MUST NOT interpret a notification's own status
  value as an indication of success or failure, under any circumstance.

- **FR-007**: The system MUST normalise field types that differ between a
  notification and the provider's query interface before comparing or
  acting on the values they represent.

- **FR-008**: The system MUST associate an inbound notification with a
  journey by the order reference it carries, and MUST discard any
  notification whose order reference matches no known journey, without
  further action.

- **FR-009**: The system MUST tolerate receiving the same notification
  more than once without producing more than one resulting action from
  it.

- **FR-010**: The system MUST periodically reconcile active journeys
  against the provider independently of whether any notification has been
  received for them, on the basis that notification delivery is not
  guaranteed.

- **FR-011**: The system MUST wake the agent for a journey only after a
  notification's claim concerning that journey has been confirmed — never
  on receipt of the notification alone.

- **FR-012**: The system MUST record a discrepancy whenever a
  notification's claim and its confirmation disagree about what happened,
  distinct from the ordinary case of a claim simply not yet being
  confirmed. The confirmed truth still governs journey state either way
  (FR-004); recording the discrepancy does not change that.

- **FR-013**: The system MUST bound the number of confirmation queries
  triggered against the provider for a single journey within a short time
  window, so that a burst of notifications for that journey — whether
  duplicates, distinct legitimate notifications, or a forged flood
  exploiting the channel's lack of authentication — collapses into a
  bounded number of confirmations rather than one per notification
  received.

### Non-Functional Requirements

- **NFR-001**: Acknowledgement of an inbound notification MUST NOT depend
  on the outcome, timing, or completion of the confirmation step for that
  notification.

- **NFR-002**: No inbound notification MUST be capable of causing a
  journey state change on the strength of its own assertion alone, under
  any configuration or condition.

### Key Entities

- **Inbound Notification**: The raw, untrusted message received at the
  endpoint. Carries a declared event type, an order reference, and
  whatever other fields the provider includes (including a status value
  that is recorded but never trusted, per FR-006). Persisted in full
  before anything else happens to it (FR-002), regardless of what is later
  discovered about its truth.

- **Confirmation**: The independent query of the provider's own interface
  that establishes what actually happened, in response to a notification's
  claim (FR-004). A notification's claim is never itself the confirmation.
  Carries the timestamp at which its query observed the provider's state;
  when confirmations for the same journey conflict, the one with the most
  recent observed timestamp governs, regardless of processing order
  (FR-004).

- **Journey Association**: The link, by order reference, between a
  notification and the one journey it concerns (FR-008). Its absence
  means the notification is discarded, not guessed at.

- **Reconciliation Sweep**: A periodic check of an active journey against
  the provider, run on its own schedule regardless of notification history
  (FR-010) — the safety net for a channel with no delivery guarantee.

- **Wake Signal**: The trigger that resumes the agent's processing for a
  specific journey, issued only once that journey's relevant claim has
  been confirmed (FR-011) — never issued directly from notification
  receipt.

- **Discrepancy**: The recorded fact that a notification's claim and its
  confirmation disagreed about what happened (FR-012). Not a resolution of
  which one was "right" — the confirmed truth always governs (FR-004) —
  but a preserved record that the disagreement happened, mirroring the
  same concept in Post-Action Verification (012).

- **Confirmation Budget Window**: The short time window per journey within
  which confirmation-query volume is bounded (FR-013), regardless of how
  many individual notifications for that journey arrive within it —
  distinct from the reconciliation interval (Reconciliation Sweep), which
  runs independently of notification volume altogether.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every notification sent to the endpoint in the test suite
  receives an acknowledgement before its confirmation step could have
  completed — 100%, with acknowledgement latency independent of
  confirmation latency.

- **SC-002**: Every notification accepted in the test suite is present in
  storage, in full and unmodified, before any routing or confirmation
  step is observed to begin — 100%.

- **SC-003**: Zero instances, across the test suite, of a journey's state
  changing without a preceding, independently confirmed query for that
  specific claim.

- **SC-004**: Zero instances, across the test suite, of a notification's
  own status value being used as the basis for any success/failure
  determination.

- **SC-005**: Every notification in the test suite carrying a field in a
  type inconsistent with the query interface's reporting of the same
  value is normalised before any comparison is made — 100%, zero
  false-positive or false-negative comparisons attributable to type
  mismatch.

- **SC-006**: Every notification in the test suite whose order reference
  matches no known journey is discarded with zero effect on any journey —
  100%.

- **SC-007**: Sending the same notification any number of times in the
  test suite never produces more than one resulting action — 100% of
  repeated-delivery scenarios.

- **SC-008**: Every active journey in the test suite is reconciled against
  the provider at least once within its defined reconciliation interval,
  regardless of whether it ever received a notification — 100%.

- **SC-009**: Zero instances, across the test suite, of the agent being
  woken for a journey before that journey's relevant claim was
  independently confirmed.

- **SC-010**: When two confirmations for the same journey in a test
  scenario would produce conflicting journey states, the resulting state
  always matches the confirmation with the more recent observed
  timestamp, 100% of the time — including scenarios where that
  confirmation finishes local processing after the other one.

- **SC-011**: Every test scenario in which a notification's claim and its
  confirmation disagree produces a recorded discrepancy — 100%, none
  silently dropped once the confirmed truth is known.

- **SC-012**: In every test scenario that sends a burst of notifications
  for a single journey within the confirmation budget window, the number
  of confirmation queries triggered stays bounded rather than scaling
  one-to-one with notification volume — 100%, including bursts
  constructed entirely of forged notifications.

---

## Out of Scope

- Simulating events — generating notifications for demonstration or
  testing is a separate capability (feature 008) that sends into this
  receiver, not this feature's own concern
- Evaluating the impact of a confirmed change on the traveller's objective
  — this feature establishes what is true and wakes the agent; deciding
  what a confirmed change means for the objective is the agent's and
  scoring's concern
- Searching for alternatives in response to a confirmed change — a
  separate capability the woken agent may invoke, not this feature's
  concern
- Recovery — deciding or executing what should happen as a result of a
  confirmed adverse change (rebooking, refund, void) is out of scope; this
  feature's responsibility ends at waking the agent with a confirmed fact

---

## Assumptions

- The only event type verified in live production so far is
  `order.ticketed` (captured 2026-08-15, `.antabay/atlas-capability-map.md`
  §7c); other types (a schedule-change event is explicitly anticipated)
  are expected to follow the same dotted-string `type` convention but are
  not yet enumerated. FR-005's routing is therefore keyed on whatever
  `type` value arrives, not a closed, pre-registered list.
- "Confirm the claim... against the provider's own interface" (FR-004) is
  the same independent-verification discipline this project already
  applies to its own actions (see Post-Action Verification): this feature
  is what triggers that discipline in response to an external,
  unauthenticated notification, rather than redefining what "confirmed"
  means.
- "Wake the agent" (FR-011) means resuming the agent's own processing for
  the affected journey; what the agent does once woken is outside this
  feature.
- The order reference a notification carries is the same opaque identifier
  already used elsewhere in this system to key a journey, and is preserved
  unmodified when used to look up the journey it belongs to — consistent
  with this project's general identifier-integrity convention.
- A notification's own status value has no meaning across different event
  types or even within one (the capture in §7c shows `status: -1` on a
  successful `order.ticketed` event) — FR-006's prohibition is treated as
  categorical, not merely a default to be overridden once a status
  encoding is better understood.
- The reconciliation interval (FR-010) is a tunable operational parameter,
  not a fixed value this specification mandates; it is chosen to be
  frequent enough that a missed notification is discovered before it could
  cause customer-facing harm, consistent with this project's general
  preference (established for held-identifier freshness) for checking
  earlier rather than at the last safe moment.
- The confirmation budget window (FR-013) is likewise a tunable operational
  parameter, distinct from the reconciliation interval — it bounds
  burst-driven confirmation volume per journey, not the baseline sweep
  cadence — and is chosen short enough to collapse a genuine flood while
  still confirming any single legitimate notification promptly.
- A notification for a journey that has already reached a terminal state
  is persisted (FR-002 is unconditional) but does not trigger confirmation
  or a wake, since there is no active processing left for it to resume.
