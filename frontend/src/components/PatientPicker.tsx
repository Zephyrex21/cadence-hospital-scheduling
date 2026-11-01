import { useEffect, useState } from 'react'

import { usePatients } from '../features/patients/api'
import type { Patient } from '../types'
import { Input } from './Input'
import { Select } from './Select'

const PAGE = 50 // the API returns at most this many matches per query

interface PatientPickerProps {
  name: string
  value: number | null
  onChange: (id: number | null) => void
}

/**
 * Patient selector with server-side search. A plain dropdown of "the first 50
 * patients" makes everyone beyond that unreachable, so the list is filtered by
 * name / MRN on the server and the chosen patient stays selectable while the
 * search text changes.
 */
export function PatientPicker({ name, value, onChange }: PatientPickerProps) {
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Patient | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setQuery(text.trim()), 250)
    return () => clearTimeout(t)
  }, [text])

  const patients = usePatients(query)
  const found = patients.data ?? []
  const options =
    selected && !found.some((p) => p.id === selected.id) ? [selected, ...found] : found

  return (
    <div className="flex flex-col gap-2">
      <Input
        label="Search by name or MRN"
        labelHidden
        name={`${name}-search`}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Search by name, MRN, phone or city"
        autoComplete="off"
      />
      <Select
        label="Patient"
        name={name}
        value={value ?? ''}
        onChange={(e) => {
          const id = e.target.value ? Number(e.target.value) : null
          setSelected(options.find((p) => p.id === id) ?? null)
          onChange(id)
        }}
      >
        <option value="" disabled>
          Select patient
        </option>
        {options.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} ({p.mrn})
          </option>
        ))}
      </Select>
      {found.length >= PAGE && (
        <p className="text-xs text-muted">
          Showing the first {PAGE} matches — keep typing to narrow the list.
        </p>
      )}
      {patients.isError && (
        <p role="alert" className="text-xs text-danger">
          Could not load patients.
        </p>
      )}
    </div>
  )
}
