import { describe, expect, it } from 'vitest'

import { formatRunningDelay } from './api'

describe('dashboard formatting', () => {
  it('reads a doctor running delay', () => {
    expect(formatRunningDelay(0)).toBe('On time')
    expect(formatRunningDelay(-5)).toBe('On time')
    expect(formatRunningDelay(25)).toBe('25 min behind')
  })
})
