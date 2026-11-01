export { formatDateTime } from '../../lib/time'

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
