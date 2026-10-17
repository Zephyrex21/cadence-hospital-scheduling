import { lazy, Suspense, useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useAuth } from '../features/auth/AuthContext'
import { HeroFallback } from '../features/login/HeroFallback'
import { ApiError } from '../lib/api'

const Hero3D = lazy(() => import('../features/login/Hero3D'))

function hasWebGL(): boolean {
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch {
    return false
  }
}

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: string } }

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [use3D, setUse3D] = useState(false)

  useEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const small = window.matchMedia('(max-width: 1023px)').matches
    setUse3D(!reduce && !small && hasWebGL())
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(location.state?.from ?? '/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Form side */}
      <div className="flex items-center justify-center bg-canvas px-4 py-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex flex-col items-center gap-3 text-center">
            <div className="flex h-11 w-11 items-center justify-center rounded-card bg-brand-gradient text-white shadow-sm">
              <span className="font-display text-xl font-semibold">C</span>
            </div>
            <div>
              <h1 className="font-display text-title font-semibold text-ink">Cadence</h1>
              <p className="text-sm text-muted">Sign in to the clinical flow platform</p>
            </div>
          </div>

          <form
            onSubmit={onSubmit}
            className="flex flex-col gap-4 rounded-card border border-hairline bg-surface p-6 shadow-sm"
            noValidate
          >
            <Input
              label="Email"
              name="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {error ? (
              <div
                role="alert"
                className="rounded-control border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
              >
                {error}
              </div>
            ) : null}

            <Button type="submit" loading={submitting} className="w-full">
              Sign in
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-muted">
            Synthetic demo data only — not for clinical use.
          </p>
        </div>
      </div>

      {/* Hero side — fixed-dark showcase panel (always dark so the frosted blocks read). */}
      <div className="relative hidden overflow-hidden bg-hero lg:block">
        {use3D ? (
          <Suspense fallback={<HeroFallback />}>
            <Hero3D />
          </Suspense>
        ) : (
          <HeroFallback />
        )}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/50 to-transparent p-10">
          <p className="font-display text-2xl font-semibold text-white">
            Calm scheduling under pressure
          </p>
          <p className="mt-1 max-w-md text-sm text-white/70">
            Priority-aware appointments that absorb walk-in emergencies without losing a patient.
          </p>
        </div>
      </div>
    </div>
  )
}
