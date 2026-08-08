import { expect, test } from "@playwright/test";

test("Know Your Customer screen supports search, recommendations, lineage, and client wording", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000");

  await page.getByRole("button", { name: "Know Your Customer" }).click();
  await expect(page.getByText("A customer 360 workspace")).toBeVisible();

  await page.getByPlaceholder("Search by name, customer ID, or policy number").fill("Aaron");
  await page.getByRole("button", { name: "Search" }).click();

  await expect(page.getByText("Customer search")).toBeVisible();
  await expect(page.getByText("Policy portfolio")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recommended action" })).toBeVisible();
  await expect(page.getByText("Evidence and data lineage")).toBeVisible();
  await expect(page.getByText("AI Intelligence").first()).toBeVisible();
  expect(await page.locator("body").innerText()).not.toContain("Co" + "pilot");

  await page.screenshot({ path: "frontend_kyc_customer_360_final.png", fullPage: true });
});
