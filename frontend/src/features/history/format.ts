/** Full date-time in UTC (history views span days, unlike the single-day schedule). */
export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(iso))
}

export function decisionStatusLabel(status: string): string {
  if (status === 'auto_committed') return 'Auto-committed'
  if (status === 'escalated') return 'Escalated'
  return status
}

export function decisionStatusTone(status: string): 'success' | 'warning' | 'neutral' {
  if (status === 'auto_committed') return 'success'
  if (status === 'escalated') return 'warning'
  return 'neutral'
}

/** Compact label for an audit action code. */
export function auditActionLabel(action: string): string {
  const map: Record<string, string> = {
    create: 'Created',
    update: 'Updated',
    cancel: 'Cancelled',
    delete: 'Deleted',
    login: 'Signed in',
  }
  return map[action] ?? action
}
