# Antabay — 48-Hour Execution Plan

**Now:** 28 August 2026
**Due:** 30 August 2026, 23:59 SGT
**Reality:** thirteen specs is not deliverable. Four is.

Everything below is ordered. Do it top to bottom. Do not skip ahead.

---

## Hour 0 — Setup, copy-paste

### 1. Repo and Spec Kit

```bash
mkdir -p ~/Documents/antabay && cd ~/Documents/antabay
git init

specify init . --ai qodercli
specify check          # must show: Qoder CLI (available)

mkdir -p .antabay fixtures/atlas
```

### 2. Gitignore FIRST — credentials are in the newman reports

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

### 3. Environment

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

Paste your DashScope key in. `dashscope-intl` is Singapore — the Beijing
endpoint has no free quota.

### 4. Context documents

Adjust the source path if yours differ.

```bash
cd ~/Documents/antabay
cp ~/Downloads/constitution.md                    .antabay/constitution.md
cp ~/Downloads/atlas-capability-map.md            .antabay/atlas-capability-map.md
cp ~/Downloads/demo-scenario.md                   .antabay/demo-scenario.md
cp ~/Downloads/antabay-architecture-diagrams.md   .antabay/architecture.md
cp ~/Downloads/demo-sequence-diagram.md           .antabay/demo-sequence.md
cp ~/Downloads/antabay-48h-execution-plan.md      .antabay/plan.md
```

| Source file | Lands at | Purpose |
|---|---|---|
| `constitution.md` | `.antabay/constitution.md` | governing rules |
| `atlas-capability-map.md` | `.antabay/atlas-capability-map.md` | **the verified contract** |
| `demo-scenario.md` | `.antabay/demo-scenario.md` | locked scenario, real data |
| `antabay-architecture-diagrams.md` | `.antabay/architecture.md` | architecture |
| `demo-sequence-diagram.md` | `.antabay/demo-sequence.md` | video storyboard |
| `antabay-48h-execution-plan.md` | `.antabay/plan.md` | this file |

Not copied: `antabay-speckit-run-sheet.md` and
`antabay-specs-000-003-006-010.md` are superseded by the four blocks
below. `antabay-spec-013-mobile.md` is **cut** — not scored.

### 5. Fixtures, redacted

Run from wherever your captured JSON lives.

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
for f in ["sel_tyo_search.json", "sel_tyo_verify.json"] + glob.glob("events/*.json"):
    if not os.path.exists(f):
        print("skip", f); continue
    name = "webhook_order_ticketed.json" if f.startswith("events/") else os.path.basename(f)
    json.dump(red(json.load(open(f))), open(f"{out}/{name}", "w"), indent=2)
    print("wrote", name)
PY
```

### 6. Qoder setup and first commit

```bash
cd ~/Documents/antabay
qodercli plugins install better-harness
qodercli wiki

git add -A
git status             # .env and report*.html must NOT appear
git commit -m "chore: repo init, spec kit, verified Atlas contract and context docs"
```

### 7. Then, in Qoder

Paste the `/speckit.constitution` block from the run sheet, then **Spec A**
below.

---



## What got cut, and why

| Cut | Reason |
|---|---|
| Spec 013 mobile | not scored, 3–4 days |
| Preemptive risk rule | nice-to-have, needs the core first |
| Two-tier E2E automation | run Tier 2 manually |
| Void/refund of the original | recovery books the new leg; state the void as designed-not-built |
| Seat, baggage, ancillaries | not scored |
| Any UI polish before hour 30 | completeness scores 4/2/0 |

Constitution principles still hold. Article VII's test pyramid becomes
"tests exist for the policy engine and the scoring rules" — those are the
two places a bug is fatal.

---

## Timeline

**Day 1 — 28 Aug**

| Hours | Work |
|---|---|
| 0–1 | Repo, Spec Kit init, context docs in, `qodercli` plugins (`better-harness`), Repo Wiki on |
| 1–2 | Spec A — contract + journey model |
| 2–6 | Spec B — booking path, search → score → verify → order → pay → confirm |
| 6–10 | Spec C — console + trace, live against real Atlas calls |

End of day 1: you can state a goal and watch it book a real sandbox ticket.

**Day 2 — 29 Aug**

| Hours | Work |
|---|---|
| 0–4 | Spec D — webhook, injector, impact, recovery, policy gate, verify |
| 4–6 | Deploy frontend to Vercel, backend anywhere public |
| 6–8 | Full run rehearsal, record the event stream |
| 8–12 | **Video.** Do not skip. 20% of the score. |

**30 Aug** — buffer, then submit. Do not start anything new.

---

## Spec A — Contract and Journey Model

```
/speckit.specify

Create a Feature Specification.

Feature ID
001-contract-and-journey

Feature Name
Atlas Contract and Journey Model

Business Goal
Give the system one enforced definition of the travel API it may call, and
one durable record of the traveller's objective and journey state.

