/** Token persistence. localStorage keeps the session across reloads for this
 *  demo; a production build would prefer httpOnly cookies to resist XSS. */

import type { Tokens } from '../types'

const ACCESS_KEY = 'cadence.access'
const REFRESH_KEY = 'cadence.refresh'

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function storeTokens(tokens: Tokens): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token)
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}
