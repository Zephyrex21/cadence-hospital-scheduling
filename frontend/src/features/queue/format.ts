import type { AppointmentStatus, ConsultationAction } from '../../types'

/** Human-readable wait estimate. 0 means the patient is next up. */
export function formatWait(min: number): string {
  if (min <= 0) return 'Next up'
  if (min < 60) return `~${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `~${h}h ${m}m` : `~${h}h`
}

export const ACTION_LABEL: Record<ConsultationAction, string> = {
  check_in: 'Check in',
  start: 'Start',
  complete: 'Complete',
  no_show: 'No show',
}

/** Valid consultation actions for a status — only when the user may manage it. */
export function availableActions(
  status: AppointmentStatus,
  canManage: boolean,
): ConsultationAction[] {
  if (!canManage) return []
  switch (status) {
    case 'booked':
      return ['check_in', 'start', 'no_show']
    case 'checked_in':
      return ['start', 'no_show']
    case 'in_progress':
      return ['complete']
    default:
      return []
  }
}
