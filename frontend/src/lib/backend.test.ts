import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  __test,
  getBackendStatus,
  recheckIfStale,
  reportBackendDown,
  startBackendCheck,
  subscribeBackend,
  waitForBackend,
} from './backend'

/** A stand-in for fetch where `/health` is controllable. */
function stubFetch(isUp: () => boolean) {
  const fn = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async (input) => {
    const url = String(input)
    if (!url.endsWith('/health')) throw new Error(`unexpected request: ${url}`)
    return isUp()
      ? new Response(JSON.stringify({ status: 'ok', service: 'cadence-api' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      : new Response('<html>Service waking up</html>', { status: 503 })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

const proxyHealthCalls = (fn: ReturnType<typeof stubFetch>) =>
  fn.mock.calls.filter(([u]) => String(u).startsWith('/api/health')).length

describe('backend wake store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    __test.reset()
  })
  afterEach(() => {
    __test.reset()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('stays silent when the backend answers right away', async () => {
    stubFetch(() => true)
    const phases: string[] = []
    subscribeBackend(() => phases.push(getBackendStatus().phase))

    await startBackendCheck()

    expect(getBackendStatus()).toMatchObject({ phase: 'ready', wokeAfterWait: false })
    expect(phases).not.toContain('waking')
  })

  it('shows "waking" only after a short grace period, then reports ready after a real wait', async () => {
    let up = false
    stubFetch(() => up)
    void startBackendCheck()

    await vi.advanceTimersByTimeAsync(500)
    expect(getBackendStatus().phase).toBe('checking') // too soon to bother the user

    await vi.advanceTimersByTimeAsync(1_000)
    expect(getBackendStatus().phase).toBe('waking')

    up = true
    await vi.advanceTimersByTimeAsync(3_000)
    expect(getBackendStatus()).toMatchObject({ phase: 'ready', wokeAfterWait: true })
  })

  it('gives up after a few minutes without hanging callers', async () => {
    stubFetch(() => false)
    const done = waitForBackend()
    await vi.advanceTimersByTimeAsync(4 * 60_000 + 30_000)
    await done
    expect(getBackendStatus().phase).toBe('failed')
  })

  it('shares one polling loop between many waiters', async () => {
    let up = false
    const fetchMock = stubFetch(() => up)
    const waiters = Array.from({ length: 5 }, () => waitForBackend())

    await vi.advanceTimersByTimeAsync(100)
    expect(proxyHealthCalls(fetchMock)).toBe(1)

    up = true
    await vi.advanceTimersByTimeAsync(3_000)
    await Promise.all(waiters)
    expect(getBackendStatus().phase).toBe('ready')
  })

  it('kicks the Render service directly (no-cors) so the wake does not depend on the proxy', async () => {
    __test.config.directUrl = 'https://cadence-api.example.onrender.com'
    const fetchMock = stubFetch(() => true)

    await startBackendCheck()

    const direct = fetchMock.mock.calls.find(
      ([u]) => String(u) === 'https://cadence-api.example.onrender.com/health',
    )
    expect(direct).toBeDefined()
    expect(direct![1]?.mode).toBe('no-cors')
  })

  it('goes back to checking when a request reports the backend went away', async () => {
    let up = true
    stubFetch(() => up)
    await startBackendCheck()
    expect(getBackendStatus().phase).toBe('ready')

    up = false
    reportBackendDown()
    expect(getBackendStatus().phase).toBe('checking')

    await vi.advanceTimersByTimeAsync(1_500)
    expect(getBackendStatus().phase).toBe('waking')

    up = true
    await vi.advanceTimersByTimeAsync(3_000)
    expect(getBackendStatus()).toMatchObject({ phase: 'ready', wokeAfterWait: true })
  })

  it('re-checks a tab that has been idle long enough for Render to sleep', async () => {
    const fetchMock = stubFetch(() => true)
    await startBackendCheck()
    const before = proxyHealthCalls(fetchMock)

    await vi.advanceTimersByTimeAsync(2 * 60_000)
    recheckIfStale()
    await vi.advanceTimersByTimeAsync(10)
    expect(proxyHealthCalls(fetchMock)).toBe(before) // still fresh: no extra call

    await vi.advanceTimersByTimeAsync(10 * 60_000)
    recheckIfStale()
    await vi.advanceTimersByTimeAsync(10)
    expect(proxyHealthCalls(fetchMock)).toBeGreaterThan(before)
  })
})
