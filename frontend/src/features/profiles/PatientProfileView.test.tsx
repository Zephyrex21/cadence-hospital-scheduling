import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PatientProfileView } from './PatientProfileView'

const profile = { patient_id: 1, mrn: 'CAD-1', address: { city: 'Pune' } }

describe('PatientProfileView', () => {
  it('says the clinical block is restricted instead of "Not recorded" when it was withheld', () => {
    render(<PatientProfileView profile={profile} redacted={['medical']} />)
    expect(screen.getByText('Restricted to clinical staff')).toBeInTheDocument()
  })

  it('shows "Not recorded" when there is simply nothing recorded', () => {
    render(<PatientProfileView profile={profile} />)
    expect(screen.queryByText('Restricted to clinical staff')).not.toBeInTheDocument()
  })
})
