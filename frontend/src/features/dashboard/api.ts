import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { DashboardSummary } from '../../types'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: () => apiFetch<DashboardSummary>('/dashboard/summary'),
    refetchInterval: 20_000, // the workload board is live
  })
}

export function formatRunningDelay(min: number): string {
  return min <= 0 ? 'On time' : `${min} min behind`
}
