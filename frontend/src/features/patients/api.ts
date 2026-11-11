import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

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

const PAGE_SIZE = 50

/** The patient list, 50 at a time (the server caps a single response). */
export function usePatientPages(query: string) {
  return useInfiniteQuery({
    queryKey: ['patients', 'pages', query],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      apiFetch<Patient[]>(
        `/patients?limit=${PAGE_SIZE}&offset=${pageParam}${
          query ? `&q=${encodeURIComponent(query)}` : ''
        }`,
      ),
    getNextPageParam: (last, all) => (last.length === PAGE_SIZE ? all.length * PAGE_SIZE : undefined),
  })
}

/** How many patients match, so the page can say "50 of 64". */
export function usePatientCount(query: string) {
  return useQuery({
    queryKey: ['patients', 'count', query],
    queryFn: () =>
      apiFetch<{ total: number }>(`/patients/count${query ? `?q=${encodeURIComponent(query)}` : ''}`),
  })
}
