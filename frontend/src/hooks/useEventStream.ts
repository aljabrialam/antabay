import { fetchEventSource } from '@microsoft/fetch-event-source'
import { useEffect, useReducer, useRef } from 'react'
import { apiUrl } from '../lib/apiBase'
import {
  consoleReducer,
  initialState,
} from '../reducer/consoleReducer'
import type { ConsoleAction } from '../reducer/consoleReducer'
import { useExpiryClocks } from './useExpiryClocks'
import type { ConsoleState, EventType, JourneyEvent } from '../types/events'

export interface UseEventStreamResult {
  state: ConsoleState
  connectionStatus: ConsoleState['connectionStatus']
}

const ACTION_FOR_EVENT_TYPE: Record<EventType, ConsoleAction['type']> = {
  external_call: 'EXTERNAL_CALL',
  decision: 'DECISION',
  state_change: 'STATE_CHANGE',
  identifier_issued: 'IDENTIFIER_ISSUED',
  identifier_expired: 'IDENTIFIER_EXPIRED',
  call_budget_updated: 'CALL_BUDGET_UPDATED',
  authorisation_requested: 'AUTH_REQUESTED',
  authorisation_outcome: 'AUTH_OUTCOME',
  option_rejected: 'OPTION_REJECTED',
  objective_violated: 'OBJECTIVE_VIOLATED',
  objective_set: 'OBJECTIVE_SET',
  replay_started: 'REPLAY_STARTED',
  replay_ended: 'REPLAY_ENDED',
}

interface SSEMessage {
  event: string
  id: string
  data: string
}

function toJourneyEvent(message: SSEMessage): JourneyEvent {
  const envelope = JSON.parse(message.data) as {
    event_id: string
    payload: JourneyEvent['payload']
    simulated: boolean
    recorded_at: string
  }
  return {
    event_id: envelope.event_id,
    journey_id: '',
    sequence: Number(message.id),
    event_type: message.event as EventType,
    payload: envelope.payload,
    simulated: envelope.simulated,
    recorded_at: envelope.recorded_at,
  }
}

export interface UseEventStreamOptions {
  replay?: boolean
  speed?: number
}

export function useEventStream(
  journeyId: string,
  options: UseEventStreamOptions = {},
): UseEventStreamResult {
  const { replay = false, speed = 1 } = options
  const [state, dispatch] = useReducer(consoleReducer, initialState)
  const dispatchRef = useRef(dispatch)
  dispatchRef.current = dispatch

  useEffect(() => {
    const dispatchAction = (action: ConsoleAction) => dispatchRef.current(action)
    const controller = new AbortController()

    dispatchAction({ type: 'CONNECTION_STATUS', status: 'connecting' })

    const url = replay
      ? apiUrl(`/journeys/${journeyId}/events/replay?speed=${speed}`)
      : apiUrl(`/journeys/${journeyId}/events`)

    fetchEventSource(url, {
      signal: controller.signal,
      openWhenHidden: true,
      async onopen() {
        dispatchAction({ type: 'CONNECTION_STATUS', status: 'live' })
      },
      onmessage(message) {
        const actionType = ACTION_FOR_EVENT_TYPE[message.event as EventType]
        if (!actionType) {
          return
        }
        const event = toJourneyEvent(message)
        dispatchAction({ type: actionType, event } as ConsoleAction)
      },
      onerror() {
        dispatchAction({ type: 'CONNECTION_STATUS', status: 'reconnecting' })
      },
      onclose() {
        dispatchAction({ type: 'CONNECTION_STATUS', status: 'ended' })
      },
    })

    return () => controller.abort()
  }, [journeyId, replay, speed])

  useExpiryClocks(state.heldIdentifiers.length > 0, dispatch)

  return { state, connectionStatus: state.connectionStatus }
}
