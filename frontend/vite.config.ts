import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/journeys': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    // e2e/ holds Playwright specs (run via `npx playwright test`), not
    // Vitest ones — exclude them so Vitest doesn't try to execute them
    // against the `@playwright/test` test()/expect() globals.
    exclude: ['**/node_modules/**', '**/e2e/**'],
  },
})
