/** Core API client.
 *
 * Injects the bearer token, and on a 401 attempts a single refresh before
 * replaying the request. If refresh fails, tokens are cleared and an
 * `AuthExpiredError` is thrown so the auth layer can redirect to login.
 */

import type { ApiErrorBody, Tokens } from '../types'
import { clearTokens, getAccessToken, getRefreshToken, storeTokens } from './auth-storage'

const BASE = '/api'

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

// Single-flight refresh: concurrent 401s share one refresh round-trip.
let refreshInFlight: Promise<boolean> | null = null

async function tryRefresh(): Promise<boolean> {
  const refresh_token = getRefreshToken()
  if (!refresh_token) return false
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const resp = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token }),
        })
        if (!resp.ok) return false
        storeTokens((await resp.json()) as Tokens)
        return true
      } catch {
        return false
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
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = opts

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

  let resp = await run()

  if (resp.status === 401 && auth && getAccessToken()) {
    const refreshed = await tryRefresh()
    if (refreshed) {
      resp = await run()
    } else {
      clearTokens()
      throw new AuthExpiredError()
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
  return apiFetch<HealthResponse>('/health', { auth: false })
}
