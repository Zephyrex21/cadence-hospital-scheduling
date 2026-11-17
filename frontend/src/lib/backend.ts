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

const DEFAULT_TIMING = {
  /** Don't flash a notice if the backend answers within this long. */
  graceMs: 1_200,
  retryMs: 2_500,
  pingTimeoutMs: 15_000,
  /** After this long without an answer we stop and offer a manual retry. */
  giveUpMs: 4 * 60_000,
  /** Re-send the direct wake signal this often while waiting (cheap, and it can't hurt). */
  kickEveryMs: 10_000,
  kickTimeoutMs: 90_000,
  /** Render sleeps after ~15 min without traffic; re-check a tab that was quiet for 10. */
  staleMs: 10 * 60_000,
}

/** Where the Render service lives. Overridable per deployment with VITE_BACKEND_URL
 *  (set it to an empty string to disable the direct wake call). */
const DEFAULT_BACKEND_URL = 'https://cadence-api-opro.onrender.com'

function resolveDirectUrl(): string | null {
  // Dev and tests talk to the Vite proxy only; there is no sleeping host to wake.
  if (!import.meta.env.PROD) return null
  const url = import.meta.env.VITE_BACKEND_URL ?? DEFAULT_BACKEND_URL
  return url ? url.replace(/\/+$/, '') : null
}

const config = {
  directUrl: resolveDirectUrl(),
  apiBase: API_BASE,
  timing: { ...DEFAULT_TIMING },
}

export type BackendPhase = 'idle' | 'checking' | 'waking' | 'ready' | 'failed'

export type ProbeKind =
  | 'ok'
  | 'waking' // 502/503/504: the host is up but the app is still booting
  | 'html' // Render's "service is starting" placeholder page
  | 'no-service' // Render says nothing lives at this address
  | 'proxy-error' // Vercel could not reach the API at all
  | 'http'
  | 'network'
  | 'timeout'

/** What the most recent health check actually saw — shown to the user so a long wait is never a mystery. */
export interface ProbeResult {
  ok: boolean
  kind: ProbeKind
  status?: number
  detail: string
}

export interface BackendStatus {
  phase: BackendPhase
  /** When the current check began (identifies a wake cycle). */
  startedAt: number | null
  /** True when this cycle was slow enough that the user was told the server was waking. */
  wokeAfterWait: boolean
  /** Health checks made so far in this session. */
  attempts: number
  /** Direct wake signals sent to the Render service so far. */
  kicks: number
  /** Whether the direct wake signal is enabled at all. */
  directWake: boolean
  last: ProbeResult | null
}

type CoreStatus = Pick<BackendStatus, 'phase' | 'startedAt' | 'wokeAfterWait'>

const diag: { attempts: number; kicks: number; last: ProbeResult | null } = {
  attempts: 0,
  kicks: 0,
  last: null,
}

function withDiag(core: CoreStatus): BackendStatus {
  return { ...core, ...diag, directWake: config.directUrl !== null }
}

const IDLE: BackendStatus = withDiag({ phase: 'idle', startedAt: null, wokeAfterWait: false })

let status: BackendStatus = IDLE
let lastHealthyAt = 0
let generation = 0
let inFlight: Promise<void> | null = null
let watching = false
const listeners = new Set<() => void>()

function setStatus(next: CoreStatus): void {
  status = withDiag(next)
  listeners.forEach((listener) => listener())
}

