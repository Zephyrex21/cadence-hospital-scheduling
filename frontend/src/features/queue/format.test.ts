import { describe, expect, it } from 'vitest'

import { ACTION_LABEL, availableActions, formatWait } from './format'

describe('queue formatting', () => {
  it('formats wait estimates in plain language', () => {
    expect(formatWait(0)).toBe('Next up')
    expect(formatWait(20)).toBe('~20 min')
    expect(formatWait(60)).toBe('~1h')
    expect(formatWait(95)).toBe('~1h 35m')
  })

  it('offers valid transitions per status when manageable', () => {
    expect(availableActions('booked', true)).toEqual(['check_in', 'start', 'no_show'])
    expect(availableActions('checked_in', true)).toEqual(['start', 'no_show'])
    expect(availableActions('in_progress', true)).toEqual(['complete'])
    expect(availableActions('completed', true)).toEqual([])
  })

  it('offers nothing when the user cannot manage the appointment', () => {
    expect(availableActions('booked', false)).toEqual([])
  })

  it('labels every action', () => {
    expect(ACTION_LABEL.start).toBe('Start')
    expect(ACTION_LABEL.no_show).toBe('No show')
  })
})
