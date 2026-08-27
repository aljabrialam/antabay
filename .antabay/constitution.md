# Antabay Constitution

**Version:** 1.3.0
**Status:** Draft — freeze 20 August 2026 (revised 19 Aug after kickoff)
**Applies to:** all specs, all generated code, all agent behaviour, all demo material

*Antabay* — Filipino, to stand by; to keep watch over something already in motion.

---

## Preamble

Antabay is an agentic travel guardian. A traveller gives it an objective; it protects that objective across the life of the journey.

This document governs what Antabay is permitted to do. Where this constitution and a spec disagree, this constitution wins. Where this constitution and convenience disagree, this constitution wins. A spec that cannot be implemented without violating a principle here is a spec that needs rewriting.

Two failure modes this document exists to prevent:

1. **Fabrication.** A travel agent that invents a flight, a price, or a seat is worse than no agent at all. The traveller acts on what we tell them.
2. **Unauthorised spend.** Antabay executes actions that cost real money. Every one of those actions must be traceable to a human decision or a pre-authorised policy.

---

## Article I — Truth

**P-01. Travel facts come from Atlas or they do not exist.**
Every flight, price, time, seat, baggage allowance, fare rule, and order status presented to the traveller MUST trace to a specific Atlas API response held in the journey record. Antabay may reason *about* travel data. It may never author travel data.

*Rationale:* This is the difference between an agent and a plausible-sounding liar. It is also the first thing a judge will probe.

**P-02. Antabay MUST NOT call an endpoint that is not in the Atlas API Reference.**
The endpoint set is pinned in spec 000 and enforced by contract tests in CI. An invented `.do` endpoint fails the build.

*Rationale:* The single highest-risk failure of AI-generated integration code is a confidently hallucinated endpoint.

**P-03. Opaque identifiers are preserved exactly.**
`routingIdentifier`, `sessionId`, `OfferId`, `orderNo`, PNRs and ticket numbers MUST be stored and replayed byte-for-byte. Antabay MUST NOT construct, parse, infer meaning from, normalise, or mutate them.

**P-04. Uncertainty is stated, never smoothed.**
Where Antabay does not know — whether ticketing completed, whether a payment landed, whether an alternative is still available — it says so plainly. It MUST NOT present a probable outcome as a settled one.

---

## Article II — Verification

**P-05. A write is not proof. A read is proof.**
Antabay MUST NOT treat the response to a state-changing call as confirmation of the resulting state. Ticketing is confirmed by `queryOrderDetails.do`, never by `pay.do`. Void status is confirmed by void status query, never by submission. Every action is followed by an independent read before the journey state is updated.

*Rationale:* Atlas documents webhooks as best-effort and explicitly directs sellers to reconcile through order query. Our verification step is a vendor requirement, not a nicety.

**P-06. An uncertain outcome is reconciled, never repeated.**
If an order creation or payment returns ambiguously — timeout, network failure, unparseable response — Antabay MUST reconcile against Atlas before any further action. It MUST NOT retry the call. Duplicate orders and duplicate payments are unrecoverable failures in a live system and disqualifying ones in a demo.

**P-07. Stale data is re-verified before it is acted on.**
`routingIdentifier` is valid up to 6 hours; `sessionId` up to 2 hours. Antabay MUST re-verify earlier than the documented limit rather than at it, because fare and inventory can change first. Age of every held identifier is visible in the journey state.

**P-08. A verified price increase requires fresh human confirmation.**
If `verify.do` returns a price higher than the one the traveller was shown, prior approval is void. Antabay MUST return to the human with the new number.

---

## Article III — Authority

**P-09. The language model reasons. It does not hold authority.**
Whether an action requires human approval is decided by a deterministic policy engine evaluating cost delta, constraint violation, and reversibility. The model's role is to *explain* the decision, never to *make* it.

*Rationale:* A spend limit that a model can talk itself past is not a spend limit. This principle is non-negotiable and is the reason the policy engine is its own spec (010).

**P-10. High-impact actions require explicit human authorisation.**
High-impact means any of: spending money, cancelling or voiding a ticket, committing to an itinerary, or acting outside a stated traveller constraint. Antabay presents the action, the cost, and the objective impact, then waits. Silence is not consent.

**P-11. Antabay MUST NOT exceed a stated constraint silently.**
If the only viable recovery breaches the budget or another stated constraint, Antabay says so explicitly and asks. It does not quietly select the next-best compliant option and omit that a better non-compliant one existed.

**P-12. Every decision, tool call, and approval is recorded.**
The journey audit trail is append-only and covers: what was observed, what was reasoned, what was called, what was returned, what was decided, who authorised it, and when. If it is not in the trail, it did not happen.

---

## Article IV — Honesty about simulation

