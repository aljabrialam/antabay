import type {
  AuthorisationOutcomePayload,
  AuthorisationRequestedPayload,
  CallBudgetUpdatedPayload,
  DecisionPayload,
  ExternalCallPayload,
  IdentifierExpiredPayload,
  IdentifierIssuedPayload,
  JourneyEvent,
  ObjectiveViolatedPayload,
  OptionRejectedPayload,
  StateChangePayload,
} from '../types/events'

export interface EventItemProps {
  event: JourneyEvent
}

function isEmphasised(event: JourneyEvent): boolean {
  if (event.event_type === 'objective_violated') {
    return true
  }
  if (event.event_type === 'option_rejected') {
    return (event.payload as OptionRejectedPayload).satisfies_numeric_constraints
  }
  if (event.event_type === 'authorisation_requested') {
    return true
  }
  return false
}

function emphasisClass(event: JourneyEvent): string {
  return event.event_type === 'authorisation_requested' ? 'hold' : 'violation'
}

function Provider({ children }: { children: React.ReactNode }) {
  return (
    <span className="provider-value" data-testid="provider-value">
      {children}
    </span>
  )
}

function summarise(event: JourneyEvent): React.ReactNode {
  switch (event.event_type) {
    case 'external_call': {
      const p = event.payload as ExternalCallPayload
      return (
        <>
          <strong>
            <Provider>{p.endpoint}</Provider>
          </strong>{' '}
          · {p.outcome} · {p.elapsed_ms}ms
        </>
      )
    }
    case 'decision': {
      const p = event.payload as DecisionPayload
      return (
        <>
          {p.description}
          <span className="event-sub">{p.reason}</span>
        </>
      )
    }
    case 'state_change': {
      const p = event.payload as StateChangePayload
      return (
        <>
          {p.from_state} → <strong>{p.to_state}</strong>
        </>
      )
    }
    case 'identifier_issued': {
      const p = event.payload as IdentifierIssuedPayload
      return (
        <>
          Identifier issued: <Provider>{p.value}</Provider>
        </>
      )
    }
    case 'identifier_expired': {
      const p = event.payload as IdentifierExpiredPayload
      return <>Identifier expired: {p.identifier_id}</>
    }
    case 'call_budget_updated': {
      const p = event.payload as CallBudgetUpdatedPayload
      return <>Call budget: {p.budget_remaining} remaining</>
    }
    case 'authorisation_requested': {
      const p = event.payload as AuthorisationRequestedPayload
      return (
        <>
          <strong>Authorisation requested</strong>
          <span className="event-sub">
            {p.action} · {p.cost} · {p.objective_effect}
          </span>
        </>
      )
    }
    case 'authorisation_outcome': {
      const p = event.payload as AuthorisationOutcomePayload
      return (
        <>
          Authorisation {p.outcome}
          <span className="event-sub">rule {p.rule_id}</span>
        </>
      )
    }
    case 'option_rejected': {
      const p = event.payload as OptionRejectedPayload
      return (
        <>
          Rejected <Provider>{p.option_id}</Provider>
          <span className="event-sub">violates: {p.constraint_violated}</span>
        </>
      )
    }
    case 'objective_violated': {
      const p = event.payload as ObjectiveViolatedPayload
      return (
        <>
          <strong>Objective violated</strong>
          <span className="event-sub">{p.description}</span>
        </>
      )
    }
    case 'objective_set':
      return <>Objective set</>
    case 'replay_started':
      return <>Replay started</>
    case 'replay_ended':
      return <>Replay ended</>
    default:
      return null
  }
}

export function EventItem({ event }: EventItemProps) {
  const emphasised = isEmphasised(event)
  const classes = ['event-item']
  const testIds = ['event-item']
  if (emphasised) {
    classes.push('event-item-emphasised', emphasisClass(event))
    testIds.push('event-item-emphasised')
  }
  if (event.simulated) {
    classes.push('event-item-simulated')
    testIds.push('event-item-simulated')
  }

  return (
    // A row can carry more than one marker (e.g. emphasised + simulated),
    // so data-testid is a space-separated token list. Select it with the
    // CSS "contains word" operator: `[data-testid~="event-item-emphasised"]`.
    <div className={classes.join(' ')} data-testid={testIds.join(' ')}>
      <span className="event-time console-mono">
        {new Date(event.recorded_at).toLocaleTimeString()}
      </span>
      <span className="event-body">
        {event.simulated && <span className="event-sub">SIMULATED</span>}
        {summarise(event)}
        {(event.event_type === 'authorisation_requested' ||
          event.event_type === 'authorisation_outcome') && (
          <span className="rule-cite">
            {(event.payload as AuthorisationRequestedPayload | AuthorisationOutcomePayload)
              .rule_id}
          </span>
        )}
      </span>
    </div>
  )
}