Business Value
Prevents invented endpoints, and gives every later feature a single place
to read and write journey truth.

Reference
.antabay/atlas-capability-map.md is the verified contract and the input to
this feature.

Functional Requirements

FR-001 The system shall declare every external endpoint it may call, and
shall reject at build time any call to an endpoint outside that
declaration.

FR-002 The system shall define typed request and response shapes for
search, verify, order, pay, and order query.

FR-003 The system shall preserve every externally issued identifier
unmodified, and shall provide no means to construct or alter one.

FR-004 The system shall define one canonical total-price calculation and
shall not permit totals to be computed elsewhere.

FR-005 The system shall normalise fields whose type differs between the
API and its event notifications.

FR-006 The system shall classify known error codes as retryable,
reconcilable, or terminal, and shall treat a duplicate-booking rejection
as reconcilable by surfacing the existing order reference returned with
it.

FR-007 The system shall accept a travel goal in natural language and
extract origin, destination, latest acceptable arrival, budget with
currency, traveller count, and stated preferences.

FR-008 The system shall classify each extracted element as a hard
constraint or a soft preference and record that classification.

FR-009 The system shall present the parsed objective for confirmation
before any downstream action.

FR-010 The system shall create a journey record with a unique identifier,
the confirmed objective, and a state, and shall permit only defined
transitions between states.

FR-011 The system shall persist journey state durably such that a journey
can be fully reconstructed after the process handling it has terminated.

FR-012 The system shall record for each held identifier the time it was
issued and the time it becomes unusable.

FR-013 The system shall maintain an append-only audit trail of
observations, decisions, external calls, and authorisations.

Non-Functional Requirements

No journey state required for correctness shall reside only in a language
model context window or in process memory.

The system shall not author, infer, or default any travel fact.

Out of Scope
Searching, scoring, booking, monitoring, recovery, user interface.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details. Do not generate source code.
```

Then: `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`.
**Skip `/speckit.clarify` and `/speckit.analyze` on all four specs.** They
are the right practice and you do not have the hours.

---

## Spec B — Booking Path

```
/speckit.specify

Create a Feature Specification.

Feature ID
002-booking-path

Feature Name
Search, Selection, and Booking

Business Goal
Turn a confirmed objective into a ticketed flight, selecting against the
objective and verifying every state change independently.

Business Value
This is the agent doing the traveller's job: not listing options, but
choosing one, defending the choice, and confirming the outcome.

Reference
.antabay/atlas-capability-map.md for the contract.
.antabay/demo-scenario.md for the worked example.

Functional Requirements

FR-001 The system shall search for travel options matching the objective.

FR-002 The system shall eliminate any option violating a hard constraint
and record which constraint it violated.

FR-003 The system shall evaluate arrival time against the deadline and
express the result as the margin between them.

FR-004 The system shall treat an option with more than one leg as a
connection and compute the time between consecutive legs.

FR-005 The system shall reject a connection the traveller has excluded,
regardless of whether the option satisfies arrival time and cost.

FR-006 The system shall incorporate available seat scarcity and sell-out
risk signals into its evaluation.

FR-007 The system shall select one option and state a rationale naming the
objective elements satisfied, and shall state a reason for each rejected
option that would otherwise have ranked highly.

FR-008 The system shall report when no option satisfies all hard
constraints and state which constraints could not be satisfied together.

FR-009 The system shall verify price and bookability before committing,
and shall treat a reported price change as invalidating any prior
authorisation.

FR-010 The system shall not act on an option whose held offer has expired.

FR-011 The system shall create an order using the passenger field
requirements returned at verification time rather than a fixed form.

FR-012 The system shall not treat a payment response as confirmation of
ticketing, and shall confirm ticketing only by an independent order query
returning issued ticket numbers.

FR-013 The system shall reconcile rather than retry when an order or
payment outcome is uncertain.

FR-014 The system shall operate within a declared call budget per journey
for rate-limited endpoints and shall honour any wait instruction returned
with a rate-limit rejection.

Non-Functional Requirements

Selection shall be deterministic and explainable in one short paragraph a
traveller can verify against the option data.

No travel fact shall be presented that did not come from a verified
external response.

Out of Scope
Monitoring, disruption, recovery, authorisation policy, user interface.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details. Do not generate source code.
```

---

## Spec C — Console and Agent Trace

```
/speckit.specify

Create a Feature Specification.

Feature ID
003-console-and-trace

Feature Name
Journey Console and Agent Trace

Business Goal
Make the agent's behaviour visible in real time to a person watching a
screen.

Business Value
This is the debugging surface during development and the surface on which
the product is assessed. Behaviour that cannot be seen earns nothing.

Functional Requirements

FR-001 The system shall present the objective as structured elements,
distinguishing hard constraints from preferences.

FR-002 The system shall present current journey state and every held
identifier with the time remaining before it becomes unusable.

