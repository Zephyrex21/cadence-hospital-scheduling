import { Lock } from 'lucide-react'
import { useState } from 'react'
import { createPortal } from 'react-dom'

import { StatusBadge } from '../../components/StatusBadge'
import type { Appointment, Doctor } from '../../types'
import {
  PX_PER_MIN,
  blockGeometry,
  computeWindow,
  formatHour,
  formatTime,
  hourLabels,
  minutesFromDayStart,
  statusLabel,
  statusTone,
  windowHeightPx,
  type DayWindow,
} from './timeline'

const HEADER_H = 48 // column header height (h-12), also the gutter's top padding

interface ScheduleTimelineProps {
  doctors: Doctor[]
  appointments: Appointment[]
  /** ISO instant for the "now" line; omit to hide it (e.g. when not viewing today). */
  nowIso?: string
}

/**
 * The signature read-only schedule: a vertical time axis with one column per
 * doctor. Blocks are positioned by start/duration; in-progress consultations are
 * visually locked and glow (they are protected from displacement by the engine).
 * A live "now" line marks the current time; hovering/focusing a block reveals its
 * detail in a portalled card.
 */
export function ScheduleTimeline({ doctors, appointments, nowIso }: ScheduleTimelineProps) {
  const [hover, setHover] = useState<{ appt: Appointment; rect: DOMRect } | null>(null)

  const byDoctor = new Map<number, Appointment[]>()
  for (const a of appointments) {
    const list = byDoctor.get(a.doctor.id) ?? []
    list.push(a)
    byDoctor.set(a.doctor.id, list)
  }

  const win = computeWindow(appointments)
  const timelineHeightPx = windowHeightPx(win)
  const hourTop = (h: number) => (h - win.startHour) * 60 * PX_PER_MIN
  const nowTop = nowIso ? minutesFromDayStart(nowIso, win) * PX_PER_MIN : null
  const showNow = nowTop !== null && nowTop >= 0 && nowTop <= timelineHeightPx

  return (
    <div className="overflow-x-auto rounded-card border border-hairline bg-surface shadow-card">
      <div className="flex min-w-[640px]">
        {/* Hour gutter */}
        <div className="w-16 shrink-0 border-r border-hairline" style={{ paddingTop: HEADER_H }}>
          <div className="relative" style={{ height: timelineHeightPx }}>
            {hourLabels(win).map((h) => (
              <div
                key={h}
                className="absolute right-2 -translate-y-1/2 text-xs tabular-nums text-muted"
                style={{ top: hourTop(h) }}
              >
                {formatHour(h)}
              </div>
            ))}
            {showNow && (
              <div
                className="absolute -right-1 h-2 w-2 -translate-y-1/2 rounded-full bg-danger shadow-glow-success"
                style={{ top: nowTop as number }}
                aria-hidden
              />
            )}
          </div>
        </div>

        {/* Doctor columns */}
        {doctors.map((doctor) => (
          <div key={doctor.id} className="flex-1 border-r border-hairline/60 last:border-0">
            <div className="flex h-12 items-center justify-center border-b border-hairline bg-canvas px-3 text-center">
              <span className="truncate font-display text-sm font-semibold text-ink">
                {doctor.name}
              </span>
            </div>
            <div className="relative" style={{ height: timelineHeightPx }}>
              {hourLabels(win).map((h) => (
                <div
                  key={h}
                  className="absolute inset-x-0 border-t border-hairline/40"
                  style={{ top: hourTop(h) }}
                />
              ))}
              {showNow && (
                <div
                  className="pointer-events-none absolute inset-x-0 z-10 h-px bg-danger/50"
                  style={{ top: nowTop as number }}
                  aria-hidden
                />
              )}
              {(byDoctor.get(doctor.id) ?? [])
                .filter((a) => a.status !== 'cancelled')
                .map((a) => (
                  <AppointmentBlock
                    key={a.id}
                    appointment={a}
                    window={win}
                    active={hover?.appt.id === a.id}
                    onShow={(rect) => setHover({ appt: a, rect })}
                    onHide={() => setHover(null)}
                  />
                ))}
            </div>
          </div>
        ))}
      </div>

      {hover && createPortal(<HoverCard appt={hover.appt} rect={hover.rect} />, document.body)}
    </div>
  )
}

