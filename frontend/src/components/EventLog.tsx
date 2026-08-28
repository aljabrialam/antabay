import type { JourneyEvent } from '../types/events'
import { EventItem } from './EventItem'

export interface EventLogProps {
  log: JourneyEvent[]
}

export function EventLog({ log }: EventLogProps) {
  return (
    <div className="console-sec">
      <div className="console-eyebrow">Agent trace</div>
      <div className="event-log" data-testid="event-log">
        {log.map((event) => (
          <EventItem event={event} key={event.event_id} />
        ))}
      </div>
    </div>
  )
}
