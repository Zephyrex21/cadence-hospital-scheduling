/**
 * Clinic time. Everything the user sees is in the clinic's timezone (India Standard
 * Time) and Indian conventions: 12-hour clock with am/pm, day-first dates
 * ("30 Oct 2026"), en-IN number grouping. The backend stores and exchanges UTC
 * instants; only *presentation* and "what day is it" live here.
 *
 * IST has no daylight saving, but zone maths still goes through Intl so changing
 * CLINIC_TZ (e.g. for another deployment) just works.
 */

export const CLINIC_TZ = 'Asia/Kolkata'
export const CLINIC_TZ_LABEL = 'IST'
const LOCALE = 'en-IN'

const fmt = (opts: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(LOCALE, { timeZone: CLINIC_TZ, ...opts })

const timeFmt = fmt({ hour: 'numeric', minute: '2-digit', hour12: true })
const timeSecFmt = fmt({ hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true })
const dateFmt = fmt({ day: 'numeric', month: 'short', year: 'numeric' })
const dateLongFmt = fmt({ weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
const dateShortFmt = fmt({ weekday: 'short', day: 'numeric', month: 'short' })
const dateTimeFmt = fmt({
  day: 'numeric',
  month: 'short',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
})
const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: CLINIC_TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

const toDate = (v: string | number | Date) => (v instanceof Date ? v : new Date(v))

/** "4:42 pm" */
export const formatTime = (v: string | number | Date) =>
  timeFmt.format(toDate(v)).replace(/\s/g, ' ')
/** "4:42:07 pm" */
export const formatTimeSeconds = (v: string | number | Date) => timeSecFmt.format(toDate(v))
/** "30 Oct 2026" */
export const formatDate = (v: string | number | Date) => dateFmt.format(toDate(v))
/** "Fri, 30 Oct 2026" */
export const formatDateLong = (v: string | number | Date) =>
  dateLongFmt.format(toDate(v)).replace(/,\s(\d{4})$/, ' $1')
/** "Fri, 30 Oct" */
export const formatDateShort = (v: string | number | Date) => dateShortFmt.format(toDate(v))
/** "30 Oct, 4:42 pm" */
export const formatDateTime = (v: string | number | Date) => dateTimeFmt.format(toDate(v))

/** Indian digit grouping (1,23,456). */
export const formatNumber = (n: number) => new Intl.NumberFormat(LOCALE).format(n)

function partsOf(v: string | number | Date) {
  const out: Record<string, string> = {}
  for (const p of partsFmt.formatToParts(toDate(v))) out[p.type] = p.value
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
 * The instant to send the API for a picked YYYY-MM-DD. Noon UTC is 17:30 IST — the
 * same IST calendar date — so the backend resolves the intended clinic day.
 */
export const dayParam = (isoDate: string) => `${isoDate}T12:00:00Z`

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
