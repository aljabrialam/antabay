# Antabay — All Thirteen Specs

Complete set, in execution order. Every block is paste-ready.

**Grounded in verified data.** Every endpoint, field, error code, and clock
below was observed in a real Atlas sandbox response. See
`.antabay/atlas-capability-map.md`.

---

# SETUP — do this first

## 1. Create the repo

```bash
mkdir -p ~/Documents/antabay && cd ~/Documents/antabay
git init
```

## 2. Initialise Spec Kit

```bash
specify init . --ai qodercli
specify check          # must show: Qoder CLI (available)
```

If your Spec Kit is newer and rejects `--ai`, use:

```bash
specify init . --integration qodercli
```

## 3. Create the folders

```bash
mkdir -p .antabay fixtures/atlas
```

## 4. Gitignore FIRST

Your Atlas credentials are inside the newman reports. Do this before any
`git add`.

```bash
cat > .gitignore <<'EOF'
.env
.env.*
report*.html
events/
__pycache__/
node_modules/
*.pyc
.DS_Store
EOF
```

## 5. Environment file

```bash
cat > .env <<'EOF'
ATLAS_BASE_URL=https://sandbox.atriptech.com
ATLAS_CLIENT_ID=ZVM98377_api_1
ATLAS_CLIENT_SECRET=sandbox-sk-ZVM98377_api_1
DASHSCOPE_API_KEY=
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=qwen-plus
EOF
```

Paste your DashScope key in. Keep `dashscope-intl` — that is Singapore.
The Beijing endpoint has no free quota and bills from the first token.

## 6. Copy the context documents in

Adjust the source path if your downloads are elsewhere.

```bash
cd ~/Documents/antabay
cp ~/Downloads/constitution.md                    .antabay/constitution.md
cp ~/Downloads/atlas-capability-map.md            .antabay/atlas-capability-map.md
cp ~/Downloads/demo-scenario.md                   .antabay/demo-scenario.md
cp ~/Downloads/antabay-architecture-diagrams.md   .antabay/architecture.md
cp ~/Downloads/demo-sequence-diagram.md           .antabay/demo-sequence.md
cp ~/Downloads/antabay-all-specs.md               .antabay/specs.md
cp ~/Downloads/antabay-48h-execution-plan.md      .antabay/plan.md
cp ~/Downloads/antabay-console-mockup.html        .antabay/console-mockup.html

ls -la .antabay/      # expect 8 files
open .antabay/console-mockup.html                 # look at what you are building
```

| Source | Lands at | Purpose |
|---|---|---|
| `constitution.md` | `.antabay/constitution.md` | governing rules |
| `atlas-capability-map.md` | `.antabay/atlas-capability-map.md` | **the verified contract** |
| `demo-scenario.md` | `.antabay/demo-scenario.md` | locked scenario, real data |
| `antabay-architecture-diagrams.md` | `.antabay/architecture.md` | architecture + state machine |
| `demo-sequence-diagram.md` | `.antabay/demo-sequence.md` | video storyboard |
| `antabay-all-specs.md` | `.antabay/specs.md` | this file |
| `antabay-48h-execution-plan.md` | `.antabay/plan.md` | fallback plan if behind |
| `antabay-console-mockup.html` | `.antabay/console-mockup.html` | **visual reference — the build target** |

## 7. Copy the fixtures in, redacted

Run this from wherever your captured JSON lives (`~/Documents/atlas`).

```bash
cd ~/Documents/atlas

python3 - <<'PY'
import json, glob, os
SECRET = {"routingIdentifier","sessionId","orderNo","offerId","OfferId","fid",
          "pnr","pnrCode","ticketNo","ticketNos","airlinePNRs","token","cid",
          "apiKey","secret","accessToken","email","phone","mobile",
          "firstName","lastName","name","cardNum","cardNumber","cardExpired",
          "passportNo","documentNo","birthday","dateOfBirth"}
def red(o):
    if isinstance(o, dict):
        return {k: ("<REDACTED>" if k in SECRET else red(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [red(x) for x in o[:3]]
    return o
out = os.path.expanduser("~/Documents/antabay/fixtures/atlas")
os.makedirs(out, exist_ok=True)
for f in ["sel_tyo_search.json", "sel_tyo_verify.json"] + sorted(glob.glob("events/*.json")):
    if not os.path.exists(f):
        print("skip", f); continue
    name = "webhook_order_ticketed.json" if f.startswith("events/") else os.path.basename(f)
    json.dump(red(json.load(open(f))), open(f"{out}/{name}", "w"), indent=2)
    print("wrote", name)
PY
```

These three fixtures are the seed for recorded tests. Per the
constitution, fixtures come from live runs and are never handwritten.

## 8. Qoder setup

```bash
cd ~/Documents/antabay
qodercli plugins install better-harness
qodercli wiki
```

`better-harness` grades your agent setup and produces the report that
"Use of Qoder" scores on. `wiki` writes to `.qoder/repowiki` and is
citable evidence. Run `wiki` again before submission.

## 9. First commit — check before you push

```bash
git add -A
git status              # .env and report*.html must NOT be listed
git commit -m "chore: repo init, spec kit, verified Atlas contract, context docs"
```

If `.env` appears in `git status`, stop and fix `.gitignore` before
committing.

## 10. Open Qoder and paste the constitution

```bash
qodercli
```

Paste the `/speckit.constitution` block from
`antabay-speckit-run-sheet.md`, then start with **000** below.

---

# DESIGN REFERENCE

`.antabay/console-mockup.html` is the visual target. Open it before
building anything in specification 006, and build against it rather than
inventing a layout.

**Design language: the airline operations flight strip.** Ops control
rooms move one paper strip per flight between racks as its state changes.
That is the journey state machine. Paper ground, ink-blue text, typed
monospace data, hairline rules, square corners.

