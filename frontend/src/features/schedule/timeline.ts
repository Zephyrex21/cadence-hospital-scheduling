import type { AppointmentStatus } from '../../types'

/**
 * Pure geometry + formatting helpers for the schedule timeline.
 *
 * Times are rendered in UTC to stay consistent with stored data (the clinic
 * timezone defaults to UTC in the MVP). Keeping the math here — not inline in
 * the component — makes block positioning unit-testable.
 */

export const DAY_START_HOUR = 8
export const DAY_END_HOUR = 18
export const PX_PER_MIN = 1.4

export const dayWindowMinutes = (DAY_END_HOUR - DAY_START_HOUR) * 60
export const timelineHeightPx = dayWindowMinutes * PX_PER_MIN

/** Minutes from the top of the timeline (DAY_START_HOUR) for an ISO instant, in UTC. */
export function minutesFromDayStart(iso: string): number {
  const d = new Date(iso)
  return d.getUTCHours() * 60 + d.getUTCMinutes() - DAY_START_HOUR * 60
}

export interface BlockGeometry {
  top: number
  height: number
}

/** Pixel position/height of an appointment block, clamped to the visible day window. */
export function blockGeometry(startIso: string, endIso: string): BlockGeometry {
  const rawTop = minutesFromDayStart(startIso)
  const rawEnd = minutesFromDayStart(endIso)
  const top = Math.max(0, rawTop)
  const end = Math.min(dayWindowMinutes, rawEnd)
  const height = Math.max(0, end - top)
  return { top: top * PX_PER_MIN, height: height * PX_PER_MIN }
}

/** Hour labels for the left gutter, inclusive of the end hour. */
export function hourLabels(): number[] {
  const hours: number[] = []
  for (let h = DAY_START_HOUR; h <= DAY_END_HOUR; h++) hours.push(h)
  return hours
}

/** HH:MM in UTC for an ISO instant. */
export function formatTime(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(iso))
}

/** "08:00" label for an integer hour. */
export function formatHour(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`
}

const STATUS_TONE: Record<AppointmentStatus, 'neutral' | 'success' | 'warning' | 'danger' | 'info'> =
  {
    booked: 'info',
    checked_in: 'warning',
    in_progress: 'success',
    completed: 'neutral',
    cancelled: 'neutral',
    no_show: 'danger',
    displaced: 'danger',
  }

export function statusTone(status: AppointmentStatus) {
  return STATUS_TONE[status]
}

const STATUS_LABEL: Record<AppointmentStatus, string> = {
  booked: 'Booked',
  checked_in: 'Checked in',
  in_progress: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
  no_show: 'No show',
  displaced: 'Displaced',
}

export function statusLabel(status: AppointmentStatus): string {
  return STATUS_LABEL[status]
}

/** Today's date as YYYY-MM-DD in the clinic's reference (UTC) for the date picker. */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}
