import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { ConsultationAction, QueueEntry } from '../../types'

export function useQueue(doctorId?: number) {
  return useQuery({
    queryKey: ['queue', doctorId ?? 'all'],
    queryFn: () =>
      apiFetch<QueueEntry[]>(`/queue${doctorId ? `?doctor_id=${doctorId}` : ''}`),
    refetchInterval: 15_000, // the queue is live; poll gently
  })
}

interface StatusInput {
  id: number
  action: ConsultationAction
  version?: number
}

export function useChangeStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action, version }: StatusInput) =>
      apiFetch<{ id: number; status: string; version: number }>(
        `/appointments/${id}/status`,
        { method: 'POST', body: { action, version } },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['queue'] })
      void qc.invalidateQueries({ queryKey: ['schedule'] })
    },
  })
}