**Palette — fixed. Colour carries meaning, never decoration.**

| Token | Hex | Means |
|---|---|---|
| paper | `#E4E2DC` | ground |
| strip | `#FAF9F7` | a record |
| ink | `#141A21` | text, current state |
| rule | `#C2BEB5` | division |
| hold amber | `#B0700F` | attention, awaiting authority |
| violation red | `#9E2B1C` | constraint broken |
| confirmation blue | `#1B5A87` | verified |
| simulation violet | `#6B3FA0` | not provider-originated |

**Type.** Archivo for interface text. JetBrains Mono for every value that
came from Atlas — times, prices, identifiers, endpoints. If it is data, it
is monospace.

**Layout.** Three columns: objective and state rack on the left, agent
trace in the centre, expiry clocks and the authorisation gate on the
right, with the traveller surface beneath them. Collapses to one column
below 1100px, which is what makes the traveller view nearly free.

**The signature element is the expiry clocks.** All three permanently
visible with time remaining and a depleting bar. A spent clock is shown
spent, not hidden.

**Exactly three moments carry visual weight** — coloured left rule, extra
room, more lines:

1. The rejection of an option that arrives in time and is within budget
2. The statement that the objective is violated
3. The authorisation gate

Everything else in the trace is uniform and quiet.

**Every decision is shown with its reason.** Rejections name the
constraint violated. Policy decisions cite the rule identifier in the
interface.

**Two densities, one event stream.** The console cites endpoints,
identifiers, timings and rule names. The traveller surface says "Your
10:00 meeting is at risk" and shows none of it.

**Provenance is permanent.** Sandbox status, reasoning model, and any
active simulation sit in a footer that is always on screen.

**Legibility at video scale is a requirement.** The interface is assessed
as a recording viewed small. Anything unreadable at reduced size is
redesigned or removed.

---

# WORKING RULES

Everything that produces a file goes through `qodercli`. The 80%
eligibility threshold is measured by credit consumption and is
all-or-nothing on the 8-point Qoder category. Hand-written patches reduce
the numerator and produce no evidence.

Route models deliberately — Lite or Efficient for scaffolding, higher
tiers only for reasoning-heavy work. "Core flow does not depend on
top-tier models" is a scored Cost Controllability point. Off-peak runs
14:00–00:00 UTC.

Commit after every spec. One spec, one commit, one demonstrable
capability.


---

## How to run these

Full cycle per spec:

```
/speckit.specify   → /speckit.clarify  → /speckit.plan
→ /speckit.tasks   → /speckit.analyze  → /speckit.implement
```

Short cycle, when time is tight — drop `clarify` and `analyze`:

```
/speckit.specify → /speckit.plan → /speckit.tasks → /speckit.implement
```

Everything producing a file goes through `qodercli`. The 80% eligibility
threshold is measured by credit consumption and is all-or-nothing on the
8-point Qoder category.

---

## Delivery order and stop lines

Build in this order. Each line marks what you have if you stop there.

| Order | Spec | If you stop here |
|---|---|---|
| 1 | 000 Atlas capability contract | nothing runs, but nothing is invented |
| 2 | 001 Journey + objective model | a goal becomes a durable journey |
| 3 | 002 Flight search | real options from real Atlas |
| 4 | 003 Option scoring | **the agent chooses and defends it** |
| 5 | 006 Console + trace | **visible. First point at which a demo exists** |
| 6 | 004 Price verification | committing safely |
| 7 | 005 Booking path | **a real ticket. Half a demo** |
| 8 | 012 Post-action verification | paid ≠ ticketed, proven |
| 9 | 010 Authorisation policy | **human authority. Core differentiator** |
| 10 | 007 Webhook receiver | real events arrive and get verified |
| 11 | 008 Disruption injector | the disruption fires |
| 12 | 009 Impact + alternatives | the agent knows the objective broke |
| 13 | 011 Recovery execution | **complete journey. Full demo** |
| 14 | 013 Traveller mobile view | not scored — only if 1–13 are done and deployed |

**Minimum viable submission: through 011.** Everything before it is
partial and Demo Completeness scores 4/2/0 with no partial credit.

**If you are behind at any point, stop adding and switch to the merged
four-spec plan in `.antabay/plan.md`.** It contains the same capabilities
with one quarter of the ceremony.

---

# 000 — Atlas Capability Contract

