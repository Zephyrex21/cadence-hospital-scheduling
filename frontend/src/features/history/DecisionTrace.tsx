import { ArrowRight } from 'lucide-react'

import { Card } from '../../components/Card'
import { StatusBadge } from '../../components/StatusBadge'
import type { DecisionDetail } from '../../types'
import { reasonText } from '../emergency/format'
import { formatTime } from '../schedule/timeline'
import { decisionStatusLabel, decisionStatusTone, formatDateTime } from './format'

/** Renders a persisted decision's trace — what was decided, by whom, and why. */
export function DecisionTrace({ detail }: { detail: DecisionDetail }) {
  const p = detail.parameters as Record<string, unknown>
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="font-display text-base font-semibold text-ink">
            {detail.patient.name}{' '}
            <span className="font-mono text-xs tabular-nums text-muted">{detail.patient.mrn}</span>
          </p>
          <p className="text-xs text-muted">
            {formatDateTime(detail.created_at)} · by {detail.actor.name} · {detail.engine_version}
          </p>
        </div>
        <StatusBadge tone={decisionStatusTone(detail.status)}>
          {decisionStatusLabel(detail.status)}
        </StatusBadge>
      </div>

      {detail.reasons.length > 0 && (
        <ul className="flex flex-col gap-1.5 rounded-control border border-warning/20 bg-warning/5 p-3 text-sm text-warning">
          {detail.reasons.map((r) => (
            <li key={r}>{reasonText(r)}</li>
          ))}
        </ul>
      )}

      {detail.chosen_plan && (
        <div className="text-sm text-slate">
          Placed with <span className="font-medium">Doctor #{detail.chosen_plan.placement.doctor_id}</span>{' '}
          at{' '}
          <span className="font-mono tabular-nums">
            {formatTime(detail.chosen_plan.placement.start)}–
            {formatTime(detail.chosen_plan.placement.end)}
          </span>
        </div>
      )}

      <Card padded className="bg-canvas shadow-none">
        <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
          Displaced ({detail.displacements.length})
        </p>
        {detail.displacements.length === 0 ? (
          <p className="text-sm text-success">No appointments were displaced.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {detail.displacements.map((d) => (
              <li
                key={d.appointment_id}
                className="flex items-center justify-between gap-3 rounded-control bg-surface px-3 py-2 text-sm ring-1 ring-inset ring-hairline"
              >
                <span className="truncate font-medium text-ink">{d.patient_name}</span>
                <span className="flex items-center gap-2 font-mono text-xs tabular-nums text-slate">
                  {formatTime(d.from_start)}
                  <ArrowRight size={12} className="text-muted" />
                  {formatTime(d.to_start)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="flex flex-wrap gap-x-6 gap-y-1 border-t border-hairline pt-3 text-xs text-muted">
        <span>Fairness cap: {String(p.max_displacements ?? '—')}</span>
        <span>Auto-displace limit: {String(p.max_auto_displaced ?? '—')}</span>
        <span>Alternatives considered: {detail.alternatives.length}</span>
      </div>
    </div>
  )
}
