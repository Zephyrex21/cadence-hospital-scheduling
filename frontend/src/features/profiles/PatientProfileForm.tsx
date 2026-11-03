import { useState, type FormEvent } from 'react'

import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../lib/api'
import type { Patient, PatientProfile } from '../../types'
import { BLOOD_GROUPS } from '../patients/schema'
import { useUpdatePatientProfile } from './api'
import { FormSection, INSURANCE_SCHEMES, LANGUAGES, RowList } from './fields'
import {
  patientPayload,
  toPatientDraft,
  type PatientDraft,
  type PatientSection,
} from './payload'

/** Edit the profile sections the current role is allowed to write. */
export function PatientProfileForm({
  patient,
  profile,
  sections,
  onDone,
}: {
  patient: Patient
  profile: PatientProfile | null
  sections: readonly PatientSection[]
  onDone: () => void
}) {
  const update = useUpdatePatientProfile(patient.id)
  const { toast } = useToast()
  const [draft, setDraft] = useState<PatientDraft>(() => toPatientDraft(profile))
  const [error, setError] = useState<string | null>(null)
  const has = (s: PatientSection) => sections.includes(s)

  const set = <K extends keyof PatientDraft>(key: K, value: PatientDraft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }))
  const text = (key: Exclude<keyof PatientDraft, 'emergency' | 'allergies' | 'medications'>) => ({
    name: key,
    value: draft[key],
    onChange: (e: { target: { value: string } }) => set(key, e.target.value),
  })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await update.mutateAsync(patientPayload(draft, sections))
      toast({ tone: 'success', title: 'Profile saved', description: patient.name })
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the profile.')
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {has('contact') && (
        <FormSection title="Contact">
          <div className="grid gap-3 sm:grid-cols-3">
            <Input label="Mobile" inputMode="tel" {...text('phone')} />
            <Input label="Alternate phone" inputMode="tel" {...text('alt_phone')} />
            <Input label="Email" type="email" {...text('email')} />
          </div>
        </FormSection>
      )}

      {has('address') && (
        <FormSection title="Address">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Address line 1" {...text('line1')} />
            <Input label="Address line 2" {...text('line2')} />
            <Input label="City" {...text('city')} />
            <Input label="State" {...text('state')} />
            <Input
              label="PIN code"
              inputMode="numeric"
              maxLength={6}
              hint="6 digits"
              {...text('pin_code')}
            />
          </div>
        </FormSection>
      )}

      {has('demographics') && (
        <FormSection title="Language & occupation">
          <div className="grid gap-3 sm:grid-cols-2">
            <Select
              label="Preferred language"
              {...text('preferred_language')}
              onChange={(e) => set('preferred_language', e.target.value)}
            >
              <option value="">Not specified</option>
              {Object.entries(LANGUAGES).map(([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </Select>
            <Input label="Occupation" {...text('occupation')} />
          </div>
        </FormSection>
      )}

      {has('emergency_contacts') && (
        <FormSection title="Emergency contacts">
          <RowList
            rows={draft.emergency}
            onChange={(rows) => set('emergency', rows)}
            blank={{ name: '', relation: '', phone: '', is_primary: false }}
            addLabel="Add contact"
            render={(row, i, up) => (
              <>
                <Input
                  label="Name"
                  name={`ec-${i}-name`}
                  value={row.name}
                  onChange={(e) => up({ name: e.target.value })}
                />
                <Input
                  label="Relation"
                  name={`ec-${i}-relation`}
                  value={row.relation}
                  onChange={(e) => up({ relation: e.target.value })}
                />
                <Input
                  label="Phone"
                  name={`ec-${i}-phone`}
                  value={row.phone}
                  onChange={(e) => up({ phone: e.target.value })}
                />
                <label className="flex items-center gap-2 text-sm text-slate sm:col-span-3">
                  <input
                    type="radio"
                    name="ec-primary"
                    checked={row.is_primary}
                    onChange={() =>
                      set(
                        'emergency',
                        draft.emergency.map((c, j) => ({ ...c, is_primary: j === i })),
                      )
                    }
                  />
                  Primary contact
                </label>
              </>
            )}
          />
        </FormSection>
      )}

      {has('medical') && (
        <FormSection title="Medical (reported — not a clinical record)">
          <Select
            label="Blood group"
            {...text('blood_group')}
            onChange={(e) => set('blood_group', e.target.value)}
          >
            <option value="">Unknown</option>
            {BLOOD_GROUPS.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </Select>
          <p className="text-[13px] font-medium text-slate">Allergies</p>
          <RowList
            rows={draft.allergies}
            onChange={(rows) => set('allergies', rows)}
            blank={{ substance: '', reaction: '', severity: '' }}
            addLabel="Add allergy"
            render={(row, i, up) => (
              <>
                <Input
                  label="Substance"
                  name={`al-${i}-substance`}
                  value={row.substance}
                  onChange={(e) => up({ substance: e.target.value })}
                />
                <Input
                  label="Reaction"
                  name={`al-${i}-reaction`}
                  value={row.reaction}
                  onChange={(e) => up({ reaction: e.target.value })}
                />
                <Select
                  label="Severity"
                  name={`al-${i}-severity`}
                  value={row.severity}
                  onChange={(e) => up({ severity: e.target.value })}
                >
                  <option value="">—</option>
                  <option value="mild">Mild</option>
                  <option value="moderate">Moderate</option>
                  <option value="severe">Severe</option>
                </Select>
              </>
            )}
          />
          <Input
            label="Conditions"
            hint="Comma-separated, e.g. Asthma, Hypertension"
            {...text('conditions')}
          />
          <p className="text-[13px] font-medium text-slate">Medications</p>
          <RowList
            rows={draft.medications}
            onChange={(rows) => set('medications', rows)}
            blank={{ name: '', dose: '', frequency: '' }}
            addLabel="Add medication"
            render={(row, i, up) => (
              <>
                <Input
                  label="Name"
                  name={`med-${i}-name`}
                  value={row.name}
                  onChange={(e) => up({ name: e.target.value })}
                />
                <Input
                  label="Dose"
                  name={`med-${i}-dose`}
                  value={row.dose}
                  onChange={(e) => up({ dose: e.target.value })}
                />
                <Input
                  label="Frequency"
                  name={`med-${i}-frequency`}
                  value={row.frequency}
                  onChange={(e) => up({ frequency: e.target.value })}
                />
              </>
            )}
          />
        </FormSection>
      )}

      {has('insurance') && (
        <FormSection title="Insurance & identifiers">
          <div className="grid gap-3 sm:grid-cols-3">
            <Select
              label="Scheme"
              {...text('scheme')}
              onChange={(e) => set('scheme', e.target.value)}
            >
              <option value="">Not specified</option>
              {Object.entries(INSURANCE_SCHEMES).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
            <Input label="Provider" {...text('provider')} />
            <Input label="Policy no." {...text('policy_no')} />
          </div>
          {has('identifiers') && (
            <Input label="ABHA ID" hint="14 digits, optional" {...text('abha_id')} />
          )}
        </FormSection>
      )}

      {has('notes') && (
        <Textarea label="Notes" rows={3} maxLength={1000} {...text('notes')} />
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