```
/speckit.specify

Create a Feature Specification.

Feature ID
000-atlas-capability-contract

Feature Name
Atlas Capability Contract

Business Goal
Give the system a single, enforced definition of what the travel API can
do, so no other feature can call an endpoint or read a field that has not
been verified to exist.

Business Value
The primary failure mode of AI-assisted integration work is confidently
invented endpoints and field names. This feature makes that failure
impossible to commit.

Business Actors
Developer
Continuous integration pipeline

Business Capability
External Contract Governance

Reference
.antabay/atlas-capability-map.md records the verified contract and is the
input to this feature. This specification governs how it is enforced.

Functional Requirements

FR-001 The system shall maintain a machine-readable declaration of every
external travel endpoint it is permitted to call.

FR-002 The system shall reject, at build time, any attempt to call an
endpoint not present in that declaration.

FR-003 The system shall define a typed representation of each verified
request and response shape.

FR-004 The system shall preserve every externally issued identifier
without modification, and shall provide no means of constructing, parsing,
or altering one.

FR-005 The system shall define a single canonical total-price calculation
and shall not permit price totals to be computed elsewhere.

FR-006 The system shall normalise fields whose type differs between the
external API and its event notifications, so that downstream code sees one
consistent type.

FR-007 The system shall classify every known external error code as
retryable, reconcilable, or terminal, and shall expose that
classification.

FR-008 The system shall treat a duplicate-booking rejection as
reconcilable, and shall surface the existing order reference returned with
it.

FR-009 The system shall record, for every external call, the endpoint, the
outcome, and the elapsed time.

FR-010 The system shall enforce a declared call budget per journey for
rate-limited endpoints.

FR-011 The system shall honour a wait instruction returned with a
rate-limit rejection and shall not retry before it elapses.

FR-012 The system shall track, for each held offer or session, the time it
was issued and the time it becomes unusable.

Non-Functional Requirements

Any endpoint or field not present in the verified contract shall cause a
build failure, not a runtime error.

Contract tests shall run in continuous integration on every change.

Recorded fixtures used by tests shall be captured from live sandbox runs.
Handwritten fixtures are prohibited.

Out of Scope
Agent reasoning
Journey state
Any specific booking or recovery workflow
User interface

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 000-atlas-capability-contract.

Identify missing requirements, ambiguous wording, business assumptions,
missing validation rules, missing error handling, missing non-functional
requirements, and missing acceptance criteria.

Give particular attention to:
- A response contains a field not in the verified contract.
- A response omits a field the contract marks as present.
- The same logical field arrives as an integer from one surface and a
  string from another.
- An error code is returned that is not in the classification.
- An identifier is longer than expected or contains characters that look
  like structure.
- A held offer expires between being read and being acted on.
- The call budget for a journey is exhausted mid-decision.
- A recorded fixture no longer matches what the live sandbox returns.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 001 — Journey and Objective Model

```
/speckit.specify

Create a Feature Specification.

Feature ID
001-journey-objective-model

Feature Name
Journey and Objective Model

Business Goal
Turn a traveller's stated goal into a durable, structured objective that
the system can protect for the life of the journey.

Business Value
Everything later — scoring options, deciding whether a disruption matters,
judging whether recovery is worth its cost — is measured against this
objective. Without it, the product is a search box.

Business Actors
Traveller

Business Capability
Objective Management

Functional Requirements

FR-001 The system shall accept a travel goal stated in natural language.

FR-002 The system shall extract from that goal a structured objective
containing origin, destination, latest acceptable arrival time, budget with
currency, number of travellers, and stated preferences.

FR-003 The system shall classify each extracted element as either a hard
constraint or a soft preference, and shall record that classification.

FR-004 The system shall present the parsed objective to the traveller for
confirmation before any downstream action is taken.

FR-005 The system shall identify elements that were absent or ambiguous in
the stated goal and shall ask the traveller rather than infer a value.

FR-006 The system shall create a journey record with a unique identifier,
the confirmed objective, and an initial state.

FR-007 The system shall maintain a journey state and shall permit only
defined transitions between states.

FR-008 The system shall persist journey state in durable storage such that
the journey can be fully reconstructed after the process handling it has
terminated.

FR-009 The system shall record, for each externally issued identifier it
holds, the time it was issued and the time at which it should be
considered stale.

FR-010 The system shall maintain an append-only audit trail for each
journey, recording observations, decisions, external calls, and
authorisations, each with a timestamp.

FR-011 The system shall expose the current journey state, objective, and
audit trail for display.

FR-012 The system shall record the outcome of every authorisation request,
including refusals.

Objective Information
Origin, destination, latest acceptable arrival time, budget amount and
currency, number of travellers, stated preferences, hard-versus-soft
classification per element.

Journey Information
Journey identifier, current state, confirmed objective, held external
identifiers with issue and staleness times, audit trail, authorisation
history.

Non-Functional Requirements

The journey record shall be the single source of truth for journey state.
No journey state required for correctness shall reside only in a language
model context window or in process memory.

The audit trail shall be append-only.

The system shall not author, infer, or default any travel fact. Absent
information shall be requested, not assumed.

Objective parsing shall be reproducible: the same stated goal shall produce
the same structured objective.

Out of Scope
Flight search, option scoring, price verification, booking and payment,
disruption monitoring, recovery. The authorisation policy engine is a
separate feature, referenced here only as the producer of authorisation
outcomes.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 001-journey-objective-model.

Identify missing requirements, ambiguous wording, business assumptions,
missing validation rules, missing error handling, missing non-functional
requirements, and missing acceptance criteria.

Give particular attention to:
- A goal with no budget.
- A goal with no deadline.
- A relative deadline such as "tomorrow morning" resolved against a
  timezone.
- A deadline stated in the destination timezone while the traveller is in
  another.
- A budget in one currency and travel priced in another.
- A stated goal that is not a travel request at all.
- A stated goal containing two conflicting constraints.
- The traveller corrects the parsed objective rather than confirming it.
- The traveller abandons the journey before confirming.
- A journey rehydrated after a long gap with all held identifiers stale.
- A journey reaching a state from which no valid transition exists.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 002 — Flight Search

