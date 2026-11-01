import { describe, expect, it } from 'vitest'

import {
  PX_PER_MIN,
  blockGeometry,
  computeWindow,
  formatHour,
  formatTime,
  minutesFromDayStart,
  statusTone,
} from './timeline'

// Clinic time is IST (UTC+5:30), so 02:30Z is 8:00 am on the clinic clock.
describe('timeline geometry (IST)', () => {
  it('computes minutes from the 8 am day start in clinic time', () => {
    expect(minutesFromDayStart('2026-10-13T02:30:00Z')).toBe(0) // 8:00 am IST
    expect(minutesFromDayStart('2026-10-13T04:00:00Z')).toBe(90) // 9:30 am IST
  })

  it('positions a block by start and duration', () => {
    const g = blockGeometry('2026-10-13T03:30:00Z', '2026-10-13T04:00:00Z') // 9:00-9:30 am IST
    expect(g.top).toBeCloseTo(60 * PX_PER_MIN)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN)
  })

  it('clamps blocks that start before the visible window', () => {
    const g = blockGeometry('2026-10-13T02:00:00Z', '2026-10-13T03:00:00Z') // 7:30-8:30 am IST
    expect(g.top).toBe(0)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN)
  })

  it('formats time as 12-hour clinic time', () => {
    expect(formatTime('2026-10-13T09:05:00Z')).toBe('2:35 pm')
    expect(formatTime('2026-10-13T18:30:00Z')).toBe('12:00 am') // IST midnight
  })

  it('formats hour labels', () => {
    expect(formatHour(8)).toBe('8 am')
    expect(formatHour(12)).toBe('12 pm')
    expect(formatHour(0)).toBe('12 am')
    expect(formatHour(24)).toBe('12 am')
  })

  it('maps in-progress to the success tone (protected consult)', () => {
    expect(statusTone('in_progress')).toBe('success')
    expect(statusTone('displaced')).toBe('danger')
  })

  it('keeps the default 8 am-8 pm window when everything fits', () => {
    const w = computeWindow([
      { scheduled_start: '2026-10-13T03:30:00Z', scheduled_end: '2026-10-13T04:00:00Z' },
    ])
    expect(w).toEqual({ startHour: 8, endHour: 20 })
  })

  it('widens the window so late appointments stay visible', () => {
    const late = { scheduled_start: '2026-10-13T15:30:00Z', scheduled_end: '2026-10-13T16:00:00Z' } // 9-9:30 pm IST
    const w = computeWindow([late])
    expect(w.endHour).toBeGreaterThanOrEqual(22)
    const g = blockGeometry(late.scheduled_start, late.scheduled_end, w)
    expect(g.height).toBeCloseTo(30 * PX_PER_MIN) // used to be 0 -> invisible
  })

  it('keeps a block that crosses clinic midnight visible', () => {
    const night = { scheduled_start: '2026-10-13T18:15:00Z', scheduled_end: '2026-10-13T18:45:00Z' } // 11:45 pm-12:15 am IST
    const w = computeWindow([night])
    const g = blockGeometry(night.scheduled_start, night.scheduled_end, w)
    expect(g.height).toBeGreaterThan(0)
  })
})
