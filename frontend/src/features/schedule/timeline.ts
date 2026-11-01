import { clinicMinutesOfDay, clinicToday, formatTime as formatClinicTime } from '../../lib/time'
import type { AppointmentStatus } from '../../types'

/**
 * Pure geometry + formatting helpers for the schedule timeline.
 *
 * Everything is laid out in clinic time (IST) — see `lib/time.ts`. Keeping the math
 * here, not inline in the component, makes block positioning unit-testable.
 */

export const DAY_START_HOUR = 8
export const DAY_END_HOUR = 20
export const PX_PER_MIN = 1.4

export const dayWindowMinutes = (DAY_END_HOUR - DAY_START_HOUR) * 60
export const timelineHeightPx = dayWindowMinutes * PX_PER_MIN

/** The visible hours of the timeline. Defaults to 8 am–8 pm, but widens to fit
 *  any appointment outside it (night shifts, late emergencies) — otherwise those
 *  appointments would silently render with zero height. */
export interface DayWindow {
  startHour: number
  endHour: number
}

export const DEFAULT_WINDOW: DayWindow = { startHour: DAY_START_HOUR, endHour: DAY_END_HOUR }

export const windowMinutes = (w: DayWindow): number => (w.endHour - w.startHour) * 60
export const windowHeightPx = (w: DayWindow): number => windowMinutes(w) * PX_PER_MIN

const clinicMinutes = (iso: string): number => clinicMinutesOfDay(iso)

/** Smallest window (always covering 8 am–8 pm) that contains every appointment. */
export function computeWindow(
  appointments: { scheduled_start: string; scheduled_end: string }[],
): DayWindow {
  let startMin = DAY_START_HOUR * 60
  let endMin = DAY_END_HOUR * 60
  for (const a of appointments) {
    const s = clinicMinutes(a.scheduled_start)
    const durationMin = (Date.parse(a.scheduled_end) - Date.parse(a.scheduled_start)) / 60_000
    startMin = Math.min(startMin, s)
    endMin = Math.max(endMin, s + durationMin)
  }
  return {
    startHour: Math.max(0, Math.floor(startMin / 60)),
    endHour: Math.min(24, Math.ceil(endMin / 60)),
  }
}

/** Minutes from the top of the timeline window for an ISO instant, in clinic time. */
export function minutesFromDayStart(iso: string, window: DayWindow = DEFAULT_WINDOW): number {
  return clinicMinutes(iso) - window.startHour * 60
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
  // End is measured from the start (not the clock) so a block that crosses
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

/** "4:42 pm" in clinic time for an ISO instant. */
export function formatTime(iso: string): string {
  return formatClinicTime(iso)
}

/** "8 am" / "12 pm" label for an integer hour (24 wraps to midnight). */
export function formatHour(hour: number): string {
  const h = hour % 24
  const suffix = h < 12 ? 'am' : 'pm'
  return `${h % 12 === 0 ? 12 : h % 12} ${suffix}`
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

/** Today's date in the clinic (IST) as YYYY-MM-DD, for the date picker. */
export function todayIso(): string {
  return clinicToday()
}
