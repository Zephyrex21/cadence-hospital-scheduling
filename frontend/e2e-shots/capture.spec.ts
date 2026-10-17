import fs from 'node:fs'

import { expect, test } from '@playwright/test'

/**
 * Captures the key screens at desktop (1440) and mobile (390) in light and dark,
 * for self-review each phase. Not part of the signature-flow gate.
 */

const OUT = 'e2e-shots/out'
const THEMES = ['light', 'dark'] as const
const DESKTOP = { width: 1440, height: 900 }
const MOBILE = { width: 390, height: 844 }
const ROUTES = [
  { path: '/', name: 'dashboard' },
  { path: '/schedule', name: 'schedule' },
  { path: '/queue', name: 'queue' },
  { path: '/emergency', name: 'emergency' },
  { path: '/displacements', name: 'displacements' },
  { path: '/patients', name: 'patients' },
  { path: '/audit', name: 'audit' },
]
const MOBILE_ROUTES = ['/', '/schedule', '/queue', '/emergency']
const ADMIN = { email: 'admin@cadence.dev', password: 'cadence123' }

test.describe.configure({ mode: 'serial' })

for (const theme of THEMES) {
  test(`capture ${theme}`, async ({ page }) => {
    fs.mkdirSync(OUT, { recursive: true })
    await page.addInitScript((t) => {
      try {
        localStorage.setItem('cadence.theme', t)
      } catch {
        /* ignore */
      }
    }, theme)

    // Login (unauthenticated).
    for (const vp of [DESKTOP, MOBILE]) {
      await page.setViewportSize(vp)
      await page.goto('/login')
      await page.waitForSelector('input[name="email"]')
      await page.waitForTimeout(700)
      await page.screenshot({ path: `${OUT}/${theme}-${vp.width}-login.png` })
    }

    // Authenticate.
    await page.setViewportSize(DESKTOP)
    await page.goto('/login')
    await page.fill('input[name="email"]', ADMIN.email)
    await page.fill('input[name="password"]', ADMIN.password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByRole('heading', { name: /Welcome/ })).toBeVisible()

    // Desktop routes.
    for (const r of ROUTES) {
      await page.goto(r.path)
      await page.waitForTimeout(600)
      await page.screenshot({ path: `${OUT}/${theme}-1440-${r.name}.png`, fullPage: true })
    }

    // Booking modal.
    await page.goto('/schedule')
    await page.getByRole('button', { name: 'Book appointment' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.waitForTimeout(400)
    await page.screenshot({ path: `${OUT}/${theme}-1440-booking.png` })

    // Emergency review step (dry-run plan → mini-timeline + commit button).
    await page.goto('/emergency')
    await page.getByLabel('Patient').selectOption({ label: 'Walkin Wendy (CAD-E0003)' })
    await page.getByLabel('Appointment type').selectOption({ label: 'General consultation · 30m' })
    await page.getByLabel('Chief complaint').fill('Chest pain, 20 minutes')
    await page.getByRole('button', { name: 'Review plan' }).click()
    await expect(page.getByRole('button', { name: 'Commit schedule' })).toBeVisible()
    await page.waitForTimeout(1000)
    await page.screenshot({ path: `${OUT}/${theme}-1440-emergency-review.png`, fullPage: true })

    // Mobile routes.
    await page.setViewportSize(MOBILE)
    for (const path of MOBILE_ROUTES) {
      await page.goto(path)
      await page.waitForTimeout(600)
      const name = path === '/' ? 'dashboard' : path.slice(1)
      await page.screenshot({ path: `${OUT}/${theme}-390-${name}.png`, fullPage: true })
    }
  })
}
