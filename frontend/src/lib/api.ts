/** Core API client.
 *
 * Injects the bearer token, and on a 401 attempts a single refresh before
 * replaying the request. If the refresh token is *rejected*, tokens are cleared and an
 * `AuthExpiredError` is thrown so the auth layer can redirect to login.
 *
 * The backend sits on a host that sleeps when idle, so every request first waits for the
 * backend to be awake (see `backend.ts`) instead of firing into a gateway error. A
 * gateway error / network failure never deletes the session — only a genuine 401 does.
 */

import type { ApiErrorBody, Tokens } from '../types'
import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from './auth-storage'
import {
  API_BASE as BASE,
  getBackendStatus,
  reportBackendDown,
  touchBackend,
  waitForBackend,
} from './backend'

/** Gateway statuses a proxy returns while the upstream is asleep or still booting. */
const TRANSIENT_STATUS = new Set([502, 503, 504])
/** How many times a safe request is replayed after re-waking the backend. */
const MAX_WAKE_RETRIES = 2
const WAKING_MESSAGE = 'The server is waking up. Please try again in a moment.'
const NETWORK_MESSAGE = "Can't reach the server. Check your connection and try again."

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** Fired on `window` when the session can no longer be refreshed. */
export const AUTH_EXPIRED_EVENT = 'cadence:auth-expired'

export class AuthExpiredError extends ApiError {
  constructor() {
    super(401, 'session_expired', 'Your session has expired. Please sign in again.')
    this.name = 'AuthExpiredError'
  }
}

async function parseError(resp: Response): Promise<ApiError> {
  try {
    const body = (await resp.json()) as ApiErrorBody
    return new ApiError(resp.status, body.error.code, body.error.message, body.error.details)
  } catch {
    return new ApiError(resp.status, 'unknown', resp.statusText || 'Request failed')
  }
}

type RefreshOutcome = 'ok' | 'rejected' | 'unavailable'

// Single-flight refresh: concurrent 401s share one refresh round-trip.
let refreshInFlight: Promise<RefreshOutcome> | null = null

/** `rejected` = the server said the refresh token is no good (sign out);
 *  `unavailable` = we couldn't tell because the server is down (keep the session). */
async function tryRefresh(): Promise<RefreshOutcome> {
  const refresh_token = getRefreshToken()
  if (!refresh_token) return 'rejected'
  if (!refreshInFlight) {
    refreshInFlight = (async (): Promise<RefreshOutcome> => {
      try {
        const resp = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token }),
        })
        if (resp.ok) {
          storeTokens((await resp.json()) as Tokens)
          return 'ok'
        }
        const clientError = resp.status >= 400 && resp.status < 500
        return clientError && resp.status !== 408 && resp.status !== 429 ? 'rejected' : 'unavailable'
      } catch {
        return 'unavailable'
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
  /** Safe to replay if the backend turns out to be asleep (default: GET only). */
  retry?: boolean
  /** Wait for the backend to be awake before sending (default: true). */
  wake?: boolean
}

/** Send once; if the backend is down, re-wake it and (when `retry`) replay. */
async function send(
  run: () => Promise<Response>,
  retry: boolean,
  wake: boolean,
): Promise<Response> {
  for (let attempt = 0; ; attempt++) {
    let failure: ApiError
    try {
      const resp = await run()
      if (!TRANSIENT_STATUS.has(resp.status)) {
        touchBackend()
        return resp
      }
      failure = new ApiError(resp.status, 'server_unavailable', WAKING_MESSAGE)
    } catch (err) {
      if (!(err instanceof TypeError)) throw err // e.g. an abort — not a connectivity problem
      failure = new ApiError(0, 'network_error', NETWORK_MESSAGE)
    }
    reportBackendDown()
    if (!wake || !retry || attempt >= MAX_WAKE_RETRIES) throw failure
    await waitForBackend()
    if (getBackendStatus().phase === 'failed') throw failure
  }
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, retry = method === 'GET', wake = true } = opts

  const run = async (): Promise<Response> => {
    const headers: Record<string, string> = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (auth) {
      const token = getAccessToken()
      if (token) headers.Authorization = `Bearer ${token}`
    }
    return fetch(`${BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  }

  // Never fire into a sleeping backend: wait (the banner explains why) until it is up.
  if (wake) await waitForBackend()

  let resp = await send(run, retry, wake)

  if (resp.status === 401 && auth && getAccessToken()) {
    const outcome = await tryRefresh()
    if (outcome === 'ok') {
      resp = await send(run, retry, wake)
    } else if (outcome === 'rejected') {
      clearTokens()
      // Tell the auth layer so it can drop the session and send the user to login.
      if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
      throw new AuthExpiredError()
    } else {
      // The server is down, not the session: keep the tokens and let the caller retry.
      reportBackendDown()
      throw new ApiError(503, 'server_unavailable', WAKING_MESSAGE)
    }
  }

  if (!resp.ok) throw await parseError(resp)
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}

export interface HealthResponse {
  status: string
  service: string
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health', { auth: false, wake: false })
}
