import type { Qualification, StaffEntry } from '../../types'
import { Block, Chip, NotRecorded, languageName } from './fields'

const qualificationText = (q: Qualification) =>
  [q.degree, q.institution, q.year].filter(Boolean).join(' · ')

const SHIFT = { day: 'Day', night: 'Night', rotating: 'Rotating' } as const

/** Read-only view of one staff member's MongoDB profile. */
export function StaffProfileView({ entry }: { entry: StaffEntry }) {
  const p = entry.profile
  if (!p) {
    return <p className="text-sm text-muted">No profile details recorded yet.</p>
  }
  const detail = p.doctor ?? p.nurse
  const registration = detail?.registration
  const shift = p.nurse?.shift_pattern ?? p.reception?.shift_pattern

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Block title="Employee ID">{p.employee_id || <NotRecorded />}</Block>
      <Block title="Department">{p.department || <NotRecorded />}</Block>
      <Block title="Phone">
        {p.contact?.phone ? (
          [p.contact.phone, p.contact.alt_phone].filter(Boolean).join(' · ')
        ) : (
          <NotRecorded />
        )}
      </Block>
      <Block title="Languages">
        {p.languages?.length ? p.languages.map(languageName).join(', ') : <NotRecorded />}
      </Block>
      <Block title="Employment">
        {[p.employment?.status?.replace('_', ' '), p.employment?.joined_on && `since ${p.employment.joined_on}`]
          .filter(Boolean)
          .join(' · ') || <NotRecorded />}
      </Block>
      {shift ? <Block title="Shift pattern">{SHIFT[shift]}</Block> : null}

      {registration?.number ? (
        <Block title="Registration">
          {[registration.council, registration.number].filter(Boolean).join(' · ')}
        </Block>
      ) : null}
      {detail?.qualifications?.length ? (
        <Block title="Qualifications" wide>
          <ul className="flex flex-col gap-0.5">
            {detail.qualifications.map((q, i) => (
              <li key={i}>{qualificationText(q)}</li>
            ))}
          </ul>
        </Block>
      ) : null}

      {p.doctor ? (
        <>
          {p.doctor.sub_specialties?.length ? (
            <Block title="Sub-specialties" wide>
              <div className="flex flex-wrap gap-1.5">
                {p.doctor.sub_specialties.map((s) => (
                  <Chip key={s}>{s}</Chip>
                ))}
              </div>
            </Block>
          ) : null}
          <Block title="Experience · fee">
            {[
              p.doctor.experience_years != null && `${p.doctor.experience_years} yrs`,
              p.doctor.consultation_fee_inr != null && `₹${p.doctor.consultation_fee_inr}`,
            ]
              .filter(Boolean)
              .join(' · ') || <NotRecorded />}
          </Block>
          {p.doctor.bio ? (
            <Block title="About" wide>
              {p.doctor.bio}
            </Block>
          ) : null}
        </>
      ) : null}

      {p.nurse ? (
        <>
          <Block title="Ward">{p.nurse.ward || <NotRecorded />}</Block>
          {p.nurse.certifications?.length ? (
            <Block title="Certifications" wide>
              <div className="flex flex-wrap gap-1.5">
                {p.nurse.certifications.map((c) => (
                  <Chip key={c.name} tone="muted">
                    {c.name}
                    {c.expires_on ? ` · expires ${c.expires_on}` : ''}
                  </Chip>
                ))}
              </div>
            </Block>
          ) : null}
        </>
      ) : null}

      {p.reception ? (
        <>
          <Block title="Counter">{p.reception.counter || <NotRecorded />}</Block>
          {p.reception.training?.length ? (
            <Block title="Training" wide>
              <div className="flex flex-wrap gap-1.5">
                {p.reception.training.map((t) => (
                  <Chip key={t}>{t}</Chip>
                ))}
              </div>
            </Block>
          ) : null}
        </>
      ) : null}
    </div>
  )
}
