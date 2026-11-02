/** Backend wake-up tracking.
 *
 * The API runs on a free host (Render) that sleeps after ~15 min idle and takes up to a
 * minute or two to come back. This module is the single source of truth for "is the
 * backend up?", shared by the notice banner, the API client and the login form:
 *
 *  - On app open we ping the backend (and also kick Render directly, see `kick`).
 *  - While it is asleep, `waitForBackend()` lets requests queue instead of failing.
 *  - When a request later hits a gateway error, `reportBackendDown()` re-runs the wake.
 *  - A tab left idle long enough for Render to sleep is re-checked when it is revisited.
 */

export const API_BASE = '/api'

/** Don't flash a notice if the backend answers within this long. */
const GRACE_MS = 1_200
const RETRY_MS = 2_500
const PING_TIMEOUT_MS = 15_000
/** After this long without an answer we stop and offer a manual retry. */
const GIVE_UP_MS = 4 * 60_000
const KICK_EVERY_MS = 20_000
const KICK_TIMEOUT_MS = 90_000
/** Render sleeps after ~15 min without traffic; re-check a tab that was quiet for 10. */
const STALE_MS = 10 * 60_000

/** Where the Render service lives. Overridable per deployment with VITE_BACKEND_URL
 *  (set it to an empty string to disable the direct wake call). */
const DEFAULT_BACKEND_URL = 'https://cadence-api-opro.onrender.com'

function resolveDirectUrl(): string | null {
  // Dev and tests talk to the Vite proxy only; there is no sleeping host to wake.
  if (!import.meta.env.PROD) return null
  const url = import.meta.env.VITE_BACKEND_URL ?? DEFAULT_BACKEND_URL
  return url ? url.replace(/\/+$/, '') : null
}

const config = { directUrl: resolveDirectUrl() }

export type BackendPhase = 'idle' | 'checking' | 'waking' | 'ready' | 'failed'

export interface BackendStatus {
  phase: BackendPhase
  /** When the current check began (identifies a wake cycle). */
  startedAt: number | null
  /** True when this cycle was slow enough that the user was told the server was waking. */
  wokeAfterWait: boolean
}

const IDLE: BackendStatus = { phase: 'idle', startedAt: null, wokeAfterWait: false }

let status: BackendStatus = IDLE
let lastHealthyAt = 0
let generation = 0
let inFlight: Promise<void> | null = null
let watching = false
const listeners = new Set<() => void>()

function setStatus(next: BackendStatus): void {
  status = next
  listeners.forEach((listener) => listener())
}

export function getBackendStatus(): BackendStatus {
  return status
}

export function subscribeBackend(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

async function probe(url: string, timeoutMs: number): Promise<boolean> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const resp = await fetch(url, { signal: controller.signal, cache: 'no-store' })
    if (!resp.ok) return false
    const body = (await resp.json()) as { status?: string }
    return body.status === 'ok'
  } catch {
    // Timeout, network error, or a non-JSON "waking up" placeholder page.
    return false
  } finally {
    clearTimeout(timer)
  }
}

/** Is the API actually up *through the same path real requests take* (`/api`)? Never throws. */
export function pingBackend(timeoutMs = PING_TIMEOUT_MS): Promise<boolean> {
  return probe(`${API_BASE}/health`, timeoutMs)
}

/** Fire-and-forget request straight at the Render service from the browser.
 *
 * Sleeping Render services wake on any inbound request. Sending one directly means the
 * wake never depends on Vercel's proxy hop (which can time out or answer 502 while the
 * upstream is still booting). `no-cors` keeps it independent of CORS configuration —
 * we ignore the opaque result; readiness is decided by `pingBackend`.
 */
function kick(): void {
  const base = config.directUrl
  if (!base) return
  const controller = new AbortController()
  setTimeout(() => controller.abort(), KICK_TIMEOUT_MS)
  fetch(`${base}/health`, {
    mode: 'no-cors',
    cache: 'no-store',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    signal: controller.signal,
  }).catch(() => {
    /* expected while the host is booting */
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function run(gen: number, startedAt: number): Promise<void> {
  let lastKick = Date.now()
  kick()
  const grace = setTimeout(() => {
    if (gen === generation && status.phase === 'checking') {
      setStatus({ ...status, phase: 'waking' })
    }
  }, GRACE_MS)

  try {
    for (;;) {
      const ok = await pingBackend()
      if (gen !== generation) return
      if (ok) {
        lastHealthyAt = Date.now()
        setStatus({ phase: 'ready', startedAt, wokeAfterWait: status.phase === 'waking' })
        return
      }
      if (Date.now() - startedAt > GIVE_UP_MS) {
        setStatus({ phase: 'failed', startedAt, wokeAfterWait: false })
        return
      }
      if (Date.now() - lastKick > KICK_EVERY_MS) {
        kick()
        lastKick = Date.now()
      }
      await sleep(RETRY_MS)
      if (gen !== generation) return
    }
  } finally {
    clearTimeout(grace)
  }
}

function begin(): Promise<void> {
  generation += 1
  const gen = generation
  const startedAt = Date.now()
  setStatus({ phase: 'checking', startedAt, wokeAfterWait: false })
  const promise: Promise<void> = run(gen, startedAt).finally(() => {
    if (inFlight === promise) inFlight = null
  })
  inFlight = promise
  return promise
}

function watchVisibility(): void {
  if (watching || typeof document === 'undefined') return
  watching = true
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') recheckIfStale()
  })
}

/** Call once when the app opens: pings (and wakes) the backend. Safe to call again. */
export function startBackendCheck(): Promise<void> {
  watchVisibility()
  if (inFlight) return inFlight
  if (status.phase === 'idle') return begin()
  return Promise.resolve()
}

/** Resolves once the backend is up — or once we've given up, so callers never hang forever. */
export function waitForBackend(): Promise<void> {
  if (status.phase === 'ready' || status.phase === 'failed') return Promise.resolve()
  return inFlight ?? begin()
}

/** A request just hit a gateway error / network failure: start waking the backend again. */
export function reportBackendDown(): void {
  if (inFlight) return
  void begin()
}

/** A real response came back, so the host is awake and its idle timer has reset. */
export function touchBackend(): void {
  lastHealthyAt = Date.now()
}

/** Re-check a tab that's been quiet long enough for the host to have gone back to sleep. */
export function recheckIfStale(): void {
  if (inFlight || status.phase === 'idle') return
  if (Date.now() - lastHealthyAt < STALE_MS) return
  void begin()
}

/** Test seam — never used by app code. */
export const __test = {
  config,
  reset(): void {
    generation += 1
    inFlight = null
    status = IDLE
    lastHealthyAt = 0
    config.directUrl = resolveDirectUrl()
    listeners.clear()
  },
}
