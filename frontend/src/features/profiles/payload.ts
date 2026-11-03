/** Form drafts <-> API payloads for the MongoDB profiles. Pure, so it's unit-tested.
 *
 * Drafts hold plain strings (what inputs produce). The builders drop blanks, so a
 * section whose fields are all empty becomes `null` — which clears it on the server. */

import type { PatientProfile, Role, StaffProfile } from '../../types'

export type PatientSection =
  | 'demographics'
  | 'contact'
  | 'address'
  | 'emergency_contacts'
  | 'medical'
  | 'insurance'
  | 'identifiers'
  | 'notes'

/** Which patient-profile sections each role may write (mirrors the backend). */
export const PATIENT_SECTIONS_BY_ROLE: Record<Role, readonly PatientSection[]> = {
  administrator: [
    'demographics',
    'contact',
    'address',
    'emergency_contacts',
    'medical',
    'insurance',
    'identifiers',
    'notes',
  ],
  receptionist: [
    'demographics',
    'contact',
    'address',
    'emergency_contacts',
    'insurance',
    'identifiers',
    'notes',
  ],
  triage_nurse: ['medical', 'contact', 'emergency_contacts', 'notes'],
  doctor: [],
}

const blank = (v: unknown) => v === undefined || v === null || (typeof v === 'string' && !v.trim())

/** Drop blank values; `null` when nothing is left. */
export function compact(obj: Record<string, unknown>): Record<string, unknown> | null {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    if (Array.isArray(v) ? v.length > 0 : !blank(v)) out[k] = typeof v === 'string' ? v.trim() : v
  }
  return Object.keys(out).length > 0 ? out : null
}

export const splitList = (text: string): string[] =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)

const num = (text: string): number | undefined => {
  const n = Number(text)
  return text.trim() !== '' && Number.isFinite(n) ? n : undefined
}

// --- patient ------------------------------------------------------------------------

export interface PatientDraft {
  preferred_language: string
  occupation: string
  phone: string
  alt_phone: string
  email: string
  line1: string
  line2: string
  city: string
  state: string
  pin_code: string
  emergency: { name: string; relation: string; phone: string; is_primary: boolean }[]
  blood_group: string
  allergies: { substance: string; reaction: string; severity: string }[]
  conditions: string
  medications: { name: string; dose: string; frequency: string }[]
  scheme: string
  provider: string
  policy_no: string
  abha_id: string
  notes: string
}

export function toPatientDraft(p: PatientProfile | null): PatientDraft {
  return {
    preferred_language: p?.demographics?.preferred_language ?? '',
    occupation: p?.demographics?.occupation ?? '',
    phone: p?.contact?.phone ?? '',
    alt_phone: p?.contact?.alt_phone ?? '',
    email: p?.contact?.email ?? '',
    line1: p?.address?.line1 ?? '',
    line2: p?.address?.line2 ?? '',
    city: p?.address?.city ?? '',
    state: p?.address?.state ?? '',
    pin_code: p?.address?.pin_code ?? '',
    emergency: (p?.emergency_contacts ?? []).map((c) => ({
      name: c.name,
      relation: c.relation ?? '',
      phone: c.phone ?? '',
      is_primary: !!c.is_primary,
    })),
    blood_group: p?.medical?.blood_group ?? '',
    allergies: (p?.medical?.allergies ?? []).map((a) => ({
      substance: a.substance,
      reaction: a.reaction ?? '',
      severity: a.severity ?? '',
    })),
    conditions: (p?.medical?.conditions ?? []).join(', '),
    medications: (p?.medical?.medications ?? []).map((m) => ({
      name: m.name,
      dose: m.dose ?? '',
      frequency: m.frequency ?? '',
    })),
    scheme: p?.insurance?.scheme ?? '',
    provider: p?.insurance?.provider ?? '',
    policy_no: p?.insurance?.policy_no ?? '',
    abha_id: p?.identifiers?.abha_id ?? '',
    notes: p?.notes ?? '',
  }
}

export function patientPayload(
  d: PatientDraft,
  sections: readonly PatientSection[],
): Record<string, unknown> {
  const build: Record<PatientSection, () => unknown> = {
    demographics: () =>
      compact({ preferred_language: d.preferred_language, occupation: d.occupation }),
    contact: () => compact({ phone: d.phone, alt_phone: d.alt_phone, email: d.email }),
    address: () =>
      compact({
        line1: d.line1,
        line2: d.line2,
        city: d.city,
        state: d.state,
        pin_code: d.pin_code,
      }),
    emergency_contacts: () => {
      const rows = d.emergency.filter((c) => c.name.trim())
      if (rows.length === 0) return null
      // Exactly one primary contact: keep the first ticked one, default to the first row.
      const primary = Math.max(
        0,
        rows.findIndex((c) => c.is_primary),
      )
      return rows.map((c, i) => ({
        ...compact({ name: c.name, relation: c.relation, phone: c.phone }),
        is_primary: i === primary,
      }))
    },
    medical: () =>
      compact({
        blood_group: d.blood_group,
        allergies: d.allergies
          .filter((a) => a.substance.trim())
          .map((a) => compact({ substance: a.substance, reaction: a.reaction, severity: a.severity })),
        conditions: splitList(d.conditions),
        medications: d.medications
          .filter((m) => m.name.trim())
          .map((m) => compact({ name: m.name, dose: m.dose, frequency: m.frequency })),
      }),
    insurance: () => compact({ scheme: d.scheme, provider: d.provider, policy_no: d.policy_no }),
    identifiers: () => compact({ abha_id: d.abha_id }),
    notes: () => d.notes.trim() || null,
  }
  return Object.fromEntries(sections.map((s) => [s, build[s]()]))
}

