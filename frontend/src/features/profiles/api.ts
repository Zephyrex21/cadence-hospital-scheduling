import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { MongoStatus, PatientProfileResponse, StaffEntry } from '../../types'

export function usePatientProfile(patientId: number) {
  return useQuery({
    queryKey: ['patient-profile', patientId],
    queryFn: () => apiFetch<PatientProfileResponse>(`/patients/${patientId}/profile`),
  })
}

export function useUpdatePatientProfile(patientId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sections: Record<string, unknown>) =>
      apiFetch<PatientProfileResponse>(`/patients/${patientId}/profile`, {
        method: 'PUT',
        body: sections,
      }),
    onSuccess: (data) => {
      qc.setQueryData(['patient-profile', patientId], data)
      // The server mirrors a few fields (phone, city, blood group…) into the list view.
      void qc.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}

export function useStaff() {
  return useQuery({ queryKey: ['staff'], queryFn: () => apiFetch<StaffEntry[]>('/staff') })
}

export function useUpdateStaffProfile(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sections: Record<string, unknown>) =>
      apiFetch<StaffEntry>(`/staff/${userId}/profile`, { method: 'PUT', body: sections }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['staff'] }),
  })
}

/** Is the optional MongoDB profile store configured / reachable? (public, cheap) */
export function useMongoStatus() {
  return useQuery({
    queryKey: ['mongo-status'],
    queryFn: () => apiFetch<MongoStatus>('/health/mongo', { auth: false }),
    staleTime: 60_000,
  })
}
