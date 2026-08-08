import { expect, test } from "@playwright/test";

test("Agent Performance Tracking dashboard shows KPIs, leaderboard, clusters, MDRT, rising stars, risks, coaching, and evidence", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000");

  await page.getByRole("button", { name: "Agent Performance Tracking" }).click();

  await expect(page.getByText("Track agent productivity")).toBeVisible();
  await expect(page.getByText("Total agents")).toBeVisible();
  await expect(page.getByText("Agent leaderboard")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Rising stars" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "MDRT agents" })).toBeVisible();
  await expect(page.getByText("MAPA productivity")).toBeVisible();
  await expect(page.getByText("Performance trends")).toBeVisible();
  await expect(page.getByText("Agent peer clusters")).toBeVisible();
  await expect(page.getByText("Risk alerts")).toBeVisible();
  await expect(page.getByText("Coaching recommendations")).toBeVisible();
  await expect(page.getByText("Data evidence")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Diane Lyons" })).toBeVisible({ timeout: 20000 });
  await expect(page.locator("article").filter({ hasText: "Maurice Price" }).first()).toBeVisible({ timeout: 20000 });
  expect(await page.locator("body").innerText()).not.toContain("Co" + "pilot");

  await page.screenshot({ path: "frontend_agent_performance_tracking_final.png", fullPage: true });
});
