import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { BrandMark } from '../components/BrandMark'
import { Button } from '../components/Button'
import { Input } from '../components/Input'
import { useAuth } from '../features/auth/AuthContext'
import { HeroScene } from '../features/login/HeroScene'
import { ApiError } from '../lib/api'
import { ThemeToggle } from '../theme/ThemeToggle'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation() as { state?: { from?: string } }

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

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
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      {/* Form side */}
      <div className="relative flex items-center justify-center px-5 py-12">
        <div className="absolute right-5 top-5">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-[22rem] animate-fade-in-up">
          <div className="mb-9 flex flex-col items-center gap-4 text-center">
            <BrandMark size={56} />
            <div>
              <h1 className="font-display text-display font-semibold text-ink">Cadence</h1>
              <p className="mt-1.5 text-[15px] text-muted">Sign in to the clinical flow platform</p>
            </div>
          </div>

          <form
            onSubmit={onSubmit}
            className="lit flex flex-col gap-4 rounded-modal p-7 shadow-md"
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
                className="rounded-control border border-danger/20 bg-danger/5 px-3.5 py-2.5 text-sm text-danger"
              >
                {error}
              </div>
            ) : null}

            <Button type="submit" size="lg" loading={submitting} className="mt-1 w-full">
              Sign in
            </Button>
          </form>

          <p className="mt-7 text-center text-xs text-muted">
            Demo environment — a scheduling tool, not a clinical decision system.
          </p>
        </div>
      </div>

      {/* Showcase side */}
      <div className="relative hidden overflow-hidden border-l border-hairline lg:block">
        <HeroScene />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 p-12">
          <p className="font-display text-display font-semibold text-ink">
            Calm scheduling under pressure.
          </p>
          <p className="mt-2 max-w-md text-[15px] text-slate">
            Priority-aware appointments that absorb walk-in emergencies without losing a patient.
          </p>
        </div>
      </div>
    </div>
  )
}
