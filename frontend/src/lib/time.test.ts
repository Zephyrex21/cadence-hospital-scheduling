import { describe, expect, it } from 'vitest'

import {
  addDays,
  clinicDate,
  clinicMinutesOfDay,
  dayParam,
  formatDate,
  formatDateLong,
  formatDateShort,
  formatDateTime,
  formatNumber,
  formatPickedDate,
  formatTime,
} from './time'
import { formatAge, formatDob, initials } from '../features/patients/format'

// Clinic time is Asia/Kolkata = UTC+5:30 (no daylight saving).
describe('clinic time (IST)', () => {
  it('formats 12-hour times with lowercase am/pm', () => {
    expect(formatTime('2026-10-30T11:12:00Z')).toBe('4:42 pm')
    expect(formatTime('2026-10-30T03:30:00Z')).toBe('9:00 am')
  })

  it('formats Indian day-first dates', () => {
    expect(formatDate('2026-10-30T06:00:00Z')).toBe('30 Oct 2026')
    expect(formatDateLong('2026-10-30T06:00:00Z')).toBe('Fri, 30 Oct 2026')
    expect(formatDateShort('2026-10-30T06:00:00Z')).toBe('Fri, 30 Oct')
    expect(formatDateTime('2026-10-30T11:12:00Z')).toBe('30 Oct, 4:42 pm')
    expect(formatPickedDate('2026-10-30')).toBe('Friday, 30 October 2026')
  })

  it('uses Indian digit grouping', () => {
    expect(formatNumber(1234567)).toBe('12,34,567')
  })

  it('knows the clinic calendar day, which starts at 18:30 UTC the evening before', () => {
    expect(clinicDate('2026-10-30T18:29:00Z')).toBe('2026-10-30')
    expect(clinicDate('2026-10-30T18:30:00Z')).toBe('2026-10-31') // midnight IST
    expect(clinicMinutesOfDay('2026-10-30T18:30:00Z')).toBe(0)
    expect(clinicMinutesOfDay('2026-10-30T11:12:00Z')).toBe(16 * 60 + 42)
  })

  it('sends noon UTC for a picked date (17:30 IST, the same clinic day)', () => {
    expect(dayParam('2026-10-31')).toBe('2026-10-31T12:00:00Z')
    expect(clinicDate(dayParam('2026-10-31'))).toBe('2026-10-31')
  })

  it('adds days across month and year boundaries', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29')
  })
})

describe('patient display helpers', () => {
  it('computes age as of a clinic date', () => {
    expect(formatAge('1978-03-14', '2026-10-30')).toBe('48 y')
    expect(formatAge('1978-12-02', '2026-10-30')).toBe('47 y') // birthday not reached yet
    expect(formatAge('2026-05-01', '2026-10-30')).toBe('5 mo')
    expect(formatAge('2026-10-20', '2026-10-30')).toBe('10 d')
  })

  it('formats dates of birth and initials', () => {
    expect(formatDob('1978-03-14')).toBe('14 Mar 1978')
    expect(initials('Dr. Priya Sharma')).toBe('PS')
    expect(initials('Mohammed Irfan Qureshi')).toBe('MI')
  })
})
