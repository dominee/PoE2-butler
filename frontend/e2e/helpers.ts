import { expect, type Page } from "@playwright/test";

export async function loginViaMock(page: Page, user = "exile_one"): Promise<void> {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await page.goto("/api/auth/login");
    await expect(page.locator("h1")).toHaveText(/mock ggg/i, { timeout: 20_000 });
    await page.locator("select#user").selectOption(user);
    await page.getByRole("button", { name: /authorize/i }).click();

    await expect(page).toHaveURL(/\/app$/, { timeout: 30_000 });

    try {
      await expect(page.getByRole("button", { name: /logout/i })).toBeVisible({ timeout: 20_000 });
      return;
    } catch {
      if (attempt === 2) {
        throw new Error("Login reached /app but never became authenticated (no Logout button).");
      }
    }
  }
}
