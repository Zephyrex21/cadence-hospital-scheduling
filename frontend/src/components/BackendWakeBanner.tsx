import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Loader2, X } from './icons'
import { useEffect, useRef, useState } from 'react'

import { pingBackend } from '../lib/api'
import { Button } from './Button'

type Phase = 'waking' | 'slow' | 'ready' | 'leaving' | 'hidden'

const AWAKE_KEY = 'cadence:backend-awake-at'
/** Render's free tier sleeps after ~15 min idle; treat "awake" as fresh for 10. */
const AWAKE_TTL_MS = 10 * 60_000
const RETRY_MS = 2_500
const GIVE_UP_MS = 4 * 60_000
/** Keep the notice up at least this long so a fast response doesn't flash. */
const MIN_NOTICE_MS = 1_400
const WELCOME_MS = 2_600
const FADE_MS = 400

function recentlyAwake(): boolean {
  try {
    const at = Number(sessionStorage.getItem(AWAKE_KEY))
    return Number.isFinite(at) && at > 0 && Date.now() - at < AWAKE_TTL_MS
  } catch {
    return false
  }
}

function markAwake(): void {
  try {
    sessionStorage.setItem(AWAKE_KEY, String(Date.now()))
  } catch {
    /* storage unavailable (private mode) — the notice just shows again next load */
  }
}

/**
 * The API runs on a free hosting plan that goes to sleep when idle, so the first
 * request after a quiet period can take up to a minute. This notice tells people
 * that up front, polls the health endpoint, then says "Welcome" once the backend
 * is awake and fades away. Pages whose first requests failed during the cold start
 * are refetched automatically when it comes up.
 */
export function BackendWakeBanner() {
  const queryClient = useQueryClient()
  const [phase, setPhase] = useState<Phase>(() => (recentlyAwake() ? 'hidden' : 'waking'))
  const [elapsed, setElapsed] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const dismissed = useRef(false)

  useEffect(() => {
    if (recentlyAwake()) {
      setPhase('hidden')
      return
    }
    dismissed.current = false
    setPhase('waking')
    setElapsed(0)

    let cancelled = false
    const started = Date.now()
    const timers: ReturnType<typeof setTimeout>[] = []
    const later = (fn: () => void, ms: number) => {
      timers.push(setTimeout(fn, ms))
    }
    const show = (next: Phase) => {
      if (!cancelled && !dismissed.current) setPhase(next)
    }
    const clock = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)

    async function poll() {
      while (!cancelled) {
        const ok = await pingBackend()
        if (cancelled) return
        if (ok) {
          markAwake()
          const waited = Date.now() - started
          // Anything that fired during a real cold start has already failed — retry it.
          if (waited > 3_000) void queryClient.invalidateQueries()
          later(
            () => {
              show('ready')
              later(() => {
                show('leaving')
                later(() => show('hidden'), FADE_MS)
              }, WELCOME_MS)
            },
            Math.max(0, MIN_NOTICE_MS - waited),
          )
          return
        }
        if (Date.now() - started > GIVE_UP_MS) {
          show('slow')
          return
        }
        await new Promise<void>((resolve) => later(resolve, RETRY_MS))
      }
    }
    void poll()

    return () => {
      cancelled = true
      clearInterval(clock)
      timers.forEach(clearTimeout)
    }
  }, [attempt, queryClient])

  if (phase === 'hidden') return null

  const ready = phase === 'ready' || phase === 'leaving'

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed left-1/2 top-3 z-[100] w-[min(calc(100vw-2rem),26rem)] -translate-x-1/2 transition duration-300 ease-out motion-reduce:transition-none ${
        phase === 'leaving' ? '-translate-y-2 opacity-0' : 'translate-y-0 opacity-100'
      } ${ready ? 'pointer-events-none' : ''}`}
    >
      <div className="flex items-start gap-3 glass rounded-card border border-hairline p-4 shadow-lg">
        {ready ? (
          <CheckCircle2
            weight="fill"
            className="mt-0.5 h-5 w-5 shrink-0 text-success"
            aria-hidden
          />
        ) : (
          <Loader2
            className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-brand motion-reduce:animate-none"
            aria-hidden
          />
        )}
        <div className="min-w-0 flex-1">
          {ready ? (
            <>
              <p className="font-display text-sm font-semibold text-ink">Welcome to Cadence</p>
              <p className="mt-0.5 text-sm text-muted">The backend is awake and ready.</p>
            </>
          ) : phase === 'slow' ? (
            <>
              <p className="font-display text-sm font-semibold text-ink">Still waking up</p>
              <p className="mt-0.5 text-sm text-muted">
                This is taking longer than usual. The free server may be starting from cold.
              </p>
              <div className="mt-3">
                <Button size="sm" variant="secondary" onClick={() => setAttempt((n) => n + 1)}>
                  Try again
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="font-display text-sm font-semibold text-ink">Waking up the server…</p>
              <p className="mt-0.5 text-sm text-muted">
                Cadence is hosted on a free platform, so the backend sleeps when idle and may take
                up to a minute to wake. Hang tight — we&apos;ll let you know when it&apos;s ready.
              </p>
              {elapsed >= 3 && (
                <p className="mt-1.5 text-xs tabular-nums text-muted">{elapsed}s elapsed</p>
              )}
            </>
          )}
        </div>
        {!ready && (
          <button
            type="button"
            aria-label="Dismiss notice"
            onClick={() => {
              dismissed.current = true
              setPhase('hidden')
            }}
            className="-m-1 rounded-control p-1 text-muted outline-none transition hover:text-ink focus-visible:ring-2 focus-visible:ring-brand/40"
          >
            <X size={16} aria-hidden />
          </button>
        )}
      </div>
    </div>
  )
}
