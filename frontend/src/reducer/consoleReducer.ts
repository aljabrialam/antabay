import type { ConsoleState, JourneyEvent } from '../types/events'

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

export function consoleReducer(
  state: ConsoleState,
  action: ConsoleAction,
): ConsoleState {
  switch (action.type) {
    default:
      return state
  }
}
