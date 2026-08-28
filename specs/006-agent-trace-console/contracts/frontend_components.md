# Contract: Frontend UI Components

**Feature**: 006-agent-trace-console
**Type**: React component interface contracts
**Consumed by**: Playwright E2E tests, Vitest unit tests

---

## Data Attributes (test selectors)

All interactive and observable elements MUST carry `data-testid` attributes. The canonical set is:

| `data-testid` | Element | Notes |
|---|---|---|
| `objective-panel` | Container for the TravellerObjective display | FR-001 |
| `objective-hard-constraint` | Each hard constraint item | FR-001 |
| `objective-preference` | Each preference item | FR-001 |
| `journey-state-stepper` | Ordered stage sequence | FR-017 |
| `journey-state-step` | Each individual stage | FR-017 |
| `call-budget` | Remaining call budget display | FR-007 |
| `expiry-clock` | Each held-identifier clock | FR-003, FR-014 |
| `expiry-clock-spent` | A spent (expired) clock | FR-014 |
| `event-log` | The scrollable event stream container | FR-004, FR-005 |
| `event-item` | Each event row in the log | — |
| `event-item-emphasised` | An event carrying visual emphasis | FR-015 |
| `event-item-simulated` | An event flagged as simulated | FR-010 |
| `auth-request-panel` | Outstanding authorisation request | FR-008 |
| `auth-approve-button` | Approve action | FR-008, US2 |
| `auth-refuse-button` | Refuse action | FR-008, US2 |
| `provenance-bar` | Persistent footer with env/model/sim state | FR-018 |
| `replay-label` | Persistent replay indicator | NFR-004 |
| `replay-speed-control` | Speed multiplier input | FR-012 |
| `provider-value` | Any value rendered in provider typeface | FR-019 |

---

## Reducer State Shape

The React `useReducer` state MUST conform to:

```typescript
interface ConsoleState {
  log: JourneyEvent[];                          // append-only
  journeyState: JourneyStateSequence;           // FR-017
  heldIdentifiers: HeldIdentifier[];            // FR-002, FR-003, FR-014
  callBudget: number | null;                    // FR-007
  objective: TravellerObjective | null;         // FR-001
  pendingAuth: AuthorisationRequest | null;     // FR-008, FR-015
  provenance: Provenance;                       // FR-018
  replayActive: boolean;                        // NFR-004
  connectionStatus: 'connecting' | 'live' | 'reconnecting' | 'ended';
}
```

---

## Reducer Action Types

Each SSE `event_type` maps to a reducer action. The reducer MUST be a pure function with no side effects.

| SSE `event_type` | Reducer action | State change |
|---|---|---|
| `external_call` | `EXTERNAL_CALL` | Appends to `log` |
| `decision` | `DECISION` | Appends to `log` |
| `state_change` | `STATE_CHANGE` | Updates `journeyState`, appends to `log` |
| `identifier_issued` | `IDENTIFIER_ISSUED` | Adds to `heldIdentifiers`, appends to `log` |
| `identifier_expired` | `IDENTIFIER_EXPIRED` | Marks identifier as spent, appends to `log` |
| `call_budget_updated` | `CALL_BUDGET_UPDATED` | Updates `callBudget`, appends to `log` |
| `authorisation_requested` | `AUTH_REQUESTED` | Sets `pendingAuth`, appends to `log` |
| `authorisation_outcome` | `AUTH_OUTCOME` | Clears `pendingAuth`, appends to `log` |
| `option_rejected` | `OPTION_REJECTED` | Appends to `log` (emphasised if `satisfies_numeric_constraints`) |
| `objective_violated` | `OBJECTIVE_VIOLATED` | Appends to `log` (emphasised) |
| `replay_started` | `REPLAY_STARTED` | Sets `replayActive = true`, appends to `log` |
| `replay_ended` | `REPLAY_ENDED` | Sets `replayActive = false`, appends to `log` |
| `CLOCK_TICK` | `CLOCK_TICK` | Decrements `time_remaining_seconds` on each `HeldIdentifier` |
| `CONNECTION_STATUS` | `CONNECTION_STATUS` | Updates `connectionStatus` |

---

## Visual Emphasis Rules (FR-015)

Exactly three event classes carry visual emphasis. The test contract is:

| Condition | `data-testid` present | Colour token |
|---|---|---|
| `option_rejected` with `satisfies_numeric_constraints: true` | `event-item-emphasised` | Violation red `#9E2B1C` |
| `objective_violated` | `event-item-emphasised` | Violation red `#9E2B1C` |
| `pendingAuth !== null` | `auth-request-panel` + `event-item-emphasised` | Hold amber `#B0700F` |
| All other events | `event-item` only | Ink `#141A21` (uniform) |

---

## Provenance Bar Contract (FR-018)

The provenance bar MUST be permanently visible and MUST contain:

| Field | Content |
|---|---|
| Environment | `sandbox` or `live` |
| Reasoning model | Model name string |
| Simulation indicator | Visible and labelled if `simulation_active = true` |
| Replay indicator | `data-testid="replay-label"`, visible throughout replay |