FR-003 The system shall emit an observable event for every external call
stating the endpoint, outcome, and elapsed time.

FR-004 The system shall emit an observable event for every decision
stating what was decided and why.

FR-005 The system shall stream events to the interface as they occur,
without the interface polling.

FR-006 The system shall present the remaining call budget for the journey.

FR-007 The system shall present an outstanding authorisation request
stating the action, its cost relative to the current position, and its
effect on the objective, and shall present the outcome including refusals.

FR-008 The system shall visually distinguish simulated events from events
received from the external provider.

FR-009 The system shall record a complete event stream for a journey and
shall replay it through the same interface at a controllable pace without
contacting any external service.

FR-010 The interface shall hold no state of its own and shall render only
what the event stream provides.

FR-011 The system shall present a traveller-facing view of the same
journey at its own address, showing status, the booked itinerary, any
outstanding authorisation, and nothing of the agent's internals.

Non-Functional Requirements

The interface shall be legible when recorded as video and viewed at
reduced size.

A complete journey shall require no more than three human interactions.

The traveller-facing view shall be legible and operable on a phone-sized
screen.

Out of Scope
Agent reasoning, external API integration, authentication, multiple
concurrent journeys.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details. Do not generate source code.
```

FR-011 is the mobile view. Responsive breakpoint, same event stream.
Half a day, not four.

---

## Spec D — Disruption, Authority, and Recovery

```
/speckit.specify

Create a Feature Specification.

Feature ID
004-disruption-and-recovery

Feature Name
Disruption Detection, Authorisation, and Recovery

Business Goal
Detect that the traveller's objective is at risk, determine what it would
cost to protect it, obtain human authorisation, execute, and verify.

Business Value
This is the entire differentiator. Everything before it is booking.

Reference
.antabay/atlas-capability-map.md section 7c for the captured event
envelope.

Functional Requirements

FR-001 The system shall accept inbound event notifications at a public
endpoint.

FR-002 The system shall treat every inbound notification as an untrusted
hint and shall confirm the claim against the external API before changing
journey state.

FR-003 The system shall route on the event type and shall not treat the
notification's status value as an indication of success or failure.

FR-004 The system shall provide a means of emitting a schedule-change
notification conforming to the observed envelope, for demonstration, and
shall mark every such event as simulated in storage and in the interface.

FR-005 The system shall rehydrate the affected journey from durable
storage on waking.

FR-006 The system shall evaluate whether the objective remains achievable
and state the result in terms of the objective, not the flight.

FR-007 The system shall search for and verify alternatives when the
objective is violated.

FR-008 The system shall recommend one alternative, stating its cost
relative to the current position and its effect on the objective, and
shall state when the only compliant alternative breaches a stated
constraint.

FR-009 The system shall evaluate every proposed action before execution
and classify it as permitted autonomously or requiring human
authorisation.

FR-010 The system shall require human authorisation for any action that
spends money, cancels or voids a booking, cannot be reversed, or breaches
a stated hard constraint.

FR-011 The system shall reach that classification without consulting a
language model, and shall state the specific rule that determined it.

FR-012 The system shall treat absence of a response as refusal.

FR-013 The system shall prevent execution of any action for which
authorisation was required and not granted, and shall record every
authorisation outcome including refusals.

FR-014 The system shall treat an authorisation as applying to one specific
action only, and shall void it if the cost of that action changes before
execution.

FR-015 The system shall verify the outcome of every executed action by
independent query before updating journey state.

FR-016 The system shall resume monitoring after recovery.

Non-Functional Requirements

The authorisation classification shall be deterministic, individually
testable per rule in both the granting and refusing directions, and shall
not be overridable by any configuration, prompt, or input.

Simulated events shall never be presented as provider-originated.

Out of Scope
Cancellation or refund of the superseded booking, which is designed but
not implemented in this iteration.

Generate the specification following the GitHub Spec Kit format.
Do not generate implementation details. Do not generate source code.
```

---

## Qoder discipline

Everything producing a file goes through `qodercli`. The 80% threshold is
measured by credit consumption and is all-or-nothing on 8 points.

Before spec A:

```bash
qodercli plugins install better-harness
qodercli wiki
```

Route models deliberately — Lite or Efficient for scaffolding, higher
tiers only for the reasoning-heavy parts. "Core flow does not depend on
top-tier models" is a scored Cost Controllability point, and off-peak runs
14:00–00:00 UTC.

Run `qodercli wiki` again before submission. It writes to `.qoder/repowiki`
and is citable evidence.

---

## If you fall behind

Cut in this order. Stop when you are back on schedule.

1. The traveller mobile view (FR-011 of spec C)
2. Replay mode — record the screen live instead
3. Backend deployment — keep the frontend on Vercel, run the backend
   through the tunnel
4. The call-budget display
5. Spec B's scarcity signals (FR-006)

**Never cut:** the rejection with its stated reason, the webhook
verification, the authorisation gate, or the video.
