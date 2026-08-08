import { expect, test } from "@playwright/test";

test("AI Intelligence supports role-aware natural language insight flow", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000/ai-intelligence");

  await expect(page.getByRole("heading", { name: "AI Intelligence" }).first()).toBeVisible();
  await expect(page.getByText("Ask insurance business questions using live data")).toBeVisible();
  await expect(page.getByText("Try asking")).toBeVisible();

  await page.getByRole("combobox").first().selectOption("Agency Manager");
  await expect(page.getByRole("button", { name: "Which agents need coaching this month?" })).toBeVisible();

  await page.getByPlaceholder("Type any insurance business question").fill("Which agents need coaching this month?");
  await page.getByRole("button", { name: "Generate Insight" }).click();

  await expect(page.getByRole("heading", { name: "Answer summary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Key data points used" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "SQL generated" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence summary" })).toBeVisible({ timeout: 90000 });
  await expect(page.getByRole("heading", { name: "Result preview" })).toBeVisible();
  await expect(page.getByRole("button", { name: "View Full Evidence" })).toBeVisible();

  const body = await page.locator("body").innerText();
  expect(body).not.toContain("AI Intelligence v1.0");
  expect(body).not.toContain("Model Insights");
  expect(body.toLowerCase()).not.toContain("copilot");

  await page.screenshot({ path: "frontend_ai_intelligence_final.png", fullPage: true });
});
