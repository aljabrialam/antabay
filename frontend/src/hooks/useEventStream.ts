import { useEffect, useReducer } from 'react'
import {
  consoleReducer,
  initialState,
} from '../reducer/consoleReducer'
import type { ConsoleState } from '../types/events'

export interface UseEventStreamResult {
  state: ConsoleState
  connectionStatus: ConsoleState['connectionStatus']
}

export function useEventStream(journeyId: string): UseEventStreamResult {
  const [state, dispatch] = useReducer(consoleReducer, initialState)

  useEffect(() => {
    dispatch({ type: 'CONNECTION_STATUS', status: 'connecting' })
  }, [journeyId])

  return { state, connectionStatus: state.connectionStatus }
}
