# Feature Specification: Option Scoring Against Objective

**Feature Branch**: `003-option-scoring`

**Created**: 2026-08-28

**Status**: Draft

## Clarifications

### Session 2026-08-28

- Q: How are multiple preferences ordered against each other during ranking? → A: The confirmed objective carries an explicit priority ordering of its preferences; scoring follows that order.
- Q: Is scoring order-independent with respect to the input option set? → A: Yes — any permutation of the same option set produces identical output.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Hard Constraint Elimination and Selection (Priority: P1)

A traveller has stated an objective with hard constraints. After a flight
search returns options, the system eliminates every option that violates
any hard constraint, selects the best remaining option using the
traveller's preferences, and presents a rationale the traveller can check
against the displayed option data.

**Why this priority**: Constraint elimination is the safety gate of the
selection process. A recommended option that violates a hard constraint
is worse than no recommendation. Everything else depends on this working
correctly first.

**Independent Test**: Supply a set of options where some violate hard
constraints and some do not; confirm that violating options are eliminated
with the violated constraint recorded; confirm that the selected option
satisfies all hard constraints and a rationale is produced.

**Acceptance Scenarios**:

1. **Given** an option violates a hard constraint, **When** scoring
   runs, **Then** the option is eliminated and the specific constraint
   that it violated is recorded alongside it.

2. **Given** all options violate hard constraints, **When** scoring
   runs, **Then** no option is selected and the system reports which
   constraints could not be satisfied together.

3. **Given** one or more options survive hard-constraint elimination,
   **When** scoring runs, **Then** the selected option is accompanied by
   a rationale naming the objective elements satisfied.

4. **Given** an option whose held offer has already expired, **When**
   scoring runs, **Then** that option is eliminated regardless of how
   well it matches the objective.

5. **Given** options are expressed in different currencies, **When**
   scoring runs, **Then** no cross-currency comparison is made and any
   affected option is flagged rather than evaluated on cost.

---

### User Story 2 — Preference Ranking and Rejection Explanation (Priority: P2)

Among options that satisfy hard constraints, the system ranks them by the
traveller's stated preferences. For each option that would have ranked
highly but was rejected, the system produces a stated reason.

**Why this priority**: Ranking without explanation is opaque and
untestable. The traveller's objective demands that every significant
rejection be traceable to a specific reason, not just a score.

**Independent Test**: Supply a set of options all satisfying hard
constraints but differing on preferences; confirm the ranked order
matches the priority order declared in the confirmed objective; confirm
that each high-ranking rejected option carries a rejection reason.

**Acceptance Scenarios**:

1. **Given** multiple options satisfy hard constraints, **When** scoring
   runs, **Then** options are ordered by preference satisfaction and the
   top-ranked option is selected.

2. **Given** an option would rank highly but is rejected, **When**
   scoring produces output, **Then** a rejection reason is stated for
   that option.

3. **Given** arrival time is a preference, **When** scoring evaluates an
   option, **Then** the margin between the option's arrival and the
   traveller's deadline is computed and included in the rationale.

4. **Given** a scarcity or sell-out risk signal is present on an option,
   **When** scoring runs, **Then** that signal is incorporated into the
   evaluation and reflected in the rationale or rejection reason.

---

### User Story 3 — Connection and Multi-Leg Evaluation (Priority: P3)

Options with more than one leg are evaluated as connections. Connection
time between consecutive legs is computed. If the traveller has excluded
connections of a given kind, any option with such a connection is
eliminated regardless of its cost and arrival time.

**Why this priority**: Connection handling is a distinct evaluation
concern. A traveller who has excluded short connections must never be
offered one, even if it appears price-competitive.

**Independent Test**: Supply multi-leg options with varying connection
times and a traveller objective that excludes a connection type; confirm
that excluded connections are eliminated; confirm connection time is
computed and present in the evaluation output.

**Acceptance Scenarios**:

1. **Given** an option has more than one leg, **When** scoring runs,
   **Then** the option is treated as a connection and the connection time
   between consecutive legs is computed.

2. **Given** the traveller has excluded connections of a specific kind,
   **When** an option contains such a connection, **Then** the option is
   eliminated and the exclusion rule is recorded as the reason.

3. **Given** a direct option and a connection option both satisfy hard
   constraints, **When** preferences do not favour connections, **Then**
   the direct option ranks above the connection option.

---

### Edge Cases

- What if an option has no scarcity or sell-out signal? The option is
  evaluated without those inputs; their absence is noted in the
  evaluation output but does not disqualify the option.

- What if arrival time is not a stated preference or constraint? The
  margin computation is skipped for that objective; arrival time plays no
  role in ranking or elimination.

- What if the option set is empty after a search? No scoring runs; the
  system reports that no options are available to evaluate.

- What if two options are exactly equal after scoring all preference
  dimensions? The tie is reported explicitly; the system does not break
  ties arbitrarily without a stated tiebreaker rule.

- What if the confirmed objective has no preferences defined (only hard
  constraints)? The preference priority ordering is empty; all
  constraint-satisfying options are treated as equal on preferences.
  The system applies scarcity signal as the final tiebreaker; if no
  scarcity signal distinguishes them, a tie is reported.

- What if an option's currency differs from the objective currency? The
  option is not evaluated on cost; the currency mismatch is recorded and
  the option is flagged for human review rather than silently ranked.

- What if a held offer's expiry cannot be determined? The option is
  treated as potentially expired and eliminated with the uncertainty
  recorded.

