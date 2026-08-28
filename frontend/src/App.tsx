import { useState } from 'react'
import './console.css'
import { AuthPanel } from './components/AuthPanel'
import { CallBudget } from './components/CallBudget'
import { EventLog } from './components/EventLog'
import { ExpiryClockPanel } from './components/ExpiryClockPanel'
import { JourneyStateStepper } from './components/JourneyStateStepper'
import { ObjectivePanel } from './components/ObjectivePanel'
import { ProvenanceBar } from './components/ProvenanceBar'
import { useEventStream } from './hooks/useEventStream'

function parseJourney(pathname: string): { journeyId: string | null; replay: boolean } {
  const match = pathname.match(/^\/journey\/([^/]+)(\/replay)?/)
  return { journeyId: match ? match[1] : null, replay: Boolean(match?.[2]) }
}

interface JourneyConsoleProps {
  journeyId: string
  replay: boolean
  speed: number
}

function JourneyConsole({ journeyId, replay, speed }: JourneyConsoleProps) {
  const { state, connectionStatus } = useEventStream(journeyId, { replay, speed })

  return (
    <div className="console-app">
      <header className="console-header">
        <div className="constraint-value">Antabay — journey console</div>
        <div className="console-mono">{journeyId}</div>
        <div
          className={`console-status ${connectionStatus}`}
          style={{ marginLeft: 'auto' }}
        >
          {connectionStatus}
        </div>
      </header>

      <main className="console-main">
        <div className="console-col">
          <ObjectivePanel objective={state.objective} />
          <JourneyStateStepper journeyState={state.journeyState} />
          <CallBudget callBudget={state.callBudget} />
        </div>

        <div className="console-col">
          <EventLog log={state.log} />
        </div>

        <div className="console-col">
          <ExpiryClockPanel heldIdentifiers={state.heldIdentifiers} />
          {state.pendingAuth !== null && (
            <AuthPanel journeyId={journeyId} pendingAuth={state.pendingAuth} />
          )}
        </div>
      </main>

      <ProvenanceBar provenance={state.provenance} replayActive={state.replayActive} />
    </div>
  )
}

function App() {
  const { journeyId, replay } = parseJourney(window.location.pathname)
  const [speed, setSpeed] = useState(1)

  if (!journeyId) {
    return (
      <div className="console-app">
        <header className="console-header">
          <div>Antabay — journey console</div>
        </header>
        <main className="console-main" style={{ gridTemplateColumns: '1fr' }}>
          <div className="console-col">
            Open <code>/journey/&#123;id&#125;</code> to observe a journey, or{' '}
            <code>/journey/&#123;id&#125;/replay</code> to replay a recording.
          </div>
        </main>
      </div>
    )
  }

  return (
    <>
      {replay && (
        <div className="replay-controls" style={{ padding: '8px 20px', background: 'var(--strip)' }}>
          <label htmlFor="replay-speed">Speed</label>
          <input
            data-testid="replay-speed-control"
            id="replay-speed"
            min={0.1}
            onChange={(event) => {
              const next = Number(event.target.value)
              if (next > 0) {
                setSpeed(next)
              }
            }}
            step={0.5}
            type="number"
            value={speed}
          />
        </div>
      )}
      {/* Keying on speed forces a clean remount (fresh reducer state) when
          the observer changes the replay pace, instead of appending a
          second replay onto the existing log. */}
      <JourneyConsole
        journeyId={journeyId}
        key={replay ? `replay-${speed}` : 'live'}
        replay={replay}
        speed={speed}
      />
    </>
  )
}

export default App
