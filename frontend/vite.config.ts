/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The frontend talks to the backend through `/api/*`, which is proxied to the
// FastAPI server in development and stripped to the backend's real routes.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Unit tests live under src/; e2e/ is Playwright's and must not be collected here.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
})
