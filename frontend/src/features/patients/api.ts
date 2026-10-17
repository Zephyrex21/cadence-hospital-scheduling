import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { Patient } from '../../types'
import type { PatientFormValues } from './schema'

export function usePatients(query: string) {
  return useQuery({
    queryKey: ['patients', query],
    queryFn: () =>
      apiFetch<Patient[]>(`/patients${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  })
}

export function useRegisterPatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (values: PatientFormValues) => {
      const payload = { ...values, contact: values.contact?.trim() || null }
      return apiFetch<Patient>('/patients', { method: 'POST', body: payload })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
