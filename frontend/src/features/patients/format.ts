import { clinicToday, formatDate } from '../../lib/time'

/** "46 y" / "7 mo" / "12 d" from a YYYY-MM-DD date of birth, as of today in the clinic. */
export function formatAge(dob: string, today: string = clinicToday()): string {
  const [by, bm, bd] = dob.split('-').map(Number)
  const [ty, tm, td] = today.split('-').map(Number)
  let years = ty - by
  if (tm < bm || (tm === bm && td < bd)) years -= 1
  if (years >= 2) return `${years} y`
  const months = (ty - by) * 12 + (tm - bm) - (td < bd ? 1 : 0)
  if (months >= 1) return `${months} mo`
  const days = Math.max(
    0,
    Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(by, bm - 1, bd)) / 86_400_000),
  )
  return `${days} d`
}

/** "14 Mar 1978" */
export const formatDob = (dob: string) => formatDate(`${dob}T12:00:00Z`)

export function initials(name: string): string {
  return name
    .replace(/^Dr\.?\s+/i, '')
    .split(/\s+/)
    .filter(Boolean)
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export const sexLabel = (sex: string) => sex.charAt(0).toUpperCase() + sex.slice(1)
