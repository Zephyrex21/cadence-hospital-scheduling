import { describe, expect, it } from 'vitest'

import { canRegisterPatients } from '../auth/roles'
import { isValidContact, patientFormSchema } from './schema'

describe('patientFormSchema', () => {
  it('accepts a valid patient', () => {
    const result = patientFormSchema.safeParse({
      name: 'Jordan Rivera',
      date_of_birth: '1990-05-02',
      sex: 'other',
      contact: '',
    })
    expect(result.success).toBe(true)
  })

  it('rejects a blank name', () => {
    const result = patientFormSchema.safeParse({
      name: '   ',
      date_of_birth: '1990-05-02',
      sex: 'female',
    })
    expect(result.success).toBe(false)
  })

  it('rejects a future date of birth', () => {
    const future = new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)
    const result = patientFormSchema.safeParse({
      name: 'Future Person',
      date_of_birth: future,
      sex: 'male',
    })
    expect(result.success).toBe(false)
  })
})

describe('canRegisterPatients', () => {
  it('allows reception, triage, and admin', () => {
    expect(canRegisterPatients('receptionist')).toBe(true)
    expect(canRegisterPatients('triage_nurse')).toBe(true)
    expect(canRegisterPatients('administrator')).toBe(true)
  })

  it('denies doctors', () => {
    expect(canRegisterPatients('doctor')).toBe(false)
  })
})

describe('patient form: name length and contact', () => {
  const base = { date_of_birth: '1990-05-02', sex: 'female' }

  it('rejects a one-character name with the same rule as the server', () => {
    const r = patientFormSchema.safeParse({ ...base, name: 'A' })
    expect(r.success).toBe(false)
    if (!r.success) expect(r.error.issues[0].message).toMatch(/at least 2/)
  })

  it('accepts phones and e-mails, rejects junk, allows blank', () => {
    for (const ok of ['+91 98765 43210', '555-0101', '(011) 2345 6789', 'a@b.co', '']) {
      expect(isValidContact(ok)).toBe(true)
    }
    for (const bad of ['abc', '12', 'call me', 'a@b', '+++']) {
      expect(isValidContact(bad)).toBe(false)
    }
    expect(patientFormSchema.safeParse({ ...base, name: 'Asha', contact: 'abc' }).success).toBe(
      false,
    )
  })
})
