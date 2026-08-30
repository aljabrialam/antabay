import { expect, test } from '@playwright/test'
import { seedJourney } from './seed'

// 014-demonstration-capture, User Story 2 (FR-002, FR-005, FR-006, FR-012).
//
// Records the operator console for a verified run's full replay. FR-005's
// three emphasised moments are held on screen by the replay's own real
// recorded inter-event gaps (the fixture already has multi-second gaps
// around each moment) — choosing a moderate speed (not the 1000x
// replay.spec.ts uses to compress a full replay into test time) preserves
// those gaps as genuine on-screen pauses, satisfying FR-006's "legible
// pace, not machine speed" without an artificial injected wait.

test.use({ video: 'on' })
test.setTimeout(60000)

test.describe('Operator capture', () => {
  let capturedJourneyId: string | null = null

  test.afterEach(async ({ page }) => {
    // FR-012: name the output file for the run that produced it, so
    // footage can be traced to a verified execution. Video finalises on
    // context/page close — saveAs() must be awaited after that, not
    // while the page is still open, or it hangs indefinitely.
    const video = page.video()
    await page.close()
    if (video && capturedJourneyId) {
      await video.saveAs(`test-results/capture-operator-${capturedJourneyId}.webm`)
    }
  })

  test('replay holds on each emphasised moment and records a video', async ({ page }) => {
    const { journey_id } = seedJourney('replay')
    capturedJourneyId = journey_id

    await page.goto(`/journey/${journey_id}/replay`)
    await expect(page.getByTestId('replay-label')).toBeVisible()

    // A legible pace, not machine speed: the fixture's own ~90s of real
    // recorded gaps become ~9s of on-screen pacing, preserving their
    // relative hold time around each emphasised moment.
    await page.getByTestId('replay-speed-control').fill('10')

    // Emphasised rows carry a compound data-testid ("event-item
    // event-item-emphasised"), which getByTestId's default exact-match
    // semantics never matches (see auth_gate.spec.ts's own comment on
    // this) — the CSS "contains word" selector is the correct query.
    const emphasised = page.locator('[data-testid~="event-item-emphasised"]')

    // Moment 1: the rejection of an option satisfying the numeric
    // constraints (option_rejected, satisfies_numeric_constraints=true).
    await expect(emphasised.first()).toBeVisible({ timeout: 30000 })

    // Moment 2: the objective-violated statement.
    const violation = emphasised.filter({ hasText: 'Objective violated' })
    await expect(violation).toBeVisible({ timeout: 30000 })

    // Moment 3: the authorisation gate.
    const authRequest = emphasised.filter({ hasText: 'Authorisation requested' })
    await expect(authRequest).toBeVisible({ timeout: 30000 })

    await expect(page.getByTestId('event-item').filter({ hasText: 'Replay ended' })).toBeVisible({
      timeout: 30000,
    })
  })
})