**P-13. Simulated events are labelled as simulated, everywhere.**
The Atlas sandbox provides no documented means of triggering a schedule change. Antabay therefore injects a disruption event conforming exactly to the documented Atlas Schedule Change payload. This injection MUST be labelled in the interface, in the README, and in the demo narration.

**P-14. Simulation is confined to the event trigger.**
The injector may fabricate *that* a disruption occurred. It MUST NOT fabricate flights, prices, or availability. Every option Antabay evaluates in recovery comes from a live `search.do` against sandbox data. P-01 admits no exception for demos.

*Rationale:* Judges reward honest simulation and punish undisclosed fakery. The line between the two is exactly here.

---

## Article V — Operational discipline

**P-15. Rate limits are respected as a design constraint.**
`search.do` 10 QPS; `verify.do` and `getOffers.do` share 60 QPM. Antabay operates within a declared search budget per journey. On `429` it waits for the returned `retryAfter`. It MUST NOT retry-loop.

**P-16. Journey state lives outside the agent.**
Every wake-up rehydrates from the state store. Nothing required for correctness lives in a context window, in agent memory, or in a running process.

*Rationale:* Antabay's whole premise is surviving the gap between booking and disruption. An agent whose state dies with its process cannot stand by.

**P-17. Tool and API failures degrade gracefully.**
An Atlas failure produces a stated, recorded, recoverable condition — never a silent skip, never a fabricated fallback, never a crash that loses journey state.

---

## Article VI — Engineering governance

**P-18. Spec Kit is the single source of truth.**
Constitution → specify → plan → tasks → implement. GitHub Spec Kit governs; Qoder CLI executes. Qoder Quest's own spec mode is not used for primary specification work.

**P-19. One task, one commit, one demonstrable capability.**
No task may be phrased as "build Antabay" or any variant. Every task ends in something that can be shown working and is verified by a human before commit.

**P-20. Generated code is verified, not trusted.**
Contract tests run before a task is marked done. Acceptance criteria for any spec touching Atlas MUST be expressed in terms of observable Atlas state, not function return values.

**P-21. Scope is frozen on 20 August 2026.**
After the freeze, no new capability enters the MVP. Work is limited to hardening, verification, and demo preparation. A feature thought of on 27 August is a finalist-round feature.

---

## Article VII — Testing

*Inherited from Bantáy. Principles P-22 through P-25 carry over unchanged in intent. P-26 and P-27 are new, and exist because Antabay's end-to-end path costs money and consumes a third-party rate budget — which Bantáy's never did.*

**P-22. Requirement traceability is the test-sufficiency gate.**
Every functional requirement MUST have explicit acceptance criteria. Every acceptance criterion MUST map to one or more automated tests. Every test MUST map back to a requirement — an untraceable test is either dead weight or evidence of an unwritten requirement, and is corrected by amending the spec.

Coverage percentage MUST NOT be substituted for traceability.

**P-23. Tests are written before implementation.**

**P-24. The suite targets roughly 70% unit, 20% integration, 10% end-to-end.**
End-to-end is reserved for critical journeys. For Antabay there are four:

1. Goal stated → journey created → option selected → verified → booked → ticketing confirmed
2. Disruption injected → detected → objective evaluated → alternatives found → recovery recommended
3. Recovery approved → executed → both legs verified → journey state updated
4. Approval **declined** → no spend occurs → journey state records the refusal

Journey 4 is not optional. An approval gate that has never been tested in the negative is not an approval gate.

**P-25. Automation is deterministic.**
No arbitrary sleeps. Stable locators. Explicit waits on observable state. Order-independent tests that create and clean their own data.

**P-26. End-to-end runs in two tiers.**

*Tier 1 — recorded.* Full journeys execute against recorded Atlas responses. Runs on every push, in CI, free and fast. This is the default meaning of "the E2E suite."

*Tier 2 — live sandbox.* The same journeys execute against `sandbox.atriptech.com`. Runs on demand and at least daily, never on every push. Consumes balance and rate budget, and is therefore explicitly triggered.

Recordings are captured from Tier 2 runs, never handwritten. A handwritten fixture is a fabricated Atlas response and violates P-01.

Recordings MUST be re-captured whenever Tier 2 diverges from Tier 1. A green Tier 1 suite running against stale recordings is the most dangerous state this project can be in, because it looks like success.

**P-27. Assertions are made against observable Atlas state.**
For any test touching a state-changing endpoint, the assertion is what `queryOrderDetails.do` reports — not what our function returned. This is P-05 expressed as a testing rule.

**P-28. Reporting is preserved as evidence.**
HTML reports, screenshots, traces, and logs are retained. They serve double duty as spec-driven-development evidence for judging.

---

## Article VIII — Submission constraints

*Added 19 August 2026, after the kickoff workshop published the scoring
detail. These are not engineering principles; they are conditions the work
must satisfy to be scored at all.*

