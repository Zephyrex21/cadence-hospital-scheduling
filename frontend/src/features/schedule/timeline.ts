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

/** The visible hours of the timeline. Defaults to 08:00–18:00, but widens to fit
 *  any appointment outside it (night shifts, late emergencies) — otherwise those
 *  appointments would silently render with zero height. */
export interface DayWindow {
  startHour: number
  endHour: number
}

export const DEFAULT_WINDOW: DayWindow = { startHour: DAY_START_HOUR, endHour: DAY_END_HOUR }

export const windowMinutes = (w: DayWindow): number => (w.endHour - w.startHour) * 60
export const windowHeightPx = (w: DayWindow): number => windowMinutes(w) * PX_PER_MIN

function utcMinutesOfDay(iso: string): number {
  const d = new Date(iso)
  return d.getUTCHours() * 60 + d.getUTCMinutes()
}

/** Smallest window (always covering 08:00–18:00) that contains every appointment. */
export function computeWindow(
  appointments: { scheduled_start: string; scheduled_end: string }[],
): DayWindow {
  let startMin = DAY_START_HOUR * 60
  let endMin = DAY_END_HOUR * 60
  for (const a of appointments) {
    const s = utcMinutesOfDay(a.scheduled_start)
    const durationMin = (Date.parse(a.scheduled_end) - Date.parse(a.scheduled_start)) / 60_000
    startMin = Math.min(startMin, s)
    endMin = Math.max(endMin, s + durationMin)
  }
  return {
    startHour: Math.max(0, Math.floor(startMin / 60)),
    endHour: Math.min(24, Math.ceil(endMin / 60)),
  }
}

/** Minutes from the top of the timeline window for an ISO instant, in UTC. */
export function minutesFromDayStart(iso: string, window: DayWindow = DEFAULT_WINDOW): number {
  return utcMinutesOfDay(iso) - window.startHour * 60
}

export interface BlockGeometry {
  top: number
  height: number
}

/** Pixel position/height of an appointment block, clamped to the visible day window. */
export function blockGeometry(
  startIso: string,
  endIso: string,
  window: DayWindow = DEFAULT_WINDOW,
): BlockGeometry {
  const rawTop = minutesFromDayStart(startIso, window)
  // End is measured from the start (not the clock) so a block that crosses UTC
  // midnight keeps its full length instead of wrapping to a negative height.
  const rawEnd = rawTop + (Date.parse(endIso) - Date.parse(startIso)) / 60_000
  const top = Math.max(0, rawTop)
  const end = Math.min(windowMinutes(window), rawEnd)
  const height = Math.max(0, end - top)
  return { top: top * PX_PER_MIN, height: height * PX_PER_MIN }
}

/** Hour labels for the left gutter, inclusive of the end hour. */
export function hourLabels(window: DayWindow = DEFAULT_WINDOW): number[] {
  const hours: number[] = []
  for (let h = window.startHour; h <= window.endHour; h++) hours.push(h)
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
  return `${String(hour % 24).padStart(2, '0')}:00`
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
