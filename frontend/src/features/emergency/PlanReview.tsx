import { useReducedMotion, m } from 'framer-motion'
import { ArrowRight } from 'lucide-react'

import { StatusBadge } from '../../components/StatusBadge'
import type { EmergencyMove, EmergencyPlan, PlanResponse } from '../../types'
import { formatTime } from '../schedule/timeline'
import { AcuityChip } from './AcuityChip'
import { formatDelayMin, reasonText, statusLabel, statusTone } from './format'

/**
 * The plan-diff review: shows exactly where the emergency lands and which booked
 * appointments move, by how much, and why — before anything is committed. When a
 * plan is chosen with displacements, an animated before/after mini-timeline shows
 * each displaced block sliding from its old time to its new one.
 */
export function PlanReview({ plan }: { plan: PlanResponse }) {
  const { decision, appointment_details, doctor_names, emergency_patient } = plan
  const chosen = decision.chosen

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div>
            <p className="font-display text-base font-semibold text-ink">
              {emergency_patient.name}
            </p>
            <p className="font-mono text-xs tabular-nums text-muted">{emergency_patient.mrn}</p>
          </div>
          <AcuityChip acuity={decision.request.acuity} />
        </div>
        <StatusBadge tone={statusTone(decision.status)}>{statusLabel(decision.status)}</StatusBadge>
      </div>

      {decision.reasons.length > 0 && (
        <ul className="flex flex-col gap-1.5 rounded-control border border-warning/20 bg-warning/5 p-3 text-sm text-warning">
          {decision.reasons.map((r) => (
            <li key={r}>{reasonText(r)}</li>
          ))}
        </ul>
      )}

      {chosen ? (
        <PlanBody plan={chosen} details={appointment_details} doctorNames={doctor_names} />
      ) : decision.alternatives.length > 0 ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            No plan can be applied automatically. Closest options for a clinician to weigh:
          </p>
          {decision.alternatives.slice(0, 3).map((alt, i) => (
            <div key={i} className="rounded-card border border-hairline bg-canvas p-3">
              <PlanBody plan={alt} details={appointment_details} doctorNames={doctor_names} muted />
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-control border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
          No eligible doctor has availability for this emergency.
        </p>
      )}
    </div>
  )
}

function PlanBody({
  plan,
  details,
  doctorNames,
  muted,
}: {
  plan: EmergencyPlan
  details: PlanResponse['appointment_details']
  doctorNames: Record<string, string>
  muted?: boolean
}) {
  const doctor =
    doctorNames[String(plan.placement.doctor_id)] ?? `Doctor ${plan.placement.doctor_id}`

  return (
    <div className="flex flex-col gap-3">
      <div className={`text-sm ${muted ? 'text-slate' : 'text-ink'}`}>
        Place with <span className="font-medium">{doctor}</span> at{' '}
        <span className="font-mono tabular-nums">
          {formatTime(plan.placement.start)}–{formatTime(plan.placement.end)}
        </span>
      </div>

      {plan.moves.length === 0 ? (
        <p className="text-sm text-success">No booked appointments are displaced.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {!muted && <MiniTimeline plan={plan} details={details} />}
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted">
              Displaced appointments ({plan.moves.length})
            </p>
            <ul className="flex flex-col gap-1.5">
              {plan.moves.map((m2) => {
                const d = details[String(m2.appointment_id)]
                return (
                  <li
                    key={m2.appointment_id}
                    className="flex items-center justify-between gap-3 rounded-control bg-surface px-3 py-2 text-sm ring-1 ring-inset ring-hairline"
                  >
                    <span className="truncate font-medium text-ink">
                      {d ? d.patient_name : `Appointment ${m2.appointment_id}`}
                    </span>
                    <span className="flex items-center gap-2 font-mono text-xs tabular-nums text-slate">
                      {formatTime(m2.from_start)}
                      <ArrowRight size={12} className="text-muted" />
                      {m2.to_start ? formatTime(m2.to_start) : '—'}
                      <span className="rounded bg-warning/10 px-1.5 py-0.5 text-warning">
                        {formatDelayMin(m2.delay_min)}
                      </span>
                    </span>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

/** Animated before/after: displaced blocks glide from their old slot to the new one. */
function MiniTimeline({
  plan,
  details,
}: {
  plan: EmergencyPlan
  details: PlanResponse['appointment_details']
}) {
  const reduce = useReducedMotion()
  const ms = (iso: string) => Date.parse(iso)
  const MIN_MS = 10 * 60_000 // visual floor so a short block still reads
  const startMs = ms(plan.placement.start)
  const endMs = ms(plan.placement.end)
  const emergencyDurMs = Math.max(endMs - startMs, MIN_MS)

  // Each displaced appointment is sized by ITS OWN duration, not the emergency's.
  const moveDurMs = (mv: EmergencyMove) => Math.max(mv.duration_min * 60_000, MIN_MS)

  const froms = plan.moves.map((mv) => ms(mv.from_start))
  const t0 = Math.min(startMs, ...froms)
  const ends: number[] = [endMs, startMs + emergencyDurMs]
  for (const mv of plan.moves) {
    const dur = moveDurMs(mv)
    ends.push(ms(mv.from_start) + dur)
    if (mv.to_start) ends.push(ms(mv.to_start) + dur)
  }
  const t1 = Math.max(...ends)
  const span = Math.max(t1 - t0, 1)
  const pct = (m2: number) => ((m2 - t0) / span) * 100
  const widthFor = (durMs: number) => (durMs / span) * 100

  return (
    <div
      className="rounded-control border border-hairline bg-canvas p-3"
      role="img"
      aria-label="Before and after timeline of the proposed changes"
    >
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted">
        How the day shifts
      </p>
      <div className="flex flex-col gap-2">
        {/* Emergency insertion */}
        <Row label="Emergency">
          <m.div
            initial={reduce ? false : { opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: 'spring', stiffness: 300, damping: 24 }}
            className="absolute inset-y-1 rounded bg-brand"
            style={{ left: `${pct(startMs)}%`, width: `${widthFor(emergencyDurMs)}%` }}
          />
        </Row>
        {/* Each displaced appointment: ghost at old slot, solid glides to new slot */}
        {plan.moves.map((mv) => {
          const d = details[String(mv.appointment_id)]
          const w = widthFor(moveDurMs(mv))
          const fromPct = pct(ms(mv.from_start))
          const toPct = mv.to_start ? pct(ms(mv.to_start)) : fromPct
          return (
            <Row key={mv.appointment_id} label={d?.patient_name ?? `#${mv.appointment_id}`}>
              <div
                className="absolute inset-y-1 rounded border border-dashed border-slate/40 bg-slate/5"
                style={{ left: `${fromPct}%`, width: `${w}%` }}
                aria-hidden
              />
              <m.div
                initial={reduce ? false : { left: `${fromPct}%` }}
                animate={{ left: `${toPct}%` }}
                transition={{ type: 'spring', stiffness: 200, damping: 26, delay: 0.15 }}
                className="absolute inset-y-1 rounded bg-warning/70"
                style={{ left: `${toPct}%`, width: `${w}%` }}
              />
            </Row>
          )
        })}
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] tabular-nums text-muted">
        <span>{formatTime(new Date(t0).toISOString())}</span>
        <span>{formatTime(new Date(t1).toISOString())}</span>
      </div>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 truncate text-[11px] text-muted">{label}</span>
      <div className="relative h-6 flex-1 overflow-hidden rounded bg-surface ring-1 ring-inset ring-hairline">
        {children}
      </div>
    </div>
  )
}
