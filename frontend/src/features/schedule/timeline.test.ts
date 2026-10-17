import { describe, expect, it } from 'vitest'

import {
  PX_PER_MIN,
  blockGeometry,
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
})
