import { AuthPanel } from './components/AuthPanel'
import { JourneyStateStepper } from './components/JourneyStateStepper'
import { ObjectivePanel } from './components/ObjectivePanel'
import { useEventStream } from './hooks/useEventStream'

export interface TravellerConsoleProps {
  journeyId: string
  replay: boolean
  speed: number
}

/**
 * The traveller-facing surface (014-demonstration-capture, research.md
 * R5): the same event stream and reducer the operator console uses, at
 * phone density — objective, current state, and the authorisation tap
 * when one is pending. No event log, call budget, or expiry-clock detail
 * — those are operator-only (Constitution Principle XX: operator and
 * traveller surfaces render from the same stream at different densities).
 */
export function TravellerConsole({ journeyId, replay, speed }: TravellerConsoleProps) {
  const { state } = useEventStream(journeyId, { replay, speed })

  return (
    <div className="console-app" data-testid="traveller-console">
      <header className="console-header">
        <div className="constraint-value">Antabay</div>
      </header>

      <main className="console-main" style={{ gridTemplateColumns: '1fr' }}>
        <div className="console-col">
          <ObjectivePanel objective={state.objective} />
          <JourneyStateStepper journeyState={state.journeyState} />
          {state.pendingAuth !== null && (
            <AuthPanel journeyId={journeyId} pendingAuth={state.pendingAuth} />
          )}
        </div>
      </main>
    </div>
  )
}
