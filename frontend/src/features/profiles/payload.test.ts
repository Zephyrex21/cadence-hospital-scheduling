import { describe, expect, it } from 'vitest'

import {
  compact,
  patientPayload,
  staffPayload,
  staffSectionsFor,
  toPatientDraft,
  toStaffDraft,
} from './payload'

describe('compact', () => {
  it('drops blanks and returns null when nothing is left', () => {
    expect(compact({ a: ' x ', b: '', c: undefined, d: [] })).toEqual({ a: 'x' })
    expect(compact({ a: '  ', b: [] })).toBeNull()
  })
})

describe('patientPayload', () => {
  const draft = toPatientDraft(null)

  it('clears a section by sending null when all its fields are empty', () => {
    expect(patientPayload(draft, ['contact', 'address', 'notes'])).toEqual({
      contact: null,
      address: null,
      notes: null,
    })
  })

  it('only includes the sections it is told to (role permissions)', () => {
    const body = patientPayload({ ...draft, phone: '123', blood_group: 'O+' }, ['contact'])
    expect(Object.keys(body)).toEqual(['contact'])
    expect(body.contact).toEqual({ phone: '123' })
  })

  it('always marks exactly one emergency contact as primary', () => {
    const body = patientPayload(
      {
        ...draft,
        emergency: [
          { name: 'A', relation: '', phone: '1', is_primary: false },
          { name: 'B', relation: 'wife', phone: '', is_primary: true },
          { name: '', relation: '', phone: '', is_primary: true }, // blank row is dropped
        ],
      },
      ['emergency_contacts'],
    )
    expect(body.emergency_contacts).toEqual([
      { name: 'A', phone: '1', is_primary: false },
      { name: 'B', relation: 'wife', is_primary: true },
    ])
    const defaulted = patientPayload(
      { ...draft, emergency: [{ name: 'Solo', relation: '', phone: '', is_primary: false }] },
      ['emergency_contacts'],
    )
    expect(defaulted.emergency_contacts).toEqual([{ name: 'Solo', is_primary: true }])
  })

  it('builds the medical block from rows and a comma list', () => {
    const body = patientPayload(
      {
        ...draft,
        blood_group: 'B+',
        conditions: 'Asthma, , Diabetes',
        allergies: [
          { substance: 'Penicillin', reaction: 'rash', severity: 'moderate' },
          { substance: '', reaction: 'ignored', severity: '' },
        ],
        medications: [{ name: 'Metformin', dose: '500 mg', frequency: '' }],
      },
      ['medical'],
    )
    expect(body.medical).toEqual({
      blood_group: 'B+',
      allergies: [{ substance: 'Penicillin', reaction: 'rash', severity: 'moderate' }],
      conditions: ['Asthma', 'Diabetes'],
      medications: [{ name: 'Metformin', dose: '500 mg' }],
    })
  })

  it('round-trips a loaded profile', () => {
    const loaded = toPatientDraft({
      patient_id: 1,
      mrn: 'CAD-1',
      contact: { phone: '99', email: 'a@b.co' },
      medical: { blood_group: 'A+', conditions: ['Asthma'], allergies: [], medications: [] },
    })
    expect(patientPayload(loaded, ['contact', 'medical'])).toEqual({
      contact: { phone: '99', email: 'a@b.co' },
      medical: { blood_group: 'A+', conditions: ['Asthma'] },
    })
  })
})

describe('staff payloads', () => {
  it('non-admins may only touch contact + languages; admins also get their role block', () => {
    expect(staffSectionsFor(false, 'doctor')).toEqual(['contact', 'languages'])
    expect(staffSectionsFor(true, 'doctor')).toContain('doctor')
    expect(staffSectionsFor(true, 'triage_nurse')).toContain('nurse')
    expect(staffSectionsFor(true, 'receptionist')).toContain('reception')
    expect(staffSectionsFor(true, 'administrator')).not.toContain('doctor')
  })

  it('builds a doctor block with numbers parsed and blanks dropped', () => {
    const draft = {
      ...toStaffDraft('doctor', null),
      reg_council: 'Delhi Medical Council',
      reg_number: 'DMC-1',
      qualifications: [{ degree: 'MD', institution: 'AIIMS', year: '2010' }, { degree: '', institution: 'x', year: '' }],
      experience_years: '12',
      fee: '',
      sub_specialties: 'Diabetology',
    }
    expect(staffPayload(draft, ['doctor']).doctor).toEqual({
      registration: { council: 'Delhi Medical Council', number: 'DMC-1' },
      qualifications: [{ degree: 'MD', institution: 'AIIMS', year: 2010 }],
      sub_specialties: ['Diabetology'],
      experience_years: 12,
    })
  })

  it('clears scalar fields with null and languages as a list', () => {
    const body = staffPayload(
      { ...toStaffDraft('doctor', null), languages: 'en, hi' },
      ['employee_id', 'department', 'languages'],
    )
    expect(body).toEqual({ employee_id: null, department: null, languages: ['en', 'hi'] })
  })
})
