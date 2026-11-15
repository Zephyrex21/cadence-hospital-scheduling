import type { NotificationStatus, PatientNotification } from '../../types'

export function notificationTone(status: NotificationStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  switch (status) {
    case 'sent':
      return 'success'
    case 'queued':
      return 'warning'
    case 'failed':
      return 'danger'
    default:
      return 'neutral'
  }
}

/** Plain-language status. A "sent" message from the demo provider was only logged, never delivered. */
export function notificationLabel(n: Pick<PatientNotification, 'status' | 'provider'>): string {
  if (n.status === 'sent') return n.provider === 'console' ? 'Logged (demo)' : 'Sent'
  if (n.status === 'skipped') return 'No phone on file'
  if (n.status === 'queued') return 'Sending'
  return 'Failed'
}

export function channelLabel(channel: PatientNotification['channel']): string {
  return channel === 'whatsapp' ? 'WhatsApp' : channel === 'sms' ? 'SMS' : '—'
}

/** Only failed messages can be retried by hand. */
export function canRetry(n: Pick<PatientNotification, 'status' | 'attempts'>): boolean {
  return n.status === 'failed' && n.attempts < 5
}
