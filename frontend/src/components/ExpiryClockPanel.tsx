import type { HeldIdentifier } from '../types/events'

export interface ExpiryClockPanelProps {
  heldIdentifiers: HeldIdentifier[]
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return [h, m, s].map((n) => String(n).padStart(2, '0')).join(':')
}

export function ExpiryClockPanel({ heldIdentifiers }: ExpiryClockPanelProps) {
  return (
    <div className="console-sec">
      <div className="console-eyebrow">Expiry clocks</div>
      {heldIdentifiers.map((identifier) => {
        const fraction =
          identifier.time_remaining_seconds <= 0
            ? 0
            : Math.min(identifier.time_remaining_seconds / 7200, 1)
        const barClass = identifier.spent
          ? 'clock-bar dead'
          : fraction < 0.2
            ? 'clock-bar warn'
            : 'clock-bar'
        return (
          <div
            className={`clock${identifier.spent ? ' spent' : ''}`}
            data-testid="expiry-clock"
            key={identifier.identifier_id}
          >
            <div className="clock-top">
              <span className="clock-name">{identifier.identifier_id}</span>
              <span className="clock-time console-mono">
                {identifier.spent ? '—' : formatTime(identifier.time_remaining_seconds)}
              </span>
            </div>
            <div className={barClass}>
              <i style={{ width: `${fraction * 100}%` }} />
            </div>
            {identifier.spent && (
              <div className="event-sub" data-testid="expiry-clock-spent">
                spent
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
