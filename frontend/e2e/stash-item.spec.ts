import { expect, test } from "@playwright/test";
import { loginViaMock } from "./helpers";

/**
 * Post-login: Stash view, tab strip, and item detail pane.
 * Requires the dev docker-compose stack (see playwright.config.ts); base URL
 * should match Traefik (e.g. http://app.dev.hideoutbutler.com with Hosts file).
 */
test("mock GGG login: browse stash and open item detail", async ({ page }) => {
  test.setTimeout(120_000);

  await loginViaMock(page, "exile_one");
  await expect(page.getByRole("heading", { name: /characters/i })).toBeVisible();
  await page.getByRole("combobox", { name: /league/i }).selectOption("Dawn of the Hunt");

  await page.getByRole("button", { name: "Stash" }).click();
  await expect(page.getByRole("button", { name: /refresh stash/i })).toBeVisible({
    timeout: 20_000,
  });

  const noTabs = page.getByText(/no stash tabs yet/i);
  if (await noTabs.isVisible().catch(() => false)) {
    // Profile refresh (not “Refresh stash”); repopulates stash list from GGG.
    await page.getByRole("button", { name: /^Refresh$/ }).click();
    await expect(noTabs).toBeHidden({ timeout: 60_000 });
  }

  const tablist = page.getByRole("tablist", { name: /stash tabs/i });
  await expect(tablist).toBeVisible({ timeout: 60_000 });
  const gearTab = page.getByRole("tab", { name: /gear dump/i });
  if (await gearTab.isVisible().catch(() => false)) {
    await gearTab.click();
  } else {
    await page.getByTestId("stash-tab").first().click();
  }

  const itemButton = page.getByRole("button", { name: /agony beads/i });
  await expect(itemButton).toBeVisible();
  await itemButton.click();

  const detail = page.getByRole("complementary", { name: "Item details" });
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("Agony Beads");
});