```
/speckit.specify

Create a Feature Specification.

Feature ID
002-flight-search

Feature Name
Flight Search

Business Goal
Retrieve real travel options matching the traveller's objective, from the
verified external provider.

Business Value
Every downstream decision rests on real inventory. Fabricated or stale
options make every later capability worthless.

Business Actors
Traveller
Agent

Business Capability
Inventory Discovery

Reference
.antabay/atlas-capability-map.md sections 3, 4 and 7.

Functional Requirements

FR-001 The system shall search for travel options using the origin,
destination, date, and traveller count taken from the confirmed objective.

FR-002 The system shall request results in the objective's currency.

FR-003 The system shall record, for every returned option, the identifier
required to act on it, preserved unmodified.

FR-004 The system shall record, for every returned option, the time it was
priced and the time it becomes unusable.

FR-005 The system shall treat a returned option as already partially aged,
and shall compute remaining usable time from the current time rather than
from receipt.

FR-006 The system shall report the number of options returned and the
carriers represented.

FR-007 The system shall distinguish single-leg options from multi-leg
options.

FR-008 The system shall record, for every returned option, available
scarcity and sell-out risk indicators.

FR-009 The system shall count every search against the journey's call
budget.

FR-010 The system shall handle a result set containing no options without
error, and shall state that no options were returned.

FR-011 The system shall not modify, enrich, or supplement any returned
travel fact.

Non-Functional Requirements

Search responses shall be persisted in full for audit and for use as test
fixtures.

The system shall respect the provider's documented request rate and shall
not retry after a rate-limit rejection before the instructed interval has
elapsed.

Out of Scope
Scoring, selection, verification, booking, and any presentation of results.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 002-flight-search.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The search returns zero options.
- The search returns options that are already expired on arrival.
- The provider returns a rate-limit rejection.
- The provider returns a success status with a malformed body.
- The requested currency is not honoured in the response.
- The route requested is not served by the provider at all.
- A returned option omits a scarcity indicator.
- The response is large enough to affect processing time.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 003 — Option Scoring Against Objective

```
/speckit.specify

Create a Feature Specification.

Feature ID
003-option-scoring

Feature Name
Option Scoring Against Objective

Business Goal
Choose the travel option that best serves the traveller's stated
objective, and explain the choice in terms the traveller can check.

Business Value
This is where the product stops being a search box. A ranked list is not a
decision. The traveller gave an objective, so the system must select
against that objective and defend the selection.

Business Actors
Traveller

Business Capability
Objective-Based Selection

Functional Requirements

FR-001 The system shall evaluate every returned option against the
traveller's confirmed objective.

FR-002 The system shall eliminate any option that violates a hard
constraint, and shall record which constraint each eliminated option
violated.

FR-003 The system shall rank the remaining options using the traveller's
stated preferences.

FR-004 The system shall evaluate arrival time against the traveller's
deadline and shall express the result as the margin between them.

FR-005 The system shall evaluate total cost using the single canonical
price calculation.

FR-006 The system shall treat an option comprising more than one leg as a
connection, and shall compute the connection time between consecutive
legs.

FR-007 The system shall treat a connection as unacceptable when the
traveller has excluded connections of that kind, regardless of whether the
option satisfies arrival time and cost.

FR-008 The system shall incorporate available scarcity and sell-out risk
signals into its evaluation.

FR-009 The system shall produce, for the selected option, a stated
rationale naming the objective elements satisfied.

FR-010 The system shall produce, for each rejected option that would
otherwise have ranked highly, a stated reason for rejection.

FR-011 The system shall report when no option satisfies all hard
constraints, and shall state which constraints could not be satisfied
together.

FR-012 The system shall not select an option whose held offer has already
expired.

FR-013 The system shall express every scoring input in the objective's
currency and time reference, and shall not combine values expressed in
different currencies.

Non-Functional Requirements

Scoring shall be deterministic. The same option set and the same objective
shall produce the same selection and the same rationale.

Scoring shall be explainable in a single short paragraph a non-technical
traveller can verify against the option data.

The scoring function shall not consume any travel fact that did not come
from a verified external response.

Out of Scope
Searching, verifying prices, booking, authorisation, recovery.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 003-option-scoring.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- An option arrives before the deadline but only by departing the previous
  evening and spending ten hours in an intermediate airport.
- An option satisfies arrival time and cost but violates a preference the
  traveller expressed loosely.
- Two options are equivalent on every scored dimension.
- Every option violates at least one hard constraint.
- Only one option satisfies the objective and it has one seat remaining.
- Arrival and departure times are in different local timezones.
- Fare amounts and fee amounts are in different currencies.
- The cheapest option arrives with a two-minute margin.
- An option is flagged as at risk of selling out.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 006 — Agent Trace and Journey Console

*Built before booking. It is the debugging surface for everything that
follows, and the surface on which the product is assessed.*

