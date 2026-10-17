import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders its label', () => {
    render(<StatusBadge tone="success">API: cadence-api</StatusBadge>)
    expect(screen.getByText('API: cadence-api')).toBeInTheDocument()
  })

  it('defaults to the neutral tone', () => {
    render(<StatusBadge>Connecting…</StatusBadge>)
    expect(screen.getByText('Connecting…')).toBeInTheDocument()
  })
})
