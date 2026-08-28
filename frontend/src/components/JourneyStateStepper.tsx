import type { JourneyStateSequence } from '../types/events'

export interface JourneyStateStepperProps {
  journeyState: JourneyStateSequence
}

export function JourneyStateStepper({ journeyState }: JourneyStateStepperProps) {
  const currentIndex = journeyState.current
    ? journeyState.stages.indexOf(journeyState.current)
    : -1

  return (
    <div className="console-sec">
      <div className="console-eyebrow">Journey state</div>
      <div className="rack" data-testid="journey-state-stepper">
        {journeyState.stages.map((stage, index) => {
          const status =
            index < currentIndex ? 'done' : index === currentIndex ? 'now' : 'pending'
          return (
            <div
              className={`rack-row ${status !== 'pending' ? status : ''}`.trim()}
              data-testid="journey-state-step"
              data-status={status}
              key={stage}
            >
              <span className="rack-mark">
                {status === 'done' ? '✓' : status === 'now' ? '▶' : '·'}
              </span>
              {stage}
            </div>
          )
        })}
      </div>
    </div>
  )
}
