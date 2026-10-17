import { apiFetch } from '../../lib/api'
import type { Tokens, User } from '../../types'

export function loginRequest(email: string, password: string): Promise<Tokens> {
  return apiFetch<Tokens>('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  })
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>('/auth/me')
}
