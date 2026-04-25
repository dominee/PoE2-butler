import { expect, type Page } from "@playwright/test";

export async function loginViaMock(page: Page, user = "exile_one"): Promise<void> {
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await page.goto("/api/auth/login");
    await expect(page.locator("h1")).toHaveText(/mock ggg/i, { timeout: 20_000 });
    await page.locator("select#user").selectOption(user);
    await page.getByRole("button", { name: /authorize/i }).click();

    await expect(page).toHaveURL(/\/app$/, { timeout: 45_000 });

    const logoutBtn = page.getByRole("button", { name: /logout/i });
    const signedOutPanel = page.getByRole("link", { name: /sign in with ggg/i });
    const isAuthenticated = async () => {
      try {
        await expect(logoutBtn).toBeVisible({ timeout: 15_000 });
        return true;
      } catch {
        return false;
      }
    };

    if (await isAuthenticated()) {
      return;
    }

    // In CI, the first /app paint can race with cookie/session availability.
    // A hard reload replays requests with final cookies and resolves this race.
    await page.reload();
    if (await isAuthenticated()) {
      return;
    }

    if (attempt === 2) {
      if (await signedOutPanel.isVisible().catch(() => false)) {
        throw new Error("Login reached /app but UI remained signed out after retry.");
      }
      throw new Error("Login reached /app but never became authenticated (no Logout button).");
    }
  }
}
