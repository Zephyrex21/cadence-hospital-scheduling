import type { PatientProfile } from '../../types'
import { Block, Chip, INSURANCE_SCHEMES, NotRecorded, languageName } from './fields'

const SEVERITY_TONE = { mild: 'muted', moderate: 'brand', severe: 'danger' } as const

function formatAddress(a: PatientProfile['address']): string {
  if (!a) return ''
  const cityLine = [a.city, a.state].filter(Boolean).join(', ')
  return [a.line1, a.line2, [cityLine, a.pin_code].filter(Boolean).join(' – ')]
    .filter(Boolean)
    .join(', ')
}

/** Read-only view of a patient's MongoDB profile. */
export function PatientProfileView({
  profile: p,
  redacted = [],
}: {
  profile: PatientProfile
  redacted?: string[]
}) {
  const address = formatAddress(p.address)
  const medical = p.medical
  const noMedical =
    !medical?.blood_group &&
    !medical?.allergies?.length &&
    !medical?.conditions?.length &&
    !medical?.medications?.length

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Block title="Mobile">{p.contact?.phone || <NotRecorded />}</Block>
      <Block title="Email / alternate">
        {p.contact?.email || p.contact?.alt_phone ? (
          [p.contact?.email, p.contact?.alt_phone].filter(Boolean).join(' · ')
        ) : (
          <NotRecorded />
        )}
      </Block>
      <Block title="Address" wide>
        {address || <NotRecorded />}
      </Block>
      <Block title="Language · occupation">
        {p.demographics?.preferred_language || p.demographics?.occupation ? (
          [
            p.demographics?.preferred_language && languageName(p.demographics.preferred_language),
            p.demographics?.occupation,
          ]
            .filter(Boolean)
            .join(' · ')
        ) : (
          <NotRecorded />
        )}
      </Block>
      <Block title="Insurance">
        {p.insurance?.scheme && p.insurance.scheme !== 'none' ? (
          [INSURANCE_SCHEMES[p.insurance.scheme] ?? p.insurance.scheme, p.insurance.provider, p.insurance.policy_no]
            .filter(Boolean)
            .join(' · ')
        ) : (
          <NotRecorded />
        )}
      </Block>

      <Block title="Emergency contacts" wide>
        {p.emergency_contacts?.length ? (
          <ul className="flex flex-col gap-1">
            {p.emergency_contacts.map((c, i) => (
              <li key={i}>
                <span className="font-medium">{c.name}</span>
                {c.relation ? <span className="text-muted"> ({c.relation})</span> : null}
                {c.phone ? <span className="tabular-nums"> · {c.phone}</span> : null}
                {c.is_primary ? (
                  <span className="ml-2 align-middle">
                    <Chip>Primary</Chip>
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <NotRecorded />
        )}
      </Block>

      <Block title="Medical (reported — not a clinical record)" wide>
        {redacted.includes('medical') ? (
          <span className="text-muted">Restricted to clinical staff</span>
        ) : noMedical ? (
          <NotRecorded />
        ) : (
          <div className="flex flex-col gap-2.5">
            {medical?.blood_group ? (
              <p>
                <span className="text-muted">Blood group </span>
                <Chip tone="danger">{medical.blood_group}</Chip>
              </p>
            ) : null}
            {medical?.allergies?.length ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted">Allergies</span>
                {medical.allergies.map((a, i) => (
                  <Chip key={i} tone={a.severity ? SEVERITY_TONE[a.severity] : 'muted'}>
                    {a.substance}
                    {a.reaction ? ` — ${a.reaction}` : ''}
                    {a.severity ? ` (${a.severity})` : ''}
                  </Chip>
                ))}
              </div>
            ) : null}
            {medical?.conditions?.length ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted">Conditions</span>
                {medical.conditions.map((c) => (
                  <Chip key={c}>{c}</Chip>
                ))}
              </div>
            ) : null}
            {medical?.medications?.length ? (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-muted">Medications</span>
                {medical.medications.map((m, i) => (
                  <Chip key={i} tone="muted">
                    {[m.name, m.dose, m.frequency].filter(Boolean).join(' ')}
                  </Chip>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </Block>

      {p.identifiers?.abha_id ? (
        <Block title="ABHA ID">
          <span className="font-mono tabular-nums">{p.identifiers.abha_id}</span>
        </Block>
      ) : null}
      <Block title="Notes" wide>
        {p.notes || <NotRecorded />}
      </Block>
    </div>
  )
}
