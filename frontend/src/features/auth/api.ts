import { apiFetch } from '../../lib/api'
import type { Tokens, User } from '../../types'

export function loginRequest(email: string, password: string): Promise<Tokens> {
  return apiFetch<Tokens>('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
    // Safe to replay: if the gateway answered 502/503 the request never reached the app.
    retry: true,
  })
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/auth/me')
}

/** Tell the server to revoke the refresh token (best effort: sign-out never waits on it). */
export function logoutRequest(refreshToken: string): Promise<void> {
  return apiFetch<void>('/auth/logout', {
    method: 'POST',
    body: { refresh_token: refreshToken },
    auth: false,
    wake: false,
  }).catch(() => undefined)
}
