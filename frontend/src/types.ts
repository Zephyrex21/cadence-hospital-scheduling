/** Shared API types. Kept hand-written for Phase 1; in a later phase these
 *  can be generated from the backend OpenAPI schema via openapi-typescript. */

export type Role = 'receptionist' | 'triage_nurse' | 'doctor' | 'administrator'

export interface User {
  id: number
  name: string
  email: string
  role: Role
  is_active: boolean
}

export interface Tokens {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface Patient {
  id: number
  mrn: string
  name: string
  date_of_birth: string
  sex: string
  contact: string | null
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}

export type AppointmentStatus =
  | 'booked'
  | 'checked_in'
  | 'in_progress'
  | 'completed'
  | 'cancelled'
  | 'no_show'
  | 'displaced'

export type AppointmentOrigin = 'booked' | 'walk_in' | 'emergency'

export interface Doctor {
  id: number
  name: string
  specialty: string
}

export interface AppointmentType {
  id: number
  name: string
  default_duration_min: number
  specialty: string
}

export interface Slot {
  start: string
  end: string
}

export interface Appointment {
  id: number
  status: AppointmentStatus
  origin: AppointmentOrigin
  scheduled_start: string
  scheduled_end: string
  version: number
  patient: { id: number; name: string; mrn: string }
  doctor: Doctor
  type: AppointmentType
}

export type Acuity = 'a1' | 'a2' | 'a3' | 'a4' | 'a5'

export interface EmergencyMove {
  appointment_id: number
  doctor_id: number
  from_start: string
  to_start: string | null
  delay_min: number | null
  duration_min: number
  reason: string
}

export interface EmergencyPlan {
  placement: { doctor_id: number; start: string; end: string }
  cost: number
  feasible: boolean
  reject_reasons: string[]
  moves: EmergencyMove[]
}

export type DecisionStatus = 'auto' | 'escalate' | 'infeasible'

export interface EmergencyDecision {
  status: DecisionStatus
  engine_version: string
  reasons: string[]
  request: {
    patient_id: number
    acuity: Acuity
    duration_min: number
    now: string
    eligible_doctor_ids: number[]
  }
  parameters: Record<string, unknown>
  chosen: EmergencyPlan | null
  alternatives: EmergencyPlan[]
}

export interface ApptDetail {
  patient_name: string
  mrn: string
  type_name: string
  doctor_name: string
  acuity: Acuity
}

export interface PlanResponse {
  fingerprint: string
  /** Hash of the proposed placement + moves; sent back on commit so a plan that
   *  changed after review is refused instead of silently applied. */
  plan_digest: string | null
  /** The server instant the plan was computed against (informational). */
  now: string
  decision: EmergencyDecision
  emergency_patient: { id: number; name: string; mrn: string }
  appointment_details: Record<string, ApptDetail>
  doctor_names: Record<string, string>
}

export interface LatestTriage {
  id: number
  patient_id: number
  nurse_id: number
  acuity: Acuity
  chief_complaint: string
  vitals: Record<string, unknown> | null
  assessed_at: string
}

export interface CommitResponse {
  status: 'auto' | 'escalate' | 'applied'
  decision_id: number
  emergency_appointment_id: number | null
  reasons: string[]
  displaced: { appointment_id: number; patient_name: string; from_start: string; to_start: string }[]
}

export type ConsultationAction = 'check_in' | 'start' | 'complete' | 'no_show'

export interface QueueEntry {
  appointment_id: number
  position: number
  est_wait_min: number
  acuity: Acuity
  status: AppointmentStatus
  scheduled_start: string
  patient: { id: number; name: string; mrn: string }
  doctor: { id: number; name: string }
  type_name: string
}

export interface Displacement {
  id: number
  appointment_id: number
  decision_id: number
  patient_name: string
  mrn: string
  doctor_name: string
  from_start: string
  to_start: string
  delay_min: number
  reason: string
  created_at: string
}

export interface DecisionSummary {
  id: number
  created_at: string
  trigger: string
  status: string
  engine_version: string
  patient_name: string
  actor_name: string
  emergency_appointment_id: number | null
  reason_count: number
  displaced_count: number
}

export interface DecisionDisplaced {
  appointment_id: number
  patient_name: string
  from_start: string
  to_start: string
  delay_min: number
  reason: string
}

export interface DecisionDetail {
  id: number
  trigger: string
  status: string
  engine_version: string
  created_at: string
  actor: { id: number; name: string }
  patient: { id: number; name: string; mrn: string }
  emergency_appointment_id: number | null
  reasons: string[]
  chosen_plan: EmergencyPlan | null
  alternatives: EmergencyPlan[]
  parameters: Record<string, unknown>
  input_snapshot: Record<string, unknown>
  displacements: DecisionDisplaced[]
}

export interface AuditEntry {
  id: number
  entity_type: string
  entity_id: string
  action: string
  actor_name: string
  reason: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

export interface DoctorLoad {
  doctor_id: number
  name: string
  waiting: number
  in_progress: number
  running_delay_min: number
}

export interface EscalationItem {
  decision_id: number
  patient_name: string
  created_at: string
  reasons: string[]
}

export interface DashboardSummary {
  now: string
  total_waiting: number
  in_progress: number
  completed_today: number
  displaced_today: number
  escalations_pending: number
  waiting_by_acuity: Record<Acuity, number>
  recent_escalations: EscalationItem[]
  doctor_load: DoctorLoad[]
}

export interface EscalationOption extends EmergencyPlan {
  index: number
  /** False when the option violates a hard safety constraint (informational only). */
  applicable: boolean
}

export interface EscalationOptions {
  decision_id: number
  reasons: string[]
  emergency_patient: { id: number; name: string; mrn: string }
  options: EscalationOption[]
  appointment_details: Record<string, ApptDetail>
  doctor_names: Record<string, string>
}