- What if the connection time between legs is zero or negative (implied
  by the schedule data)? The connection is flagged as physically
  impossible and the option is eliminated.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST evaluate every returned option against the
  traveller's confirmed objective.

- **FR-002**: The system MUST eliminate any option that violates a hard
  constraint, and MUST record, for each eliminated option, the specific
  constraint it violated.

- **FR-003**: The system MUST rank surviving options using the
  traveller's stated preferences, applied in the priority order declared
  in the confirmed objective. The highest-priority preference is applied
  first; lower-priority preferences are applied only to break ties among
  options equal on all higher-priority dimensions.

- **FR-004**: The system MUST evaluate arrival time against the
  traveller's deadline and MUST express the result as the margin between
  the option's arrival time and that deadline.

- **FR-005**: The system MUST evaluate total cost using the single
  canonical price calculation; no alternative cost calculation may be
  used.

- **FR-006**: The system MUST treat any option comprising more than one
  leg as a connection, and MUST compute the connection time between each
  pair of consecutive legs.

- **FR-007**: The system MUST eliminate any option containing a
  connection of a kind the traveller has excluded, regardless of whether
  the option satisfies arrival time and cost constraints; the exclusion
  rule MUST be recorded as the elimination reason.

- **FR-008**: The system MUST incorporate available scarcity and
  sell-out risk signals into its evaluation when those signals are
  present in the option data.

- **FR-009**: The system MUST produce, for the selected option, a
  rationale that names each objective element the option satisfies.

- **FR-010**: The system MUST produce, for each option that would
  otherwise have ranked highly but was rejected, a stated reason for
  rejection.

- **FR-011**: The system MUST report when no option satisfies all hard
  constraints, stating which constraints could not be simultaneously
  satisfied.

- **FR-012**: The system MUST NOT select an option whose held offer has
  already expired at the time of scoring.

- **FR-013**: The system MUST express every scoring input in the
  objective's currency and time reference; it MUST NOT combine or
  compare values expressed in different currencies.

### Non-Functional Requirements

- **NFR-001**: Scoring MUST be deterministic and order-independent: any
  permutation of the same option set combined with the same confirmed
  objective MUST produce the same selection, the same ranking, and the
  same rationale. Input order MUST NOT influence the output.

- **NFR-002**: The rationale for the selected option MUST be expressible
  as a single short paragraph that a non-technical traveller can verify
  by checking it against the displayed option data.

- **NFR-003**: The scoring function MUST NOT consume any travel fact
  that did not originate from a verified external API response held in
  the journey record.

### Key Entities

- **ScoredOption**: An option that has been evaluated against the
  objective. Carries the original option, an outcome (selected,
  eliminated, or ranked), and the evaluation detail — rationale if
  selected, rejection reason if eliminated.

- **EliminationRecord**: The record of a hard-constraint or exclusion
  elimination. Names the option and the specific constraint or rule that
  caused elimination.

- **Rationale**: The human-readable explanation produced for the
  selected option. References objective elements by name; is verifiable
  against displayed option data without external knowledge.

- **RejectionReason**: The stated reason why a high-ranking option was
  not selected. References the specific factor (constraint, preference,
  expiry, currency mismatch) that caused rejection.

- **ConnectionEvaluation**: The computed result for a multi-leg option.
  Carries per-leg connection times and the outcome of any connection
  exclusion check.

- **ScoringRun**: The complete output of one scoring invocation — the
  confirmed objective, the full set of evaluated options, the selected
  option (if any), and the no-satisfying-option report (if applicable).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every option in a given set is evaluated; no option is
  silently skipped.

- **SC-002**: Every eliminated option carries a recorded constraint or
  rule identifier; no option is eliminated without a stated reason.

- **SC-003**: The selected option satisfies every hard constraint in the
  confirmed objective; no exception.

- **SC-004**: Scoring the same option set against the same objective
  twice in succession, and in any permutation of input order, produces
  identical output — same selection, same ranking, same rationale text.

- **SC-005**: The rationale for the selected option references only
  facts present in the option data and the confirmed objective; no
  inferred or authored facts appear.

- **SC-006**: When no option satisfies all hard constraints, the report
  names every constraint that could not be satisfied; none are omitted.

- **SC-007**: A non-technical reader presented with the selected option
  data and its rationale can verify every claim in the rationale without
  additional information.

---

## Assumptions

- Scoring operates on a set of options already returned by a flight
  search; it does not initiate searches or contact any external service.

- The confirmed objective is the sole source of constraints and
  preferences used in scoring; the system does not apply rules not
  present in the objective. Preferences are stored in an explicit
  priority order; that order is the sole determinant of ranking sequence.

- The canonical price calculation is the sum of adult base price and
  adult tax as recorded in the option; no other cost components are
  included unless the objective specifies them.

- "Held offer" refers to an option with a known expiry time; an option
  without an expiry is treated as expiry-unknown and handled per the
  edge case rule (eliminated with uncertainty recorded).

- Connection kind exclusion (FR-007) is defined as a typed preference in
  the confirmed objective (for example, "no connections shorter than
  60 minutes" or "direct flights only"); the system does not infer
  connection preferences.

- The system produces one selected option or a no-satisfying-option
  report; it does not present a ranked shortlist to the traveller.

- Scarcity and sell-out signals are incorporated as tie-breaking or
  weighting inputs, not as hard constraints; their absence does not
  block selection.
