import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end config for Cadence. Boots two servers: the FastAPI backend against a
 * throwaway SQLite database seeded with the deterministic signature-flow data,
 * and the Vite dev server (whose `/api` proxy forwards to the backend, so the
 * browser sees one origin and no CORS is involved).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run python -m app.e2e_server',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        CADENCE_DATABASE_URL: 'sqlite+pysqlite:///./e2e.db',
        CADENCE_CORS_ORIGINS: 'http://localhost:5173',
        CADENCE_JWT_SECRET: 'e2e-only-insecure-secret-key-0123456789abcd',
        CADENCE_ENV: 'e2e',
      },
    },
    {
      command: 'pnpm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
})
