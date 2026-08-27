# Antabay — Demo Scenario (Locked)

**Status:** locked 15 August 2026, judging map added 19 August
**Data source:** verified `search.do` response, SEL→TYO, 2026-09-05
**Constraint:** must fit a 3-minute submission video

Every flight, price, and time below came from a real Atlas sandbox
response. Nothing is invented. If the sandbox data changes, this document
changes with it — the scenario never drifts ahead of the data.

---

## Traveller goal

> "Get me to Tokyo before 10 AM tomorrow. Under USD 120. No overnight
> connections."

### Parsed objective

| Element | Value | Type |
|---|---|---|
| Origin | SEL | hard constraint |
| Destination | TYO | hard constraint |
| Latest arrival | 10:00 local | hard constraint |
| Budget | USD 120 | hard constraint |
| Overnight connections | excluded | hard constraint |
| Travellers | 1 adult | hard constraint |

## The option set

30 routings returned. Three arrive before 10:00:

| Flight | Route | Dep | Arr | Total USD | Seats |
|---|---|---|---|---|---|
| TW237 | ICN→NRT | 06:55 | 09:30 | 141.94 | 3 |
| **ZE605** | **ICN→NRT** | **07:25** | **09:50** | **90.39** | **7** |
| LJ201 | ICN→NRT | 07:25 | 09:55 | 96.63 | 9 |

TW237 arrives earliest but **exceeds the USD 120 budget**.

### The trap

Two connecting options exist, both `7C907` GMP→PUS→NRT:

| Legs | Layover | Total journey | USD | Arrives |
|---|---|---|---|---|
| 7C907 + 7C1151 | 625 min (10.4 h) | 13.6 h | 98.93 | 09:30 next day |
| 7C907 + 7C1153 | 835 min (13.9 h) | 17.1 h | 175.06 | 13:00 next day |

**The first one arrives 09:30 and costs USD 98.93 — it passes both a naive
arrival check and a naive budget check.** It departs GMP at 19:55 the
previous evening and sits in Busan for over ten hours.

An agent that scores only on arrival time and price selects this. Antabay
must reject it and say why. This is the clearest single proof in the demo
that reasoning is happening rather than sorting.

## Selection

Antabay selects **ZE605**.

Stated reasoning: meets the 09:50 arrival deadline with a 10-minute
buffer, cheapest compliant option at USD 90.39, seven seats remaining, no
connection. TW237 rejected on budget. The Busan itineraries rejected on
the overnight-connection constraint despite passing arrival and price.

## Freshness pressure

Observed on this route: `refreshTime` 09:21:03Z, `expireTime` 09:28:46Z —
a **7 minute 43 second** window, and the offer was already partly aged on
arrival.

Antabay re-verifies before committing and surfaces the remaining window in
the trace. This is real, not staged.

## Booking

`verify.do` → `order.do` → `pay.do` → poll `queryOrderDetails.do` until
ticketing is confirmed. Payment success is not proof; the order query is.

## Disruption

A Schedule Change event is injected against ZE605, pushing arrival past
10:00. The objective is now violated.

The event conforms exactly to the documented Atlas Schedule Change webhook
payload and enters through the real webhook receiver. **It is labelled as
simulated in the interface, the README, and the narration.** The sandbox
provides no documented way to trigger a schedule change; the flights,
prices, and alternatives remain real sandbox data throughout.

## Recovery

Antabay re-searches, verifies alternatives, and evaluates:

| Option | Arrives | Delta vs ZE605 | Objective |
|---|---|---|---|
| LJ201 | 09:55 | **+USD 6.24** | preserved, within budget |
| TW237 | 09:30 | +USD 51.55 | preserved, **breaks USD 120 budget** |

Recommendation: **LJ201**, +USD 6.24, arrives 09:55, five minutes inside
the deadline, no connection, nine seats.

## Approval gate

The action spends money, so the deterministic policy engine requires
authorisation. Antabay presents the option, the delta, the objective
impact, and waits.

If the traveller declines, no spend occurs and the refusal is recorded.
That path is tested — it is critical journey 4 in the constitution.

## Execution and verification

New order created and paid. Void or refund initiated on the ZE605 order.
Both legs independently verified through order query before journey state
is updated. Monitoring resumes.

---

## Video beat sheet (3:00)

| Time | Beat |
|---|---|
| 0:00–0:20 | Goal stated in plain language; parsed objective appears |
| 0:20–0:50 | Search runs; 30 real options; trace shows `search.do` |
| 0:50–1:15 | Scoring; the Busan trap rejected out loud; ZE605 selected |
| 1:15–1:35 | Verify, order, pay, ticketing confirmed by order query |
| 1:35–1:50 | Disruption injected (labelled); agent wakes |
| 1:50–2:20 | Impact evaluated; alternatives searched and verified |
| 2:20–2:40 | Recommendation with delta; approval gate; human approves |
| 2:40–3:00 | Execution, both legs verified, state updated, monitoring resumes |

Three human touches in the whole run: state the goal, fire the disruption,
approve the recovery. Everything between is the agent.

---

## Scoring map — what each beat is worth

All 40 points are assessed from this video. Every beat below is placed
because it earns something specific.

| Beat | Sub-dimension | Say this aloud |
|---|---|---|
| Objective parsed into hard vs soft constraints | Scenario/Experience, Agent Technology | "A goal, not an itinerary." |
| 30 real options from Atlas sandbox | Operating Scale | "140+ carriers through one integration. Sandbox — test transactions, not real bookings." |
| Busan itinerary rejected despite arriving 09:30 | Agent Technology, AI Multiplier | "It arrives in time and it's in budget. It's also thirteen hours with an overnight in Busan. Rejected." |
| Offer expiry counting down on screen | Compliance & Safety | "This offer dies in seven minutes. Re-verify before committing." |
| `pay.do` succeeds, ticket not yet issued | Agent Technology | "Payment succeeded. That is not a ticket. Confirm against the order query." |
| Webhook arrives, agent queries Atlas anyway | Compliance & Safety | "This webhook is unauthenticated. Anyone could send it. The event says look again — the API says what's true." |
| Cost delta and objective impact shown | Business/Form, Operations/Cost | "Six dollars and twenty-four cents to save the meeting." |
| Approval gate blocks execution | Compliance & Safety, Agent Technology | "It spends money, so it stops. A rule decides that, not the model." |
| Both legs verified after execution | Agent Technology | "Verify, then update state. Never assume." |
| Search budget visible in the trace | Cost Controllability | "Rate-limited endpoints have a per-journey budget. The agent cannot loop." |

**Presentation discipline.** Demo sub-dimensions score 4 / 2 / 0 with no
partial credit — a complete plain run beats a beautiful partial one. All
sixteen MVP steps appear before any time is spent on styling.

**The multiplier.** Innovation carries a ×2 to ×0.5 multiplier and a
bolted-on model scores *worse* than none. Qwen must be visibly doing the
reasoning — parsing the objective, scoring the options, producing the
rationale that rejects Busan — and the trace must show it.

**Recording, not live.** Submission is a video. Record a real end-to-end
run as an event stream and drive the console from it. Same interface, same
code path, controllable pace. Nothing depends on network conditions.
