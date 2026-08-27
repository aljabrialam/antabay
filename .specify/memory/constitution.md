<!--
SYNC IMPACT REPORT
==================
Version change: (template, unversioned) → 1.3.0
Bump rationale: MINOR — initial population of all principles, sections, and
governance from the Antabay project brief. No prior numbered version existed
in the file being replaced (it was a blank template).

Modified principles:
  All 21 principles are new (template placeholders replaced).

Added sections:
  - Core Principles (21 numbered principles)
  - Technology Standards
  - Development Workflow
  - Definition of Done
  - Governance

Removed sections:
  - Generic template placeholders ([SECTION_2_NAME], [SECTION_3_NAME], etc.)

Templates reviewed:
  ✅ .specify/templates/plan-template.md
     Constitution Check section is generic ("Gates determined based on
     constitution file") — no outdated hard-coded principle references found.
  ✅ .specify/templates/spec-template.md
     No constitution-specific references; template remains valid.
  ✅ .specify/templates/tasks-template.md
     No constitution-specific references; template remains valid.
  ⚠  .specify/templates/commands/ — directory not found; no command templates
     to review.

Follow-up TODOs:
  - RATIFICATION_DATE is set to 2026-08-28 (today, first adoption).
    Update if an earlier governance date applies.
  - No Tier 2 E2E sandbox run has been executed yet; "verified at least once"
    in the Definition of Done is a future gate.
-->

# Antabay Constitution

## Core Principles

### I. Truth Over Fluency

Every travel fact presented to a traveller MUST trace to a specific
third-party API response held in the journey record.
The system MUST NOT author travel data.
The system MUST NOT call an endpoint absent from the published API reference.
Opaque identifiers MUST be preserved byte-for-byte and MUST NOT be
constructed, parsed, or mutated.

**Rationale**: Fabricated or inferred travel data causes real financial and
physical harm. Traceability to a held API response is the only acceptable
source of truth.

### II. Verification After Action

A state-changing call MUST NOT be treated as confirmation of the resulting
state.
Every action MUST be followed by an independent read before journey state
is updated.
An ambiguous outcome MUST be reconciled; it MUST NOT be retried blindly.

**Rationale**: Third-party travel systems can accept a request yet fail to
commit it. Silent optimism here produces phantom bookings and missed flights.

### III. Separation of Reasoning and Authority

The language model MUST only reason and explain.
A deterministic policy engine MUST decide whether an action requires human
authorisation.
Authority MUST NOT be delegated to a model.

**Rationale**: Models are probabilistic; authority is binary. Conflating them
creates an unbounded attack surface and violates traveller trust.

### IV. Human Authorisation for High-Impact Actions

High-impact is defined as: spending money, cancelling or voiding a ticket,
committing to an itinerary, or acting outside a stated constraint.
Silence MUST NOT constitute consent.
Stated constraints MUST NOT be exceeded silently.

**Rationale**: Irreversible financial and logistical actions require explicit
human intent. Any system that infers consent from absence of objection is
operating outside its authority.

### V. Honest Simulation

Simulated events MUST be labelled as simulated in the interface, the README,
and the demo narration.
Simulation MUST be confined to event triggers.
Travel options MUST always come from live API responses, never from
fabricated or cached simulation data.

**Rationale**: Demos that blur the line between simulation and live data
mislead evaluators and erode confidence in the system's real capabilities.

### VI. State Outside the Agent

Journey state MUST live in durable storage, not in a context window, agent
memory, or a running process.
Every agent wake-up MUST rehydrate fully from storage before taking any
action.

**Rationale**: Processes restart. Context windows are finite. Journey
continuity is a safety property; it cannot depend on ephemeral runtime state.

### VII. Operational Discipline

Third-party rate limits MUST be treated as design constraints, not error
conditions.
Held identifiers MUST be re-verified before their documented expiry, not
at it.
Tool failures MUST degrade into stated, recorded, recoverable conditions;
they MUST NOT propagate silently or cause undefined behaviour.

**Rationale**: Travel APIs have hard quotas and time-bounded identifiers.
Systems that treat these as exceptional rather than expected will fail in
production.

### VIII. End-to-End Traceability

Every requirement MUST have acceptance criteria.
Every acceptance criterion MUST map to one or more automated tests.
Every automated test MUST map back to a requirement.
Traceability — not coverage percentage — is the test-sufficiency gate.

**Rationale**: Coverage percentages measure quantity. Traceability measures
whether the right things are tested. An untested requirement is an untested
guarantee.

### IX. Test-First Development

Tests MUST be written before implementation.
Tests MUST be verified to fail before implementation begins.
The Red → Green → Refactor cycle is mandatory.

**Rationale**: Tests written after the fact are often shaped by the
implementation rather than the requirement, undermining their value as
independent verification.

### X. Testing Pyramid

The target distribution is approximately 70% unit, 20% integration,
10% end-to-end.
End-to-end tests are reserved for critical business journeys.

**Rationale**: Pyramidal distribution maximises feedback speed while ensuring
full-stack confidence where it matters most.

### XI. Two-Tier End-to-End Testing

**Tier 1** executes full journeys against recorded third-party responses,
runs on every push, and is the default meaning of "the E2E suite".
**Tier 2** executes the same journeys against the live sandbox, runs on
demand and at least daily, and consumes balance and rate budget.
Recordings MUST be captured from Tier 2 runs and MUST NOT be handwritten.
Recordings MUST be re-captured whenever the tiers diverge.

**Rationale**: Live sandbox calls are rate-limited and cost money. Tier 1
gives fast, free CI. Tier 2 proves the recordings still match reality.

### XII. Assertions Against Observable External State

Tests touching state-changing endpoints MUST assert on what the external
system reports, not on what the local function returned.

**Rationale**: A function that returns success while the external system
disagrees is a lie. Observable external state is the only ground truth.

### XIII. Deterministic Automation

No arbitrary sleeps are permitted.
Locators MUST be stable and semantically meaningful.
Waits MUST be explicit and conditioned on observable state.
Tests MUST be order-independent and MUST create and clean their own data.

**Rationale**: Flaky tests produce false confidence. Determinism is a
first-class design constraint, not an optimisation.

### XIV. Auditability

Every observation, decision, tool call, and authorisation MUST be recorded
in an append-only journey audit trail.

**Rationale**: Post-incident analysis, regulatory compliance, and traveller
trust all require a complete, immutable record of what the system did and why.

### XV. AI-Assisted Development Under Human Review

AI MAY generate specifications, plans, tasks, and code.
Human verification is REQUIRED before commit.
No task SHALL be phrased as "build the application".
One task = one commit = one demonstrable capability.

**Rationale**: AI generation accelerates delivery but introduces errors that
only human review catches. Granular tasks keep commits reviewable and
demonstrable.

### XVI. Single Capability Principle

Each task, commit, and feature MUST deliver exactly one demonstrable
capability.
Tasks MUST NOT be bundled into omnibus units.

**Rationale**: Atomic capabilities are independently testable, reviewable,
and rollback-safe. Bundled tasks obscure failure attribution.

### XVII. Built With Qoder

Core functionality MUST be built using Qoder CLI.
Anything producing a file MUST be generated through it.
Hand-written patches are prohibited.

**Rationale**: Consistency, auditability, and reproducibility of the
development process depend on a single authoritative tool path.

### XVIII. Demonstrability

All assessment is made from a three-minute recording.
A capability that cannot be shown in that recording earns nothing.
Every feature specification MUST state what it looks like on screen.

**Rationale**: Invisible capabilities cannot be evaluated. The recording
constraint forces features to be concrete and visually verifiable.

### XIX. Completeness Before Polish

The complete end-to-end journey MUST be finished before any effort is spent
on visual refinement.

**Rationale**: Polish applied to an incomplete system is waste. The demo
window is fixed; completeness must be secured first.

### XX. Visual Discipline

The expiry clocks MUST be permanently visible and are the signature element
of the interface.
Exactly three moments SHALL carry visual weight: the rejection of an option
that passes naive filters, the statement that the objective is violated, and
the authorisation gate.
No decision SHALL be displayed without the reason that produced it; policy
decisions MUST cite the rule identifier.
The operator surface and the traveller surface MUST render from the same
event stream at different densities.
Sandbox status, reasoning model, and any active simulation MUST be stated
in a persistent footer.
Any element that cannot be read in a recording viewed at reduced size MUST
be redesigned or removed.

**Rationale**: Visual weight is a scarce resource. Misallocating it obscures
the moments that matter to evaluators and travellers.

### XXI. Scope Freeze

Scope freezes on 2026-08-20.
After the freeze date, work is limited to hardening, verification, and demo
preparation.

**Rationale**: Open scope in the final phase dilutes quality. The freeze date
creates a clear commitment boundary.

## Technology Standards

### Frontend

- **Framework**: React with TypeScript, bundled with Vite.

### Backend

- **Framework**: Python, FastAPI.
- **Agent loop**: Purpose-built ReAct loop. No third-party agent framework
  is permitted.

### Reasoning

- **Model**: Qwen via Alibaba Cloud Model Studio (DashScope), Singapore
  region.
- The model reasons and explains. It MUST NOT decide authority.

### Travel Execution

- **API**: Atlas API (atriptech.com), sandbox environment.
- Sandbox orders are test transactions and MUST be described as such in all
  interfaces and communications.

### Runtime and Data

- Deployed backend holding long-lived connections.
- Durable journey store outside the process (provider-agnostic).
- Static frontend served separately (provider-agnostic).

### Visual Design

The design language is the airline operations flight strip: paper ground,
ink-blue text, typed monospace data, hairline rules, square corners.
Palette is fixed; colour carries meaning, never decoration.

| Token             | Hex     | Meaning              |
|-------------------|---------|----------------------|
| Paper             | #E4E2DC | Page background      |
| Strip             | #FAF9F7 | Card/strip surface   |
| Ink               | #141A21 | Primary text         |
| Rule              | #C2BEB5 | Hairline dividers    |
| Hold amber        | #B0700F | Hold / warning state |
| Violation red     | #9E2B1C | Objective violated   |
| Confirmation blue | #1B5A87 | Authorised / confirmed |
| Simulation violet | #6B3FA0 | Simulated event      |

Reference implementation: `.antabay/console-mockup.html`.

### Testing Tools

- **Backend**: Pytest. Generate HTML test reports.
- **Frontend / E2E**: Playwright. Generate HTML reports, screenshots, and
  traces.

## Development Workflow

```
Business Request
  → Specification (/speckit.specify)
  → Clarify (/speckit.clarify)
  → Architecture Plan (/speckit.plan)
  → Tasks (/speckit.tasks)
  → Test Design
  → Test Generation
  → Implementation (/speckit.implement)
  → Validation
  → Regression
  → Deploy
```

## Definition of Done

A Feature is complete only when **all** of the following gates are passed:

- [ ] Specification approved
- [ ] Tasks completed
- [ ] Unit tests passed
- [ ] Integration tests passed
- [ ] Tier 1 end-to-end tests passed
- [ ] Tier 2 end-to-end verified at least once against the live sandbox
- [ ] Traceability confirmed from every requirement to at least one test
- [ ] Visual evidence generated (screenshot or recording)
- [ ] Human verification recorded

## Governance

This constitution supersedes all other practices and guidelines.
Amendments require:
1. A documented rationale describing what changed and why.
2. A version bump following semantic versioning:
   - **MAJOR**: backward-incompatible governance changes, principle removals,
     or redefinitions that invalidate prior compliance.
   - **MINOR**: new principle or section added, or materially expanded
     guidance.
   - **PATCH**: clarifications, wording corrections, typo fixes, non-semantic
     refinements.
3. Update the **Last Amended** date in the version line to the amendment date.
4. Propagation review across all `.specify/templates/` files.
5. Human sign-off before the amended constitution is committed.

All specifications, plans, tasks, and code generated under this project are
subject to this constitution. Non-compliance discovered during review MUST be
raised before the artefact is committed.

**Version**: 1.3.0 | **Ratified**: 2026-08-28 | **Last Amended**: 2026-08-28
