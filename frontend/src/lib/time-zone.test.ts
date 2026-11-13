import { afterEach, describe, expect, it } from 'vitest'

import {
  clinicDate,
  clinicTzLabel,
  dayParam,
  formatTime,
  getClinicTimezone,
  setClinicTimezone,
} from './time'

afterEach(() => setClinicTimezone('Asia/Kolkata'))

describe('clinic timezone', () => {
  it('defaults to India Standard Time', () => {
    expect(getClinicTimezone()).toBe('Asia/Kolkata')
    expect(clinicTzLabel()).toBe('IST')
    expect(formatTime('2026-11-04T12:00:00Z')).toBe('5:30 pm')
    expect(dayParam('2026-11-04')).toBe('2026-11-04T12:00:00Z') // unchanged for IST
  })

  it('switches every formatter when the server says the clinic is elsewhere', () => {
    setClinicTimezone('America/New_York')
    expect(getClinicTimezone()).toBe('America/New_York')
    expect(formatTime('2026-11-04T12:00:00Z')).toBe('7:00 am')
    expect(clinicDate('2026-11-04T02:00:00Z')).toBe('2026-11-03') // still "yesterday" in New York
    expect(clinicTzLabel().length).toBeGreaterThan(0)
  })

  it('ignores a timezone name it does not understand', () => {
    setClinicTimezone('Not/AZone')
    expect(getClinicTimezone()).toBe('Asia/Kolkata')
  })

  it('still sends an instant on the picked day for a zone far ahead of UTC', () => {
    setClinicTimezone('Pacific/Auckland') // noon UTC is already the *next* day there
    expect(clinicDate(dayParam('2026-11-05'))).toBe('2026-11-05')
  })
})
