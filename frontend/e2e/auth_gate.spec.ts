import { expect, test } from '@playwright/test'
import { seedJourney } from './seed'

// US2 — Authorisation Gate (FR-008–009, FR-015–016, SC-003).

test.describe('Authorisation Gate', () => {
  test('shows the outstanding request with emphasis, then approve records the outcome', async ({
    page,
  }) => {
    const { journey_id } = seedJourney('auth')

    await page.goto(`/journey/${journey_id}`)

    const panel = page.getByTestId('auth-request-panel')
    await expect(panel).toBeVisible()
    await expect(panel).toContainText('Rebook LJ201')
    await expect(panel).toContainText('+USD 6.24')
    await expect(panel).toContainText('Preserved')

    // The panel itself renders inside the hold-amber `.auth-gate` emphasis
    // treatment (FR-015); the log also carries an emphasised entry for it.
    // (Two rows match: the seeded option_rejected and this auth request —
    // asserting on .first() is enough to prove emphasis rendering works.)
    await expect(page.locator('[data-testid~="event-item-emphasised"]').first()).toBeVisible()

    await page.getByTestId('auth-approve-button').click()

    await expect(panel).toBeHidden()
    // getByTestId does an exact match, which is fine here since an
    // authorisation_outcome row carries no emphasis/simulated marker.
    const outcomeEntry = page.getByTestId('event-item').filter({ hasText: 'approved' })
    await expect(outcomeEntry).toBeVisible()
    await expect(outcomeEntry).toContainText('AUTH-01')
  })

  test('refuse records a refusal outcome and clears the panel', async ({ page }) => {
    const { journey_id } = seedJourney('auth')

    await page.goto(`/journey/${journey_id}`)
    await expect(page.getByTestId('auth-request-panel')).toBeVisible()

    await page.getByTestId('auth-refuse-button').click()

    await expect(page.getByTestId('auth-request-panel')).toBeHidden()
    const outcomeEntry = page.getByTestId('event-item').filter({ hasText: 'refused' })
    await expect(outcomeEntry).toBeVisible()
    await expect(outcomeEntry).toContainText('AUTH-01')
  })
})
