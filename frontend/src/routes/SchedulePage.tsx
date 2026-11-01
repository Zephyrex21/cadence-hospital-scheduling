import { ChevronLeft, ChevronRight } from '../components/icons'
import { useEffect, useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { EmptyState, ErrorState, LoadingState } from '../components/states'
import { useAuth } from '../features/auth/AuthContext'
import { canBookAppointments } from '../features/auth/roles'
import { useDoctors, useSchedule } from '../features/schedule/api'
import { BookingDialog } from '../features/schedule/BookingDialog'
import { ScheduleTimeline } from '../features/schedule/ScheduleTimeline'
import { todayIso } from '../features/schedule/timeline'
import { addDays, formatDateLong } from '../lib/time'

const shiftDay = addDays

export function SchedulePage() {
  const { user } = useAuth()
  const [date, setDate] = useState(todayIso())
  const [booking, setBooking] = useState(false)

  const doctors = useDoctors()
  const schedule = useSchedule(date)
  const canBook = user ? canBookAppointments(user.role) : false
  const isToday = date === todayIso()

  // Keep the "now" line live on today's view (re-render every ~30s).
  const [nowTick, setNowTick] = useState(() => Date.now())
  useEffect(() => {
    if (!isToday) return
    const id = setInterval(() => setNowTick(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [isToday])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-title font-semibold text-ink">Schedule</h2>
          <p className="text-sm text-muted">
            Pre-booked appointments by doctor and time. In-progress consultations are protected.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-pill border border-hairline bg-surface p-0.5 shadow-xs">
            <button
              onClick={() => setDate(shiftDay(date, -1))}
              aria-label="Previous day"
              className="rounded-pill p-2 text-muted transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            >
              <ChevronLeft size={16} weight="bold" />
            </button>
            {/* A formatted label over a transparent native date input: Indian date
                format on screen, the platform's own date picker on click. */}
            <label className="relative cursor-pointer rounded-pill px-3.5 py-1.5 text-sm font-medium tabular-nums text-ink transition-colors hover:bg-ink/5 focus-within:ring-2 focus-within:ring-brand/50">
              {formatDateLong(`${date}T12:00:00Z`)}
              <input
                type="date"
                value={date}
                onChange={(e) => e.target.value && setDate(e.target.value)}
                onClick={(e) => e.currentTarget.showPicker?.()}
                aria-label="Schedule date"
                className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
              />
            </label>
            <button
              onClick={() => setDate(shiftDay(date, 1))}
              aria-label="Next day"
              className="rounded-pill p-2 text-muted transition-colors hover:bg-ink/5 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50"
            >
              <ChevronRight size={16} weight="bold" />
            </button>
          </div>
          {!isToday && (
            <Button variant="ghost" size="sm" onClick={() => setDate(todayIso())}>
              Today
            </Button>
          )}
          {canBook && <Button onClick={() => setBooking(true)}>Book appointment</Button>}
        </div>
      </div>

      {doctors.isError || schedule.isError ? (
        <Card>
          <ErrorState
            label="Could not load the schedule."
            onRetry={() => {
              doctors.refetch()
              schedule.refetch()
            }}
          />
        </Card>
      ) : doctors.isLoading || schedule.isLoading ? (
        <Card>
          <LoadingState label="Loading schedule…" />
        </Card>
      ) : (doctors.data ?? []).length === 0 ? (
        <Card>
          <EmptyState title="No doctors are configured yet." />
        </Card>
      ) : (
        <ScheduleTimeline
          doctors={doctors.data!}
          appointments={schedule.data ?? []}
          nowIso={isToday ? new Date(nowTick).toISOString() : undefined}
        />
      )}

      {booking && (
        <BookingDialog
          date={date}
          onClose={() => setBooking(false)}
          onBooked={() => schedule.refetch()}
        />
      )}
    </div>
  )
}
