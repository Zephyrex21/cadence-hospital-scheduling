import { ChevronLeft, ChevronRight } from 'lucide-react'
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

function shiftDay(iso: string, delta: number): string {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + delta)
  return d.toISOString().slice(0, 10)
}

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
          <div className="flex items-center rounded-control border border-hairline bg-surface shadow-xs">
            <button
              onClick={() => setDate(shiftDay(date, -1))}
              aria-label="Previous day"
              className="rounded-l-control px-2 py-2 text-muted transition-colors hover:bg-canvas hover:text-ink"
            >
              <ChevronLeft size={16} />
            </button>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              aria-label="Schedule date"
              className="border-x border-hairline bg-transparent px-3 py-1.5 text-sm tabular-nums text-ink outline-none focus:ring-2 focus:ring-brand/30"
            />
            <button
              onClick={() => setDate(shiftDay(date, 1))}
              aria-label="Next day"
              className="rounded-r-control px-2 py-2 text-muted transition-colors hover:bg-canvas hover:text-ink"
            >
              <ChevronRight size={16} />
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
