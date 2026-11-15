import { useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { IllustrationEmptyList } from '../components/illustrations'
import { StatusBadge } from '../components/StatusBadge'
import { TableSkeleton } from '../components/Skeleton'
import { EmptyState, ErrorState } from '../components/states'
import { useToast } from '../components/Toast'
import { formatDateTime } from '../features/history/format'
import { useNotifications, useRetryNotification } from '../features/notifications/api'
import {
  canRetry,
  channelLabel,
  notificationLabel,
  notificationTone,
} from '../features/notifications/format'
import { ApiError } from '../lib/api'
import type { NotificationStatus } from '../types'

const FILTERS: { value: NotificationStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'failed', label: 'Failed' },
  { value: 'skipped', label: 'No phone' },
  { value: 'sent', label: 'Sent' },
]

export function NotificationsPage() {
  const [filter, setFilter] = useState<NotificationStatus | undefined>(undefined)
  const notifications = useNotifications(filter)
  const retry = useRetryNotification()
  const { toast } = useToast()
  const rows = notifications.data ?? []

  async function retryOne(id: number) {
    try {
      const res = await retry.mutateAsync(id)
      toast({
        tone: res.status === 'sent' ? 'success' : 'warning',
        title: res.status === 'sent' ? 'Message sent' : 'Still failing',
        description: res.status === 'sent' ? res.patient.name : (res.error ?? undefined),
      })
    } catch (err) {
      toast({
        tone: 'danger',
        title: 'Could not retry',
        description: err instanceof ApiError ? err.message : undefined,
      })
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Patient notifications</h2>
        <p className="text-sm text-muted">
          Patients are messaged when an emergency or an overrunning consultation moves their
          appointment. Failed messages can be retried; patients with no phone number on file need
          a call from the front desk.
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <Button
            key={f.label}
            size="sm"
            variant={filter === f.value ? 'primary' : 'secondary'}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </Button>
        ))}
      </div>

      <Card>
        {notifications.isLoading ? (
          <TableSkeleton cols={5} />
        ) : notifications.isError ? (
          <ErrorState label="Could not load notifications." onRetry={() => notifications.refetch()} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<IllustrationEmptyList />}
            title="No notifications yet."
            hint="When an appointment is moved, the patient's message appears here."
          />
        ) : (
          <div className="max-h-[65vh] overflow-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">Patient</th>
                  <th className="px-4 py-3 font-medium">Message</th>
                  <th className="px-4 py-3 font-medium">Via</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">When</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {rows.map((n) => (
                  <tr key={n.id} className="border-b border-hairline/60 align-top last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{n.patient.name}</div>
                      <div className="font-mono text-xs text-muted">{n.patient.mrn}</div>
                    </td>
                    <td className="max-w-md px-4 py-3 text-slate">{n.body}</td>
                    <td className="px-4 py-3 text-muted">
                      <div>{channelLabel(n.channel)}</div>
                      {n.recipient && <div className="font-mono text-xs">{n.recipient}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge tone={notificationTone(n.status)}>
                        {notificationLabel(n)}
                      </StatusBadge>
                      {n.error && <div className="mt-1 text-xs text-muted">{n.error}</div>}
                    </td>
                    <td className="px-4 py-3 text-muted tabular-nums">
                      {formatDateTime(n.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {canRetry(n) && (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={retry.isPending && retry.variables === n.id}
                          onClick={() => void retryOne(n.id)}
                        >
                          Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
