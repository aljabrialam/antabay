import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { E2E_DB_URL } from '../playwright.config'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const backendDir = path.resolve(__dirname, '..', '..', 'backend')
const backendPython = path.join(backendDir, '.venv', 'bin', 'python')

interface SeedResult {
  journey_id: string
  request_id?: string
}

/**
 * Seeds a brand-new journey (fresh UUID) directly into the same SQLite file
 * the running backend server reads from, via `scripts/seed_console_fixture.py`.
 * Each call creates its own journey, so tests can run in any order without
 * cleaning up after each other (Constitution Principle XIII).
 */
export function seedJourney(scenario: 'live' | 'auth' | 'replay'): SeedResult {
  const output = execFileSync(
    backendPython,
    ['-m', 'scripts.seed_console_fixture', scenario],
    { cwd: backendDir, env: { ...process.env, JOURNEY_DB_URL: E2E_DB_URL } },
  )
  return JSON.parse(output.toString().trim()) as SeedResult
}
