import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, AUTH_EXPIRED_EVENT, apiFetch } from './api'
import { __test } from './backend'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const bad = (status: number) => new Response('<html>Bad gateway</html>', { status })
const healthy = () => json({ status: 'ok', service: 'cadence-api' })

type Handler = (call: number) => Response | Promise<Response>
function stubFetch(routes: Record<string, Handler>) {
  const calls: Record<string, number> = {}
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^\/api/, '')
    const handler = routes[path]
    if (!handler) throw new Error(`unexpected request: ${path}`)
    calls[path] = (calls[path] ?? 0) + 1
    return handler(calls[path])
  })
  vi.stubGlobal('fetch', fn)
  return { fn, calls }
}

describe('apiFetch against a sleeping backend', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    __test.reset()
  })
  afterEach(() => {
    __test.reset()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('holds the request until the backend is awake instead of firing into a 502', async () => {
    const { calls } = stubFetch({
      '/health': (n) => (n < 3 ? bad(503) : healthy()),
      '/auth/login': () => json({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' }),
    })

    const p = apiFetch('/auth/login', { method: 'POST', body: {}, auth: false, retry: true })
    await vi.advanceTimersByTimeAsync(1_000)
    expect(calls['/auth/login']).toBeUndefined() // still waiting for the server

    await vi.advanceTimersByTimeAsync(6_000)
    await expect(p).resolves.toMatchObject({ access_token: 'a' })
    expect(calls['/auth/login']).toBe(1)
  })

  it('re-wakes and replays a login that hit a 502 mid-flight', async () => {
    const { calls } = stubFetch({
      '/health': () => healthy(),
      '/auth/login': (n) =>
        n === 1 ? bad(502) : json({ access_token: 'a', refresh_token: 'r', token_type: 'bearer' }),
    })

    const p = apiFetch('/auth/login', { method: 'POST', body: {}, auth: false, retry: true })
    await vi.advanceTimersByTimeAsync(10_000)

    await expect(p).resolves.toMatchObject({ access_token: 'a' })
    expect(calls['/auth/login']).toBe(2)
  })

  it('never says "Request failed" for a gateway error, and does not replay unsafe writes', async () => {
    const { calls } = stubFetch({
      '/health': () => healthy(),
      '/patients': () => bad(502),
    })

    const p = apiFetch('/patients', { method: 'POST', body: { name: 'x' } })
    const caught = p.catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(5_000)
    const err = await caught

    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 502, code: 'server_unavailable' })
    expect((err as ApiError).message).toMatch(/waking up/i)
    expect((err as ApiError).message).not.toMatch(/request failed/i)
    expect(calls['/patients']).toBe(1) // a write that may have landed is not replayed
  })

  it('retries a GET after a network error', async () => {
    const { calls } = stubFetch({
      '/health': () => healthy(),
      '/patients': (n) => {
        if (n === 1) throw new TypeError('Failed to fetch')
        return json([{ id: 1 }])
      },
    })

    const p = apiFetch<unknown[]>('/patients')
    await vi.advanceTimersByTimeAsync(10_000)
    await expect(p).resolves.toEqual([{ id: 1 }])
    expect(calls['/patients']).toBe(2)
  })

  it('keeps the session when the refresh call fails only because the server is down', async () => {
    localStorage.setItem('cadence.access', 'old')
    localStorage.setItem('cadence.refresh', 'refresh')
    const onExpired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    stubFetch({
      '/health': () => healthy(),
      '/patients': () => json({ error: { code: 'unauthorized', message: 'expired' } }, 401),
      '/auth/refresh': () => bad(503),
    })

    const caught = apiFetch('/patients').catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(5_000)
    const err = await caught

    expect(err).toMatchObject({ code: 'server_unavailable' })
    expect(localStorage.getItem('cadence.refresh')).toBe('refresh')
    expect(onExpired).not.toHaveBeenCalled()
    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  })

  it('still signs the user out when the refresh token is genuinely rejected', async () => {
    localStorage.setItem('cadence.access', 'old')
    localStorage.setItem('cadence.refresh', 'bad')
    const onExpired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    stubFetch({
      '/health': () => healthy(),
      '/patients': () => json({ error: { code: 'unauthorized', message: 'expired' } }, 401),
      '/auth/refresh': () => json({ error: { code: 'unauthorized', message: 'nope' } }, 401),
    })

    const caught = apiFetch('/patients').catch((e: unknown) => e)
    await vi.advanceTimersByTimeAsync(5_000)
    const err = await caught

    expect(err).toMatchObject({ status: 401, code: 'session_expired' })
    expect(localStorage.getItem('cadence.refresh')).toBeNull()
    expect(onExpired).toHaveBeenCalled()
    window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  })
})
