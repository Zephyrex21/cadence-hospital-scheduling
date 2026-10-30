import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BackendWakeBanner } from './BackendWakeBanner'

const pingBackend = vi.hoisted(() => vi.fn<() => Promise<boolean>>())
vi.mock('../lib/api', () => ({ pingBackend }))

function renderBanner() {
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  render(
    <QueryClientProvider client={client}>
      <BackendWakeBanner />
    </QueryClientProvider>,
  )
  return { invalidate }
}

/** Flush pending promise callbacks and advance fake timers together. */
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('BackendWakeBanner', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    sessionStorage.clear()
    pingBackend.mockReset()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('explains the free-hosting delay, then welcomes the user and disappears', async () => {
    // Sleeping for two polls, then awake.
    pingBackend.mockResolvedValueOnce(false).mockResolvedValueOnce(false).mockResolvedValue(true)
    const { invalidate } = renderBanner()

    expect(screen.getByText(/waking up the server/i)).toBeInTheDocument()
    expect(screen.getByText(/hosted on a free platform/i)).toBeInTheDocument()

    await advance(6_000) // two failed polls (2.5s apart) then success
    expect(screen.getByText(/welcome to cadence/i)).toBeInTheDocument()
    expect(screen.queryByText(/waking up the server/i)).not.toBeInTheDocument()
    // Requests that failed during the cold start are retried.
    expect(invalidate).toHaveBeenCalled()

    await advance(3_500) // welcome stays briefly, then fades out
    expect(screen.queryByText(/welcome to cadence/i)).not.toBeInTheDocument()
    expect(sessionStorage.getItem('cadence:backend-awake-at')).not.toBeNull()
  })

  it('stays out of the way when the backend was confirmed awake moments ago', () => {
    sessionStorage.setItem('cadence:backend-awake-at', String(Date.now()))
    renderBanner()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(pingBackend).not.toHaveBeenCalled()
  })

  it('offers a retry when the server is still down after a long wait', async () => {
    pingBackend.mockResolvedValue(false)
    renderBanner()
    await advance(4 * 60_000 + 10_000)
    expect(screen.getByText(/still waking up/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('can be dismissed while waiting and stays dismissed', async () => {
    pingBackend.mockResolvedValueOnce(false).mockResolvedValue(true)
    renderBanner()
    await act(async () => {
      screen.getByRole('button', { name: /dismiss notice/i }).click()
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    await advance(10_000) // backend wakes up — no welcome pops back in
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
