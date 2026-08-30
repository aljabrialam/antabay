import { expect, test } from '@playwright/test'
import { seedJourney } from './seed'

// 014-demonstration-capture, User Story 4 (FR-003, NFR-002).
//
// Records the traveller-facing surface (not the operator console) for
// the same underlying journey, at a handheld viewport, so trace text
// remains legible when the footage is viewed at reduced size.

test.use({
  video: 'on',
  viewport: { width: 390, height: 844 }, // handheld device size
})
test.setTimeout(60000)

test.describe('Traveller capture', () => {
  let capturedJourneyId: string | null = null

  test.afterEach(async ({ page }) => {
    const video = page.video()
    await page.close()
    if (video && capturedJourneyId) {
      await video.saveAs(`test-results/capture-traveller-${capturedJourneyId}.webm`)
    }
  })

  test('shows the traveller surface, not the operator console, for the same journey', async ({
    page,
  }) => {
    const { journey_id } = seedJourney('replay')
    capturedJourneyId = journey_id

    await page.goto(`/journey/${journey_id}/traveller/replay`)

    await expect(page.getByTestId('traveller-console')).toBeVisible()
    await expect(page.getByTestId('objective-panel')).toBeVisible()
    await expect(page.getByTestId('journey-state-stepper')).toBeVisible()

    // Operator-only surfaces must never render here.
    await expect(page.getByTestId('event-log')).toHaveCount(0)
    await expect(page.getByTestId('call-budget')).toHaveCount(0)

    await page.getByTestId('replay-speed-control').fill('10')

    // The authorisation tap the traveller narration describes.
    const authPanel = page.getByTestId('auth-request-panel')
    await expect(authPanel).toBeVisible({ timeout: 30000 })
    await expect(page.getByTestId('auth-approve-button')).toBeVisible()
  })
})