```
/speckit.specify

Create a Feature Specification.

Feature ID
006-agent-trace-console

Feature Name
Agent Trace and Journey Console

Business Goal
Make the agent's behaviour observable in real time, to a person watching a
screen, without reading logs.

Business Value
Three purposes at once: the primary debugging surface during development,
the artifact by which the product is judged, and a recorded output that
drives demonstrations without live network access.

Business Actors
Traveller
Observer

Business Capability
Observability

Functional Requirements

FR-001 The system shall present the traveller's objective as structured
elements, distinguishing hard constraints from preferences.

FR-002 The system shall present the current journey state and the
identifiers currently held.

FR-003 The system shall present, for each held identifier, the time
remaining before it becomes unusable.

FR-004 The system shall emit an observable event for every external call,
stating the endpoint, the outcome, and the elapsed time.

FR-005 The system shall emit an observable event for every decision,
stating what was decided and why.

FR-006 The system shall stream these events to the interface as they
occur, without the interface polling for them.

FR-007 The system shall present the remaining call budget for the journey.

FR-008 The system shall present an authorisation request when one is
outstanding, stating the action, its cost, and its effect on the
objective.

FR-009 The system shall present the outcome of every authorisation
request, including refusals.

FR-010 The system shall visually distinguish simulated events from events
received from the external provider.

FR-011 The system shall record a complete event stream for a journey to
durable storage.

FR-012 The system shall replay a recorded event stream through the same
interface, at a controllable pace, without contacting any external
service.

FR-013 The system shall hold no state of its own in the interface; the
interface shall render only what the event stream provides.

FR-014 The system shall present the expiry clocks persistently, each with
its time remaining and a proportional indicator, and shall show a spent
clock as spent rather than removing it.

FR-015 The system shall give visual emphasis to exactly three classes of
event: the rejection of an option that satisfies the traveller's numeric
constraints, the determination that the objective is violated, and an
outstanding authorisation request. All other events shall be presented
uniformly.

FR-016 The system shall present, alongside every rejection, the constraint
that was violated, and alongside every authorisation decision, the
identifier of the rule that produced it.

FR-017 The system shall present the journey state as an ordered sequence
showing completed, current, and pending states.

FR-018 The system shall present provenance persistently: the environment
in use, the reasoning model, and whether any simulated event is active.

FR-019 The system shall render values originating from the travel provider
in a typeface visually distinct from interface text.

Non-Functional Requirements

The interface shall be legible when recorded as video and viewed at
reduced size.

The interface shall follow the visual reference at
.antabay/console-mockup.html. The palette is fixed and colour shall carry
meaning rather than decoration.

The interface shall require no more than three human interactions during a
complete journey.

Replay shall be indistinguishable from live operation in appearance, and
shall be clearly labelled as replay.

Recorded event streams shall be usable as fixtures by the test suite.

Out of Scope
Agent reasoning, external API integration, authentication, multiple
concurrent journeys, the traveller-facing mobile surface.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 006-agent-trace-console.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- Events arrive faster than a human can read them.
- An external call takes long enough that the interface appears frozen.
- The event stream disconnects mid-journey and reconnects.
- A held identifier expires while displayed on screen.
- An authorisation request is outstanding and the observer walks away.
- A recorded stream is replayed after the underlying data has changed.
- The journey ends in failure rather than success.
- Two events are emitted with the same timestamp.
- A simulated event and a real event arrive close together.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 004 — Price Verification and Staleness

```
/speckit.specify

Create a Feature Specification.

Feature ID
004-price-verification

Feature Name
Price Verification and Offer Staleness

Business Goal
Confirm that a selected option is still available at the stated price
before any commitment is made, and manage the shifting freshness windows
that govern how long a held position remains usable.

Business Value
Offers age faster than they appear to. Committing on a stale offer means
booking something the traveller did not agree to, at a price they did not
approve.

Business Actors
Agent

Business Capability
Commitment Safety

Reference
.antabay/atlas-capability-map.md section 7a.

Functional Requirements

FR-001 The system shall verify the selected option before creating any
order.

FR-002 The system shall pass the option's identifier unmodified when
verifying.

FR-003 The system shall read the provider's own price-change indicator
rather than comparing prices itself.

FR-004 The system shall treat a reported price change as invalidating any
authorisation previously granted for that option.

FR-005 The system shall record the session identifier returned by
verification and shall preserve it unmodified.

FR-006 The system shall recognise that the offer-level freshness window is
replaced by a session-level window once verification succeeds, and shall
track each separately.

FR-007 The system shall record the passenger field requirements returned
at verification time and shall use them rather than a fixed set.

FR-008 The system shall record the maximum bookable quantity returned at
verification time.

FR-009 The system shall return the journey to search when verification
reports the option is no longer available.

FR-010 The system shall re-verify rather than proceed when the held
position is closer to expiry than a declared safety margin.

FR-011 The system shall count every verification against the journey's
call budget.

Non-Functional Requirements

The system shall prefer re-verifying earlier than the documented expiry
rather than at it, because inventory and price can change first.

Verification responses shall be persisted in full for audit.

Out of Scope
Searching, scoring, order creation, payment, authorisation policy.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 004-price-verification.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The verified price is higher than the price shown to the traveller.
- The verified price is lower.
- Verification succeeds but returns fewer bookable seats than requested.
- The offer expires between selection and verification.
- Verification returns a session that expires before the order is created.
- The passenger requirements returned differ from those previously seen.
- Verification times out with an unknown outcome.
- The same option is verified twice.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 005 — Booking Path

```
/speckit.specify

Create a Feature Specification.

Feature ID
005-booking-path

Feature Name
Order Creation and Payment

Business Goal
Convert a verified option into a booked and ticketed journey, without ever
assuming an outcome that has not been independently confirmed.

Business Value
This is where money moves and where mistakes are irreversible. Duplicate
orders and false confirmations are the two failures that matter.

Business Actors
Traveller
Agent

Business Capability
Transaction Execution

Reference
.antabay/atlas-capability-map.md section 7b.

Functional Requirements

FR-001 The system shall create an order using the session identifier from
verification, preserved unmodified.

FR-002 The system shall populate passenger and contact details according to
the requirements returned at verification time.

FR-003 The system shall record the order reference and any booking
reference returned.

FR-004 The system shall not treat a booking reference as evidence that a
ticket has been issued.

FR-005 The system shall record the ticketing deadline returned with the
order and shall track it as a distinct expiry.

FR-006 The system shall detect a duplicate-order rejection, read the
existing order reference returned with it, query that order, and resume
from its actual state.

FR-007 The system shall never repeat an order creation or payment whose
outcome is uncertain.

FR-008 The system shall submit payment only after an order has been
successfully created.

FR-009 The system shall not treat a successful payment response as
evidence that a ticket has been issued.

FR-010 The system shall query the order independently after payment and
shall treat the presence of issued ticket numbers as the only evidence of
ticketing.

FR-011 The system shall continue querying until ticketing is confirmed,
the ticketing deadline passes, or a terminal error is returned.

FR-012 The system shall transition the journey to monitoring only once
ticketing is confirmed.

Non-Functional Requirements

Every state-changing call shall be followed by an independent read before
journey state is updated.

Order and payment responses shall be persisted in full for audit.

Out of Scope
Searching, scoring, verification, authorisation policy, monitoring,
recovery.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 005-booking-path.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- Order creation returns a duplicate rejection naming an existing order.
- Order creation times out with no response.
- Payment succeeds but ticketing never completes before the deadline.
- Payment is declined.
- The session expires between verification and order creation.
- The order query returns a status not previously observed.
- Ticket numbers appear for some passengers but not others.
- The ticketing deadline passes while the query loop is running.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 012 — Post-Action Verification

```
/speckit.specify

