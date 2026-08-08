import { expect, test } from "@playwright/test";

test("Policy Lapse Risk dashboard shows decision sections from live lapse data", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000");

  await page.getByRole("button", { name: "Policy Lapse Risk" }).click();

  await expect(page.getByText("A retention decision intelligence product")).toBeVisible();
  await expect(page.getByText("Policies at risk")).toBeVisible();
  await expect(page.getByText("Lapse hotspots")).toBeVisible();
  await expect(page.getByText("Top products at risk")).toBeVisible();
  await expect(page.getByText("Top customers at risk")).toBeVisible();
  await expect(page.getByText("Associated agents")).toBeVisible();
  await expect(page.getByText("Root cause analysis")).toBeVisible();
  await expect(page.getByText("Cross-sell opportunities")).toBeVisible();
  await expect(page.getByText("Retention action center")).toBeVisible();
  await expect(page.getByText("AI explanation panel")).toBeVisible();
  await expect(page.getByText("Scenario simulator")).toBeVisible();
  await expect(page.getByText("Schema additions proposed")).toBeVisible();
  await expect(page.getByText("ML enhancements proposed")).toBeVisible();
  await expect(page.locator("article").filter({ hasText: "Evergreen Wealth Multi-Currency Plan" }).first()).toBeVisible({ timeout: 20000 });

  expect(await page.locator("body").innerText()).not.toContain("Co" + "pilot");

  await page.screenshot({ path: "frontend_policy_lapse_risk_final.png", fullPage: true });
});
