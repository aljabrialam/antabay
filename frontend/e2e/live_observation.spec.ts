import { expect, test } from '@playwright/test'
import { seedJourney } from './seed'

// US1 — Live Journey Observation (FR-001–007, FR-013–019, SC-001–002).
// Each test seeds its own fresh journey (Constitution Principle XIII:
// order-independent, self-seeding data) and asserts only on observable
// state via stable data-testid locators — no arbitrary sleeps.

test.describe('Live Journey Observation', () => {
  test('renders objective, journey state, event log, call budget, and provenance', async ({
    page,
  }) => {
    const { journey_id } = seedJourney('live')

    await page.goto(`/journey/${journey_id}`)

    await expect(page.getByTestId('objective-panel')).toBeVisible()
    await expect(page.getByTestId('objective-hard-constraint').first()).toBeVisible()
    await expect(page.getByTestId('objective-preference').first()).toBeVisible()

    await expect(page.getByTestId('journey-state-stepper')).toBeVisible()
    await expect(page.getByTestId('journey-state-step')).toHaveCount(2)

    await expect(page.getByTestId('call-budget')).toHaveText('9')

    // objective_set, state_change, external_call, call_budget_updated,
    // 2x identifier_issued, identifier_expired, option_rejected.
    //
    // Playwright's getByTestId() does an EXACT match on the attribute
    // value, but EventItem's data-testid is a space-separated token list
    // when a row carries more than one marker (see EventItem.tsx) — so an
    // emphasised or simulated row's testid ("event-item event-item-...")
    // never matches getByTestId('event-item'). Use the CSS "contains word"
    // operator instead to count every row regardless of its markers.
    await expect(
      page.getByTestId('event-log').locator('[data-testid~="event-item"]'),
    ).toHaveCount(8)

    // Exactly one event carries emphasis in this seed: the option_rejected
    // whose satisfies_numeric_constraints is true (FR-015).
    await expect(page.locator('[data-testid~="event-item-emphasised"]')).toHaveCount(1)

    await expect(page.getByTestId('provenance-bar')).toBeVisible()
  })

  test('a spent expiry clock remains visible and is marked spent', async ({ page }) => {
    const { journey_id } = seedJourney('live')

    await page.goto(`/journey/${journey_id}`)

    const clocks = page.getByTestId('expiry-clock')
    await expect(clocks).toHaveCount(2)
    await expect(page.getByTestId('expiry-clock-spent')).toBeVisible()
    // The still-active identifier must not itself be marked spent.
    await expect(clocks.filter({ hasNotText: 'spent' }).first()).toBeVisible()
  })

  test('an active expiry clock counts down without polling or refresh', async ({ page }) => {
    const { journey_id } = seedJourney('live')

    // Installed after the initial render (not before navigation) so it
    // doesn't interfere with the SSE connection's own setup; only the
    // 1s countdown interval in useExpiryClocks needs virtualising here.
    await page.goto(`/journey/${journey_id}`)
    const activeClock = page
      .getByTestId('expiry-clock')
      .filter({ hasNotText: 'spent' })
      .first()
    await expect(activeClock).toBeVisible()

    const before = await activeClock.locator('.clock-time').innerText()
    await page.clock.install()
    await page.clock.fastForward(5000)
    await expect(activeClock.locator('.clock-time')).not.toHaveText(before)
  })
})
