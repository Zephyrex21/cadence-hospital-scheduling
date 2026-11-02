import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { startBackendCheck, reportBackendDown } from '../lib/backend'
import { useBackendStatus } from '../lib/useBackendStatus'
import { Button } from './Button'
import { CheckCircle2, Loader2, X } from './icons'

type Stage = 'notice' | 'live' | 'leaving' | 'hidden'

const WELCOME_MS = 2_600
const FADE_MS = 400

/**
 * The API runs on a free hosting plan that goes to sleep when idle, so the first
 * request after a quiet period can take up to a minute or two. Opening the app pings
 * the backend (`startBackendCheck`); if it doesn't answer right away this notice says so,
 * keeps polling, then announces "Service is live" and fades away. Requests that were
 * waiting (or failed) during the cold start are refetched automatically.
 *
 * All the waking logic lives in `lib/backend.ts`; this component only presents it.
 */
export function BackendWakeBanner() {
  const queryClient = useQueryClient()
  const backend = useBackendStatus()
  const [now, setNow] = useState(() => Date.now())
  // The wake cycle (startedAt) the user dismissed, so a later cycle can show again.
  const [dismissedCycle, setDismissedCycle] = useState<number | null>(null)
  const [stage, setStage] = useState<Stage>('notice')

  useEffect(() => {
    void startBackendCheck()
  }, [])

  const cycle = backend.startedAt
  const dismissed = cycle !== null && dismissedCycle === cycle
  const waking = backend.phase === 'waking'
  const failed = backend.phase === 'failed'
  const announce = backend.phase === 'ready' && backend.wokeAfterWait

  // Seconds counter while waiting.
  useEffect(() => {
    if (!waking) return
    setNow(Date.now())
    const clock = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(clock)
  }, [waking, cycle])

  // Once the backend is up after a real wait: refetch what failed, then show/fade the success.
  useEffect(() => {
    if (!announce) return
    void queryClient.invalidateQueries()
    if (dismissed) return
    setStage('live')
    const timers = [
      setTimeout(() => setStage('leaving'), WELCOME_MS),
      setTimeout(() => setStage('hidden'), WELCOME_MS + FADE_MS),
    ]
    return () => timers.forEach(clearTimeout)
    // `dismissed` is read once per announcement; re-running on it would restart the timers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [announce, cycle, queryClient])

  const showNotice = (waking || failed) && !dismissed
  const showLive = announce && !dismissed && (stage === 'live' || stage === 'leaving')
  if (!showNotice && !showLive) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed left-1/2 top-3 z-[100] w-[min(calc(100vw-2rem),26rem)] -translate-x-1/2 transition duration-300 ease-out motion-reduce:transition-none ${
        showLive && stage === 'leaving' ? '-translate-y-2 opacity-0' : 'translate-y-0 opacity-100'
      } ${showLive ? 'pointer-events-none' : ''}`}
    >
      <div className="flex items-start gap-3 glass rounded-card border border-hairline p-4 shadow-lg">
        {showLive ? (
          <CheckCircle2 weight="fill" className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
        ) : (
          <Loader2
            className="mt-0.5 h-5 w-5 shrink-0 animate-spin text-brand motion-reduce:animate-none"
            aria-hidden
          />
        )}
        <div className="min-w-0 flex-1">
          {showLive ? (
            <>
              <p className="font-display text-sm font-semibold text-ink">Service is live</p>
              <p className="mt-0.5 text-sm text-muted">
                The Cadence server is awake and ready — you can sign in now.
              </p>
            </>
          ) : failed ? (
            <>
              <p className="font-display text-sm font-semibold text-ink">
                The server isn&apos;t responding
              </p>
              <p className="mt-0.5 text-sm text-muted">
                This is taking longer than usual. The free server may be starting from cold.
              </p>
              <div className="mt-3">
                <Button size="sm" variant="secondary" onClick={() => reportBackendDown()}>
                  Try again
                </Button>
              </div>
            </>
          ) : (
            <>
              <p className="font-display text-sm font-semibold text-ink">Waking up the server…</p>
              <p className="mt-0.5 text-sm text-muted">
                Cadence is hosted on a free platform, so the backend sleeps when idle and may take
                up to a minute or two to wake. Hang tight — we&apos;ll let you know when it&apos;s
                live.
              </p>
              {cycle !== null && now - cycle >= 3_000 && (
                <p className="mt-1.5 text-xs tabular-nums text-muted">
                  {Math.floor((now - cycle) / 1000)}s elapsed
                </p>
              )}
            </>
          )}
        </div>
        {!showLive && (
          <button
            type="button"
            aria-label="Dismiss notice"
            onClick={() => setDismissedCycle(cycle)}
            className="-m-1 rounded-control p-1 text-muted outline-none transition hover:text-ink focus-visible:ring-2 focus-visible:ring-brand/40"
          >
            <X size={16} aria-hidden />
          </button>
        )}
      </div>
    </div>
  )
}