/** Re-publish the current status after the diagnostics changed (new check / new wake signal). */
function refreshDiag(): void {
  status = withDiag(status)
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

/** Defeat any CDN / browser cache between us and the API: a stale "still starting" answer
 *  must never be mistaken for the live one. */
function bust(url: string): string {
  return `${url}${url.includes('?') ? '&' : '?'}_=${Date.now()}`
}

async function probe(url: string, timeoutMs: number): Promise<ProbeResult> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const resp = await fetch(bust(url), { signal: controller.signal, cache: 'no-store' })
    const code = resp.status
    if (resp.headers.get('x-render-routing') === 'no-server') {
      return {
        ok: false,
        kind: 'no-service',
        status: code,
        detail: `Render has no service at this address (HTTP ${code}). Check the API URL in vercel.json.`,
      }
    }
    const vercelError = resp.headers.get('x-vercel-error')
    if (vercelError) {
      return {
        ok: false,
        kind: 'proxy-error',
        status: code,
        detail: `Vercel couldn't reach the API (${vercelError}, HTTP ${code}).`,
      }
    }
    if (!resp.ok) {
      if (code === 502 || code === 503 || code === 504) {
        return { ok: false, kind: 'waking', status: code, detail: `Server is still starting (HTTP ${code}).` }
      }
      return {
        ok: false,
        kind: 'http',
        status: code,
        detail:
          code === 404
            ? 'HTTP 404 from the API — its address may be wrong.'
            : `Unexpected response (HTTP ${code}).`,
      }
    }
    try {
      const body = (await resp.json()) as { status?: string }
      if (body.status === 'ok') return { ok: true, kind: 'ok', status: code, detail: 'Server is up.' }
      return { ok: false, kind: 'http', status: code, detail: 'The API answered, but not with a healthy status.' }
    } catch {
      const html = (resp.headers.get('content-type') ?? '').includes('html')
      return {
        ok: false,
        kind: html ? 'html' : 'http',
        status: code,
        detail: html
          ? "Got the host's loading page instead of the API — it is starting up."
          : 'The API returned something that is not JSON.',
      }
    }
  } catch {
    return controller.signal.aborted
      ? { ok: false, kind: 'timeout', detail: `No answer within ${Math.round(timeoutMs / 1000)}s.` }
      : { ok: false, kind: 'network', detail: "Couldn't connect to the server (network error)." }
  } finally {
    clearTimeout(timer)
  }
}

async function probeProxy(timeoutMs: number): Promise<ProbeResult> {
  const result = await probe(`${config.apiBase}/health`, timeoutMs)
  diag.attempts += 1
  diag.last = result
  refreshDiag()
  return result
}

/** Is the API actually up *through the same path real requests take* (`/api`)? Never throws. */
export async function pingBackend(timeoutMs = config.timing.pingTimeoutMs): Promise<boolean> {
  return (await probeProxy(timeoutMs)).ok
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
  setTimeout(() => controller.abort(), config.timing.kickTimeoutMs)
  diag.kicks += 1
  refreshDiag()
  fetch(bust(`${base}/health`), {
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
  }, config.timing.graceMs)

  try {
    for (;;) {
      const { ok } = await probeProxy(config.timing.pingTimeoutMs)
      if (gen !== generation) return
      if (ok) {
        lastHealthyAt = Date.now()
        setStatus({ phase: 'ready', startedAt, wokeAfterWait: status.phase === 'waking' })
        return
      }
      if (Date.now() - startedAt > config.timing.giveUpMs) {
        setStatus({ phase: 'failed', startedAt, wokeAfterWait: false })
        return
      }
      if (Date.now() - lastKick > config.timing.kickEveryMs) {
        kick()
        lastKick = Date.now()
      }
      await sleep(config.timing.retryMs)
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
  if (Date.now() - lastHealthyAt < config.timing.staleMs) return
  void begin()
}

/** Test seam — never used by app code. */
export const __test = {
  config,
  reset(): void {
    generation += 1
    inFlight = null
    diag.attempts = 0
    diag.kicks = 0
    diag.last = null
    config.directUrl = resolveDirectUrl()
    config.apiBase = API_BASE
    config.timing = { ...DEFAULT_TIMING }
    status = withDiag({ phase: 'idle', startedAt: null, wokeAfterWait: false })
    lastHealthyAt = 0
    listeners.clear()
  },
}
