import { useState } from 'react'

import { Card, CardHeader, CardTitle } from '../components/Card'
import { IllustrationCalendar, IllustrationEmptyList } from '../components/illustrations'
import { TableSkeleton } from '../components/Skeleton'
import { StatusBadge } from '../components/StatusBadge'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { useAudit, useDecision, useDecisions } from '../features/history/api'
import { DecisionTrace } from '../features/history/DecisionTrace'
import {
  auditActionLabel,
  decisionStatusLabel,
  decisionStatusTone,
  formatDateTime,
} from '../features/history/format'

export function AuditPage() {
  const decisions = useDecisions()
  const audit = useAudit()
  const [selected, setSelected] = useState<number | null>(null)
  const detail = useDecision(selected)

  const decisionRows = decisions.data ?? []
  const auditRows = audit.data ?? []

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Decisions &amp; audit</h2>
        <p className="text-sm text-muted">
          The engine&apos;s scheduling decisions and the full audit trail — for oversight and
          reproducibility.
        </p>
      </div>

      {/* Scheduling decisions */}
      <section className="flex flex-col gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Scheduling decisions</CardTitle>
          </CardHeader>
          {decisions.isLoading ? (
            <TableSkeleton cols={6} />
          ) : decisions.isError ? (
            <ErrorState label="Could not load decisions." onRetry={() => decisions.refetch()} />
          ) : decisionRows.length === 0 ? (
            <EmptyState
              icon={<IllustrationCalendar />}
              title="No scheduling decisions recorded yet."
            />
          ) : (
            <div className="max-h-[55vh] overflow-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="sticky top-0 z-10 bg-surface">
                  <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium">When</th>
                    <th className="px-4 py-3 font-medium">Patient</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Displaced</th>
                    <th className="px-4 py-3 font-medium">By</th>
                    <th className="px-4 py-3 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {decisionRows.map((d) => (
                    <tr
                      key={d.id}
                      className="border-b border-hairline/60 transition-colors last:border-0 hover:bg-canvas"
                    >
                      <td className="px-4 py-3 tabular-nums text-muted">
                        {formatDateTime(d.created_at)}
                      </td>
                      <td className="px-4 py-3 font-medium text-ink">{d.patient_name}</td>
                      <td className="px-4 py-3">
                        <StatusBadge tone={decisionStatusTone(d.status)}>
                          {decisionStatusLabel(d.status)}
                        </StatusBadge>
                      </td>
                      <td className="px-4 py-3 tabular-nums text-slate">{d.displaced_count}</td>
                      <td className="px-4 py-3 text-slate">{d.actor_name}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setSelected(d.id)}
                          className="rounded-control bg-canvas px-2.5 py-1 text-xs font-medium text-brand ring-1 ring-inset ring-hairline transition-colors hover:bg-hairline/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
                        >
                          View trace
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {selected != null && (
          <Card padded>
            <div className="mb-4 flex items-center justify-between">
              <h4 className="font-display text-base font-semibold text-ink">Decision #{selected}</h4>
              <button
                onClick={() => setSelected(null)}
                className="text-sm text-muted transition-colors hover:text-ink"
              >
                Close
              </button>
            </div>
            {detail.isLoading ? (
              <LoadingState label="Loading trace…" />
            ) : detail.data ? (
              <DecisionTrace detail={detail.data} />
            ) : (
              <ErrorState label="Could not load the trace." />
            )}
          </Card>
        )}
      </section>

      {/* Audit log */}
      <section className="flex flex-col gap-3">
        <Card>
          <CardHeader>
            <CardTitle>Audit log</CardTitle>
          </CardHeader>
          {audit.isLoading ? (
            <TableSkeleton cols={5} />
          ) : audit.isError ? (
            <ErrorState label="Could not load the audit log." onRetry={() => audit.refetch()} />
          ) : auditRows.length === 0 ? (
            <EmptyState icon={<IllustrationEmptyList />} title="No audit entries yet." />
          ) : (
            <div className="max-h-[55vh] overflow-auto">
              <table className="w-full min-w-[640px] text-left text-sm">
                <thead className="sticky top-0 z-10 bg-surface">
                  <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium">When</th>
                    <th className="px-4 py-3 font-medium">Entity</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">By</th>
                    <th className="px-4 py-3 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {auditRows.map((a) => (
                    <tr
                      key={a.id}
                      className="border-b border-hairline/60 transition-colors last:border-0 hover:bg-canvas"
                    >
                      <td className="px-4 py-3 tabular-nums text-muted">
                        {formatDateTime(a.created_at)}
                      </td>
                      <td className="px-4 py-3 text-slate">
                        {a.entity_type} <span className="text-muted">#{a.entity_id}</span>
                      </td>
                      <td className="px-4 py-3 text-ink">{auditActionLabel(a.action)}</td>
                      <td className="px-4 py-3 text-slate">{a.actor_name}</td>
                      <td className="px-4 py-3 text-muted">{a.reason ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>
    </div>
  )
}
