import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: 1,          // serial — avoids race conditions on shared SQLite in CI
  reporter: process.env.CI ? 'github' : 'list',

  use: {
    baseURL: 'http://localhost:5173',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  // Start Vite dev server automatically for local runs.
  // In CI the frontend is pre-built and served via `vite preview`.
  webServer: {
    command: process.env.CI ? 'npm run preview -- --port 5173' : 'npm run dev',
    port: 5173,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
