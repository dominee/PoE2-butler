import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config for end-to-end smoke tests.
 *
 * Expects the dev stack to be running (via `docker compose -f
 * deploy/compose/docker-compose.dev.yml up`). Override the base URL via
 * `PLAYWRIGHT_BASE_URL` when pointing at a non-local environment.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: process.env.CI ? 1 : undefined,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://app.dev.hideoutbutler.com",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
