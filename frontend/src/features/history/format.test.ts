import { describe, expect, it } from 'vitest'

import {
  auditActionLabel,
  decisionStatusLabel,
  decisionStatusTone,
  formatDateTime,
} from './format'

describe('history formatting', () => {
  it('formats a full UTC timestamp regardless of locale', () => {
    const out = formatDateTime('2026-10-13T09:05:00Z')
    expect(out).toContain('13 Oct')
    expect(out).toContain('09:05')
  })

  it('labels and tones decision status', () => {
    expect(decisionStatusLabel('auto_committed')).toBe('Auto-committed')
    expect(decisionStatusLabel('escalated')).toBe('Escalated')
    expect(decisionStatusTone('auto_committed')).toBe('success')
    expect(decisionStatusTone('escalated')).toBe('warning')
    expect(decisionStatusTone('other')).toBe('neutral')
  })

  it('labels audit actions and degrades gracefully', () => {
    expect(auditActionLabel('create')).toBe('Created')
    expect(auditActionLabel('mystery')).toBe('mystery')
  })
})
