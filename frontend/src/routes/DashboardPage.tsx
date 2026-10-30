import { m } from 'framer-motion'
import { useState } from 'react'

import { Button } from '../components/Button'
import { Card, CardHeader, CardTitle } from '../components/Card'
import { CountUp } from '../components/CountUp'
import { IllustrationCalm } from '../components/illustrations'
import { Modal } from '../components/Modal'
import { Skeleton } from '../components/Skeleton'
import { ErrorState } from '../components/states'
import { useToast } from '../components/Toast'
import { useAuth } from '../features/auth/AuthContext'
import { canRecordTriage, ROLE_LABELS } from '../features/auth/roles'
import { formatRunningDelay, useDashboard } from '../features/dashboard/api'
import { useApplyEscalation, useEscalationOptions } from '../features/emergency/api'
import { ACUITY_LABEL, ACUITY_ORDER, acuityDotClass, reasonText } from '../features/emergency/format'
import { PlanBody } from '../features/emergency/PlanReview'
import { formatDateTime } from '../features/history/format'
import { useResolveEscalation } from '../features/history/api'
import { ApiError } from '../lib/api'
import { fadeUp, staggerContainer } from '../motion'
import type { DashboardSummary, EscalationItem } from '../types'

export function DashboardPage() {
  const { user } = useAuth()
  const dash = useDashboard()

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">
          Welcome{user ? `, ${user.name.split(' ')[0]}` : ''}
        </h2>
        <p className="text-sm text-muted">
          {user ? ROLE_LABELS[user.role] : ''} · live hospital workload
        </p>
      </div>

      {dash.isLoading ? (
        <DashboardSkeleton />
      ) : dash.isError || !dash.data ? (
        <Card>
          <ErrorState label="Could not load the dashboard." onRetry={() => dash.refetch()} />
        </Card>
      ) : (
        <DashboardBody data={dash.data} />
      )}
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6" role="status" aria-busy aria-label="Loading workload">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i} padded>
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-8 w-12" />
          </Card>
        ))}
      </div>
      <Card padded>
        <Skeleton className="h-3 w-28" />
        <Skeleton className="mt-3 h-3 w-full" />
      </Card>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} padded>
            <Skeleton className="h-4 w-32" />
            <div className="mt-4 flex flex-col gap-3">
              {Array.from({ length: 3 }).map((_, j) => (
                <Skeleton key={j} className="h-10 w-full" />
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

function DashboardBody({ data }: { data: DashboardSummary }) {
  const { user } = useAuth()
  const canResolve = user ? canRecordTriage(user.role) : false
  const [resolving, setResolving] = useState<EscalationItem | null>(null)
  const [reviewing, setReviewing] = useState<EscalationItem | null>(null)
  return (
    <m.div
      variants={staggerContainer(0.06)}
      initial="initial"
      animate="animate"
      className="flex flex-col gap-6"
    >
      {/* Tiles */}
      <m.div variants={fadeUp} className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Tile label="Waiting" value={data.total_waiting} />
        <Tile label="In consultation" value={data.in_progress} />
        <Tile label="Displaced today" value={data.displaced_today} />
        <Tile
          label="Escalations"
          value={data.escalations_pending}
          tone={data.escalations_pending > 0 ? 'warning' : 'neutral'}
        />
      </m.div>

      {/* Acuity distribution */}
      <m.div variants={fadeUp}>
        <Card padded>
          <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted">
            Waiting by acuity
          </p>
          <AcuityBar data={data} />
          <div className="mt-4 flex flex-wrap gap-2">
            {ACUITY_ORDER.map((a) => (
              <span
                key={a}
                className="inline-flex items-center gap-2 rounded-pill bg-canvas px-3 py-1 text-sm ring-1 ring-inset ring-hairline"
              >
                <span aria-hidden className={`h-2 w-2 rounded-full ${acuityDotClass(a)}`} />
                <span className="font-medium text-ink">{a.toUpperCase()}</span>
                <span className="tabular-nums text-slate">{data.waiting_by_acuity[a] ?? 0}</span>
              </span>
            ))}
          </div>
        </Card>
      </m.div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Escalation inbox */}
        <m.div variants={fadeUp}>
          <Card>
            <CardHeader>
              <CardTitle>Escalation inbox</CardTitle>
            </CardHeader>
            {data.recent_escalations.length === 0 ? (
              <div className="flex flex-col items-center gap-3 p-8 text-center">
                <IllustrationCalm />
                <p className="text-sm font-medium text-ink">No pending escalations</p>
                <p className="text-xs text-muted">
                  Emergencies the engine can&apos;t auto-schedule will appear here for a clinician.
                </p>
              </div>
            ) : (
              <ul className="flex flex-col">
                {data.recent_escalations.map((e) => (
                  <li
                    key={e.decision_id}
                    className="border-b border-hairline/60 px-5 py-3 last:border-0"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-ink">{e.patient_name}</span>
                      <span className="text-xs tabular-nums text-muted">
                        {formatDateTime(e.created_at)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-warning">
                      {e.reasons.map((r) => reasonText(r)).join(' · ')}
                    </p>
                    {canResolve && (
                      <div className="mt-2 flex gap-2">
                        <Button size="sm" onClick={() => setReviewing(e)}>
                          Review options
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setResolving(e)}>
                          Resolve
                        </Button>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </m.div>

        {/* Doctor load */}
        <m.div variants={fadeUp}>
          <Card>
            <CardHeader>
              <CardTitle>Doctor load</CardTitle>
            </CardHeader>
            {data.doctor_load.length === 0 ? (
              <p className="p-5 text-sm text-muted">No doctors on shift.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[420px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                      <th className="px-5 py-2 font-medium">Doctor</th>
                      <th className="px-5 py-2 font-medium">Waiting</th>
                      <th className="px-5 py-2 font-medium">In consult</th>
                      <th className="px-5 py-2 font-medium">Delay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.doctor_load.map((d) => (
                      <tr key={d.doctor_id} className="border-b border-hairline/60 last:border-0">
                        <td className="px-5 py-2 font-medium text-ink">{d.name}</td>
                        <td className="px-5 py-2 tabular-nums text-slate">{d.waiting}</td>
                        <td className="px-5 py-2 tabular-nums text-slate">{d.in_progress}</td>
                        <td className="px-5 py-2">
                          {d.running_delay_min > 0 ? (
                            <span className="text-warning">
                              {formatRunningDelay(d.running_delay_min)}
                            </span>
                          ) : (
                            <span className="text-muted">On time</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </m.div>
      </div>

      {resolving && (
        <ResolveDialog item={resolving} onClose={() => setResolving(null)} />
      )}
      {reviewing && (
        <OptionsDialog item={reviewing} onClose={() => setReviewing(null)} />
      )}
    </m.div>
  )
}

/** Clinician review of an escalation: pick one of the engine's options and apply
 *  it. The server re-validates the option against the live schedule first. */
function OptionsDialog({ item, onClose }: { item: EscalationItem; onClose: () => void }) {
  const options = useEscalationOptions(item.decision_id)
  const apply = useApplyEscalation()
  const { toast } = useToast()
  const [note, setNote] = useState('')

  async function applyOption(index: number) {
    try {
      const res = await apply.mutateAsync({ id: item.decision_id, optionIndex: index, note: note.trim() })
      toast({
        tone: 'success',
        title: 'Emergency scheduled',
        description: `${item.patient_name} — ${res.displaced.length} appointment${
          res.displaced.length === 1 ? '' : 's'
        } rescheduled.`,
      })
      onClose()
    } catch {
      /* surfaced below via apply.error */
    }
  }

  const applyError =
    apply.error instanceof ApiError
      ? apply.error.message
      : apply.error
        ? 'Could not apply this option.'
        : null
  const loadError =
    options.error instanceof ApiError
      ? options.error.message
      : options.error
        ? 'Could not load the options.'
        : null
  const data = options.data

  return (
    <Modal
      title={`Review options — ${item.patient_name}`}
      onClose={onClose}
      footer={
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        {options.isLoading && <p className="text-sm text-muted">Loading options…</p>}
        {loadError && (
          <p role="alert" className="text-sm text-danger">
            {loadError}
          </p>
        )}
        {data && data.options.length === 0 && (
          <p className="text-sm text-muted">
            The engine found no placement. Handle this manually, then use Resolve to record how.
          </p>
        )}
        {data && data.options.length > 0 && (
          <>
            <p className="text-sm text-muted">
              Choose how to place this patient. The option is re-checked against the current
              schedule when you apply it; if anything changed you will be asked to re-plan.
            </p>
            {data.options.map((opt) => (
              <div
                key={opt.index}
                className="flex flex-col gap-3 rounded-card border border-hairline bg-canvas p-3"
              >
                <PlanBody
                  plan={opt}
                  details={data.appointment_details}
                  doctorNames={data.doctor_names}
                  muted={!opt.applicable}
                />
                {opt.applicable ? (
                  <div>
                    <Button
                      size="sm"
                      onClick={() => applyOption(opt.index)}
                      loading={apply.isPending}
                    >
                      Apply option {opt.index + 1}
                    </Button>
                  </div>
                ) : (
                  <p className="text-xs text-warning">
                    Not applicable automatically: {opt.reject_reasons.map(reasonText).join(' · ')}
                  </p>
                )}
              </div>
            ))}
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-medium uppercase tracking-wide text-muted">
                Note (optional, written to the audit trail)
              </span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={2}
                className="rounded-control border border-hairline bg-surface px-3 py-2 text-sm text-ink shadow-xs outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30"
              />
            </label>
          </>
        )}
        {applyError && (
          <p role="alert" className="text-sm text-danger">
            {applyError}
          </p>
        )}
      </div>
    </Modal>
  )
}

function ResolveDialog({ item, onClose }: { item: EscalationItem; onClose: () => void }) {
  const resolve = useResolveEscalation()
  const { toast } = useToast()
  const [note, setNote] = useState('')
  const canSubmit = note.trim().length > 0

  async function submit() {
    if (!canSubmit) return
    try {
      await resolve.mutateAsync({ id: item.decision_id, note: note.trim() })
      toast({ tone: 'success', title: 'Escalation resolved', description: item.patient_name })
      onClose()
    } catch {
      /* surfaced below via resolve.error */
    }
  }

  const errorMessage =
    resolve.error instanceof ApiError
      ? resolve.error.message
      : resolve.error
        ? 'Could not resolve this escalation.'
        : null

  return (
    <Modal
      title="Resolve escalation"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit} loading={resolve.isPending}>
            Resolve
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted">
          Record how <span className="font-medium text-ink">{item.patient_name}</span>&apos;s
          escalation was handled. This is written to the audit trail and clears it from the inbox.
        </p>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium uppercase tracking-wide text-muted">
            Resolution note
          </span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            autoFocus
            placeholder="e.g. Seen by the on-call physician; admitted directly."
            className="rounded-control border border-hairline bg-surface px-3 py-2 text-sm text-ink shadow-xs outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30"
          />
        </label>
        {errorMessage && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage}
          </p>
        )}
      </div>
    </Modal>
  )
}

function AcuityBar({ data }: { data: DashboardSummary }) {
  const total = data.total_waiting
  return (
    <div
      className="flex h-3 overflow-hidden rounded-pill bg-canvas ring-1 ring-inset ring-hairline"
      role="img"
      aria-label={`Waiting by acuity: ${ACUITY_ORDER.map((a) => `${a.toUpperCase()} ${data.waiting_by_acuity[a] ?? 0}`).join(', ')}`}
    >
      {total > 0 &&
        ACUITY_ORDER.map((a) => {
          const n = data.waiting_by_acuity[a] ?? 0
          if (n <= 0) return null
          return (
            <div
              key={a}
              className={acuityDotClass(a)}
              style={{ width: `${(n / total) * 100}%` }}
              title={`${ACUITY_LABEL[a]}: ${n}`}
            />
          )
        })}
    </div>
  )
}

function Tile({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: number
  tone?: 'neutral' | 'warning'
}) {
  const warn = tone === 'warning' && value > 0
  return (
    <Card
      padded
      className={`transition-colors ${warn ? 'border-warning/40' : ''}`}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
      <CountUp
        value={value}
        className={`mt-1 block font-display text-3xl font-semibold tabular-nums ${
          warn ? 'text-warning' : 'text-ink'
        }`}
      />
    </Card>
  )
}
