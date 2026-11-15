import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { NotificationStatus, PatientNotification } from '../../types'

export function useNotifications(status?: NotificationStatus) {
  return useQuery({
    queryKey: ['notifications', status ?? 'all'],
    queryFn: () =>
      apiFetch<PatientNotification[]>(`/notifications${status ? `?status=${status}` : ''}`),
    refetchInterval: 30_000,
  })
}

export function useRetryNotification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<PatientNotification>(`/notifications/${id}/retry`, { method: 'POST' }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
}
