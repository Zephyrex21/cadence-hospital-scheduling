import { defineConfig, devices } from '@playwright/test'

/**
 * Screenshot harness (separate from the signature-flow gate). Boots the same
 * backend + Vite dev server and captures the key screens for self-review.
 * Run: pnpm exec playwright test --config playwright.shots.config.ts
 */
export default defineConfig({
  testDir: './e2e-shots',
  timeout: 180_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
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
