import { expect, test } from "@playwright/test";

test("Know Your Agent screen shows distribution analytics, risks, actions, and evidence", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000");

  await page.getByRole("button", { name: "Know Your Agent" }).click();

  await expect(page.getByText("A distribution intelligence workspace")).toBeVisible();
  await page.getByPlaceholder("Search by agent name, agent code, branch, or region").fill("Aaron");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByText("Agent search")).toBeVisible();
  await expect(page.getByText("Monthly premium")).toBeVisible();
  await expect(page.getByText("MAPA metrics")).toBeVisible();
  await expect(page.getByText("Customer portfolio")).toBeVisible();
  await expect(page.getByText("Agent movement")).toBeVisible();
  await expect(page.getByText("Agent risk")).toBeVisible();
  await expect(page.getByText("Recommended manager actions")).toBeVisible();
  await expect(page.getByText("Evidence panel")).toBeVisible();
  await expect(page.getByText("Nitin Bajpai").first()).toBeVisible();
  expect(await page.locator("body").innerText()).toContain("Insurance intelligence platform");
  expect(await page.locator("body").innerText()).not.toContain("Co" + "pilot");

  await page.screenshot({ path: "frontend_agent_360_final.png", fullPage: true });
});
