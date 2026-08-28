import type { TravellerObjective } from '../types/events'

export interface ObjectivePanelProps {
  objective: TravellerObjective | null
}

export function ObjectivePanel({ objective }: ObjectivePanelProps) {
  return (
    <div className="console-sec" data-testid="objective-panel">
      <div className="console-eyebrow">Objective</div>
      {objective === null ? (
        <p className="event-sub">Awaiting objective…</p>
      ) : (
        <>
          {objective.hard_constraints.map((constraint) => (
            <div
              className="constraint-row"
              data-testid="objective-hard-constraint"
              key={`hard-${constraint.field}`}
            >
              <div>
                <div className="constraint-key">{constraint.field}</div>
                <div className="constraint-value provider-value">{constraint.value}</div>
              </div>
              <span className="constraint-tag hard">hard</span>
            </div>
          ))}
          {objective.preferences.map((preference) => (
            <div
              className="constraint-row"
              data-testid="objective-preference"
              key={`pref-${preference.field}-${preference.value}`}
            >
              <div>
                <div className="constraint-key">{preference.field}</div>
                <div className="constraint-value provider-value">{preference.value}</div>
              </div>
              <span className="constraint-tag">preference</span>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
