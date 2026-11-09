import { describe, expect, it } from 'vitest'

import { ACTION_LABEL, availableActions, formatWait, type QueueAccess } from './format'

const FULL: QueueAccess = { frontDesk: true, clinical: true }
const NONE: QueueAccess = { frontDesk: false, clinical: false }
const FRONT_DESK_ONLY: QueueAccess = { frontDesk: true, clinical: false }

describe('queue formatting', () => {
  it('formats wait estimates in plain language', () => {
    expect(formatWait(0)).toBe('Next up')
    expect(formatWait(20)).toBe('~20 min')
    expect(formatWait(60)).toBe('~1h')
    expect(formatWait(95)).toBe('~1h 35m')
  })

  it('offers valid transitions per status when manageable', () => {
    expect(availableActions('booked', FULL)).toEqual(['check_in', 'start', 'no_show'])
    expect(availableActions('checked_in', FULL)).toEqual(['start', 'no_show'])
    expect(availableActions('in_progress', FULL)).toEqual(['complete'])
    expect(availableActions('completed', FULL)).toEqual([])
  })

  it('offers nothing when the user cannot manage the appointment', () => {
    expect(availableActions('booked', NONE)).toEqual([])
  })

  it('labels every action', () => {
    expect(ACTION_LABEL.start).toBe('Start')
    expect(ACTION_LABEL.no_show).toBe('No show')
  })
})


describe('availableActions by role', () => {
  it('lets the front desk check a patient in or mark a no-show, but not start a consultation', () => {
    expect(availableActions('booked', FRONT_DESK_ONLY)).toEqual(['check_in', 'no_show'])
    expect(availableActions('checked_in', FRONT_DESK_ONLY)).toEqual(['no_show'])
    expect(availableActions('in_progress', FRONT_DESK_ONLY)).toEqual([])
  })

  it('lets a clinician-only user start and complete but not do front-desk actions', () => {
    const clinical: QueueAccess = { frontDesk: false, clinical: true }
    expect(availableActions('booked', clinical)).toEqual(['start'])
    expect(availableActions('in_progress', clinical)).toEqual(['complete'])
  })
})
