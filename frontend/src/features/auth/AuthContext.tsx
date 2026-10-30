import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { AUTH_EXPIRED_EVENT } from '../../lib/api'
import { clearTokens, getAccessToken, storeTokens } from '../../lib/auth-storage'
import type { User } from '../../types'
import { fetchMe, loginRequest } from './api'

interface AuthState {
  user: User | null
  status: 'loading' | 'authenticated' | 'anonymous'
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthState['status']>('loading')

  // On mount, restore the session from a stored token if present.
  useEffect(() => {
    let active = true
    if (!getAccessToken()) {
      setStatus('anonymous')
      return
    }
    fetchMe()
      .then((me) => {
        if (!active) return
        setUser(me)
        setStatus('authenticated')
      })
      .catch(() => {
        if (!active) return
        clearTokens()
        setStatus('anonymous')
      })
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginRequest(email, password)
    storeTokens(tokens)
    const me = await fetchMe()
    setUser(me)
    setStatus('authenticated')
  }, [])

  // The API client fires this when a refresh fails; without it the UI would stay
  // "signed in" while every request failed until the page was reloaded.
  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setStatus('anonymous')
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired)
  }, [])

  const logout = useCallback(() => {
    clearTokens()
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, status, login, logout }),
    [user, status, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
