import { describe, expect, it } from 'vitest'

import type { QueueEntry } from '../../types'
import {
  ACTION_LABEL,
  availableActions,
  formatWait,
  splitQueue,
  type QueueAccess,
} from './format'

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

describe('splitQueue', () => {
  const entry = (id: number, status: QueueEntry['status'], waiting: boolean): QueueEntry => ({
    appointment_id: id,
    position: id,
    est_wait_min: 0,
    waiting,
    acuity: 'a4',
    status,
    scheduled_start: '2026-11-14T05:00:00Z',
    patient: { id, name: `P${id}`, mrn: `CAD-${id}` },
    doctor: { id: 1, name: 'Dr X' },
    type_name: 'General',
  })

  it('puts in-consult, checked-in and due patients in the live list, the rest in later', () => {
    const { live, later } = splitQueue([
      entry(1, 'in_progress', false),
      entry(2, 'checked_in', true),
      entry(3, 'booked', true),
      entry(4, 'booked', false),
    ])
    expect(live.map((e) => e.appointment_id)).toEqual([1, 2, 3])
    expect(later.map((e) => e.appointment_id)).toEqual([4])
  })

  it('handles an empty queue', () => {
    expect(splitQueue([])).toEqual({ live: [], later: [] })
  })
})
