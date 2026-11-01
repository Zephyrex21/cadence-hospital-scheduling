import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import { dayParam as clinicDayParam } from '../../lib/time'
import type { Appointment, AppointmentType, Doctor, Slot } from '../../types'

/** The instant to send for a picked clinic date (see `lib/time.ts#dayParam`). */
export function dayParam(date: string): string {
  return new Date(clinicDayParam(date)).toISOString()
}

export function useDoctors() {
  return useQuery({
    queryKey: ['doctors'],
    queryFn: () => apiFetch<Doctor[]>('/doctors'),
    staleTime: 5 * 60 * 1000,
  })
}

export function useAppointmentTypes() {
  return useQuery({
    queryKey: ['appointment-types'],
    queryFn: () => apiFetch<AppointmentType[]>('/appointment-types'),
    staleTime: 5 * 60 * 1000,
  })
}

export function useSchedule(date: string, doctorId?: number) {
  return useQuery({
    queryKey: ['schedule', date, doctorId ?? 'all'],
    queryFn: () => {
      const params = new URLSearchParams({ day: dayParam(date) })
      if (doctorId) params.set('doctor_id', String(doctorId))
      return apiFetch<Appointment[]>(`/schedule?${params.toString()}`)
    },
  })
}

export function useSlots(doctorId: number | null, typeId: number | null, date: string) {
  return useQuery({
    queryKey: ['slots', doctorId, typeId, date],
    enabled: doctorId != null && typeId != null,
    queryFn: () => {
      const params = new URLSearchParams({
        doctor_id: String(doctorId),
        type_id: String(typeId),
        day: dayParam(date),
      })
      return apiFetch<Slot[]>(`/slots?${params.toString()}`)
    },
  })
}

interface BookInput {
  patient_id: number
  doctor_id: number
  type_id: number
  scheduled_start: string
}

export function useBookAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: BookInput) =>
      apiFetch<Appointment>('/appointments', { method: 'POST', body: input }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      void qc.invalidateQueries({ queryKey: ['slots'] })
    },
  })
}

export function useCancelAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) =>
      apiFetch<Appointment>(`/appointments/${id}/cancel`, {
        method: 'POST',
        body: { version },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      void qc.invalidateQueries({ queryKey: ['slots'] })
    },
  })
}
