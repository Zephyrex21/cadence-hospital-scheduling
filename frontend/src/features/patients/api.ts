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
      // Blank optional fields are sent as null so the record stays clean.
      const clean = (v?: string) => v?.trim() || null
      const payload = {
        name: values.name.trim(),
        date_of_birth: values.date_of_birth,
        sex: values.sex,
        contact: clean(values.contact),
        city: clean(values.city),
        blood_group: clean(values.blood_group),
        emergency_contact: clean(values.emergency_contact),
        notes: clean(values.notes),
      }
      return apiFetch<Patient>('/patients', { method: 'POST', body: payload })
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['patients'] })
    },
  })
}