Create a Feature Specification.

Feature ID
012-post-action-verification

Feature Name
Post-Action Verification

Business Goal
Establish independently, after every state-changing action, what actually
happened, and update journey state only from that.

Business Value
Confirmed twice in live testing: a successful payment response does not
mean a ticket exists. An agent that trusts its own writes will report
success that did not occur.

Business Actors
Agent

Business Capability
Truth Reconciliation

Functional Requirements

FR-001 The system shall follow every state-changing external call with an
independent query of the affected record.

FR-002 The system shall update journey state only from the result of that
query, never from the response to the action itself.

FR-003 The system shall define, for each action type, the specific
observable condition that constitutes success.

FR-004 The system shall treat the presence of issued ticket numbers as the
only evidence of ticketing.

FR-005 The system shall record any discrepancy between the response to an
action and the state subsequently observed.

FR-006 The system shall treat an unverifiable outcome as unresolved rather
than as either success or failure.

FR-007 The system shall reconcile an unresolved outcome by query, and
shall never resolve it by repeating the action.

FR-008 The system shall normalise status values whose type differs between
the query interface and event notifications before comparing them.

FR-009 The system shall record every verification attempt and result in
the journey audit trail.

FR-010 The system shall report to the traveller only outcomes that have
been independently verified.

Non-Functional Requirements

Verification shall be expressed in terms of externally observable state,
never in terms of the system's own return values.

Out of Scope
The actions themselves, authorisation policy, presentation.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 012-post-action-verification.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The action succeeded but the verifying query fails.
- The verifying query returns a state inconsistent with the action.
- Verification succeeds only after several attempts.
- The record disappears entirely.
- Two actions affecting the same record are verified concurrently.
- A status value arrives in a type not previously seen.
- Verification is still unresolved when the traveller asks for status.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 010 — Authorisation Policy Engine

```
/speckit.specify

Create a Feature Specification.

Feature ID
010-authorisation-policy

Feature Name
Authorisation Policy Engine

Business Goal
Decide, deterministically, whether a proposed action may be executed
autonomously or requires explicit human authorisation.

Business Value
The system spends the traveller's money and cancels the traveller's
tickets. The boundary of its authority must be a rule that cannot be
reasoned around, argued with, or persuaded. This is what makes autonomous
operation safe enough to permit at all.

Business Actors
Traveller
Agent

Business Capability
Authority Control

Functional Requirements

FR-001 The system shall evaluate every proposed action before it is
executed.

FR-002 The system shall classify a proposed action as permitted
autonomously or as requiring human authorisation.

FR-003 The system shall require human authorisation for any action that
spends money.

FR-004 The system shall require human authorisation for any action that
cancels or voids a booking.

FR-005 The system shall require human authorisation for any action that
cannot be reversed.

FR-006 The system shall require human authorisation for any action that
would breach a stated hard constraint.

FR-007 The system shall reach its decision without consulting a language
model.

FR-008 The system shall produce, with each decision, the specific rule
that determined it.

FR-009 The system shall present an authorisation request stating the
proposed action, its cost relative to the current position, and its effect
on the traveller's objective.

FR-010 The system shall treat absence of a response as refusal.

FR-011 The system shall record every authorisation decision, including
refusals and non-responses, in the journey audit trail.

FR-012 The system shall prevent execution of any action for which
authorisation was required and not granted.

FR-013 The system shall void a prior authorisation when the cost of the
authorised action has changed since it was granted.

FR-014 The system shall treat an authorisation as applying to one specific
action only, and shall not carry it forward to a subsequent action.

Non-Functional Requirements

The decision shall be deterministic. The same proposed action in the same
journey context shall always produce the same classification.

The rule set shall be readable by a non-engineer.

No configuration, prompt, or input shall be capable of causing an action
requiring authorisation to execute without it.

Every rule shall be individually testable in isolation, in both the
granting and the refusing direction.

Out of Scope
Executing the action, searching for alternatives, scoring options, the
user interface presenting the request.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 010-authorisation-policy.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The proposed action costs nothing but cancels an existing booking.
- The proposed action saves money relative to the current position.
- The traveller authorises, and the price changes before execution.
- The traveller refuses, and the objective then becomes unachievable.
- The traveller does not respond and a deadline passes.
- Two actions require authorisation at the same time.
- The action is a compensating step after a failure.
- The only compliant option costs more than the stated budget.
- An authorised action fails partway through execution.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 007 — Webhook Receiver and Reconciler

```
/speckit.specify

Create a Feature Specification.

Feature ID
007-webhook-receiver

Feature Name
Event Reception and Reconciliation

Business Goal
Receive change notifications from the travel provider, establish whether
each one is true, and wake the agent when it is.

Business Value
This is what makes the product continuous rather than transactional. It is
also the point of highest risk: the notification channel is
unauthenticated and delivery is not guaranteed.

Business Actors
Travel provider
Agent

Business Capability
Event Ingestion

Reference
.antabay/atlas-capability-map.md section 7c records a captured live event.

Functional Requirements

FR-001 The system shall accept inbound notifications at a publicly
reachable endpoint and shall acknowledge receipt promptly.

FR-002 The system shall persist every inbound notification in full before
acting on it.

FR-003 The system shall treat every inbound notification as an untrusted
assertion, on the basis that the channel carries no authentication.

FR-004 The system shall confirm the claim made by a notification against
the provider's own interface before changing any journey state.

