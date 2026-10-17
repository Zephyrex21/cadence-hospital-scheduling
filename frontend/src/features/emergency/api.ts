import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { Acuity, CommitResponse, LatestTriage, PlanResponse } from '../../types'

export interface PlanInput {
  patient_id: number
  type_id: number
  acuity: Acuity
  now?: string
}

export interface CommitInput extends PlanInput {
  fingerprint: string
  idempotency_key?: string
}

export interface TriageInput {
  patient_id: number
  acuity: Acuity
  chief_complaint: string
  vitals?: Record<string, unknown>
}

export function useRecordTriage() {
  return useMutation({
    mutationFn: (input: TriageInput) =>
      apiFetch<unknown>('/triage', { method: 'POST', body: input }),
  })
}

/** The patient's current (within-window) triage, or null when none exists.
 *  Lets a receptionist see the nurse's recorded acuity read-only (A2). */
export function useLatestTriage(patientId: number | null) {
  return useQuery({
    queryKey: ['latest-triage', patientId],
    enabled: patientId != null,
    queryFn: () => apiFetch<LatestTriage | null>(`/patients/${patientId}/latest-triage`),
  })
}

export function usePlanEmergency() {
  return useMutation({
    mutationFn: (input: PlanInput) =>
      apiFetch<PlanResponse>('/emergencies/plan', { method: 'POST', body: input }),
  })
}

export function useCommitEmergency() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CommitInput) =>
      apiFetch<CommitResponse>('/emergencies/commit', { method: 'POST', body: input }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      void qc.invalidateQueries({ queryKey: ['slots'] })
    },
  })
}
