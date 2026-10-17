import { AnimatePresence, m } from 'framer-motion'

import { Card } from '../components/Card'
import { IllustrationEmptyList } from '../components/illustrations'
import { Skeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { EmptyState, ErrorState } from '../components/states'
import { useAuth } from '../features/auth/AuthContext'
import { AcuityChip } from '../features/emergency/AcuityChip'
import { useChangeStatus, useQueue } from '../features/queue/api'
import { ACTION_LABEL, availableActions, formatWait } from '../features/queue/format'
import { formatTime, statusLabel, statusTone } from '../features/schedule/timeline'
import type { QueueEntry } from '../types'

export function QueuePage() {
  const { user } = useAuth()
  const queue = useQueue()
  const change = useChangeStatus()

  const canManage = (entry: QueueEntry): boolean => {
    if (!user) return false
    if (user.role === 'administrator') return true
    return user.role === 'doctor' && String(user.id) === String(entry.doctor.id)
  }

  const entries = queue.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Patient queue</h2>
        <p className="text-sm text-muted">
          Live waiting list ordered by clinical priority, with estimated waits. Estimates are
          operational guidance, not a promise.
        </p>
      </div>

      <Card>
        {queue.isLoading ? (
          <ul className="flex flex-col divide-y divide-hairline/60" role="status" aria-busy aria-label="Loading queue">
            {Array.from({ length: 5 }).map((_, i) => (
              <li key={i} className="flex items-center gap-4 px-4 py-3">
                <Skeleton className="h-7 w-7 rounded-pill" />
                <div className="flex-1">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="mt-1.5 h-3 w-56" />
                </div>
                <Skeleton className="h-8 w-16" />
              </li>
            ))}
          </ul>
        ) : queue.isError ? (
          <ErrorState label="Could not load the queue." onRetry={() => queue.refetch()} />
        ) : entries.length === 0 ? (
          <EmptyState
            icon={<IllustrationEmptyList />}
            title="No patients are waiting right now."
            hint="Booked and checked-in patients appear here, ordered by clinical priority."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-hairline/60">
            <AnimatePresence initial={false}>
              {entries.map((entry) => {
                const actions = availableActions(entry.status, canManage(entry))
                const inProgress = entry.status === 'in_progress'
                return (
                  <m.li
                    key={entry.appointment_id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 36 }}
                    className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:gap-4"
                  >
                    <div className="flex items-center gap-3 sm:w-16">
                      <span className="flex h-7 w-7 items-center justify-center rounded-pill bg-canvas text-xs font-semibold tabular-nums text-slate ring-1 ring-inset ring-hairline">
                        {entry.position}
                      </span>
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-ink">{entry.patient.name}</span>
                        <AcuityChip acuity={entry.acuity} />
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted">
                        <span className="font-mono tabular-nums">{entry.patient.mrn}</span>
                        <span>{entry.doctor.name}</span>
                        <span className="tabular-nums">{formatTime(entry.scheduled_start)}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 sm:gap-6">
                      <div className="text-right">
                        <div className="font-display text-lg font-semibold tabular-nums text-ink">
                          {inProgress ? 'Now' : formatWait(entry.est_wait_min)}
                        </div>
                        <div className="text-[11px] uppercase tracking-wide text-muted">
                          {inProgress ? 'in consult' : 'est. wait'}
                        </div>
                      </div>
                      <StatusBadge tone={statusTone(entry.status)}>
                        {statusLabel(entry.status)}
                      </StatusBadge>
                    </div>

                    {actions.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {actions.map((action) => (
                          <button
                            key={action}
                            disabled={change.isPending}
                            onClick={() => change.mutate({ id: entry.appointment_id, action })}
                            className="rounded-control bg-canvas px-2.5 py-1 text-xs font-medium text-ink ring-1 ring-inset ring-hairline transition-colors hover:bg-hairline/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {ACTION_LABEL[action]}
                          </button>
                        ))}
                      </div>
                    )}
                  </m.li>
                )
              })}
            </AnimatePresence>
          </ul>
        )}
      </Card>
    </div>
  )
}
