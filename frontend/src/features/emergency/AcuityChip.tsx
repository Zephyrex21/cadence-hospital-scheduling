import type { Acuity } from '../../types'
import { ACUITY_LABEL, acuityDotClass } from './format'

/** Acuity chip — a neutral pill with a colour-coded dot (A1–A5 token) always paired
 *  with its text label, so acuity is never conveyed by colour alone. */
export function AcuityChip({ acuity }: { acuity: Acuity }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-pill bg-canvas px-2.5 py-0.5 text-xs font-medium text-ink ring-1 ring-inset ring-hairline">
      <span aria-hidden className={`h-2 w-2 rounded-full ring-2 ring-inset ring-surface ${acuityDotClass(acuity)}`} />
      {ACUITY_LABEL[acuity]}
    </span>
  )
}