**P-29. Core functionality is built with Qoder CLI.**
The eligibility rule is 80% of core functionality built with Qoder, and
failure scores the entire Qoder category zero. Judging is by Qoder credit
consumption.

Therefore: anything that ends in a file goes through `qodercli`. Specs,
code, tests, documentation, fixtures. Hand-written patches are prohibited,
however small — they reduce the measured proportion and produce no
evidence. Credits are not spent on open-ended exploration; a Qoder session
should end in a commit.

**P-30. Unshown work does not exist.**
All four scoring dimensions are assessed from a three-minute video.
A capability that cannot be seen in that video earns nothing, regardless
of how well it is built.

Every accepted feature must therefore answer: *what does this look like on
screen, and in which second of the demo?* Where it cannot be shown, it is
either cut or deliberately accepted as invisible infrastructure.

**P-31. Completeness before polish.**
Demo sub-dimensions are scored in 4 / 2 / 0 tiers with no partial credit.
A complete but plain journey outscores a beautiful partial one. The full
end-to-end path is finished before any effort is spent on visual
refinement.

**P-32. Reasoning is visibly the model's work.**
The AI multiplier applies to Innovation and ranges from ×2 to ×0.5. A
model bolted on as decoration scores worse than none at all. Qwen must be
visibly the reasoning core — parsing the objective, scoring options,
producing rationale — and this must be legible in the trace.

**P-33. Safety and cost control are demonstrated, not asserted.**
Compliance & Safety and Cost Controllability are scored sub-dimensions.
The deterministic authorisation gate, the treatment of unauthenticated
webhooks as untrusted, the per-journey call budget, and free-tier
operation are all shown on screen and named aloud.

**P-34. Sandbox status is stated plainly.**
Atlas sandbox orders are not real transactions. The demo says so. Honest
framing is a scoring asset, not a weakness.

---

## Article IX — Visual design

*Added 29 August 2026. The reference implementation is
`.antabay/console-mockup.html`, built from verified journey data.*

**P-35. The design language is the airline operations flight strip.**
Paper ground, ink-blue text, typed monospace data, hairline rules, square
corners. Ops control rooms move one strip per flight between racks as
state changes; the journey state machine is that rack. Palette is fixed:
paper `#E4E2DC`, strip `#FAF9F7`, ink `#141A21`, rule `#C2BEB5`, hold
amber `#B0700F`, violation red `#9E2B1C`, confirmation blue `#1B5A87`,
simulation violet `#6B3FA0`. Colour carries meaning and is never
decorative.

**P-36. The expiry clocks are the signature element.**
All three — offer window, session, ticketing deadline — are permanently
visible with time remaining and a depleting bar. A spent clock is shown
spent, not hidden. This is the most distinctive thing on the screen and
nothing may crowd it.

**P-37. Three moments carry visual weight; nothing else does.**
The rejection of an option that passes naive filters, the statement that
the objective is violated, and the authorisation gate. These are marked
with a coloured rule and given room. Everything else in the trace is
uniform and quiet.

**P-38. A decision is never shown without its reason.**
Every rejection states the constraint violated. Every policy decision
cites the rule that produced it. Rule identifiers appear in the interface.

**P-39. Density is calibrated to the reader.**
The console cites endpoints, identifiers, timings and rule names. The
traveller surface states outcomes in plain language and shows none of it.
Both render from the same event stream.

**P-40. Provenance is permanently visible.**
Sandbox status, the reasoning model, and any active simulation are stated
in a persistent footer, not disclosed only on request.

**P-41. Legibility at video scale is a requirement, not a preference.**
The interface is assessed as a recording viewed small. Any element that
cannot be read at reduced size is redesigned or removed.

---

## Amendment

Amendments require a version bump and a one-line rationale recorded below. Principles may be tightened at any time. Loosening a principle before the submission deadline requires an explicit written reason in this file — "it was slowing us down" is not one.

| Version | Date | Change |
|---|---|---|
| 1.0.0 | 14 Aug 2026 | Initial draft |
| 1.1.0 | 14 Aug 2026 | Added Article VII (Testing), inherited from Bantáy. Two-tier E2E (P-26) added because the Atlas path consumes balance and rate budget. |
| 1.3.0 | 29 Aug 2026 | Added Article IX (Visual Design): flight-strip design language, fixed palette, expiry clocks as the signature element, three weighted moments, reason-with-every-decision, dual density, permanent provenance, video legibility. Reference implementation `.antabay/console-mockup.html`. |
| 1.2.0 | 19 Aug 2026 | Post-kickoff. Added Article VIII (Submission Constraints): everything is scored from a 3-minute video, and the Qoder 80% threshold is an all-or-nothing eligibility gate. Dropped AgentScope after the sponsor confirmed no framework restriction and no Alibaba hosting or LLM provision. |
