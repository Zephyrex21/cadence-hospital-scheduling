// @vitest-environment node
/**
 * Real-network test of the wake-up flow: no fetch mocks. A tiny HTTP server plays the sleeping
 * Render service (it only "wakes" some time after the FIRST request reaches it, like the real
 * thing) and another plays Vercel's /api proxy in front of it. We then "open the app"
 * (`startBackendCheck`) and verify that
 *   1. the very first request reaches the backend almost immediately, directly and via the proxy,
 *   2. it keeps trying until the backend is up and then reports ready,
 *   3. the same holds for each way a cold host misbehaves (503s, an HTML placeholder, a hung
 *      connection) and even when a CDN caches the stale "still starting" answer.
 */
import http from 'node:http'
import type { AddressInfo } from 'node:net'

import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { __test, getBackendStatus, startBackendCheck } from './backend'

type Behaviour = 'refuse-503' | 'html-200' | 'hang'

const WAKE_MS = 2_500

interface Capture {
  status: number
  type: string
  body: string
  destroyed: boolean
  writeHead(status: number, headers: Record<string, string>): void
  end(body: string): void
  on(event: string, listener: () => void): unknown
}

interface Servers {
  renderUrl: string
  proxyUrl: string
  hits: { at: number; via: 'direct' | 'proxy'; url: string }[]
  close(): Promise<void>
}

