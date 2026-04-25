import { expect, test } from "@playwright/test";
import { loginViaMock } from "./helpers";

/**
 * Smoke test: landing -> mock GGG sign-in -> /app with at least one character.
 *
 * Requires the dev docker-compose stack to be running.
 */
test("mock GGG login exposes character list", async ({ page }) => {
  await loginViaMock(page, "exile_one");
  await expect(page.getByRole("heading", { name: /characters/i })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /league/i })).not.toHaveValue("");
});
