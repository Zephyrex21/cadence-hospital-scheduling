// Builds the Content-Security-Policy for vercel.json from the REAL dist/index.html, so the
// hash of the inline theme script can never drift out of sync with the page.
//
//   node scripts/csp.mjs          print the policy
//   node scripts/csp.mjs --check  exit 1 if vercel.json's policy is stale (run after `build`)
//   node scripts/csp.mjs --write  update vercel.json in place
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'

const html = readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8')
const inline = [...html.matchAll(/<script(?![^>]*\ssrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1])
const hashes = inline.map((code) => `'sha256-${createHash('sha256').update(code).digest('base64')}'`)

// The app also pings the Render backend directly (to wake it from sleep), so its origin must be
// allowed in connect-src. It is taken from the /api rewrite so there is one source of truth.
const vercelPath = new URL('../vercel.json', import.meta.url)
const config = JSON.parse(readFileSync(vercelPath, 'utf8'))
const apiRewrite = config.rewrites?.find((r) => r.source.startsWith('/api/'))
const backendOrigin = apiRewrite ? new URL(apiRewrite.destination.replace(':path*', '')).origin : ''

export const policy = [
  "default-src 'self'",
  `script-src 'self' ${hashes.join(' ')}`.trim(),
  "style-src 'self' 'unsafe-inline'", // framer-motion / react set inline style attributes
  "img-src 'self' data: blob:",
  "font-src 'self'",
  `connect-src 'self' ${backendOrigin}`.trim(), // /api rewrite + direct wake-up ping
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join('; ')

const current = config.headers?.[0]?.headers?.find((h) => h.key === 'Content-Security-Policy')?.value

if (process.argv.includes('--write')) {
  const entry = config.headers[0].headers.find((h) => h.key === 'Content-Security-Policy')
  entry.value = policy
  writeFileSync(vercelPath, JSON.stringify(config, null, 2) + '\n')
  console.log('vercel.json updated')
} else if (process.argv.includes('--check')) {
  if (current !== policy) {
    console.error('CSP in vercel.json is stale. Run: node scripts/csp.mjs --write')
    process.exit(1)
  }
  console.log(`CSP ok (${inline.length} inline script hash${inline.length === 1 ? '' : 'es'})`)
} else {
  console.log(policy)
}