FR-005 The system shall route on the notification's declared event type.

FR-006 The system shall not interpret the notification's status value as
an indication of success or failure.

FR-007 The system shall normalise field types that differ between
notifications and the query interface.

FR-008 The system shall associate a notification with a journey by the
order reference it carries, and shall discard notifications that match no
known journey.

FR-009 The system shall tolerate duplicate notifications without
duplicating any resulting action.

FR-010 The system shall periodically reconcile active journeys against the
provider independently of any notification, on the basis that delivery is
not guaranteed.

FR-011 The system shall wake the agent only after a notification's claim
has been confirmed.

Non-Functional Requirements

Acknowledgement shall not depend on the outcome of verification.

No inbound notification shall be capable of causing a state change on its
own assertion alone.

Out of Scope
Simulating events, evaluating objective impact, searching for
alternatives, recovery.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 007-webhook-receiver.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- A notification arrives for an order the system does not recognise.
- A notification claims something the provider's interface contradicts.
- The same notification is delivered several times.
- A notification arrives while the journey is mid-action.
- No notification arrives at all, though the state has changed.
- A notification arrives with an event type never seen before.
- A forged notification is submitted by a third party.
- The verifying query fails while the notification is being processed.
- Notifications arrive out of order.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 008 — Disruption Injector

```
/speckit.specify

Create a Feature Specification.

Feature ID
008-disruption-injector

Feature Name
Disruption Injector

Business Goal
Produce a schedule-change notification on demand, for demonstration and
testing, without ever misrepresenting it as provider-originated.

Business Value
The sandbox provides no documented means of triggering a schedule change.
Without this, the product's central capability cannot be demonstrated at
all. Honesty about the simulation is what keeps it legitimate.

Business Actors
Operator

Business Capability
Test Instrumentation

Reference
.antabay/atlas-capability-map.md section 7c records the observed envelope
this must conform to.

Functional Requirements

FR-001 The system shall emit a schedule-change notification conforming to
the envelope structure observed from the real provider.

FR-002 The system shall deliver that notification through the same
reception path as provider-originated notifications.

FR-003 The system shall mark every injected notification as simulated, at
the point of reception and permanently in storage.

FR-004 The system shall present every event derived from an injected
notification as simulated in every interface.

FR-005 The system shall target a specific existing journey and shall
reference that journey's real order.

FR-006 The system shall allow the revised arrival time to be specified.

FR-007 The system shall not fabricate, alter, or supplement any travel
option, price, or availability.

FR-008 The system shall be disableable, and shall be inert when disabled.

Non-Functional Requirements

Simulated and provider-originated notifications shall be distinguishable
in storage at all times, and shall never be merged into a single
indistinguishable record.

The injector shall not be reachable by any party other than the operator.

The envelope structure shall be derived from a captured real notification,
never handwritten.

Out of Scope
Evaluating impact, searching alternatives, recovery, and any simulation of
travel data itself.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 008-disruption-injector.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- An injected notification targets a journey that does not exist.
- An injected notification targets a journey that is not yet ticketed.
- A real notification arrives for the same order shortly afterwards.
- The revised arrival time still satisfies the objective.
- The injector is triggered twice for the same journey.
- The simulation marking is absent from a stored event.
- A recorded event stream containing simulated events is replayed later.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 009 — Impact Evaluation and Alternatives

```
/speckit.specify

Create a Feature Specification.

Feature ID
009-impact-evaluation

Feature Name
Objective Impact Evaluation and Alternative Discovery

Business Goal
Determine whether the traveller's objective is still achievable after a
change, and if not, find and price the options that would restore it.

Business Value
This is the difference between reporting a delay and protecting an
outcome. The question is never "is the flight late" but "is the objective
still reachable, and what would it cost to keep it".

Business Actors
Agent
Traveller

Business Capability
Objective Protection

Functional Requirements

FR-001 The system shall reconstruct the journey and its objective from
durable storage on waking.

FR-002 The system shall evaluate the confirmed change against every
element of the objective.

FR-003 The system shall state the result in terms of the objective rather
than in terms of the flight.

FR-004 The system shall quantify the extent of any violation.

FR-005 The system shall take no further action when the objective remains
satisfied, and shall record that determination.

FR-006 The system shall search for alternatives when the objective is
violated.

FR-007 The system shall evaluate alternatives against the original
objective using the same scoring rules used for the original selection.

FR-008 The system shall verify an alternative before recommending it.

FR-009 The system shall express the cost of each alternative relative to
the traveller's current position, not as an absolute price.

FR-010 The system shall recommend one alternative and state why.

FR-011 The system shall state explicitly when the only alternative that
preserves the objective breaches a stated constraint.

FR-012 The system shall report when no alternative preserves the objective.

FR-013 The system shall count alternative searches against the journey's
call budget.

Non-Functional Requirements

Every alternative presented shall come from a verified provider response.

The recommendation shall be explainable in one sentence a traveller can
evaluate.

Out of Scope
Detecting the change, authorisation policy, executing recovery,
verification of the executed action.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 009-impact-evaluation.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The change improves the position rather than worsening it.
- The change violates one element of the objective but improves another.
- No alternative preserves the objective.
- The only viable alternative exceeds the stated budget.
- The alternative costs less than the original.
- Alternatives are found but all expire before a decision is made.
- The journey is already past departure when the change arrives.
- A second change arrives while alternatives are being evaluated.
- The call budget is exhausted before alternatives are found.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 011 — Recovery Execution

