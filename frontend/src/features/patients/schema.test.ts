import { describe, expect, it } from 'vitest'

import { canRegisterPatients } from '../auth/roles'
import { patientFormSchema } from './schema'

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
