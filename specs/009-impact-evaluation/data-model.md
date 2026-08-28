# Data Model: Objective Impact Evaluation and Alternative Discovery

## Entities

### ImpactEvaluation

One row per `evaluate_wake()` attempt (including superseded and
past-departure-inert attempts), for auditability (Constitution XIV) and
FR-005's "record the determination" requirement.

| Field | Type | Notes |
|---|---|---|
| `evaluation_id` | str (uuid) | Primary key |
| `journey_id` | str | FK to `journeys` |
| `triggering_event_id` | str | The `WAKE_REQUESTED` `JourneyEvent.event_id` that started this attempt |
| `triggering_sequence` | int | That event's `sequence` — used for the supersede check (research.md R8) |
| `started_at` | datetime | |
| `concluded_at` | datetime \| None | Null while `status == IN_PROGRESS` |
| `status` | enum: `IN_PROGRESS`, `COMPLETED`, `SUPERSEDED`, `INERT_PAST_DEPARTURE` | |
| `objective_satisfied` | bool \| None | Null for `SUPERSEDED`/`INERT_PAST_DEPARTURE` |
| `violation_description` | str \| None | Set when `objective_satisfied is False` (FR-003) |
| `violated_constraints` | list[str] (JSON) | Which objective field(s), e.g. `["latest_arrival"]` (FR-002) |
| `violation_extent` | str \| None | Quantified, e.g. `"47 minutes late"` (FR-004) |
| `recommendation_id` | str \| None | FK to `Recommendation`, set only on a successful recommendation |
| `no_alternative_reason` | str \| None | One of `"none_found"`, `"budget_exhausted"`, `"all_expired"` — internal only; traveller-facing report text is identical regardless (FR-012) |

### Recommendation

One row per alternative actually recommended (FR-010). Not created for a
no-alternative outcome.

| Field | Type | Notes |
|---|---|---|
| `recommendation_id` | str (uuid) | Primary key |
| `evaluation_id` | str | FK to `ImpactEvaluation` |
| `option_id` | str | FK to the verified `FlightOption` (feature 002) |
| `verification_id` | str | FK to the `VerificationResult` that confirmed it (feature 004, NFR-001) |
| `cost_relative_description` | str | e.g. `"+$42 over current booking"` — relative, never absolute (FR-009) |
| `rationale` | str | One sentence (NFR-002) |
| `constraint_breach` | bool | True if this is the only objective-preserving option and it breaches a stated constraint (FR-011) |
| `constraint_breach_detail` | str \| None | Which constraint, stated explicitly when `constraint_breach` is True |

### Objective Element Check (in-memory only, not persisted separately)

The per-field comparison described in research.md R4. Represented as a
list of `(field_name, previous_value, claimed_value, constraint_type,
satisfied: bool)` tuples produced during evaluation and folded into
`ImpactEvaluation.violated_constraints`/`violation_extent` — not its own
table, since every element's result is already fully captured by those
two fields plus the event payload (below).

## New `EventType` members (`journey/models/events.py`)

Added to the existing `EventType(str, Enum)` alongside the current 15
members:

```python
IMPACT_EVALUATION_SATISFIED = "impact_evaluation_satisfied"
ALTERNATIVE_RECOMMENDED = "alternative_recommended"
NO_ALTERNATIVE_FOUND = "no_alternative_found"
IMPACT_EVALUATION_SUPERSEDED = "impact_evaluation_superseded"
```

`OBJECTIVE_VIOLATED` (already defined, never produced until now) is
reused as-is for the violation case — no new event type needed for it.

New payload models, registered in `_PAYLOAD_MODELS` following the
existing convention:

```python
class ImpactEvaluationSatisfiedPayload(BaseModel):
    evaluation_id: str

class AlternativeRecommendedPayload(BaseModel):
    evaluation_id: str
    recommendation_id: str
    option_id: str
    cost_relative_description: str
    rationale: str
    constraint_breach: bool
    constraint_breach_detail: str | None = None

class NoAlternativeFoundPayload(BaseModel):
    evaluation_id: str

class ImpactEvaluationSupersededPayload(BaseModel):
    evaluation_id: str
    superseded_by_event_id: str
```

`ObjectiveViolatedPayload` (existing, unchanged) is used exactly as
defined: `description: str`, `violated_constraints: list[str]`.

## Integration points on existing modules

- **`journey/services/webhook_service.py`**: `WebhookService.__init__`
  gains `on_wake: Callable[[str, JourneyEvent], None] | None = None`.
  Invoked in `confirm()` and `reconcile_active_journeys()` immediately
  after their existing `WAKE_REQUESTED` append (research.md R1). No
  change to either method's existing behaviour when `on_wake` is `None`.
- **`journey/api/main.py`**: `_reconciliation_loop` and
  **`journey/api/routers/webhooks.py`**'s `get_webhook_service()`
  each construct a `WebhookService()` today as two separate instances;
  both must be constructed with the same
  `on_wake=impact_evaluation_service.evaluate_wake` once a single shared
  `ImpactEvaluationService` is created at app startup.
- **No changes** to `journey/services/flight_search.py`,
  `journey/services/scoring_service.py`,
  `journey/services/verification_service.py`, or
  `journey/storage/repository.py`'s existing methods — all reused
  unmodified (research.md R5–R7). New repository methods are additive
  only (below).

## New repository methods (`journey/storage/repository.py`)

Following the existing one-section-per-feature convention:

- `save_impact_evaluation(evaluation: ImpactEvaluation) -> None`
- `update_impact_evaluation(evaluation: ImpactEvaluation) -> None` (used
  to move `IN_PROGRESS → COMPLETED/SUPERSEDED/INERT_PAST_DEPARTURE`)
- `get_impact_evaluation(evaluation_id: str) -> ImpactEvaluation`
- `save_recommendation(recommendation: Recommendation) -> None`
- `get_latest_impact_evaluation(journey_id: str) -> ImpactEvaluation | None`

## New tables (`journey/storage/tables.py`)

- `impact_evaluations` — columns mirror the `ImpactEvaluation` fields
  above (`violated_constraints` stored as JSON text, matching the
  existing convention e.g. `HeldIdentifier`/audit JSON columns elsewhere).
- `recommendations` — columns mirror the `Recommendation` fields above.

One additive Alembic migration, following `a2c318f74e91_add_call_budget_to_journeys.py`'s
pattern.

## New exceptions (`journey/errors.py`)

- `NoOrderReferenceForJourneyError(journey_id)` — raised if `evaluate_wake()`
  is invoked for a journey with no order reference to look up notifications
  against (should not occur given `reconcile_active_journeys()`'s own
  precondition, but kept explicit per this codebase's one-exception-per-
  condition convention rather than an assertion).
