// Stand-in for Vercel (:4100 static + /api proxy) and the direct Render URL (:4101).
// The "Render service" sleeps: it only wakes WAKE_MS after the FIRST request reaches it.
const http = require('http'), fs = require('fs'), path = require('path')
const WAKE_MS = Number(process.env.WAKE_MS || 20000), DIST = '/tmp/dist-test'
const csp = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).headers[0].headers
  .find(h => h.key === 'Content-Security-Policy').value
  .replace('https://cadence-api-opro.onrender.com', 'http://127.0.0.1:4101')
let first = null; const log = []
const t0 = Date.now(); const stamp = () => ((Date.now() - t0) / 1000).toFixed(1)
const awake = () => first !== null && Date.now() - first >= WAKE_MS
function hit(kind, req) { if (first === null) first = Date.now(); log.push(`${stamp()}s ${kind} ${req.method} ${req.url} ${awake() ? '(awake)' : '(asleep)'}`); fs.writeFileSync('/tmp/sleepy.log', log.join('\n')) }
function forward(req, res, p) {
  const up = http.request({ host: '127.0.0.1', port: 8001, path: p, method: req.method, headers: req.headers }, r => { res.writeHead(r.statusCode, r.headers); r.pipe(res) })
  up.on('error', () => { res.writeHead(502); res.end('bad gateway') }); req.pipe(up)
}
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.json': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon' }
http.createServer((req, res) => {
  if (req.url.startsWith('/api/')) {
    hit('PROXY ', req)
    if (!awake()) { res.writeHead(503, { 'Content-Type': 'text/html' }); return res.end('<html>Service Unavailable</html>') }
    return forward(req, res, req.url.slice(4))
  }
  let f = path.join(DIST, decodeURIComponent(req.url.split('?')[0])); if (!f.startsWith(DIST) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) f = path.join(DIST, 'index.html')
  res.writeHead(200, { 'Content-Type': types[path.extname(f)] || 'application/octet-stream', 'Content-Security-Policy': csp, 'X-Content-Type-Options': 'nosniff' })
  fs.createReadStream(f).pipe(res)
}).listen(4100)
http.createServer((req, res) => {
  hit('DIRECT', req)
  res.writeHead(awake() ? 200 : 503, { 'Content-Type': 'text/html' }); res.end(awake() ? '{"status":"ok"}' : '<html>starting</html>')
}).listen(4101)
