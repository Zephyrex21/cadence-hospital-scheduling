import { useState, type FormEvent } from 'react'

import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../lib/api'
import type { StaffEntry } from '../../types'
import { useUpdateStaffProfile } from './api'
import { FormSection, RowList } from './fields'
import { staffPayload, toStaffDraft, type StaffDraft, type StaffSection } from './payload'

const SHIFTS = (
  <>
    <option value="">—</option>
    <option value="day">Day</option>
    <option value="night">Night</option>
    <option value="rotating">Rotating</option>
  </>
)

/** Edit a staff profile. `sections` is what the current user may write (server-enforced too). */
export function StaffProfileForm({
  entry,
  sections,
  onDone,
}: {
  entry: StaffEntry
  sections: readonly StaffSection[]
  onDone: () => void
}) {
  const role = entry.user.role
  const update = useUpdateStaffProfile(entry.user.id)
  const { toast } = useToast()
  const [draft, setDraft] = useState<StaffDraft>(() => toStaffDraft(role, entry.profile))
  const [error, setError] = useState<string | null>(null)
  const has = (s: StaffSection) => sections.includes(s)

  const set = <K extends keyof StaffDraft>(key: K, value: StaffDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))
  const text = (key: Exclude<keyof StaffDraft, 'qualifications' | 'certifications'>) => ({
    name: key,
    value: draft[key],
    onChange: (e: { target: { value: string } }) => set(key, e.target.value),
  })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await update.mutateAsync(staffPayload(draft, sections))
      toast({ tone: 'success', title: 'Profile saved', description: entry.user.name })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the profile.')
    }
  }

  const qualifications = (
    <RowList
      rows={draft.qualifications}
      onChange={(rows) => set('qualifications', rows)}
      blank={{ degree: '', institution: '', year: '' }}
      addLabel="Add qualification"
      render={(row, i, up) => (
        <>
          <Input label="Degree" name={`q-${i}-degree`} value={row.degree}
            onChange={(e) => up({ degree: e.target.value })} />
          <Input label="Institution" name={`q-${i}-institution`} value={row.institution}
            onChange={(e) => up({ institution: e.target.value })} />
          <Input label="Year" name={`q-${i}-year`} inputMode="numeric" value={row.year}
            onChange={(e) => up({ year: e.target.value })} />
        </>
      )}
    />
  )
  const registration = (
    <div className="grid gap-3 sm:grid-cols-2">
      <Input label="Registration council" {...text('reg_council')} />
      <Input label="Registration number" {...text('reg_number')} />
    </div>
  )

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {(has('employee_id') || has('department') || has('employment')) && (
        <FormSection title="Work">
          <div className="grid gap-3 sm:grid-cols-2">
            {has('employee_id') && <Input label="Employee ID" {...text('employee_id')} />}
            {has('department') && <Input label="Department" {...text('department')} />}
            {has('employment') && (
              <>
                <Select label="Status" {...text('status')}
                  onChange={(e) => set('status', e.target.value)}>
                  <option value="active">Active</option>
                  <option value="on_leave">On leave</option>
                  <option value="inactive">Inactive</option>
                </Select>
                <Input label="Joined on" type="date" {...text('joined_on')} />
              </>
            )}
          </div>
        </FormSection>
      )}

      {(has('contact') || has('languages')) && (
        <FormSection title="Contact & languages">
          <div className="grid gap-3 sm:grid-cols-2">
            {has('contact') && (
              <>
                <Input label="Phone" inputMode="tel" {...text('phone')} />
                <Input label="Alternate phone" inputMode="tel" {...text('alt_phone')} />
              </>
            )}
            {has('languages') && (
              <Input label="Languages" hint="Language codes, e.g. en, hi, pa" {...text('languages')} />
            )}
          </div>
        </FormSection>
      )}

      {has('doctor') && (
        <FormSection title="Doctor details">
          {registration}
          {qualifications}
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Sub-specialties" hint="Comma-separated" {...text('sub_specialties')} />
            <Input label="Experience (years)" inputMode="numeric" {...text('experience_years')} />
            <Input label="Consultation fee (₹)" inputMode="numeric" {...text('fee')} />
          </div>
          <Textarea label="About" rows={3} maxLength={600} {...text('bio')} />
        </FormSection>
      )}

      {has('nurse') && (
        <FormSection title="Nurse details">
          {registration}
          {qualifications}
          <p className="text-[13px] font-medium text-slate">Certifications</p>
          <RowList
            rows={draft.certifications}
            onChange={(rows) => set('certifications', rows)}
            blank={{ name: '', expires_on: '' }}
            addLabel="Add certification"
            render={(row, i, up) => (
              <>
                <Input label="Name" name={`c-${i}-name`} value={row.name}
                  onChange={(e) => up({ name: e.target.value })} />
                <Input label="Expires on" type="date" name={`c-${i}-exp`} value={row.expires_on}
                  onChange={(e) => up({ expires_on: e.target.value })} />
              </>
            )}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Ward" {...text('ward')} />
            <Select label="Shift pattern" {...text('shift_pattern')}
              onChange={(e) => set('shift_pattern', e.target.value)}>
              {SHIFTS}
            </Select>
          </div>
        </FormSection>
      )}

      {has('reception') && (
        <FormSection title="Reception details">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Counter" {...text('counter')} />
            <Select label="Shift pattern" {...text('shift_pattern')}
              onChange={(e) => set('shift_pattern', e.target.value)}>
              {SHIFTS}
            </Select>
          </div>
          <Input label="Training" hint="Comma-separated" {...text('training')} />
        </FormSection>
      )}

      {error ? (
        <p role="alert" className="rounded-control bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-3">
        <Button type="button" variant="secondary" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" loading={update.isPending}>
          Save profile
        </Button>
      </div>
    </form>
  )
}
