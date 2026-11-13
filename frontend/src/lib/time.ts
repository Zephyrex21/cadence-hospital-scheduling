/**
 * Clinic time. Everything the user sees is in the clinic's timezone (India Standard
 * Time by default) and Indian conventions: 12-hour clock with am/pm, day-first dates
 * ("30 Oct 2026"), en-IN number grouping. The backend stores and exchanges UTC
 * instants; only *presentation* and "what day is it" live here.
 *
 * The timezone is the server's `CADENCE_CLINIC_TIMEZONE` (fetched once from `/config` at
 * startup, see `ClinicTimezoneGate`) so the UI and the API can never disagree about
 * what "today" is. Until it arrives the default below is used.
 */

const DEFAULT_TZ = 'Asia/Kolkata'
const LABELS: Record<string, string> = { 'Asia/Kolkata': 'IST' }
const LOCALE = 'en-IN'

function build(tz: string) {
  const fmt = (opts: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat(LOCALE, { timeZone: tz, ...opts })
  return {
    time: fmt({ hour: 'numeric', minute: '2-digit', hour12: true }),
    timeSec: fmt({ hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true }),
    date: fmt({ day: 'numeric', month: 'short', year: 'numeric' }),
    dateLong: fmt({ weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' }),
    dateShort: fmt({ weekday: 'short', day: 'numeric', month: 'short' }),
    dateTime: fmt({ day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true }),
    parts: new Intl.DateTimeFormat('en-GB', {
      timeZone: tz,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }),
  }
}

let clinicTz = DEFAULT_TZ
let f = build(clinicTz)

export const getClinicTimezone = () => clinicTz

/** Switch the clinic timezone (an unknown zone is ignored). */
export function setClinicTimezone(tz: string): void {
  if (tz === clinicTz) return
  try {
    f = build(tz)
  } catch {
    return
  }
  clinicTz = tz
}

/** "IST" for the default; otherwise the zone's own short name. */
export function clinicTzLabel(): string {
  const known = LABELS[clinicTz]
  if (known) return known
  const name = new Intl.DateTimeFormat(LOCALE, { timeZone: clinicTz, timeZoneName: 'short' })
    .formatToParts(new Date())
    .find((p) => p.type === 'timeZoneName')
  return name?.value ?? clinicTz
}

const toDate = (v: string | number | Date) => (v instanceof Date ? v : new Date(v))

/** "4:42 pm" */
export const formatTime = (v: string | number | Date) =>
  f.time.format(toDate(v)).replace(/\s/g, ' ')
/** "4:42:07 pm" */
export const formatTimeSeconds = (v: string | number | Date) => f.timeSec.format(toDate(v))
/** "30 Oct 2026" */
export const formatDate = (v: string | number | Date) => f.date.format(toDate(v))
/** "Fri, 30 Oct 2026" */
export const formatDateLong = (v: string | number | Date) =>
  f.dateLong.format(toDate(v)).replace(/,\s(\d{4})$/, ' $1')
/** "Fri, 30 Oct" */
export const formatDateShort = (v: string | number | Date) => f.dateShort.format(toDate(v))
/** "30 Oct, 4:42 pm" */
export const formatDateTime = (v: string | number | Date) => f.dateTime.format(toDate(v))

/** Indian digit grouping (1,23,456). */
export const formatNumber = (n: number) => new Intl.NumberFormat(LOCALE).format(n)

function partsOf(v: string | number | Date) {
  const out: Record<string, string> = {}
  for (const p of f.parts.formatToParts(toDate(v))) out[p.type] = p.value
  return out
}

/** The clinic-local calendar date of an instant, as YYYY-MM-DD. */
export function clinicDate(v: string | number | Date = new Date()): string {
  const p = partsOf(v)
  return `${p.year}-${p.month}-${p.day}`
}

/** Today's date in the clinic (not the browser's, not UTC). */
export const clinicToday = () => clinicDate(new Date())

/** Minutes since clinic-local midnight for an instant. */
export function clinicMinutesOfDay(v: string | number | Date): number {
  const p = partsOf(v)
  return Number(p.hour) * 60 + Number(p.minute)
}

/**
 * The instant to send the API for a picked YYYY-MM-DD, so the backend resolves the intended
 * clinic day. Noon UTC (17:30 IST) lands on the same calendar date for most zones; for one
 * where it would not, use noon in the clinic's own zone instead.
 */
export function dayParam(isoDate: string): string {
  const noonUtc = new Date(`${isoDate}T12:00:00Z`)
  if (clinicDate(noonUtc) === isoDate) return `${isoDate}T12:00:00Z`
  const p = partsOf(noonUtc)
  const localAsUtc = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute)
  const offset = localAsUtc - noonUtc.getTime()
  return new Date(noonUtc.getTime() - offset).toISOString()
}

/** Add whole days to a YYYY-MM-DD string (pure calendar maths, tz-independent). */
export function addDays(isoDate: string, delta: number): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d + delta))
  return dt.toISOString().slice(0, 10)
}

/** "Friday, 30 October 2026" for a YYYY-MM-DD (rendered at noon UTC to avoid edge shifts). */
export function formatPickedDate(isoDate: string): string {
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: 'UTC',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(`${isoDate}T12:00:00Z`))
}
