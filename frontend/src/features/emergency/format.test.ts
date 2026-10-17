import { describe, expect, it } from 'vitest'

import { ACUITY_LABEL, acuityDotClass, formatDelayMin, reasonText, statusTone } from './format'

describe('emergency formatting', () => {
  it('maps acuity to the matching design token class', () => {
    expect(acuityDotClass('a1')).toBe('bg-acuity-1')
    expect(acuityDotClass('a5')).toBe('bg-acuity-5')
  })

  it('labels every acuity level', () => {
    expect(ACUITY_LABEL.a2).toContain('Emergent')
  })

  it('formats displacement delay in plain language', () => {
    expect(formatDelayMin(null)).toBe('no valid slot')
    expect(formatDelayMin(0)).toBe('no change')
    expect(formatDelayMin(30)).toBe('+30 min later')
    expect(formatDelayMin(29.6)).toBe('+30 min later')
  })

  it('tones decision status for the UI', () => {
    expect(statusTone('auto')).toBe('success')
    expect(statusTone('escalate')).toBe('warning')
    expect(statusTone('infeasible')).toBe('danger')
  })

  it('explains known reason codes and degrades gracefully', () => {
    expect(reasonText('acuity_a1_human_directed')).toContain('clinician')
    expect(reasonText('something_new')).toBe('something new')
  })
})
