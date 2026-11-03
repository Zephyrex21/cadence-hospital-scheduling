import { useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Info } from '../components/icons'
import { IllustrationEmptyList } from '../components/illustrations'
import { Modal } from '../components/Modal'
import { TableSkeleton } from '../components/Skeleton'
import { EmptyState, ErrorState } from '../components/states'
import { useAuth } from '../features/auth/AuthContext'
import { ROLE_LABELS } from '../features/auth/roles'
import { initials } from '../features/patients/format'
import { useMongoStatus, useStaff } from '../features/profiles/api'
import { Chip, languageName } from '../features/profiles/fields'
import { staffSectionsFor } from '../features/profiles/payload'
import { StaffProfileForm } from '../features/profiles/StaffProfileForm'
import { StaffProfileView } from '../features/profiles/StaffProfileView'
import type { Role, StaffEntry } from '../types'

const GROUPS: { role: Role; title: string }[] = [
  { role: 'doctor', title: 'Doctors' },
  { role: 'triage_nurse', title: 'Nurses' },
  { role: 'receptionist', title: 'Reception' },
  { role: 'administrator', title: 'Administration' },
]

export function StaffPage() {
  const { user } = useAuth()
  const staff = useStaff()
  const store = useMongoStatus()
  const [selected, setSelected] = useState<number | null>(null)
  const [editing, setEditing] = useState(false)

  // Derive from the live list so a saved edit shows up immediately.
  const entry = staff.data?.find((s) => s.user.id === selected) ?? null
  const storeReady = !!store.data?.enabled && store.data.ok
  const canEdit =
    !!entry && !!user && storeReady && (user.role === 'administrator' || user.id === entry.user.id)

  function close() {
    setSelected(null)
    setEditing(false)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="font-display text-title font-semibold text-ink">Staff</h2>
        <p className="mt-1 text-sm text-muted">
          Doctors, nurses and front-desk staff
          {staff.data ? ` · ${staff.data.length} people` : ''}.
        </p>
      </div>

      {store.data && !storeReady ? (
        <div className="flex items-start gap-3 rounded-control border border-hairline bg-surface px-4 py-3 text-sm text-slate">
          <Info size={18} weight="duotone" className="mt-0.5 shrink-0 text-brand" aria-hidden />
          <p>
            {store.data.enabled
              ? 'The detailed profile store is temporarily unreachable, so profiles are hidden for now.'
              : 'Detailed profiles are switched off. Set CADENCE_MONGODB_URI on the API to enable them.'}
          </p>
        </div>
      ) : null}

      {staff.isLoading ? (
        <Card>
          <TableSkeleton cols={4} />
        </Card>
      ) : staff.isError ? (
        <ErrorState label="Could not load staff." onRetry={() => staff.refetch()} />
      ) : (staff.data ?? []).length === 0 ? (
        <EmptyState icon={<IllustrationEmptyList />} title="No staff found." />
      ) : (
        GROUPS.map(({ role, title }) => {
          const members = (staff.data ?? []).filter((s) => s.user.role === role)
          if (members.length === 0) return null
          return (
            <section key={role} aria-label={title} className="flex flex-col gap-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</h3>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {members.map((m) => (
                  <StaffCard key={m.user.id} entry={m} onOpen={() => setSelected(m.user.id)} />
                ))}
              </div>
            </section>
          )
        })
      )}

      {entry && !editing ? (
        <Modal
          title={entry.user.name}
          onClose={close}
          footer={
            <>
              {canEdit ? <Button onClick={() => setEditing(true)}>Edit profile</Button> : null}
              <Button variant="secondary" onClick={close}>
                Close
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted">
              {ROLE_LABELS[entry.user.role]} · {entry.user.email}
              {entry.user.specialty ? ` · ${entry.user.specialty}` : ''}
            </p>
            <StaffProfileView entry={entry} />
          </div>
        </Modal>
      ) : null}

      {entry && editing && user ? (
        <Modal title={`Edit profile · ${entry.user.name}`} onClose={() => setEditing(false)}>
          <StaffProfileForm
            entry={entry}
            sections={staffSectionsFor(user.role === 'administrator', entry.user.role)}
            onDone={() => setEditing(false)}
          />
        </Modal>
      ) : null}
    </div>
  )
}

function StaffCard({ entry, onOpen }: { entry: StaffEntry; onOpen: () => void }) {
  const { user: u, profile: p } = entry
  const doctor = p?.doctor
  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={`View ${u.name}`}
      className="flex flex-col gap-3 rounded-card border border-hairline bg-surface p-4 text-left shadow-xs outline-none transition hover:border-brand/40 hover:shadow-md focus-visible:ring-4 focus-visible:ring-brand/15"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-pill bg-brand/10 text-sm font-semibold text-brand"
        >
          {initials(u.name)}
        </span>
        <div className="min-w-0">
          <p className="truncate font-medium text-ink">{u.name}</p>
          <p className="truncate text-xs text-muted">
            {p?.department ?? ROLE_LABELS[u.role]}
            {u.specialty ? ` · ${u.specialty}` : ''}
          </p>
        </div>
      </div>
      {p ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {p.employee_id ? <Chip tone="muted">{p.employee_id}</Chip> : null}
          {doctor?.experience_years != null ? <Chip>{doctor.experience_years} yrs</Chip> : null}
          {doctor?.registration?.number ? <Chip tone="muted">{doctor.registration.number}</Chip> : null}
          {(p.languages ?? []).slice(0, 3).map((l) => (
            <Chip key={l} tone="muted">
              {languageName(l)}
            </Chip>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted">No profile details yet</p>
      )}
      {p?.contact?.phone ? (
        <p className="text-xs tabular-nums text-slate">{p.contact.phone}</p>
      ) : null}
    </button>
  )
}
