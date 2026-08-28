// Unit tests for consoleReducer US1 action handling (T024).
//
// TDD NOTE (T027): the reducer is a Phase 2 skeleton whose switch returns
// state unchanged for every action, so all tests below FAIL until the
// US1 reducer cases are implemented (T032).
import { describe, expect, it } from 'vitest'
import { consoleReducer, initialState, MAX_LOG_ENTRIES } from './consoleReducer'
import type { JourneyEvent } from '../types/events'

let nextId = 0

function makeEvent(
  event_type: JourneyEvent['event_type'],
  payload: JourneyEvent['payload'],
  overrides: Partial<JourneyEvent> = {},
): JourneyEvent {
  nextId += 1
  return {
    event_id: `event-${nextId}`,
    journey_id: 'journey-1',
    sequence: nextId,
    event_type,
    payload,
    simulated: false,
    recorded_at: '2026-08-28T12:00:00Z',
    ...overrides,
  }
}

describe('TestConsoleReducer US1 cases', () => {
  it('EXTERNAL_CALL appends the event to the log', () => {
    const event = makeEvent('external_call', {
      endpoint: '/shopping/flightoffices',
      outcome: 'success',
      elapsed_ms: 843,
    })
    const state = consoleReducer(initialState, { type: 'EXTERNAL_CALL', event })
    expect(state.log).toHaveLength(1)
    expect(state.log[0]).toEqual(event)
  })

  it('STATE_CHANGE updates journeyState and appends to the log', () => {
    const event = makeEvent('state_change', {
      from_state: 'OBJECTIVE_CONFIRMED',
      to_state: 'SEARCHING',
    })
    const state = consoleReducer(initialState, { type: 'STATE_CHANGE', event })
    expect(state.log).toHaveLength(1)
    expect(state.journeyState.current).toBe('SEARCHING')
    expect(state.journeyState.stages).toContain('OBJECTIVE_CONFIRMED')
    expect(state.journeyState.stages).toContain('SEARCHING')
  })

  it('IDENTIFIER_ISSUED adds a held identifier and appends to the log', () => {
    const event = makeEvent('identifier_issued', {
      identifier_id: 'ident-1',
      value: 'PNR-ABC123',
      stale_after_seconds: 1800,
      stale_at: '2026-08-28T12:30:00Z',
    })
    const state = consoleReducer(initialState, {
      type: 'IDENTIFIER_ISSUED',
      event,
    })
    expect(state.log).toHaveLength(1)
    expect(state.heldIdentifiers).toHaveLength(1)
    const held = state.heldIdentifiers[0]
    expect(held.identifier_id).toBe('ident-1')
    expect(held.value).toBe('PNR-ABC123')
    expect(held.spent).toBe(false)
    expect(held.time_remaining_seconds).toBe(1800)
  })

  it('IDENTIFIER_EXPIRED marks the identifier spent but keeps it listed', () => {
    const issued = makeEvent('identifier_issued', {
      identifier_id: 'ident-1',
      value: 'PNR-ABC123',
      stale_after_seconds: 1800,
      stale_at: '2026-08-28T12:30:00Z',
    })
    let state = consoleReducer(initialState, {
      type: 'IDENTIFIER_ISSUED',
      event: issued,
    })
    const expired = makeEvent('identifier_expired', { identifier_id: 'ident-1' })
    state = consoleReducer(state, { type: 'IDENTIFIER_EXPIRED', event: expired })

    // FR-014: a spent clock is shown as spent, not removed.
    expect(state.heldIdentifiers).toHaveLength(1)
    expect(state.heldIdentifiers[0].spent).toBe(true)
    expect(state.log).toHaveLength(2)
  })

  it('CALL_BUDGET_UPDATED updates callBudget and appends to the log', () => {
    const event = makeEvent('call_budget_updated', { budget_remaining: 19 })
    const state = consoleReducer(initialState, {
      type: 'CALL_BUDGET_UPDATED',
      event,
    })
    expect(state.log).toHaveLength(1)
    expect(state.callBudget).toBe(19)
  })

  it('CLOCK_TICK decrements time_remaining_seconds on each held identifier', () => {
    const issued = makeEvent('identifier_issued', {
      identifier_id: 'ident-1',
      value: 'PNR-ABC123',
      stale_after_seconds: 120,
      stale_at: '2026-08-28T12:02:00Z',
    })
    let state = consoleReducer(initialState, {
      type: 'IDENTIFIER_ISSUED',
      event: issued,
    })
    state = consoleReducer(state, { type: 'CLOCK_TICK' })
    state = consoleReducer(state, { type: 'CLOCK_TICK' })
    expect(state.heldIdentifiers[0].time_remaining_seconds).toBe(118)
  })

  it('CLOCK_TICK never decrements time_remaining_seconds below zero', () => {
    const issued = makeEvent('identifier_issued', {
      identifier_id: 'ident-1',
      value: 'PNR-ABC123',
      stale_after_seconds: 1,
      stale_at: '2026-08-28T12:00:01Z',
    })
    let state = consoleReducer(initialState, {
      type: 'IDENTIFIER_ISSUED',
      event: issued,
    })
    state = consoleReducer(state, { type: 'CLOCK_TICK' })
    state = consoleReducer(state, { type: 'CLOCK_TICK' })
    expect(state.heldIdentifiers[0].time_remaining_seconds).toBe(0)
  })

  it('OBJECTIVE_SET populates objective with constraints and preferences', () => {
    const event = makeEvent('objective_set', {
      hard_constraints: [
        { field: 'origin', value: 'SIN' },
        { field: 'destination', value: 'LHR' },
      ],
      preferences: [{ field: 'cabin', value: 'economy' }],
    })
    const state = consoleReducer(initialState, { type: 'OBJECTIVE_SET', event })
    expect(state.objective).not.toBeNull()
    expect(state.objective?.hard_constraints).toHaveLength(2)
    expect(state.objective?.hard_constraints[0]).toEqual({
      field: 'origin',
      value: 'SIN',
    })
    expect(state.objective?.preferences).toEqual([
      { field: 'cabin', value: 'economy' },
    ])
    expect(state.log).toHaveLength(1)
  })

  it('log is capped at MAX_LOG_ENTRIES (append-only, FR-013 statelessness)', () => {
    let state = initialState
    for (let i = 0; i < MAX_LOG_ENTRIES + 5; i += 1) {
      state = consoleReducer(state, {
        type: 'EXTERNAL_CALL',
        event: makeEvent('external_call', {
          endpoint: '/p',
          outcome: 'success',
          elapsed_ms: 1,
        }),
      })
    }
    expect(state.log).toHaveLength(MAX_LOG_ENTRIES)
  })

  it('AUTH_REQUESTED sets pendingAuth and appends to the log', () => {
    const event = makeEvent('authorisation_requested', {
      request_id: 'req-1',
      action: 'Rebook LJ201',
      cost: '+USD 6.24',
      objective_effect: 'Preserved',
      rule_id: 'AUTH-01',
    })
    const state = consoleReducer(initialState, { type: 'AUTH_REQUESTED', event })
    expect(state.log).toHaveLength(1)
    expect(state.pendingAuth).toEqual({
      request_id: 'req-1',
      action: 'Rebook LJ201',
      cost: '+USD 6.24',
      objective_effect: 'Preserved',
      rule_id: 'AUTH-01',
      status: 'pending',
    })
  })

  it('AUTH_OUTCOME clears pendingAuth and appends to the log', () => {
    const requested = makeEvent('authorisation_requested', {
      request_id: 'req-1',
      action: 'Rebook LJ201',
      cost: '+USD 6.24',
      objective_effect: 'Preserved',
      rule_id: 'AUTH-01',
    })
    let state = consoleReducer(initialState, { type: 'AUTH_REQUESTED', event: requested })
    const outcome = makeEvent('authorisation_outcome', {
      request_id: 'req-1',
      outcome: 'approved',
      rule_id: 'AUTH-01',
    })
    state = consoleReducer(state, { type: 'AUTH_OUTCOME', event: outcome })
    expect(state.pendingAuth).toBeNull()
    expect(state.log).toHaveLength(2)
  })

  it('REPLAY_STARTED sets replayActive true; REPLAY_ENDED sets it false', () => {
    const started = makeEvent('replay_started', {
      source_journey_id: 'journey-1',
      speed_multiplier: 4,
    })
    let state = consoleReducer(initialState, { type: 'REPLAY_STARTED', event: started })
    expect(state.replayActive).toBe(true)

    const ended = makeEvent('replay_ended', {})
    state = consoleReducer(state, { type: 'REPLAY_ENDED', event: ended })
    expect(state.replayActive).toBe(false)
  })
})
