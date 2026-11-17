# Cold-start (wake-up) browser test

Reproduces a sleeping free-tier backend and checks, in a real Firefox, that opening the app
wakes it. `sleepy.js` serves the built frontend with the production CSP, proxies `/api` to the
real API, and only "wakes" `WAKE_MS` after the first request reaches it. `browser_test.py` (selenium)
opens the page and asserts: banner + diagnostics appear, the backend is hit immediately (directly
and via the proxy), the app reports "Service is live", and sign-in works.

```bash
cd frontend && VITE_BACKEND_URL=http://127.0.0.1:4101 pnpm exec vite build --outDir /tmp/dist-test
# run the real API on :8001, then:
WAKE_MS=20000 node tools/wake-test/sleepy.js frontend/vercel.json &
python3 tools/wake-test/browser_test.py   # needs selenium + firefox + geckodriver
```
Fast, browser-free coverage of the same flow: `pnpm exec vitest run src/lib/backend.integration.test.ts`.
