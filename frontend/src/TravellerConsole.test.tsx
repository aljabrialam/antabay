import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { TravellerConsole } from './TravellerConsole'
import type { ConsoleState } from './types/events'

const mockState: { current: ConsoleState } = {
  current: {
    connectionStatus: 'live',
    journeyState: { current: 'MONITORING', stages: ['OBJECTIVE_CONFIRMED', 'MONITORING'] },
    log: [],
    objective: {
      hard_constraints: [{ field: 'destination', value: 'NRT' }],
      preferences: [],
    },
    pendingAuth: null,
    callBudget: null,
    heldIdentifiers: [],
    provenance: { environment: 'sandbox', reasoning_model: 'qwen', simulation_active: false },
    replayActive: false,
  },
}

vi.mock('./hooks/useEventStream', () => ({
  useEventStream: () => ({ state: mockState.current, connectionStatus: 'live' }),
}))

describe('TravellerConsole', () => {
  it('renders the objective and journey state', () => {
    render(<TravellerConsole journeyId="journey-1" replay={false} speed={1} />)

    expect(screen.getByTestId('traveller-console')).toBeTruthy()
    expect(screen.getByTestId('objective-panel')).toBeTruthy()
    expect(screen.getByTestId('journey-state-stepper')).toBeTruthy()
  })

  it('shows the authorisation prompt when one is pending', () => {
    mockState.current = {
      ...mockState.current,
      pendingAuth: {
        request_id: 'req-1',
        action: 'Rebook LJ201',
        cost: '+USD 6.24',
        objective_effect: 'Preserved',
        rule_id: 'AUTH-01',
        status: 'pending',
      },
    }

    render(<TravellerConsole journeyId="journey-1" replay={false} speed={1} />)

    expect(screen.getByTestId('auth-request-panel')).toBeTruthy()
  })

  it('omits operator-only panels (event log, call budget, expiry clocks)', () => {
    mockState.current = { ...mockState.current, pendingAuth: null }

    render(<TravellerConsole journeyId="journey-1" replay={false} speed={1} />)

    expect(screen.queryByTestId('event-log')).toBeNull()
    expect(screen.queryByTestId('call-budget')).toBeNull()
    expect(screen.queryByTestId('expiry-clock')).toBeNull()
  })
})
