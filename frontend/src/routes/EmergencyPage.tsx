import { Check, CheckCircle2, ChevronLeft } from '../components/icons'
import { m } from 'framer-motion'
import { useRef, useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Select } from '../components/Select'
import { Textarea } from '../components/Textarea'
import { useToast } from '../components/Toast'
import { useAuth } from '../features/auth/AuthContext'
import { canRecordTriage } from '../features/auth/roles'
import { AcuityChip } from '../features/emergency/AcuityChip'
import {
  useCommitEmergency,
  useLatestTriage,
  usePlanEmergency,
  useRecordTriage,
} from '../features/emergency/api'
import { ACUITY_LABEL, ACUITY_ORDER, ACUITY_TARGET } from '../features/emergency/format'
import { PlanReview } from '../features/emergency/PlanReview'
import { PatientPicker } from '../components/PatientPicker'
import { useAppointmentTypes } from '../features/schedule/api'
import { formatTime } from '../features/schedule/timeline'
import { ApiError } from '../lib/api'
import type { Acuity, CommitResponse, PlanResponse } from '../types'

function newIdempotencyKey(): string {
  const c = globalThis.crypto
  return c && 'randomUUID' in c ? c.randomUUID() : `idem-${Date.now()}-${Math.random()}`
}

export function EmergencyPage() {
  const { user } = useAuth()
  const { toast } = useToast()
  const types = useAppointmentTypes()
  const triage = useRecordTriage()
  const plan = usePlanEmergency()
  const commit = useCommitEmergency()

  const [patientId, setPatientId] = useState<number | null>(null)
  const [typeId, setTypeId] = useState<number | null>(null)
  const [acuity, setAcuity] = useState<Acuity>('a2')
  const [complaint, setComplaint] = useState('')
  const [planData, setPlanData] = useState<PlanResponse | null>(null)
  const [committed, setCommitted] = useState<CommitResponse | null>(null)
  const idemRef = useRef('')
  // A3: the (patient|acuity|complaint) we last recorded a triage for, so neither
  // "Review plan" re-runs nor "Re-plan" re-triage an unchanged assessment.
  const triagedSigRef = useRef('')

  const canTriage = user ? canRecordTriage(user.role) : false
  const latestTriage = useLatestTriage(patientId)
  const recordedAcuity = latestTriage.data?.acuity ?? null

  // A2: nurses/admins set acuity inline; receptionists use the nurse's recorded
  // acuity (read-only) and cannot proceed until a triage exists.
  const effectiveAcuity: Acuity | null = canTriage ? acuity : recordedAcuity

  const ready =
    patientId != null &&
    typeId != null &&
    effectiveAcuity != null &&
    (!canTriage || complaint.trim().length > 0)
  const step = committed ? 3 : planData ? 2 : 1

  async function review() {
    if (patientId == null || typeId == null || effectiveAcuity == null) return
    if (canTriage && complaint.trim().length === 0) return
    setCommitted(null)
    try {
      if (canTriage) {
        const sig = `${patientId}|${effectiveAcuity}|${complaint.trim()}`
        if (sig !== triagedSigRef.current) {
          await triage.mutateAsync({
            patient_id: patientId,
            acuity: effectiveAcuity,
            chief_complaint: complaint.trim(),
          })
          triagedSigRef.current = sig
        }
      }
      const res = await plan.mutateAsync({
        patient_id: patientId,
        type_id: typeId,
        acuity: effectiveAcuity,
      })
      idemRef.current = newIdempotencyKey()
      setPlanData(res)
    } catch {
      /* surfaced via plan.error / triage.error */
    }
  }

  async function doCommit() {
    if (!planData || patientId == null || typeId == null || effectiveAcuity == null) return
    try {
      const res = await commit.mutateAsync({
        patient_id: patientId,
        type_id: typeId,
        acuity: effectiveAcuity,
        // The server clock is authoritative; the digest pins exactly what was reviewed.
        fingerprint: planData.fingerprint,
        plan_digest: planData.plan_digest ?? undefined,
        idempotency_key: idemRef.current,
      })
      if (res.status === 'auto') {
        toast({
          tone: 'success',
          title: 'Walk-in placed',
          description: `Moved ${res.displaced.length} booked appointment${
            res.displaced.length === 1 ? '' : 's'
          }.`,
        })
      } else {
        toast({
          tone: 'warning',
          title: 'Escalation recorded',
          description:
            'A nurse or administrator can now review and apply an option from the dashboard.',
        })
      }
      setCommitted(res)
    } catch {
      /* surfaced via commit.error */
    }
  }

  function reset() {
    // "Back" — drop the plan but keep the form so the user can tweak and re-plan.
    setPlanData(null)
    setCommitted(null)
  }

  function startOver() {
    // "Schedule another" (B10) — clear the previous patient, complaint, and plan.
    setPlanData(null)
    setCommitted(null)
    setPatientId(null)
    setTypeId(null)
    setComplaint('')
    setAcuity('a2')
    triagedSigRef.current = ''
  }

  const reviewError =
    plan.error instanceof ApiError
      ? plan.error.message
      : plan.error
        ? 'Could not compute a plan.'
        : null
  const staleCode =
    commit.error instanceof ApiError
      ? (commit.error.details as { code?: string } | undefined)?.code
      : undefined
  const scheduleChanged =
    staleCode === 'schedule_changed' || staleCode === 'plan_changed' || staleCode === 'plan_expired'
  const commitError = scheduleChanged
    ? null
    : commit.error instanceof ApiError
      ? commit.error.message
      : commit.error
        ? 'Commit failed.'
        : null

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Emergency scheduling</h2>
        <p className="text-sm text-muted">
          Triage a walk-in, review exactly who would be affected, then commit — or escalate.
        </p>
      </div>

      <Stepper current={step} />

      {/* Step 1 — Triage */}
      {step === 1 && (
        <Card padded>
          <div className="flex flex-col gap-4">
            <PatientPicker name="emergency-patient" value={patientId} onChange={setPatientId} />

            <Select
              label="Appointment type"
              name="emergency-type"
              value={typeId ?? ''}
              onChange={(e) => setTypeId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="" disabled>
                Select type
              </option>
              {(types.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} · {t.default_duration_min}m
                </option>
              ))}
            </Select>

            {canTriage ? (
              <div className="flex flex-col gap-1.5">
                <Select
                  label="Acuity (clinical judgment)"
                  name="emergency-acuity"
                  value={acuity}
                  onChange={(e) => setAcuity(e.target.value as Acuity)}
                >
                  {ACUITY_ORDER.map((a) => (
                    <option key={a} value={a}>
                      {ACUITY_LABEL[a]}
                    </option>
                  ))}
                </Select>
                <span className="text-xs text-muted">{ACUITY_TARGET[acuity]}</span>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <span className="text-sm font-medium text-ink">Acuity (clinical judgment)</span>
                {patientId == null ? (
                  <p className="text-xs text-muted">Select a patient to see their triage.</p>
                ) : latestTriage.isLoading ? (
                  <p className="text-xs text-muted">Checking triage…</p>
                ) : recordedAcuity ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <AcuityChip acuity={recordedAcuity} />
                    <span className="text-xs text-muted">{ACUITY_TARGET[recordedAcuity]}</span>
                  </div>
                ) : (
                  <p role="status" className="text-sm text-warning">
                    A nurse must triage this patient first.
                  </p>
                )}
              </div>
            )}

            {canTriage && (
              <Textarea
                label="Chief complaint"
                id="emergency-complaint"
                value={complaint}
                onChange={(e) => setComplaint(e.target.value)}
                rows={2}
                placeholder="e.g. Chest pain for 20 minutes"
              />
            )}

            {!canTriage && (
              <p className="text-xs text-muted">
                You can review and schedule, but only a nurse records the triage assessment.
              </p>
            )}
            {reviewError && (
              <p role="alert" className="text-sm text-danger">
                {reviewError}
              </p>
            )}
            <Button onClick={review} loading={plan.isPending} disabled={!ready}>
              Review plan
            </Button>
          </div>
        </Card>
      )}

      {/* Step 2 — Review & commit */}
      {step === 2 && planData && (
        <Card padded>
          <div className="flex flex-col gap-5">
            <PlanReview plan={planData} />
            <div className="flex flex-col gap-3 border-t border-hairline pt-4">
              {scheduleChanged && (
                <p role="status" className="text-sm text-warning">
                  The schedule (or the proposed plan) changed since you reviewed it. Re-plan to see
                  the current impact.
                </p>
              )}
              {planData.decision.status !== 'auto' && !scheduleChanged && (
                <p role="status" className="text-sm text-muted">
                  No plan can be applied automatically. Record the escalation; a nurse or
                  administrator will then review the options and apply one from the dashboard. The
                  schedule is left untouched until then.
                </p>
              )}
              {commitError && (
                <p role="alert" className="text-sm text-danger">
                  {commitError}
                </p>
              )}
              <div className="flex items-center justify-between gap-3">
                <Button variant="ghost" onClick={reset}>
                  <ChevronLeft size={16} aria-hidden />
                  Back
                </Button>
                {scheduleChanged ? (
                  <Button onClick={review}>Re-plan</Button>
                ) : planData.decision.status === 'auto' ? (
                  <Button onClick={doCommit} loading={commit.isPending}>
                    Commit schedule
                  </Button>
                ) : (
                  <Button onClick={doCommit} loading={commit.isPending}>
                    Record escalation
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Step 3 — Committed */}
      {step === 3 && committed && <CommitResult result={committed} onReset={startOver} />}
    </div>
  )
}

function Stepper({ current }: { current: number }) {
  const steps = ['Triage', 'Review', 'Commit']
  return (
    <ol className="flex items-center gap-1 sm:gap-2">
      {steps.map((label, i) => {
        const n = i + 1
        const state = n < current ? 'done' : n === current ? 'current' : 'todo'
        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-pill text-xs font-semibold ring-1 ring-inset transition-colors ${
                state === 'done'
                  ? 'bg-brand text-surface ring-brand'
                  : state === 'current'
                    ? 'bg-brand/10 text-brand ring-brand/30'
                    : 'bg-canvas text-muted ring-hairline'
              }`}
            >
              {state === 'done' ? <Check size={14} aria-hidden /> : n}
            </span>
            <span className={`text-sm font-medium ${state === 'todo' ? 'text-muted' : 'text-ink'}`}>
              {label}
            </span>
            {i < steps.length - 1 && <span className="mx-1 h-px w-5 bg-hairline sm:w-8" />}
          </li>
        )
      })}
    </ol>
  )
}

function CommitResult({ result, onReset }: { result: CommitResponse; onReset: () => void }) {
  const scheduled = result.status === 'auto'
  return (
    <m.div
      role="status"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 26 }}
      className="flex flex-col gap-4"
    >
      <Card padded className={scheduled ? 'border-success/40' : 'border-warning/40'}>
        <div className="flex items-start gap-3">
          {scheduled ? (
            <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-success" aria-hidden />
          ) : (
            <span className="mt-0.5 h-6 w-6 shrink-0 rounded-pill bg-warning/15 text-center text-warning">
              !
            </span>
          )}
          <div>
            {scheduled ? (
              <p className="font-medium text-ink">
                Emergency scheduled. {result.displaced.length} appointment
                {result.displaced.length === 1 ? '' : 's'} rescheduled.
              </p>
            ) : (
              <p className="font-medium text-ink">
                Escalated to a clinician — nothing was auto-scheduled yet. Open the dashboard
                escalation inbox to review and apply an option.
              </p>
            )}
          </div>
        </div>

        {result.displaced.length > 0 && (
          <ul className="mt-4 flex flex-col gap-1.5">
            {result.displaced.map((d) => (
              <li
                key={d.appointment_id}
                className="flex items-center justify-between rounded-control bg-canvas px-3 py-2 text-sm ring-1 ring-inset ring-hairline"
              >
                <span className="font-medium text-ink">{d.patient_name}</span>
                <span className="font-mono text-xs tabular-nums text-slate">
                  {formatTime(d.from_start)} → {formatTime(d.to_start)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <div>
        <Button variant="secondary" onClick={onReset}>
          Schedule another
        </Button>
      </div>
    </m.div>
  )
}
