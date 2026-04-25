import { expect, type Page } from "@playwright/test";

async function waitForAuthenticatedSession(page: Page, timeoutMs: number): Promise<boolean> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const status = await page.evaluate(async () => {
      try {
        const res = await fetch("/api/me", { credentials: "include" });
        return res.status;
      } catch {
        return 0;
      }
    });
    if (status === 200) {
      return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

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

    // In CI, first /api/me can race with cookie/session propagation and AppShell
    // caches the signed-out branch (`retry: false`). Wait for /api/me=200, then
    // hard-reload to re-run app bootstrap under authenticated session.
    if (await waitForAuthenticatedSession(page, 20_000)) {
      await page.reload();
      if (await isAuthenticated()) {
        return;
      }
    }

    // Last resort: one more reload before full login retry.
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
