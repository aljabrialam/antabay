# Antabay — Demo Scenario Sequence

Every value below is from a verified Atlas sandbox response.
Route SEL→TYO, 2026-09-05. See `.antabay/atlas-capability-map.md`.

---

## The full run, with video timings

```mermaid
sequenceDiagram
    autonumber
    actor T as Traveller
    participant UI as Journey Console
    participant AG as Antabay Agent
    participant QW as Qwen
    participant POL as Policy Engine
    participant AT as Atlas Sandbox
    participant DB as Journey State

    rect rgb(222,238,252)
    Note over T,DB: 0:00–0:20 — UNDERSTAND
    T->>UI: "Tokyo before 10 AM tomorrow.<br/>Under USD 120. No overnight connections."
    UI->>AG: goal
    AG->>QW: parse into structured objective
    QW-->>AG: TYO · arrive<10:00 · ≤USD 120<br/>· no overnight · 1 adult — all HARD
    AG->>DB: journey created
    AG->>UI: parsed objective
    end

    rect rgb(220,244,232)
    Note over T,DB: 0:20–0:50 — OBSERVE
    AG->>AT: search.do SEL→TYO
    AT-->>AG: 30 routings · 8 carriers · 2 connecting
    Note over AG: offer clock 7m43s — counting on screen<br/>search budget 1/10
    end

    rect rgb(253,240,214)
    Note over T,DB: 0:50–1:15 — REASON (the money shot)
    AG->>QW: score 30 options against objective
    QW-->>AG: rationale
    Note over AG,QW: ✗ TW237 arr 09:30 USD 141.94<br/>→ over budget by 21.94
    Note over AG,QW: ✗ 7C907+7C1151 arr 09:30 USD 98.93<br/>→ in time AND in budget<br/>→ 625 min layover at PUS · 13.6h<br/>→ VIOLATES no overnight connection
    Note over AG,QW: ✓ ZE605 ICN→NRT arr 09:50 USD 90.39<br/>7 seats · nonstop · 10 min margin
    AG->>UI: selection + rationale
    end

    rect rgb(220,244,232)
    Note over T,DB: 1:15–1:35 — ACT & VERIFY
    AG->>AT: verify.do (routingIdentifier byte-for-byte)
    AT-->>AG: sessionId · isPriceChange false
    AG->>POL: propose booking
    POL-->>AG: AUTH-01 spends money → REQUIRES AUTHORISATION
    AG->>UI: authorisation request
    T->>UI: approve
    AG->>AT: order.do
    AT-->>AG: orderNo · PNR TQQ0BU · tktLimitTime 30 min
    Note over AG: PNR is not a ticket
    AG->>AT: pay.do
    AT-->>AG: status 0
    Note over AG: payment is not a ticket
    AG->>AT: queryOrderDetails.do
    AT-->>AG: ticketStatus "0" · ticketNos []
    AT-)AG: webhook order.ticketed (~35s)
    Note over AG: UNAUTHENTICATED — hint only
    AG->>AT: queryOrderDetails.do (confirm)
    AT-->>AG: ticketNos ["S46659"] ✓
    AG->>DB: MONITORING
    end

    rect rgb(253,224,224)
    Note over T,DB: 1:35–1:50 — DISRUPTION
    T->>UI: fire disruption
    UI-)AG: schedule change [SIMULATED, labelled]
    AG->>AT: queryOrderDetails.do
    Note over AG: verify the claim before acting
    AG->>DB: rehydrate journey + objective
    AG->>AG: arrival 09:50 → 11:50<br/>OBJECTIVE VIOLATED by 1h50m
    end

    rect rgb(220,244,232)
    Note over T,DB: 1:50–2:20 — ADAPT
    AG->>AT: search.do (real data, budget 2/10)
    AT-->>AG: current options
    AG->>AT: verify.do LJ201
    AT-->>AG: confirmed USD 96.63
    Note over AG: LJ201 arr 09:55 · +USD 6.24 · compliant<br/>TW237 arr 09:30 · +USD 51.55 · breaks budget
    AG->>UI: recommend LJ201
    end

    rect rgb(253,240,214)
    Note over T,DB: 2:20–2:40 — HUMAN AUTHORITY
    AG->>POL: propose rebook + void original
    Note over POL: spends money · voids booking · irreversible<br/>three rules, one decision, no model involved
    POL-->>AG: REQUIRES AUTHORISATION
    AG->>UI: +USD 6.24 · arrives 09:55 · objective preserved
    T->>UI: approve
    AG->>DB: authorisation recorded
    end

    rect rgb(220,244,232)
    Note over T,DB: 2:40–3:00 — EXECUTE & VERIFY
    AG->>AT: order.do → pay.do (new)
    AG->>AT: void original order
    AG->>AT: queryOrderDetails.do ×2 (both legs)
    AT-->>AG: new ticketed · original voided
    AG->>DB: journey updated
    AG->>UI: objective intact · MONITORING resumes
    end
```

---

## The refusal path — critical journey 4

Must be built and tested. Worth showing if there is room.

```mermaid
sequenceDiagram
    autonumber
    actor T as Traveller
    participant UI as Console
    participant AG as Agent
    participant POL as Policy Engine
    participant DB as Journey State

    AG->>POL: propose rebook + void
    POL-->>AG: REQUIRES AUTHORISATION
    AG->>UI: +USD 6.24 · objective preserved

    alt Traveller declines
        T->>UI: decline
        AG->>DB: refusal recorded
        Note over AG: NO SPEND · NO VOID
        AG->>UI: objective at risk · no action taken
    else No response before deadline
        Note over POL: silence is refusal — FR-010
        AG->>DB: non-response recorded
        Note over AG: NO SPEND
        AG->>UI: authorisation lapsed · no action taken
    end
```

