import { expect, test } from "@playwright/test";

/**
 * Smoke test: landing -> mock GGG sign-in -> /app with at least one character.
 *
 * Requires the dev docker-compose stack to be running.
 */
test("mock GGG login exposes character list", async ({ page }) => {
  // Start directly at backend auth entrypoint to avoid frontend bootstrap timing races in CI.
  await page.goto("/api/auth/login");

  // Mock GGG renders a form where we pick a fixture user.
  await expect(page.locator("h1")).toHaveText(/mock ggg/i);
  await page.locator("select#user").selectOption("exile_one");
  await page.getByRole("button", { name: /authorize/i }).click();

  // Back on the app.
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("button", { name: /logout/i })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: /characters/i })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /league/i })).not.toHaveValue("");
});