async function startServers(behaviour: Behaviour, opts: { cdnCaches?: boolean } = {}): Promise<Servers> {
  const hits: Servers['hits'] = []
  let firstHitAt: number | null = null
  const awake = () => firstHitAt !== null && Date.now() - firstHitAt >= WAKE_MS

  /** The sleeping app: ANY request starts the boot; it answers properly once booted. */
  const respond = (res: http.ServerResponse, onDone?: () => void) => {
    const send = () => {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
      res.end(JSON.stringify({ status: 'ok', service: 'cadence-api' }))
      onDone?.()
    }
    if (awake()) return send()
    if (behaviour === 'hang') {
      const wait = setInterval(() => {
        if (awake()) {
          clearInterval(wait)
          if (!res.destroyed) send()
        }
      }, 50)
      res.on('close', () => clearInterval(wait))
      return
    }
    if (behaviour === 'html-200') {
      res.writeHead(200, { 'Content-Type': 'text/html' })
      res.end('<html><body>Your service is waking up…</body></html>')
    } else {
      res.writeHead(503, { 'Content-Type': 'text/html' })
      res.end('<html>Service Unavailable</html>')
    }
    onDone?.()
  }

  const render = http.createServer((req, res) => {
    hits.push({ at: Date.now(), via: 'direct', url: req.url ?? '' })
    firstHitAt ??= Date.now()
    respond(res)
  })

  // Vercel stand-in. With `cdnCaches`, the first answer for a URL is cached for 60 s —
  // so a probe that always asks for the identical URL would be stuck on the stale "503" forever.
  const cache = new Map<string, { status: number; type: string; body: string; until: number }>()
  const proxy = http.createServer((req: http.IncomingMessage, res: http.ServerResponse) => {
    hits.push({ at: Date.now(), via: 'proxy', url: req.url ?? '' })
    firstHitAt ??= Date.now()
    const key = req.url ?? ''
    const cached = cache.get(key)
    if (opts.cdnCaches && cached && cached.until > Date.now()) {
      res.writeHead(cached.status, { 'Content-Type': cached.type })
      return void res.end(cached.body)
    }
    const capture: Capture = {
      status: 0,
      type: '',
      body: '',
      destroyed: false,
      writeHead(status, headers) {
        capture.status = status
        capture.type = headers['Content-Type'] ?? ''
        res.writeHead(status, headers)
      },
      end(body) {
        capture.body = body
        if (opts.cdnCaches && capture.status !== 200) {
          cache.set(key, { status: capture.status, type: capture.type, body, until: Date.now() + 60_000 })
        }
        res.end(body)
      },
      on: (event, listener) => res.on(event, listener),
    }
    Object.defineProperty(capture, 'destroyed', { get: () => res.destroyed })
    const fake = capture as unknown as http.ServerResponse
    respond(fake)
  })

  const listen = (s: http.Server) =>
    new Promise<string>((resolve) => {
      s.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${(s.address() as AddressInfo).port}`))
    })
  const [renderUrl, proxyUrl] = [await listen(render), await listen(proxy)]
  return {
    renderUrl,
    proxyUrl,
    hits,
    close: () =>
      new Promise((resolve) => {
        render.closeAllConnections()
        proxy.closeAllConnections()
        render.close(() => proxy.close(() => resolve()))
      }),
  }
}

describe('opening the app wakes a sleeping backend (real HTTP, no mocks)', () => {
  let servers: Servers | null = null

  beforeEach(() => {
    __test.reset()
  })
  afterEach(async () => {
    __test.reset()
    await servers?.close()
    servers = null
  })

  const scenarios: { name: string; behaviour: Behaviour; cdnCaches?: boolean }[] = [
    { name: 'answers 503 while booting', behaviour: 'refuse-503' },
    { name: "serves an HTML 'waking up' page with status 200", behaviour: 'html-200' },
    { name: 'holds the connection open until it has booted', behaviour: 'hang' },
    { name: 'sits behind a CDN that caches the stale 503', behaviour: 'refuse-503', cdnCaches: true },
  ]

  for (const scenario of scenarios) {
    it(`wakes in a few seconds when the host ${scenario.name}`, async () => {
      servers = await startServers(scenario.behaviour, { cdnCaches: scenario.cdnCaches })
      __test.config.directUrl = servers.renderUrl
      __test.config.apiBase = servers.proxyUrl
      __test.config.timing = {
        ...__test.config.timing,
        graceMs: 150,
        retryMs: 250,
        pingTimeoutMs: 2_000,
        kickEveryMs: 1_000,
        giveUpMs: 20_000,
      }

      const opened = Date.now()
      await startBackendCheck()
      const elapsed = Date.now() - opened

      // 1. the frontend reached the backend straight away, by both routes
      const first = servers.hits[0]
      expect(first.at - opened).toBeLessThan(500)
      expect(servers.hits.some((h) => h.via === 'direct' && h.url.startsWith('/health'))).toBe(true)
      expect(servers.hits.some((h) => h.via === 'proxy' && h.url.startsWith('/health'))).toBe(true)

      // 2. it kept trying and noticed the moment the backend came up
      const status = getBackendStatus()
      expect(status.phase).toBe('ready')
      expect(status.wokeAfterWait).toBe(true)
      expect(status.attempts).toBeGreaterThanOrEqual(2)
      expect(status.last?.ok).toBe(true)
      expect(elapsed).toBeGreaterThanOrEqual(WAKE_MS - 100)
      expect(elapsed).toBeLessThan(WAKE_MS + 3_500) // woke + at most one retry/timeout later

      // 3. every probe carried a unique cache-busting query
      const probes = servers.hits.filter((h) => h.via === 'proxy').map((h) => h.url)
      expect(new Set(probes).size).toBe(probes.length)
    }, 30_000)
  }

  it('says what it saw while it waits, so a long wait is never a mystery', async () => {
    servers = await startServers('refuse-503')
    __test.config.directUrl = servers.renderUrl
    __test.config.apiBase = servers.proxyUrl
    __test.config.timing = { ...__test.config.timing, graceMs: 100, retryMs: 200, kickEveryMs: 500 }

    const seen = new Set<string>()
    const unsubscribe = (await import('./backend')).subscribeBackend(() => {
      const last = getBackendStatus().last
      if (last) seen.add(last.kind)
    })
    await startBackendCheck()
    unsubscribe()

    expect(seen.has('waking')).toBe(true) // "server is still starting (HTTP 503)"
    expect(seen.has('ok')).toBe(true)
    expect(getBackendStatus().kicks).toBeGreaterThanOrEqual(2) // re-sent while waiting
  }, 30_000)

  it('stops with a clear reason when the API address is simply wrong', async () => {
    // Nothing is listening here: the proxy URL points at a closed port.
    __test.config.directUrl = null
    __test.config.apiBase = 'http://127.0.0.1:9'
    __test.config.timing = {
      ...__test.config.timing,
      graceMs: 50,
      retryMs: 100,
      pingTimeoutMs: 500,
      giveUpMs: 1_500,
    }
    await startBackendCheck()
    const status = getBackendStatus()
    expect(status.phase).toBe('failed')
    expect(status.last?.kind).toBe('network')
    expect(status.directWake).toBe(false)
  }, 15_000)
})
