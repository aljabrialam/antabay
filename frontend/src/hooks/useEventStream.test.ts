// Unit tests for the useEventStream hook (T025).
//
// TDD NOTE (T027): the hook is a Phase 2 skeleton that only dispatches
// CONNECTION_STATUS 'connecting' and never opens an SSE connection, so
// every test below FAILS until the hook is implemented (T033).
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchEventSourceMock } = vi.hoisted(() => ({
  fetchEventSourceMock: vi.fn(),
}))

vi.mock('@microsoft/fetch-event-source', () => ({
  fetchEventSource: fetchEventSourceMock,
}))

import { useEventStream } from './useEventStream'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true

interface EventSourceMessage {
  event: string
  id: string
  data: string
  retry?: number
}

function sseMessage(
  event: string,
  id: number,
  payload: Record<string, unknown>,
  simulated = false,
): EventSourceMessage {
  return {
    event,
    id: String(id),
    data: JSON.stringify({
      event_id: `event-${id}`,
      payload,
      simulated,
      recorded_at: '2026-08-28T12:00:00Z',
    }),
  }
}

function getOptions(): {
  onopen: (response: Response) => Promise<void>
  onmessage: (message: EventSourceMessage) => void
  onerror: (error: unknown) => void
} {
  const call = fetchEventSourceMock.mock.calls[0]
  if (!call) throw new Error('fetchEventSource was never called')
  return call[1] as never
}

describe('TestUseEventStream', () => {
  beforeEach(() => {
    fetchEventSourceMock.mockReset()
  })

  it('opens the SSE connection to the journey events endpoint', () => {
    renderHook(() => useEventStream('journey-123'))

    expect(fetchEventSourceMock).toHaveBeenCalledTimes(1)
    expect(fetchEventSourceMock.mock.calls[0][0]).toBe('/journeys/journey-123/events')
    const options = getOptions()
    expect(typeof options.onopen).toBe('function')
    expect(typeof options.onmessage).toBe('function')
    expect(typeof options.onerror).toBe('function')
  })

  it('connectionStatus transitions connecting → live when the stream opens', async () => {
    const { result } = renderHook(() => useEventStream('journey-123'))

    expect(result.current.connectionStatus).toBe('connecting')

    await act(async () => {
      await getOptions().onopen(new Response('ok'))
    })

    expect(result.current.connectionStatus).toBe('live')
  })

  it('dispatches reducer actions for each SSE event type', async () => {
    const { result } = renderHook(() => useEventStream('journey-123'))
    const { onmessage } = getOptions()

    act(() => {
      onmessage(
        sseMessage('external_call', 1, {
          endpoint: '/shopping/flightoffices',
          outcome: 'success',
          elapsed_ms: 843,
        }),
      )
    })
    expect(result.current.state.log).toHaveLength(1)

    act(() => {
      onmessage(
        sseMessage('state_change', 2, {
          from_state: 'OBJECTIVE_CONFIRMED',
          to_state: 'SEARCHING',
        }),
      )
    })
    expect(result.current.state.journeyState.current).toBe('SEARCHING')

    act(() => {
      onmessage(
        sseMessage('identifier_issued', 3, {
          identifier_id: 'ident-1',
          value: 'PNR-ABC123',
          stale_after_seconds: 1800,
          stale_at: '2026-08-28T12:30:00Z',
        }),
      )
    })
    expect(result.current.state.heldIdentifiers).toHaveLength(1)

    act(() => {
      onmessage(sseMessage('call_budget_updated', 4, { budget_remaining: 19 }))
    })
    expect(result.current.state.callBudget).toBe(19)

    expect(result.current.state.log).toHaveLength(4)
    expect(result.current.state.log[0].sequence).toBe(1)
    expect(result.current.state.log[3].sequence).toBe(4)
  })

  it('propagates the simulated flag onto log entries (FR-010)', () => {
    const { result } = renderHook(() => useEventStream('journey-123'))
    const { onmessage } = getOptions()

    act(() => {
      onmessage(
        sseMessage(
          'external_call',
          1,
          { endpoint: '/p', outcome: 'success', elapsed_ms: 5 },
          true,
        ),
      )
    })

    expect(result.current.state.log).toHaveLength(1)
    expect(result.current.state.log[0].simulated).toBe(true)
  })

  it('marks the connection reconnecting on stream error', () => {
    const { result } = renderHook(() => useEventStream('journey-123'))
    const { onerror } = getOptions()

    act(() => {
      onerror(new Error('connection dropped'))
    })

    expect(result.current.connectionStatus).toBe('reconnecting')
  })
})
