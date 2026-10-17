import { useState } from 'react'

import { Button } from '../../components/Button'
import { Modal } from '../../components/Modal'
import { Select } from '../../components/Select'
import { Spinner } from '../../components/states'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../lib/api'
import { usePatients } from '../patients/api'
import { useAppointmentTypes, useBookAppointment, useDoctors, useSlots } from './api'
import { formatTime } from './timeline'

interface BookingDialogProps {
  date: string
  defaultDoctorId?: number
  onClose: () => void
  onBooked: () => void
}

/** Modal booking flow: patient + doctor + type -> pick a valid open slot -> confirm. */
export function BookingDialog({ date, defaultDoctorId, onClose, onBooked }: BookingDialogProps) {
  const doctors = useDoctors()
  const types = useAppointmentTypes()
  const patients = usePatients('')

  const [patientId, setPatientId] = useState<number | null>(null)
  const [doctorId, setDoctorId] = useState<number | null>(defaultDoctorId ?? null)
  const [typeId, setTypeId] = useState<number | null>(null)
  const [start, setStart] = useState<string | null>(null)

  const slots = useSlots(doctorId, typeId, date)
  const book = useBookAppointment()
  const { toast } = useToast()

  const canSubmit = patientId != null && doctorId != null && typeId != null && start != null

  async function submit() {
    if (patientId == null || doctorId == null || typeId == null || start == null) return
    try {
      await book.mutateAsync({
        patient_id: patientId,
        doctor_id: doctorId,
        type_id: typeId,
        scheduled_start: start,
      })
      toast({ tone: 'success', title: 'Appointment booked', description: formatTime(start) })
      onBooked()
      onClose()
    } catch {
      /* surfaced below via book.error */
    }
  }

  const errorMessage =
    book.error instanceof ApiError ? book.error.message : book.error ? 'Booking failed.' : null

  return (
    <Modal
      title="Book appointment"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!canSubmit} loading={book.isPending}>
            Confirm booking
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Select
          label="Patient"
          name="booking-patient"
          value={patientId ?? ''}
          onChange={(e) => setPatientId(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="" disabled>
            Select patient
          </option>
          {(patients.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.mrn})
            </option>
          ))}
        </Select>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            label="Doctor"
            name="booking-doctor"
            value={doctorId ?? ''}
            onChange={(e) => {
              setDoctorId(e.target.value ? Number(e.target.value) : null)
              setStart(null)
            }}
          >
            <option value="" disabled>
              Select doctor
            </option>
            {(doctors.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
          <Select
            label="Type"
            name="booking-type"
            value={typeId ?? ''}
            onChange={(e) => {
              setTypeId(e.target.value ? Number(e.target.value) : null)
              setStart(null)
            }}
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
        </div>

        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink">Available slots</span>
          {doctorId == null || typeId == null ? (
            <p className="text-sm text-muted">Choose a doctor and type to see open slots.</p>
          ) : slots.isLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted">
              <Spinner /> Finding open slots…
            </p>
          ) : (slots.data ?? []).length === 0 ? (
            <p className="text-sm text-warning">No open slots for this doctor on this day.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {slots.data!.map((s) => (
                <button
                  key={s.start}
                  onClick={() => setStart(s.start)}
                  aria-pressed={start === s.start}
                  className={`rounded-control px-3 py-1.5 text-sm font-medium tabular-nums ring-1 ring-inset transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/50 ${
                    start === s.start
                      ? 'bg-brand text-surface ring-brand'
                      : 'bg-canvas text-slate ring-hairline hover:ring-brand/40'
                  }`}
                >
                  {formatTime(s.start)}
                </button>
              ))}
            </div>
          )}
        </div>

        {errorMessage && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage}
          </p>
        )}
      </div>
    </Modal>
  )
}