// --- staff --------------------------------------------------------------------------

export type StaffSection =
  | 'employee_id'
  | 'department'
  | 'languages'
  | 'contact'
  | 'employment'
  | 'doctor'
  | 'nurse'
  | 'reception'

/** Everyone may edit these on their own profile; the rest is admin-only (server-enforced). */
export const STAFF_SELF_SECTIONS: readonly StaffSection[] = ['contact', 'languages']

export function staffSectionsFor(admin: boolean, role: Role): readonly StaffSection[] {
  if (!admin) return STAFF_SELF_SECTIONS
  const detail: StaffSection | null =
    role === 'doctor' ? 'doctor' : role === 'triage_nurse' ? 'nurse' : role === 'receptionist' ? 'reception' : null
  return [
    'employee_id',
    'department',
    'languages',
    'contact',
    'employment',
    ...(detail ? [detail] : []),
  ]
}

export interface StaffDraft {
  employee_id: string
  department: string
  languages: string
  phone: string
  alt_phone: string
  status: string
  joined_on: string
  reg_council: string
  reg_number: string
  qualifications: { degree: string; institution: string; year: string }[]
  sub_specialties: string
  experience_years: string
  fee: string
  bio: string
  certifications: { name: string; expires_on: string }[]
  ward: string
  shift_pattern: string
  counter: string
  training: string
}

export function toStaffDraft(role: Role, p: StaffProfile | null): StaffDraft {
  const detail = role === 'doctor' ? p?.doctor : role === 'triage_nurse' ? p?.nurse : undefined
  const nurse = p?.nurse
  return {
    employee_id: p?.employee_id ?? '',
    department: p?.department ?? '',
    languages: (p?.languages ?? []).join(', '),
    phone: p?.contact?.phone ?? '',
    alt_phone: p?.contact?.alt_phone ?? '',
    status: p?.employment?.status ?? 'active',
    joined_on: p?.employment?.joined_on ?? '',
    reg_council: detail?.registration?.council ?? '',
    reg_number: detail?.registration?.number ?? '',
    qualifications: (detail?.qualifications ?? []).map((q) => ({
      degree: q.degree,
      institution: q.institution ?? '',
      year: q.year ? String(q.year) : '',
    })),
    sub_specialties: (p?.doctor?.sub_specialties ?? []).join(', '),
    experience_years: p?.doctor?.experience_years != null ? String(p.doctor.experience_years) : '',
    fee: p?.doctor?.consultation_fee_inr != null ? String(p.doctor.consultation_fee_inr) : '',
    bio: p?.doctor?.bio ?? '',
    certifications: (nurse?.certifications ?? []).map((c) => ({
      name: c.name,
      expires_on: c.expires_on ?? '',
    })),
    ward: nurse?.ward ?? '',
    shift_pattern: (role === 'receptionist' ? p?.reception?.shift_pattern : nurse?.shift_pattern) ?? '',
    counter: p?.reception?.counter ?? '',
    training: (p?.reception?.training ?? []).join(', '),
  }
}

export function staffPayload(
  d: StaffDraft,
  sections: readonly StaffSection[],
): Record<string, unknown> {
  const quals = () =>
    d.qualifications
      .filter((q) => q.degree.trim())
      .map((q) => compact({ degree: q.degree, institution: q.institution, year: num(q.year) }))
  const registration = () => compact({ council: d.reg_council, number: d.reg_number })
  const build: Record<StaffSection, () => unknown> = {
    employee_id: () => d.employee_id.trim() || null,
    department: () => d.department.trim() || null,
    languages: () => {
      const list = splitList(d.languages)
      return list.length > 0 ? list : null
    },
    contact: () => compact({ phone: d.phone, alt_phone: d.alt_phone }),
    employment: () => ({ status: d.status || 'active', ...(d.joined_on ? { joined_on: d.joined_on } : {}) }),
    doctor: () =>
      compact({
        registration: registration(),
        qualifications: quals(),
        sub_specialties: splitList(d.sub_specialties),
        experience_years: num(d.experience_years),
        consultation_fee_inr: num(d.fee),
        bio: d.bio,
      }),
    nurse: () =>
      compact({
        registration: registration(),
        qualifications: quals(),
        certifications: d.certifications
          .filter((c) => c.name.trim())
          .map((c) => compact({ name: c.name, expires_on: c.expires_on })),
        ward: d.ward,
        shift_pattern: d.shift_pattern,
      }),
    reception: () =>
      compact({ counter: d.counter, shift_pattern: d.shift_pattern, training: splitList(d.training) }),
  }
  return Object.fromEntries(sections.map((s) => [s, build[s]()]))
}
