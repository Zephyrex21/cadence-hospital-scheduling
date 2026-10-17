import type { Acuity, DecisionStatus } from '../../types'

/** Acuity presentation. Colors map to the acuity-N design tokens; labels and
 *  descriptions are always shown alongside the color (never color alone). */
export const ACUITY_LABEL: Record<Acuity, string> = {
  a1: 'A1 · Critical',
  a2: 'A2 · Emergent',
  a3: 'A3 · Urgent',
  a4: 'A4 · Semi-urgent',
  a5: 'A5 · Routine',
}

export const ACUITY_TARGET: Record<Acuity, string> = {
  a1: 'Immediate — clinician-directed',
  a2: 'Seen within 15 min',
  a3: 'Seen within 60 min',
  a4: 'Seen within 2 hours',
  a5: 'Routine queue',
}

/** Tailwind background class for the acuity dot, e.g. a2 -> bg-acuity-2. */
export function acuityDotClass(acuity: Acuity): string {
  return `bg-acuity-${acuity.slice(1)}`
}

export const ACUITY_ORDER: Acuity[] = ['a1', 'a2', 'a3', 'a4', 'a5']

/** Human-readable delay for a displaced appointment. */
export function formatDelayMin(min: number | null): string {
  if (min === null) return 'no valid slot'
  if (min === 0) return 'no change'
  return `+${Math.round(min)} min later`
}

export function statusTone(status: DecisionStatus): 'success' | 'warning' | 'danger' {
  if (status === 'auto') return 'success'
  if (status === 'escalate') return 'warning'
  return 'danger'
}

export function statusLabel(status: DecisionStatus): string {
  if (status === 'auto') return 'Auto-schedulable'
  if (status === 'escalate') return 'Needs clinician approval'
  return 'No feasible plan'
}

/** Turn an engine reason code into a sentence for staff. */
const REASON_TEXT: Record<string, string> = {
  acuity_a1_human_directed: 'Critical (A1): a clinician must direct this placement.',
  no_feasible_plan: 'No placement satisfies the safety and fairness rules.',
  no_candidates: 'No eligible doctor has availability for this emergency.',
  too_many_displacements: 'Too many booked appointments would have to move.',
  cost_over_threshold: 'The least-disruptive plan is still too disruptive to auto-apply.',
  delay_over_auto_limit: 'A booked patient would be pushed back further than allowed.',
}

export function reasonText(code: string): string {
  return REASON_TEXT[code] ?? code.replace(/_/g, ' ')
}
