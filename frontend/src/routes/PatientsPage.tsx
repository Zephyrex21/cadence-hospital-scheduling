import { useEffect, useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import {
  Drop,
  MagnifyingGlass,
  MapPin,
  Notepad,
  Phone,
  Plus,
  ShieldCheck,
} from '../components/icons'
import { IllustrationEmptyList } from '../components/illustrations'
import { Modal } from '../components/Modal'
import { TableSkeleton } from '../components/Skeleton'
import { EmptyState, ErrorState } from '../components/states'
import { useAuth } from '../features/auth/AuthContext'
import { canRegisterPatients } from '../features/auth/roles'
import { usePatients } from '../features/patients/api'
import { formatAge, formatDob, initials, sexLabel } from '../features/patients/format'
import { PatientForm } from '../features/patients/PatientForm'
import type { Patient } from '../types'

export function PatientsPage() {
  const { user } = useAuth()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [selected, setSelected] = useState<Patient | null>(null)
  const patients = usePatients(query)
  const canRegister = user ? canRegisterPatients(user.role) : false
  const rows = patients.data ?? []

  // Debounce the server search so typing doesn't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setQuery(text.trim()), 250)
    return () => clearTimeout(t)
  }, [text])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="font-display text-title font-semibold text-ink">Patients</h2>
          <p className="mt-1 text-sm text-muted">
            Search, register and review patient records
            {patients.data ? ` · ${patients.data.length} shown` : ''}.
          </p>
        </div>
        {canRegister ? (
          <Button onClick={() => setShowForm(true)}>
            <Plus size={16} weight="bold" aria-hidden />
            Register patient
          </Button>
        ) : null}
      </div>

      <Card>
        <div className="border-b border-hairline p-4">
          <div className="relative max-w-md">
            <MagnifyingGlass
              size={16}
              aria-hidden
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              type="search"
              placeholder="Search by name, MRN, phone or city…"
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label="Search patients"
              className="h-11 w-full rounded-pill border border-hairline bg-canvas/60 pl-10 pr-4 text-sm text-ink outline-none transition duration-200 placeholder:text-muted/80 focus:border-brand focus:bg-surface focus:ring-4 focus:ring-brand/15"
            />
          </div>
        </div>

        {patients.isLoading ? (
          <TableSkeleton cols={4} />
        ) : patients.isError ? (
          <ErrorState label="Could not load patients." onRetry={() => patients.refetch()} />
        ) : rows.length > 0 ? (
          <div className="max-h-[68vh] overflow-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surface/95 backdrop-blur">
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th className="px-5 py-3 font-medium">Patient</th>
                  <th className="px-4 py-3 font-medium">Age · Sex</th>
                  <th className="hidden px-4 py-3 font-medium md:table-cell">Mobile</th>
                  <th className="hidden px-4 py-3 font-medium lg:table-cell">City</th>
                  <th className="px-4 py-3 font-medium">Blood</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.id}
                    tabIndex={0}
                    onClick={() => setSelected(p)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelected(p)
                      }
                    }}
                    aria-label={`View ${p.name}`}
                    className="cursor-pointer border-b border-hairline/60 outline-none transition-colors last:border-0 hover:bg-brand/[0.04] focus-visible:bg-brand/[0.06]"
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <span
                          aria-hidden
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-pill bg-brand/10 text-xs font-semibold text-brand"
                        >
                          {initials(p.name)}
                        </span>
                        <div className="min-w-0">
                          <p className="truncate font-medium text-ink">{p.name}</p>
                          <p className="font-mono text-xs tabular-nums text-muted">{p.mrn}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate">
                      <span className="tabular-nums">{formatAge(p.date_of_birth)}</span>
                      <span className="text-muted"> · {sexLabel(p.sex)}</span>
                    </td>
                    <td className="hidden px-4 py-3 tabular-nums text-slate md:table-cell">
                      {p.contact || <span className="text-muted">—</span>}
                    </td>
                    <td className="hidden px-4 py-3 text-slate lg:table-cell">
                      {p.city || <span className="text-muted">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      {p.blood_group ? (
                        <span className="rounded-pill bg-danger/10 px-2.5 py-0.5 text-xs font-semibold text-danger">
                          {p.blood_group}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={<IllustrationEmptyList />}
            title={query ? 'No patients match your search.' : 'No patients registered yet.'}
            hint={query ? undefined : 'Register a patient to get started.'}
          />
        )}
      </Card>

      {showForm && canRegister ? (
        <Modal title="Register patient" onClose={() => setShowForm(false)}>
          <PatientForm onCreated={() => setShowForm(false)} />
        </Modal>
      ) : null}

      {selected ? <PatientDetails patient={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  )
}

function PatientDetails({ patient: p, onClose }: { patient: Patient; onClose: () => void }) {
  return (
    <Modal
      title={p.name}
      onClose={onClose}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex h-12 w-12 items-center justify-center rounded-pill bg-brand-gradient text-sm font-semibold text-on-brand"
          >
            {initials(p.name)}
          </span>
          <div>
            <p className="font-mono text-sm tabular-nums text-slate">{p.mrn}</p>
            <p className="text-sm text-muted">
              {formatAge(p.date_of_birth)} · {sexLabel(p.sex)} · born {formatDob(p.date_of_birth)}
            </p>
          </div>
        </div>
        <dl className="grid gap-3 sm:grid-cols-2">
          <Detail icon={Phone} label="Mobile / email" value={p.contact} />
          <Detail icon={MapPin} label="City" value={p.city} />
          <Detail icon={Drop} label="Blood group" value={p.blood_group} />
          <Detail icon={ShieldCheck} label="Emergency contact" value={p.emergency_contact} />
        </dl>
        <Detail icon={Notepad} label="Notes" value={p.notes} wide />
      </div>
    </Modal>
  )
}

function Detail({
  icon: DetailIcon,
  label,
  value,
  wide,
}: {
  icon: typeof Phone
  label: string
  value?: string | null
  wide?: boolean
}) {
  return (
    <div
      className={`flex items-start gap-3 rounded-control bg-canvas/70 px-3.5 py-3 ${wide ? '' : ''}`}
    >
      <DetailIcon size={18} weight="duotone" className="mt-0.5 shrink-0 text-brand" aria-hidden />
      <div className="min-w-0">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="mt-0.5 break-words text-sm text-ink">
          {value || <span className="text-muted">Not recorded</span>}
        </dd>
      </div>
    </div>
  )
}