```
/speckit.specify

Create a Feature Specification.

Feature ID
011-recovery-execution

Feature Name
Recovery Execution

Business Goal
Carry out an authorised recovery, confirm independently that it succeeded,
and return the journey to monitoring with its objective intact.

Business Value
The point at which the product delivers on its promise. Everything before
this is analysis; this is the part that actually saves the traveller's
outcome.

Business Actors
Agent
Traveller

Business Capability
Outcome Restoration

Reference
The provider offers no facility to change an existing booking. Recovery is
therefore the creation of a replacement booking, followed by cancellation
of the superseded one.

Functional Requirements

FR-001 The system shall execute a recovery only when authorisation has
been granted for that specific action.

FR-002 The system shall verify the alternative immediately before
executing, and shall abandon execution if its price has changed.

FR-003 The system shall create and pay for the replacement booking.

FR-004 The system shall confirm the replacement booking's ticketing by
independent query before considering the recovery successful.

FR-005 The system shall initiate cancellation of the superseded booking
only after the replacement is confirmed.

FR-006 The system shall treat the replacement and the cancellation as
separate outcomes, each independently verified.

FR-007 The system shall record a state in which the replacement succeeded
and the cancellation did not, and shall surface it rather than conceal it.

FR-008 The system shall never leave the traveller without a confirmed
booking as a result of a recovery attempt.

FR-009 The system shall update the journey's current booking only after
the replacement is confirmed.

FR-010 The system shall return the journey to monitoring once recovery is
complete.

FR-011 The system shall record the full sequence in the audit trail,
including the authorisation that permitted it.

FR-012 The system shall report the final position to the traveller in
terms of the objective.

Non-Functional Requirements

Ordering is a safety property: the replacement is secured before the
original is released, never the reverse.

No step shall be repeated on an uncertain outcome; each shall be
reconciled by query.

Out of Scope
Detecting disruption, evaluating impact, scoring alternatives, obtaining
authorisation.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 011-recovery-execution.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The replacement booking fails after authorisation was granted.
- The replacement succeeds but cancellation of the original fails.
- The alternative's price changed between authorisation and execution.
- The alternative sold out between authorisation and execution.
- Cancellation is outside the permitted window.
- Both bookings end up active.
- Execution is interrupted partway and resumes later.
- A further disruption arrives during recovery.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```

---

# 013 — Traveller Mobile Experience

*Not scored. Build only if 000–011 are complete and deployed.
The technology decision belongs in `/speckit.plan`: a responsive view
sharing 006's event stream satisfies this specification at a fraction of
the cost of a native application.*

```
/speckit.specify

Create a Feature Specification.

Feature ID
013-traveller-mobile-experience

Feature Name
Traveller Mobile Experience

Business Goal
Give the traveller a handheld surface for the only two things they need to
do during a journey: understand what has changed, and authorise or refuse
the response to it.

Business Value
The operator console shows everything the agent does. A traveller does not
want everything. They want to be told when their objective is at risk,
told what it costs to protect it, and given a decision.

Business Actors
Traveller

Business Capability
Traveller Interaction

Functional Requirements

FR-001 The system shall present the traveller's objective in plain
language, without technical detail.

FR-002 The system shall present the current journey status as a single
clear statement of whether the objective is on track, at risk, or no
longer achievable.

FR-003 The system shall present the currently booked itinerary in
traveller terms: carrier, departure, arrival, and margin against the
stated deadline.

FR-004 The system shall notify the traveller when the objective becomes at
risk.

FR-005 The system shall present an outstanding authorisation request
stating the proposed action, the cost difference against the current
position, and the effect on the objective.

FR-006 The system shall allow the traveller to authorise or refuse a
request from this surface.

FR-007 The system shall confirm the outcome of an authorisation, including
whether the action succeeded.

FR-008 The system shall reflect changes made on this surface in the
operator console, and changes made in the console on this surface, without
either being reloaded.

FR-009 The system shall address a specific journey directly, so that a
traveller arrives at their own journey rather than a general entry point.

FR-010 The system shall present the reason for a recommendation in one
sentence the traveller can evaluate.

FR-011 The system shall not present agent internals — tool calls,
identifiers, timings, or policy rule names.

FR-012 The system shall indicate when it is showing simulated rather than
live events.

Non-Functional Requirements

The surface shall be legible and operable one-handed on a phone-sized
screen.

An authorisation decision shall be reachable in no more than two
interactions from opening the surface.

The surface shall hold no state of its own and shall render only what the
journey event stream provides.

The surface shall use the same visual language and palette as the operator
console, at a lower information density. The reference implementation is
the traveller panel in .antabay/console-mockup.html.

The surface shall remain correct when opened after a long period of
inactivity, by reconstructing state from the journey record rather than
from events it may have missed.

The choice between a native application and a responsive web view is an
implementation decision to be made during planning. Both satisfy this
specification. The decision shall be recorded with its rationale.

Out of Scope
Search and selection by the traveller, booking initiated from this
surface, payment entry, account management, authentication, multiple
journeys per traveller, push notification infrastructure, offline
operation.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details.
Do not generate source code.
```

```
/speckit.clarify

Review Feature Specification 013-traveller-mobile-experience.

Identify missing requirements, ambiguity, assumptions, missing validation,
missing error handling, missing non-functional requirements, and missing
acceptance criteria.

Give particular attention to:
- The traveller opens the surface mid-journey having missed every prior
  event.
- An authorisation request is answered from the console while the
  traveller is looking at it.
- The traveller authorises and the price has changed since the request.
- The traveller refuses and the objective becomes unachievable.
- The connection drops while an authorisation is outstanding.
- The traveller opens the surface after the journey has completed.
- The same journey is open on two devices at once.
- A recommendation must be explained without exposing agent internals.
- The journey is in a failed state rather than a successful one.

Review every functional requirement. Suggest improvements. Update the
specification where necessary.

Do not generate implementation. Do not generate source code.
```
