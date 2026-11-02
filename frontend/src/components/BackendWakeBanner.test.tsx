import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { __test } from '../lib/backend'
import { BackendWakeBanner } from './BackendWakeBanner'

function stubHealth(isUp: () => boolean) {
  const fn = vi.fn(async () =>
    isUp()
      ? new Response(JSON.stringify({ status: 'ok', service: 'cadence-api' }), { status: 200 })
      : new Response('<html>waking</html>', { status: 503 }),
  )
  vi.stubGlobal('fetch', fn)
  return fn
}

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
    __test.reset()
  })
  afterEach(() => {
    __test.reset()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('calls the backend on open, explains the wait, then says the service is live and goes away', async () => {
    let up = false
    const fetchMock = stubHealth(() => up)
    const { invalidate } = renderBanner()

    await advance(100)
    expect(fetchMock).toHaveBeenCalled() // opening the app pings the backend
    expect(screen.queryByRole('status')).not.toBeInTheDocument() // …but no flash yet

    await advance(1_500)
    expect(screen.getByText(/waking up the server/i)).toBeInTheDocument()
    expect(screen.getByText(/hosted on a free platform/i)).toBeInTheDocument()

    up = true
    await advance(3_000)
    expect(screen.getByText(/service is live/i)).toBeInTheDocument()
    expect(screen.queryByText(/waking up the server/i)).not.toBeInTheDocument()
    expect(invalidate).toHaveBeenCalled() // requests that failed during the cold start refetch

    await advance(3_500)
    expect(screen.queryByText(/service is live/i)).not.toBeInTheDocument()
  })

  it('stays completely out of the way when the backend is already awake', async () => {
    stubHealth(() => true)
    renderBanner()
    await advance(5_000)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('offers a retry when the server is still down after a long wait', async () => {
    stubHealth(() => false)
    renderBanner()
    await advance(4 * 60_000 + 10_000)
    expect(screen.getByText(/isn.t responding/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('can be dismissed while waiting and stays dismissed', async () => {
    let up = false
    stubHealth(() => up)
    renderBanner()
    await advance(1_500)
    await act(async () => {
      screen.getByRole('button', { name: /dismiss notice/i }).click()
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    up = true
    await advance(10_000)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
