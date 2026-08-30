import { useState } from 'react'
import { apiUrl } from '../lib/apiBase'
import type { AuthorisationRequest } from '../types/events'

export interface AuthPanelProps {
  journeyId: string
  pendingAuth: AuthorisationRequest
}

export function AuthPanel({ journeyId, pendingAuth }: AuthPanelProps) {
  const [submitting, setSubmitting] = useState(false)

  async function respond(outcome: 'approved' | 'refused') {
    setSubmitting(true)
    try {
      await fetch(
        apiUrl(`/journeys/${journeyId}/authorisation/${pendingAuth.request_id}`),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ outcome }),
        },
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-gate" data-testid="auth-request-panel">
      <div className="console-eyebrow">Authorisation required</div>
      <div className="auth-gate-line">
        <span>Action</span>
        <strong className="provider-value">{pendingAuth.action}</strong>
      </div>
      <div className="auth-gate-line">
        <span>Cost</span>
        <strong className="provider-value">{pendingAuth.cost}</strong>
      </div>
      <div className="auth-gate-line">
        <span>Objective effect</span>
        <strong>{pendingAuth.objective_effect}</strong>
      </div>
      <div className="auth-btns">
        <button
          className="approve"
          data-testid="auth-approve-button"
          disabled={submitting}
          onClick={() => respond('approved')}
          type="button"
        >
          Approve
        </button>
        <button
          data-testid="auth-refuse-button"
          disabled={submitting}
          onClick={() => respond('refused')}
          type="button"
        >
          Refuse
        </button>
      </div>
      <div className="event-sub" style={{ marginTop: 8 }}>
        No response is recorded as a refusal. Nothing is spent.
      </div>
    </div>
  )
}
