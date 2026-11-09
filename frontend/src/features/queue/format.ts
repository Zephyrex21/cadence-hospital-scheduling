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

/** What the current user may do to a queue entry. Arrival / no-show are front-desk work;
 *  starting and completing a consultation are clinical (the server enforces the same). */
export interface QueueAccess {
  frontDesk: boolean
  clinical: boolean
}

const FRONT_DESK_ACTIONS: ConsultationAction[] = ['check_in', 'no_show']

/** Valid consultation actions for a status, filtered by what the user may do. */
export function availableActions(
  status: AppointmentStatus,
  access: QueueAccess,
): ConsultationAction[] {
  return validActions(status).filter((action) =>
    FRONT_DESK_ACTIONS.includes(action) ? access.frontDesk : access.clinical,
  )
}

function validActions(status: AppointmentStatus): ConsultationAction[] {
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
