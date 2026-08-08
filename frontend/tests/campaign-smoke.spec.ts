import { expect, test } from "@playwright/test";

test("Campaign Effectiveness screen supports filters, funnel, conversion analytics, ML insights, recommendations, and lineage", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000");

  await page.getByRole("button", { name: "Campaign Effectiveness" }).click();

  await expect(page.getByText("A marketing intelligence workspace")).toBeVisible();
  await expect(page.getByText("Campaign search")).toBeVisible();
  await expect(page.locator("form").getByText("Medium", { exact: true })).toBeVisible();

  await page.getByPlaceholder("Search by campaign name, code, product, or objective").fill("Health");
  await page.getByRole("button", { name: "Filter" }).click();

  await expect(page.getByText("Campaign overview")).toBeVisible();
  await expect(page.getByText("Funnel metrics")).toBeVisible();
  await expect(page.getByText("Conversion analytics")).toBeVisible();
  await expect(page.getByText("Segment performance")).toBeVisible();
  await expect(page.getByText("ML-driven insights")).toBeVisible();
  await expect(page.getByText("Recommendations")).toBeVisible();
  await expect(page.getByText("Data lineage")).toBeVisible();
  await expect(page.getByRole("cell", { name: "campaign_targets" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "campaign_responses" })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("Co" + "pilot");

  await page.screenshot({ path: "frontend_campaign_effectiveness_final.png", fullPage: true });
});
