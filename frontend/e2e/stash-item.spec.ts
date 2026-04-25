import { expect, test } from "@playwright/test";

/**
 * Post-login: Stash view, tab strip, and item detail pane.
 * Requires the dev docker-compose stack (see playwright.config.ts); base URL
 * should match Traefik (e.g. http://app.dev.hideoutbutler.com with Hosts file).
 */
test("mock GGG login: browse stash and open item detail", async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /poe2 hideout butler/i })).toBeVisible({
    timeout: 15_000,
  });
  await page.getByRole("link", { name: /sign in with ggg/i }).click();
  await expect(page.locator("h1")).toHaveText(/mock ggg/i);
  await page.locator("select#user").selectOption("exile_one");
  await page.getByRole("button", { name: /authorize/i }).click();

  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByText("Pewpewer")).toBeVisible();

  await page.getByRole("button", { name: "Stash" }).click();
  const stash = page.getByRole("section", { name: "Stash" });
  await expect(stash).toBeVisible();

  const noTabs = page.getByText(/no stash tabs yet/i);
  if (await noTabs.isVisible().catch(() => false)) {
    // Profile refresh (not “Refresh stash”); repopulates stash list from GGG.
    await page.getByRole("button", { name: /^Refresh$/ }).click();
    await expect(noTabs).toBeHidden({ timeout: 60_000 });
  }

  const gearTab = page.getByRole("tab", { name: /gear dump/i });
  await expect(gearTab).toBeVisible({ timeout: 60_000 });
  await gearTab.click();

  const itemButton = page.getByRole("button", { name: /item agony beads/i });
  await expect(itemButton).toBeVisible();
  await itemButton.click();

  const detail = page.getByRole("complementary", { name: "Item details" });
  await expect(detail).toBeVisible();
  await expect(detail.getByText("Agony Beads", { exact: true })).toBeVisible();
});
