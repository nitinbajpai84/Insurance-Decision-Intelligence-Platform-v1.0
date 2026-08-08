import { expect, test } from "@playwright/test";

test("Insight Evidence Hub exposes detailed evidence and old duplicate labels are removed", async ({ page }) => {
  await page.goto("http://127.0.0.1:3000/insight-evidence-hub");

  await expect(page.getByRole("heading", { name: "Insight Evidence Hub" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Full answer traceability" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Related Tables" })).toBeVisible({ timeout: 45000 });
  await expect(page.getByRole("heading", { name: "Related Columns" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Semantic Context" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Underlying Models" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "SQL Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Technical Diagnostics" })).toBeVisible();

  const body = await page.locator("body").innerText();
  expect(body).not.toContain("AI Intelligence v1.0");
  expect(body).not.toContain("Model Insights");
  expect(body.toLowerCase()).not.toContain("copilot");

  await page.screenshot({ path: "frontend_insight_evidence_hub_final.png", fullPage: true });
});
