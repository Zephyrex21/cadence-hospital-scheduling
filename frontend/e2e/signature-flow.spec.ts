import { expect, test, type Page } from '@playwright/test'

/**
 * The signature flow, end to end against a real browser + API:
 * sign in → book an appointment → triage + schedule an emergency walk-in →
 * confirm it displaced a booked patient → see that displacement → read the
 * decision + audit trail. Exercises every phase working together.
 */

const ADMIN = { email: 'admin@cadence.dev', password: 'cadence123' }

async function signIn(page: Page): Promise<void> {
  await page.goto('/login')
  await page.fill('input[name="email"]', ADMIN.email)
  await page.fill('input[name="password"]', ADMIN.password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible()
}

test('book → emergency displacement → audit', async ({ page }) => {
  await signIn(page)

  // 1. Book a routine appointment for the cardiology doctor.
  await page.getByRole('link', { name: 'Schedule' }).click()
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('Patient').selectOption({ label: 'Spare Sam (CAD-E0002)' })
  await dialog.getByLabel('Doctor').selectOption({ label: 'Dr. Able Cardio' })
  await dialog.getByLabel('Type').selectOption({ label: 'General consultation · 30m' })
  const firstSlot = dialog.locator('button[aria-pressed]').first()
  await expect(firstSlot).toBeVisible()
  await firstSlot.click()
  await dialog.getByRole('button', { name: 'Confirm booking' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()

  // 2. Triage + schedule an emergency walk-in (acuity A2 by default).
  await page.getByRole('link', { name: 'Emergency' }).click()
  await page.getByLabel('Patient').selectOption({ label: 'Walkin Wendy (CAD-E0003)' })
  await page.getByLabel('Appointment type').selectOption({ label: 'General consultation · 30m' })
  await page.getByLabel('Chief complaint').fill('Chest pain, 20 minutes')
  await page.getByRole('button', { name: 'Review plan' }).click()

  // The engine returns an auto-approvable plan that displaces the booked patient.
  const commit = page.getByRole('button', { name: 'Commit schedule' })
  await expect(commit).toBeVisible()
  await commit.click()
  await expect(page.getByText(/Emergency scheduled/)).toBeVisible()
  await expect(page.getByText(/1 appointment rescheduled/)).toBeVisible()

  // 3. The displacement is recorded and traceable.
  await page.getByRole('link', { name: 'Displacements' }).click()
  await expect(page.getByText('Booked Barbara')).toBeVisible()

  // 4. The decision and audit trail are visible to an administrator.
  await page.getByRole('link', { name: 'Decisions & audit' }).click()
  await expect(page.getByRole('heading', { name: 'Scheduling decisions' })).toBeVisible()
  await page.getByRole('button', { name: 'View trace' }).first().click()
  await expect(page.getByText(/Decision #/)).toBeVisible()
})
