# Data Model: Authorisation Policy Engine

## ProposedAction

The input to evaluation. Not persisted by this feature in its own right —
it exists only for the duration of an `evaluate()`/`request_if_required()`
call. Carries exactly what the four rules need, and what FR-009's request
must state; nothing about the action's own execution mechanics.

| Field | Type | Notes |
|---|---|---|
| `action_id` | `str` | Caller-supplied, stable per distinct proposed action instance (research.md R4). An identical resubmission after a technical failure reuses the same `action_id`; a genuinely different action — even of the same type, even against the same booking (FR-014) — MUST use a new one. |
| `description` | `str` | Human-readable statement of the action, e.g. `"Rebook LJ201"`. Passed verbatim into the `action` field of the existing `AuthorisationRequestedPayload`. |
| `cost_amount` | `Decimal` | Signed. Positive = an outgoing charge. Zero is valid (e.g., a free-within-window cancellation). FR-003 triggers on any nonzero positive value, gross, not net (research.md R2). |
| `cost_description` | `str` | Human-readable cost statement relative to the traveller's current position, e.g. `"+USD 6.24"` — passed verbatim into the existing `cost` field. |
| `objective_effect` | `str` | Human-readable statement of the action's effect on the traveller's stated objective — passed verbatim into the existing `objective_effect` field. |
| `cancels_or_voids_booking` | `bool` | Drives FR-004. |
| `is_reversible` | `bool` | Drives FR-005 (rule triggers when `False`). |
| `breaches_hard_constraint` | `bool` | Drives FR-006. Whether a constraint is breached is decided by the caller (e.g., the scoring feature), not by this engine — this engine only acts on the caller's declaration. |

**Validation**: `action_id`, `description`, `cost_description`, and
`objective_effect` MUST be non-empty. `cost_amount` MUST NOT be `None`
(zero is explicit and valid; unknown is not — per spec.md's Edge Cases, an
unconfirmed cost does not exempt an action from FR-003, so callers MUST
resolve a cost, even a conservative estimate, before proposing an action
that will spend money).

---

## Rule

The fixed, enumerated set from FR-003 through FR-006. Not user-configurable
(NFR-003 — no configuration can add, remove, or reorder these).

| Rule ID | FR | Triggers when |
|---|---|---|
| `AUTH-MONEY` | FR-003 | `cost_amount > 0` |
| `AUTH-CANCEL` | FR-004 | `cancels_or_voids_booking is True` |
| `AUTH-IRREVERSIBLE` | FR-005 | `is_reversible is False` |
| `AUTH-CONSTRAINT` | FR-006 | `breaches_hard_constraint is True` |

Each rule is a pure function of one `ProposedAction` field — independently
testable in isolation, in both directions, per NFR-004.

---

## AuthorisationDecision

The engine's output for one `ProposedAction`. Not persisted as its own
record — it is the direct input to either "do nothing further" (permitted
autonomously) or "call the existing `EventService.append(AUTHORISATION_REQUESTED, ...)`"
(requires authorisation).

| Field | Type | Notes |
|---|---|---|
| `action_id` | `str` | Echoes the evaluated `ProposedAction`. |
| `classification` | `Literal["permitted_autonomously", "requires_authorisation"]` | FR-002 — exactly two values, no third. |
| `matched_rules` | `list[str]` | Every `Rule` ID that applied (FR-008) — not only the first. Empty iff `classification == "permitted_autonomously"`. |

---

## Existing entities this feature extends or reads (owned by feature 006, not redefined here)

- **`JourneyEvent`** (`journey/models/events.py`) — read via
  `JourneyRepository.get_events_from_sequence()` to answer "is there a
  live, matching, approved grant for this `action_id`/cost?" Never
  written to directly by anything new in this feature except through the
  existing `EventService.append()`.
- **`AuthorisationRequestedPayload`** — `request_id`, `action`, `cost`,
  `objective_effect`, `rule_id`, plus two new fields this feature adds,
  both optional and backward-compatible (006's existing fixtures never
  pass either and are unaffected):
  - `action_id: str | None = None` — without it, `EnforceAuthorised` would
    have no way to find "the current request for this action" at all; it
    is the field FR-014's scoping is actually implemented against.
  - `cost_amount: str | None = None` — the `ProposedAction.cost_amount`
    `Decimal`, serialised as text. `cost` alone (a human-readable string
    like `"+USD 50.00"`) cannot be compared against the raw `Decimal`
    `EnforceAuthorised` receives; this field is the one FR-013's
    cost-change comparison is actually implemented against.

  This feature is also the first to populate `rule_id` with a real value
  (one of the four Rule IDs above, or a `+`-joined list when more than one
  matched per FR-008) instead of a hand-seeded test placeholder.
- **`AuthorisationOutcomePayload`** — `request_id`, `outcome`
  (`"approved"` / `"refused"`), `rule_id`. Written only through the
  existing `EventService.record_auth_outcome()`; this feature does not
  add a new write path for it.

## New entity this feature adds

### `AuthorisationVoidedPayload` (new `EventType.AUTHORISATION_VOIDED`)

Recorded when `enforce_authorised()` finds a grant whose cost no longer
matches the action's current cost (FR-013). Closes the one gap in the
existing event vocabulary (research.md R3).

| Field | Type | Notes |
|---|---|---|
| `request_id` | `str` | The grant being voided. |
| `granted_cost` | `str` | The `cost_amount` (numeric, not the human-readable `cost` description — `EnforceAuthorised` only receives a raw `Decimal`, not a full `ProposedAction`) at the time authorisation was granted. |
| `current_cost` | `str` | The `cost_amount` now, that no longer matches. |

---

## Lifecycle (for one `action_id`)

```
evaluate(action) ──► permitted_autonomously ──► (nothing further recorded; caller proceeds)
       │
       └──► requires_authorisation
                  │
                  ▼
       existing live grant for (action_id, cost)?
          │                              │
         yes                            no
          │                              │
          ▼                              ▼
   reuse it, no new request     AUTHORISATION_REQUESTED (new request_id)
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                     approved         refused         no response
                          │               │               │
                          ▼               ▼               ▼
                  enforce_authorised   blocked         blocked
                  returns True         (FR-012)        (FR-012, FR-010)
                          │
                          ▼
              cost changes before execution?
                  │              │
                 yes             no
                  │              │
                  ▼              ▼
       AUTHORISATION_VOIDED   still authorised
       (FR-013); re-request
       required
```
