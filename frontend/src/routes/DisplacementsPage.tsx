import { ArrowRight } from '../components/icons'

import { Card } from '../components/Card'
import { IllustrationCalendar } from '../components/illustrations'
import { TableSkeleton } from '../components/Skeleton'
import { EmptyState, ErrorState } from '../components/states'
import { formatDelayMin } from '../features/emergency/format'
import { useDisplacements } from '../features/history/api'
import { formatDateTime } from '../features/history/format'
import { formatTime } from '../features/schedule/timeline'

export function DisplacementsPage() {
  const displacements = useDisplacements()
  const rows = displacements.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Displaced appointments</h2>
        <p className="text-sm text-muted">
          Every appointment an emergency moved — nothing is lost; each is traceable to the decision
          that moved it.
        </p>
      </div>

      <Card>
        {displacements.isLoading ? (
          <TableSkeleton cols={6} />
        ) : displacements.isError ? (
          <ErrorState
            label="Could not load displacements."
            onRetry={() => displacements.refetch()}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<IllustrationCalendar />}
            title="No appointments have been displaced."
            hint="When an emergency moves a booked appointment, it is recorded here, traceable to the decision that moved it."
          />
        ) : (
          <div className="max-h-[65vh] overflow-auto">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">Patient</th>
                  <th className="px-4 py-3 font-medium">Doctor</th>
                  <th className="px-4 py-3 font-medium">Moved</th>
                  <th className="px-4 py-3 font-medium">Delay</th>
                  <th className="px-4 py-3 font-medium">When</th>
                  <th className="px-4 py-3 font-medium">Decision</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((d) => (
                  <tr
                    key={d.id}
                    className="border-b border-hairline/60 transition-colors last:border-0 hover:bg-canvas"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-ink">{d.patient_name}</div>
                      <div className="font-mono text-xs tabular-nums text-muted">{d.mrn}</div>
                    </td>
                    <td className="px-4 py-3 text-slate">{d.doctor_name}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-2 font-mono text-xs tabular-nums text-slate">
                        {formatTime(d.from_start)}
                        <ArrowRight size={12} className="text-muted" />
                        {formatTime(d.to_start)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-warning/10 px-1.5 py-0.5 text-xs text-warning">
                        {formatDelayMin(d.delay_min)}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-muted">
                      {formatDateTime(d.created_at)}
                    </td>
                    <td className="px-4 py-3 font-mono tabular-nums text-muted">#{d.decision_id}</td>
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
