import { expect, test } from '@playwright/test'
import { seedJourney } from './seed'

// US3 — Simulation and Replay (FR-010, FR-012, NFR-004–005, SC-004, SC-006).

const ALLOWED_HOSTS = new Set(['localhost:5173', 'localhost:8000'])

test.describe('Replay', () => {
  test('replay label is visible throughout, no request leaves localhost', async ({ page }) => {
    const { journey_id } = seedJourney('replay')

    const offHostRequests: string[] = []
    page.on('request', (request) => {
      const host = new URL(request.url()).host
      if (host && !ALLOWED_HOSTS.has(host)) {
        offHostRequests.push(request.url())
      }
    })

    await page.goto(`/journey/${journey_id}/replay`)

    await expect(page.getByTestId('replay-label')).toBeVisible()

    // Bump the pace so the ~90s recorded stream finishes in test time
    // instead of waiting on it in real time (no arbitrary sleeps).
    await page.getByTestId('replay-speed-control').fill('1000')

    await expect(page.getByTestId('replay-label')).toBeVisible()
    await expect(page.getByTestId('event-item').filter({ hasText: 'Replay ended' })).toBeVisible({
      timeout: 15000,
    })

    expect(offHostRequests).toEqual([])
  })

  test('simulated events are visually distinguished from live events', async ({ page }) => {
    const { journey_id } = seedJourney('replay')

    await page.goto(`/journey/${journey_id}/replay`)
    await page.getByTestId('replay-speed-control').fill('1000')

    await expect(page.getByTestId('event-item').filter({ hasText: 'Replay ended' })).toBeVisible({
      timeout: 15000,
    })

    const simulatedEvents = page.locator('[data-testid~="event-item-simulated"]')
    // The fixture carries two simulated events (a webhook call and the
    // objective_violated it triggers).
    await expect(simulatedEvents).toHaveCount(2)
  })
})
