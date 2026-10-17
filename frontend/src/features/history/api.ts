import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { AuditEntry, DecisionDetail, DecisionSummary, Displacement } from '../../types'

export function useDisplacements() {
  return useQuery({
    queryKey: ['displacements'],
    queryFn: () => apiFetch<Displacement[]>('/displacements'),
  })
}

export function useDecisions() {
  return useQuery({
    queryKey: ['decisions'],
    queryFn: () => apiFetch<DecisionSummary[]>('/scheduling-decisions'),
  })
}

export function useDecision(id: number | null) {
  return useQuery({
    queryKey: ['decision', id],
    enabled: id != null,
    queryFn: () => apiFetch<DecisionDetail>(`/scheduling-decisions/${id}`),
  })
}

export function useAudit() {
  return useQuery({
    queryKey: ['audit'],
    queryFn: () => apiFetch<AuditEntry[]>('/audit'),
  })
}

/** Resolve an escalated decision with a required note (nurse/administrator). */
export function useResolveEscalation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) =>
      apiFetch<unknown>(`/scheduling-decisions/${id}/resolve`, {
        method: 'POST',
        body: { note },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['dashboard'] })
      void qc.invalidateQueries({ queryKey: ['decisions'] })
    },
  })
}
