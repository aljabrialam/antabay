import type { Provenance } from '../types/events'

export interface ProvenanceBarProps {
  provenance: Provenance
  replayActive: boolean
}

export function ProvenanceBar({ provenance, replayActive }: ProvenanceBarProps) {
  return (
    <footer className="console-footer" data-testid="provenance-bar">
      <span>Environment: {provenance.environment || '—'}</span>
      <span>Reasoning: {provenance.reasoning_model || '—'}</span>
      {provenance.simulation_active && (
        <span className="console-pill sim">simulated event active</span>
      )}
      {replayActive && (
        <span className="console-pill sim" data-testid="replay-label">
          replay
        </span>
      )}
    </footer>
  )
}
