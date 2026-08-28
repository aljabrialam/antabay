import type { ConsoleState, HeldIdentifier, JourneyEvent } from '../types/events'
import type {
  AuthorisationOutcomePayload,
  AuthorisationRequestedPayload,
  CallBudgetUpdatedPayload,
  IdentifierExpiredPayload,
  IdentifierIssuedPayload,
  ObjectiveSetPayload,
  StateChangePayload,
} from '../types/events'

export const MAX_LOG_ENTRIES = 500

export type ConsoleAction =
  | { type: 'EXTERNAL_CALL'; event: JourneyEvent }
  | { type: 'DECISION'; event: JourneyEvent }
  | { type: 'STATE_CHANGE'; event: JourneyEvent }
  | { type: 'IDENTIFIER_ISSUED'; event: JourneyEvent }
  | { type: 'IDENTIFIER_EXPIRED'; event: JourneyEvent }
  | { type: 'CALL_BUDGET_UPDATED'; event: JourneyEvent }
  | { type: 'AUTH_REQUESTED'; event: JourneyEvent }
  | { type: 'AUTH_OUTCOME'; event: JourneyEvent }
  | { type: 'OPTION_REJECTED'; event: JourneyEvent }
  | { type: 'OBJECTIVE_VIOLATED'; event: JourneyEvent }
  | { type: 'OBJECTIVE_SET'; event: JourneyEvent }
  | { type: 'REPLAY_STARTED'; event: JourneyEvent }
  | { type: 'REPLAY_ENDED'; event: JourneyEvent }
  | { type: 'CLOCK_TICK' }
  | {
      type: 'CONNECTION_STATUS'
      status: ConsoleState['connectionStatus']
    }

export const initialState: ConsoleState = {
  log: [],
  journeyState: { stages: [], current: null },
  heldIdentifiers: [],
  callBudget: null,
  objective: null,
  pendingAuth: null,
  provenance: { environment: '', reasoning_model: '', simulation_active: false },
  replayActive: false,
  connectionStatus: 'connecting',
}

function appendLog(state: ConsoleState, event: JourneyEvent): JourneyEvent[] {
  const log = [...state.log, event]
  if (log.length > MAX_LOG_ENTRIES) {
    return log.slice(log.length - MAX_LOG_ENTRIES)
  }
  return log
}

export function consoleReducer(
  state: ConsoleState,
  action: ConsoleAction,
): ConsoleState {
  switch (action.type) {
    case 'EXTERNAL_CALL':
    case 'DECISION':
    case 'OPTION_REJECTED':
    case 'OBJECTIVE_VIOLATED': {
      return { ...state, log: appendLog(state, action.event) }
    }

    case 'STATE_CHANGE': {
      const payload = action.event.payload as StateChangePayload
      const stages = state.journeyState.stages.includes(payload.from_state)
        ? state.journeyState.stages
        : [...state.journeyState.stages, payload.from_state]
      const withCurrent = stages.includes(payload.to_state)
        ? stages
        : [...stages, payload.to_state]
      return {
        ...state,
        log: appendLog(state, action.event),
        journeyState: { stages: withCurrent, current: payload.to_state },
      }
    }

    case 'IDENTIFIER_ISSUED': {
      const payload = action.event.payload as IdentifierIssuedPayload
      const held: HeldIdentifier = {
        identifier_id: payload.identifier_id,
        value: payload.value,
        stale_at: payload.stale_at,
        spent: false,
        time_remaining_seconds: payload.stale_after_seconds,
      }
      return {
        ...state,
        log: appendLog(state, action.event),
        heldIdentifiers: [...state.heldIdentifiers, held],
      }
    }

    case 'IDENTIFIER_EXPIRED': {
      const payload = action.event.payload as IdentifierExpiredPayload
      return {
        ...state,
        log: appendLog(state, action.event),
        heldIdentifiers: state.heldIdentifiers.map((identifier) =>
          identifier.identifier_id === payload.identifier_id
            ? { ...identifier, spent: true, time_remaining_seconds: 0 }
            : identifier,
        ),
      }
    }

    case 'CALL_BUDGET_UPDATED': {
      const payload = action.event.payload as CallBudgetUpdatedPayload
      return {
        ...state,
        log: appendLog(state, action.event),
        callBudget: payload.budget_remaining,
      }
    }

    case 'AUTH_REQUESTED': {
      const payload = action.event.payload as AuthorisationRequestedPayload
      return {
        ...state,
        log: appendLog(state, action.event),
        pendingAuth: {
          request_id: payload.request_id,
          action: payload.action,
          cost: payload.cost,
          objective_effect: payload.objective_effect,
          rule_id: payload.rule_id,
          status: 'pending',
        },
      }
    }

    case 'AUTH_OUTCOME': {
      const payload = action.event.payload as AuthorisationOutcomePayload
      return {
        ...state,
        log: appendLog(state, action.event),
        pendingAuth:
          state.pendingAuth?.request_id === payload.request_id
            ? null
            : state.pendingAuth,
      }
    }

    case 'OBJECTIVE_SET': {
      const payload = action.event.payload as ObjectiveSetPayload
      return {
        ...state,
        log: appendLog(state, action.event),
        objective: {
          hard_constraints: payload.hard_constraints,
          preferences: payload.preferences,
        },
      }
    }

    case 'REPLAY_STARTED': {
      return { ...state, log: appendLog(state, action.event), replayActive: true }
    }

    case 'REPLAY_ENDED': {
      return { ...state, log: appendLog(state, action.event), replayActive: false }
    }

    case 'CLOCK_TICK': {
      return {
        ...state,
        heldIdentifiers: state.heldIdentifiers.map((identifier) =>
          identifier.spent
            ? identifier
            : {
                ...identifier,
                time_remaining_seconds: Math.max(
                  identifier.time_remaining_seconds - 1,
                  0,
                ),
              },
        ),
      }
    }

    case 'CONNECTION_STATUS': {
      return { ...state, connectionStatus: action.status }
    }

    default:
      return state
  }
}