---

## Three beats that carry the score

**0:50 — the rejection.** An option arriving 09:30 for USD 98.93 passes
arrival and passes budget. Antabay refuses it: 625 minutes in Busan, 13.6
hours door to door. Say it aloud — *"it arrives in time and it's in
budget, and it's still wrong."* This is the clearest proof that reasoning
is happening rather than sorting.
→ Agent Technology (0–6), AI Multiplier

**1:32 — the webhook.** Atlas says the ticket is issued. Antabay queries
Atlas anyway. *"This webhook is unauthenticated — anyone who knows the URL
could send it. The event says look again. The API says what's true."*
→ Compliance & Safety, Agent Technology

**2:20 — the gate.** Three rules fire at once: spends money, voids a
booking, irreversible. Execution stops. *"A rule decides that, not the
model."*
→ Compliance & Safety, Agent Technology

Everything else is plumbing. Necessary, but these three are what gets
remembered.

---

# Narration script — 3:00

Paste into Descript, DemoPolish, or read it yourself. Timings are targets,
not constraints; the words matter more than hitting the second.

**Delivery.** Flat and factual. This is an engineer showing you a system,
not an advert. Let the screen carry the drama — the trace, the clocks, the
gate. Pause where marked; silence over a rejection scrolling past is worth
more than filling it.

**Word count 415.** At a measured 145 wpm that is about 2:52, leaving
eight seconds of air. Do not speed up to fit more in.

---

### 0:00 — 0:20 · Understand

> Everyone can search flights.
>
> Antabay is judged on what happens *after* the booking.
>
> You give it an objective, not an itinerary.

*[goal appears on screen]*

> "Tokyo, before ten. Under a hundred and twenty dollars. No overnight
> connections."
>
> Five hard constraints. Qwen parses them. From here, everything is
> measured against this — not against the flight.

---

### 0:20 — 0:50 · Observe

> Antabay searches Atlas. Thirty real options, eight carriers, sandbox
> environment — these are test transactions, not real bookings.
>
> Note the clock. This offer expires in seven minutes and forty-three
> seconds, and it was already partly aged when it arrived. That's not a
> detail. It's why the agent has to re-verify before it commits to
> anything.

---

### 0:50 — 1:15 · Reason — *the moment*

> Now watch the rejections.
>
> T-way two-three-seven arrives at nine-thirty. Over budget. Out.

*[pause]*

> And this one. Jeju, via Busan. Arrives nine-thirty. Ninety-eight
> dollars. It passes the arrival check. It passes the budget check.
>
> Antabay rejects it.

*[pause — let the reason render]*

> Six hundred and twenty-five minutes on the ground in Busan. Thirteen and
> a half hours, departing the night before.
>
> It arrives in time, it's within budget, and it's still wrong. An agent
> that sorts by price and arrival books this. An agent that reasons doesn't.
>
> It picks Eastar six-oh-five. Ninety dollars thirty-nine. Arrives
> nine-fifty. Ten minutes of margin.

---

### 1:15 — 1:35 · Act and verify

> Verify. Order. Pay.
>
> Payment succeeds — and Antabay does not call that a ticket. Neither is
> the PNR.
>
> It queries Atlas independently. Ticket numbers present. *Now* it's
> booked.

---

### 1:35 — 1:50 · Disruption

> Three hours later, a schedule change.
>
> This event is simulated and labelled as such — the sandbox has no way to
> trigger one. The envelope is copied from a real Atlas webhook we
> captured. Every flight you'll see from here is live sandbox data.
>
> And the webhook is unauthenticated. Anyone who knew the URL could send
> it. So Antabay doesn't believe it — it asks Atlas.
>
> The event says look again. The API says what's true.

---

### 1:50 — 2:20 · Adapt

> Confirmed. Arrival moves to eleven-fifty.
>
> The objective is violated by one hour fifty. Not "the flight is late" —
> the meeting is now unreachable.
>
> Antabay re-searches, verifies, and finds Jin Air two-oh-one. Arrives
> nine-fifty-five. Six dollars and twenty-four cents more.
>
> There's a faster option, but it breaks the stated budget. It says so
> rather than quietly choosing.

---

### 2:20 — 2:40 · Authority

> And here it stops.
>
> Spends money. Voids a booking. Irreversible. Three rules fire, and a
> rule decides this — not the model. Nothing the language model produces
> can talk its way past this gate.
>
> Six dollars twenty-four to save the meeting.

*[approve — cut to phone]*

> Same journey on the traveller's phone. One tap.

---

### 2:40 — 3:00 · Close

> Booked, verified, monitoring resumes.
>
> Full-service airlines rebook you when things break. Low-cost carriers
> don't — no interline, no duty of care. Atlas reaches a hundred and forty
> of them.
>
> That's who Antabay is for.
>
> You have a destination. Antabay watches over the journey.

---

## Shot list

| # | Source | Length | Note |
|---|---|---|---|
| 1 | Playwright console capture, 1440×900 | ~2:30 | `slowMo: 400`, explicit waits at the three beats |
| 2 | Playwright phone capture, 390×844 | ~0:15 | same journey, traveller route |
| 3 | Repo — specs, commits, wiki | ~0:10 | optional, for Use of Qoder |

**Text callouts on screen** — three only, matching the beats:

- `IN TIME · IN BUDGET · REJECTED` over the Busan rejection
- `UNAUTHENTICATED — VERIFYING` over the webhook
- `AUTH-01 · AUTH-02 · AUTH-03` over the gate

**Do not** add background music under the rejection or the gate. Silence
reads as confidence.

**Editing order if you run short of time:** trim 0:20–0:50 first, then
1:15–1:35. Never trim 0:50–1:15 or 2:20–2:40 — those two carry Agent
Technology, the largest single sub-dimension.
