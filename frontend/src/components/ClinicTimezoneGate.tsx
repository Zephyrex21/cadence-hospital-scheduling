import { useQuery } from '@tanstack/react-query'
import { Fragment, type ReactNode } from 'react'

import { apiFetch } from '../lib/api'
import { getClinicTimezone, setClinicTimezone } from '../lib/time'

/**
 * Adopts the server's clinic timezone, so the UI and the API always agree on what "today" and
 * "4:30 pm" mean. The tree below is re-mounted if the zone differs from the default, so every
 * formatted time is recomputed. (For the default zone nothing changes and nothing re-mounts.)
 */
export function ClinicTimezoneGate({ children }: { children: ReactNode }) {
  const config = useQuery({
    queryKey: ['config'],
    queryFn: () => apiFetch<{ clinic_timezone: string }>('/config', { auth: false }),
    staleTime: Infinity,
    retry: 1,
  })
  const tz = config.data?.clinic_timezone
  if (tz) setClinicTimezone(tz) // idempotent; runs before the children render
  return <Fragment key={tz ? getClinicTimezone() : 'default'}>{children}</Fragment>
}
