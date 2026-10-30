import { describe, expect, it } from 'vitest'

import {
  PX_PER_MIN,
  blockGeometry,
  computeWindow,
  formatTime,
  minutesFromDayStart,
  statusTone,
} from './timeline'

describe('timeline geometry', () => {
  it('computes minutes from the 08:00 day start (UTC)', () => {
    expect(minutesFromDayStart('2026-10-13T08:00:00Z')).toBe(0)
    expect(minutesFromDayStart('2026-10-13T09:30:00Z')).toBe(90)
  })

  it('positions a block by start and duration', () => {
    const g = blockGeometry('2026-10-13T09:00:00Z', '2026-10-13T09:30:00Z')
    expect(g.top).toBeCloseTo(60 * PX_PER_MIN)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN)
  })

  it('clamps blocks that start before the visible window', () => {
    const g = blockGeometry('2026-10-13T07:30:00Z', '2026-10-13T08:30:00Z')
    expect(g.top).toBe(0)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN)
  })

  it('formats time in UTC regardless of locale', () => {
    expect(formatTime('2026-10-13T09:05:00Z')).toBe('09:05')
  })

  it('maps in-progress to the success tone (protected consult)', () => {
    expect(statusTone('in_progress')).toBe('success')
    expect(statusTone('displaced')).toBe('danger')
  })

  it('keeps the default 08:00-18:00 window when everything fits', () => {
    const w = computeWindow([
      { scheduled_start: '2026-10-13T09:00:00Z', scheduled_end: '2026-10-13T09:30:00Z' },
    ])
    expect(w).toEqual({ startHour: 8, endHour: 18 })
  })

  it('widens the window so late and overnight appointments stay visible', () => {
    const late = { scheduled_start: '2026-10-13T19:00:00Z', scheduled_end: '2026-10-13T19:30:00Z' }
    const w = computeWindow([late])
    expect(w.endHour).toBeGreaterThanOrEqual(20)
    const g = blockGeometry(late.scheduled_start, late.scheduled_end, w)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN) // used to be 0 -> invisible
  })

  it('keeps full length for a block that crosses UTC midnight', () => {
    const night = { scheduled_start: '2026-10-13T23:45:00Z', scheduled_end: '2026-10-14T00:15:00Z' }
    const w = computeWindow([night])
    const g = blockGeometry(night.scheduled_start, night.scheduled_end, w)
    expect(g.height).toBeGreaterThan(0)
  })
})
