import { Search } from 'lucide-react'
import { useState } from 'react'

import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { IllustrationEmptyList } from '../components/illustrations'
import { TableSkeleton } from '../components/Skeleton'
import { EmptyState, ErrorState } from '../components/states'
import { useAuth } from '../features/auth/AuthContext'
import { canRegisterPatients } from '../features/auth/roles'
import { usePatients } from '../features/patients/api'
import { PatientForm } from '../features/patients/PatientForm'

export function PatientsPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [showForm, setShowForm] = useState(false)
  const patients = usePatients(query)
  const canRegister = user ? canRegisterPatients(user.role) : false
  const rows = patients.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-title font-semibold text-ink">Patients</h2>
          <p className="text-sm text-muted">Search and register synthetic patient records.</p>
        </div>
        {canRegister ? (
          <Button variant={showForm ? 'secondary' : 'primary'} onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Close' : 'Register patient'}
          </Button>
        ) : null}
      </div>

      {showForm && canRegister ? (
        <Card padded>
          <h3 className="mb-4 font-display text-base font-semibold text-ink">New patient</h3>
          <div className="max-w-md">
            <PatientForm onCreated={() => setShowForm(false)} />
          </div>
        </Card>
      ) : null}

      <Card>
        <div className="border-b border-hairline p-4">
          <div className="relative max-w-sm">
            <Search
              size={16}
              aria-hidden
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              type="search"
              placeholder="Search by name or MRN…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search patients"
              className="h-10 w-full rounded-control border border-hairline bg-surface pl-9 pr-3 text-sm text-ink shadow-xs outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30"
            />
          </div>
        </div>

        {patients.isLoading ? (
          <TableSkeleton cols={4} />
        ) : patients.isError ? (
          <ErrorState label="Could not load patients." onRetry={() => patients.refetch()} />
        ) : rows.length > 0 ? (
          <div className="max-h-[60vh] overflow-auto">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead className="sticky top-0 z-10 bg-surface">
                <tr className="border-b border-hairline text-xs uppercase tracking-wide text-muted">
                  <th className="px-4 py-3 font-medium">MRN</th>
                  <th className="px-4 py-3 font-medium">Name</th>
                  <th className="px-4 py-3 font-medium">Date of birth</th>
                  <th className="px-4 py-3 font-medium">Sex</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.id}
                    className="border-b border-hairline/60 transition-colors last:border-0 hover:bg-canvas"
                  >
                    <td className="px-4 py-3 font-mono tabular-nums text-slate">{p.mrn}</td>
                    <td className="px-4 py-3 font-medium text-ink">{p.name}</td>
                    <td className="px-4 py-3 tabular-nums text-slate">{p.date_of_birth}</td>
                    <td className="px-4 py-3 capitalize text-slate">{p.sex}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            icon={<IllustrationEmptyList />}
            title={query ? 'No patients match your search.' : 'No patients registered yet.'}
            hint={query ? undefined : 'Register a synthetic patient to get started.'}
          />
        )}
      </Card>
    </div>
  )
}
