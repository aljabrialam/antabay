import { useEffect } from 'react'
import type { Dispatch } from 'react'
import type { ConsoleAction } from '../reducer/consoleReducer'

const TICK_INTERVAL_MS = 1000

export function useExpiryClocks(
  hasHeldIdentifiers: boolean,
  dispatch: Dispatch<ConsoleAction>,
): void {
  useEffect(() => {
    if (!hasHeldIdentifiers) {
      return
    }
    const timer = window.setInterval(() => {
      dispatch({ type: 'CLOCK_TICK' })
    }, TICK_INTERVAL_MS)
    return () => window.clearInterval(timer)
  }, [hasHeldIdentifiers, dispatch])
}
