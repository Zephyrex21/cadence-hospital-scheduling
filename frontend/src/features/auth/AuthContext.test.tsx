import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../lib/api'
import { AuthProvider, useAuth } from './AuthContext'

const fetchMe = vi.hoisted(() => vi.fn())
vi.mock('./api', () => ({ fetchMe, loginRequest: vi.fn() }))

function Probe() {
  const { status } = useAuth()
  return <p>status:{status}</p>
}

describe('AuthProvider session restore', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem('cadence.access', 'a')
    localStorage.setItem('cadence.refresh', 'r')
    fetchMe.mockReset()
  })
  afterEach(() => localStorage.clear())

  it('does NOT throw the user out when the server is merely asleep', async () => {
    fetchMe.mockRejectedValue(new ApiError(503, 'server_unavailable', 'waking up'))
    await act(async () => {
      render(
        <AuthProvider>
          <Probe />
        </AuthProvider>,
      )
    })
    expect(screen.getByText('status:anonymous')).toBeInTheDocument()
    expect(localStorage.getItem('cadence.access')).toBe('a')
    expect(localStorage.getItem('cadence.refresh')).toBe('r')
  })

  it('clears the tokens when the server says the session is invalid', async () => {
    fetchMe.mockRejectedValue(new ApiError(401, 'session_expired', 'expired'))
    await act(async () => {
      render(
        <AuthProvider>
          <Probe />
        </AuthProvider>,
      )
    })
    expect(localStorage.getItem('cadence.access')).toBeNull()
  })
})