function AppointmentBlock({
  appointment,
  window,
  active,
  onShow,
  onHide,
}: {
  appointment: Appointment
  window: DayWindow
  active: boolean
  onShow: (rect: DOMRect) => void
  onHide: () => void
}) {
  const { top, height } = blockGeometry(
    appointment.scheduled_start,
    appointment.scheduled_end,
    window,
  )
  const tone = statusTone(appointment.status)
  const locked = appointment.status === 'in_progress'

  const toneRing: Record<string, string> = {
    info: 'border-info/30 bg-info/10 hover:bg-info/15',
    success: 'border-success/40 bg-success/10 hover:bg-success/15',
    warning: 'border-warning/40 bg-warning/10 hover:bg-warning/15',
    danger: 'border-danger/40 bg-danger/10 hover:bg-danger/15',
    neutral: 'border-hairline bg-canvas hover:bg-hairline/40',
  }

  return (
    <button
      type="button"
      onMouseEnter={(e) => onShow(e.currentTarget.getBoundingClientRect())}
      onMouseLeave={onHide}
      onFocus={(e) => onShow(e.currentTarget.getBoundingClientRect())}
      onBlur={onHide}
      // Touch/pen: tap toggles the detail card (these inputs don't hover, and
      // iOS doesn't focus buttons on tap). preventDefault suppresses the synthetic
      // mouse/focus events so the hover and keyboard paths don't double-fire.
      onPointerDown={(e) => {
        if (e.pointerType === 'touch' || e.pointerType === 'pen') {
          e.preventDefault()
          if (active) onHide()
          else onShow(e.currentTarget.getBoundingClientRect())
        }
      }}
      aria-describedby={active ? `appt-desc-${appointment.id}` : undefined}
      className={`absolute inset-x-1 overflow-hidden rounded-control border p-2 text-left outline-none transition-[background-color,box-shadow] duration-150 animate-scale-in focus-visible:ring-2 focus-visible:ring-brand/50 ${
        toneRing[tone]
      } ${locked ? 'shadow-glow-success' : ''}`}
      style={{ top, height: Math.max(height, 22) }}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="truncate text-xs font-semibold text-ink">{appointment.patient.name}</span>
        {locked && (
          <Lock size={12} className="shrink-0 text-success" aria-label="In progress — protected" />
        )}
      </div>
      <div className="truncate text-[11px] tabular-nums text-slate">
        {formatTime(appointment.scheduled_start)}–{formatTime(appointment.scheduled_end)}
      </div>
    </button>
  )
}

function HoverCard({ appt, rect }: { appt: Appointment; rect: DOMRect }) {
  const width = 232
  const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8)
  const below = rect.bottom + 8
  const above = rect.top - 8
  const openBelow = below + 150 < window.innerHeight
  const style: React.CSSProperties = openBelow
    ? { left, top: below }
    : { left, top: above, transform: 'translateY(-100%)' }

  return (
    <div
      id={`appt-desc-${appt.id}`}
      style={{ ...style, width }}
      className="pointer-events-none fixed z-[90] rounded-card border border-hairline bg-elevated p-3 shadow-lg animate-fade-in"
      role="tooltip"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-medium text-ink">{appt.patient.name}</span>
        <StatusBadge tone={statusTone(appt.status)}>{statusLabel(appt.status)}</StatusBadge>
      </div>
      <p className="mt-0.5 font-mono text-xs tabular-nums text-muted">{appt.patient.mrn}</p>
      <dl className="mt-2 flex flex-col gap-1 text-xs">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Type</dt>
          <dd className="truncate text-slate">{appt.type.name}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Time</dt>
          <dd className="tabular-nums text-slate">
            {formatTime(appt.scheduled_start)}–{formatTime(appt.scheduled_end)}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Doctor</dt>
          <dd className="truncate text-slate">{appt.doctor.name}</dd>
        </div>
      </dl>
    </div>
  )
}
