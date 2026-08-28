// Event type literals
export type EventType =
  | 'external_call'
  | 'decision'
  | 'state_change'
  | 'identifier_issued'
  | 'identifier_expired'
  | 'call_budget_updated'
  | 'authorisation_requested'
  | 'authorisation_outcome'
  | 'option_rejected'
  | 'objective_violated'
  | 'objective_set'
  | 'replay_started'
  | 'replay_ended'

// Per-event payload types (matching SSE payload schemas in contracts/sse_stream.md)
export interface ExternalCallPayload {
  endpoint: string
  outcome: string
  elapsed_ms: number
}

export interface DecisionPayload {
  description: string
  reason: string
}

export interface StateChangePayload {
  from_state: string
  to_state: string
}

export interface IdentifierIssuedPayload {
  identifier_id: string
  value: string
  stale_after_seconds: number
  stale_at: string
}

export interface IdentifierExpiredPayload {
  identifier_id: string
}

export interface CallBudgetUpdatedPayload {
  budget_remaining: number
}

export interface AuthorisationRequestedPayload {
  request_id: string
  action: string
  cost: string
  objective_effect: string
  rule_id: string
}

export interface AuthorisationOutcomePayload {
  request_id: string
  outcome: 'approved' | 'refused'
  rule_id: string
}

export interface OptionRejectedPayload {
  option_id: string
  constraint_violated: string
  satisfies_numeric_constraints: boolean
}

export interface ObjectiveViolatedPayload {
  description: string
  violated_constraints: string[]
}

export interface ObjectiveSetPayload {
  hard_constraints: Array<{ field: string; value: string }>
  preferences: Array<{ field: string; value: string }>
}

export interface ReplayStartedPayload {
  source_journey_id: string
  speed_multiplier: number
}

export type ReplayEndedPayload = Record<string, never>

// Union of all payload types
export type EventPayload =
  | ExternalCallPayload
  | DecisionPayload
  | StateChangePayload
  | IdentifierIssuedPayload
  | IdentifierExpiredPayload
  | CallBudgetUpdatedPayload
  | AuthorisationRequestedPayload
  | AuthorisationOutcomePayload
  | OptionRejectedPayload
  | ObjectiveViolatedPayload
  | ObjectiveSetPayload
  | ReplayStartedPayload
  | ReplayEndedPayload

// A single event from the journey_events table / SSE stream
export interface JourneyEvent {
  event_id: string
  journey_id: string
  sequence: number
  event_type: EventType
  payload: EventPayload
  simulated: boolean
  recorded_at: string
}

// Frontend-derived entities (held in reducer state)
export interface HeldIdentifier {
  identifier_id: string
  value: string
  stale_at: string
  spent: boolean
  time_remaining_seconds: number
}

export interface AuthorisationRequest {
  request_id: string
  action: string
  cost: string
  objective_effect: string
  rule_id: string
  status: 'pending' | 'approved' | 'refused'
}

export interface TravellerObjective {
  hard_constraints: Array<{ field: string; value: string }>
  preferences: Array<{ field: string; value: string }>
}

export interface Provenance {
  environment: string
  reasoning_model: string
  simulation_active: boolean
}

export interface JourneyStateSequence {
  stages: string[]
  current: string | null
}

// Reducer state (ConsoleState from contracts/frontend_components.md)
export interface ConsoleState {
  log: JourneyEvent[]
  journeyState: JourneyStateSequence
  heldIdentifiers: HeldIdentifier[]
  callBudget: number | null
  objective: TravellerObjective | null
  pendingAuth: AuthorisationRequest | null
  provenance: Provenance
  replayActive: boolean
  connectionStatus: 'connecting' | 'live' | 'reconnecting' | 'ended'
}
