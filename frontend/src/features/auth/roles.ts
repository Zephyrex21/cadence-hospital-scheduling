import type { Role } from '../../types'

/** Human-readable role labels for the UI. */
export const ROLE_LABELS: Record<Role, string> = {
  receptionist: 'Receptionist',
  triage_nurse: 'Triage Nurse',
  doctor: 'Doctor',
  administrator: 'Administrator',
}

/** Roles permitted to register patients (mirrors backend WRITE_ROLES). */
export const PATIENT_WRITE_ROLES: readonly Role[] = [
  'receptionist',
  'triage_nurse',
  'administrator',
]

export function canRegisterPatients(role: Role): boolean {
  return PATIENT_WRITE_ROLES.includes(role)
}

/** Roles permitted to book/cancel appointments (mirrors backend BOOKING_ROLES). */
export const BOOKING_ROLES: readonly Role[] = [
  'receptionist',
  'triage_nurse',
  'administrator',
]

export function canBookAppointments(role: Role): boolean {
  return BOOKING_ROLES.includes(role)
}

/** Roles permitted to run the emergency plan/commit flow (mirrors EMERGENCY_ROLES). */
export const EMERGENCY_ROLES: readonly Role[] = ['receptionist', 'triage_nurse', 'administrator']

export function canUseEmergency(role: Role): boolean {
  return EMERGENCY_ROLES.includes(role)
}

/** Roles permitted to record triage acuity (mirrors backend TRIAGE_ROLES). */
export const TRIAGE_ROLES: readonly Role[] = ['triage_nurse', 'administrator']

export function canRecordTriage(role: Role): boolean {
  return TRIAGE_ROLES.includes(role)
}
