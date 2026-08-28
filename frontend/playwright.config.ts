import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from '@playwright/test'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const backendDir = path.resolve(__dirname, '..', 'backend')
const backendPython = path.join(backendDir, '.venv', 'bin', 'python')
export const E2E_DB_PATH = path.join(backendDir, '.e2e_console.db')
export const E2E_DB_URL = `sqlite:///${E2E_DB_PATH}`

export default defineConfig({
  testDir: './e2e',
  webServer: [
    {
      command: `rm -f "${E2E_DB_PATH}" && "${backendPython}" -m uvicorn journey.api.main:app --port 8000`,
      cwd: backendDir,
      env: { JOURNEY_DB_URL: E2E_DB_URL },
      url: 'http://localhost:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 30000,
    },
  ],
  use: {
    baseURL: 'http://localhost:5173',
  },
})
