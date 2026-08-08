import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const videoDir = path.join(root, "docs", "demo", "videos");
const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3000";

async function main() {
  await fs.mkdir(videoDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: videoDir, size: { width: 1280, height: 720 } }
  });
  const page = await context.newPage();

  await page.goto(frontendUrl, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(15000);
  for (const label of ["Campaign Effectiveness", "Agent Performance Tracking", "Policy Lapse Risk", "Know Your Customer", "Know Your Agent", "AI Intelligence"]) {
    await page.getByRole("button", { name: label }).first().click();
    await page.waitForTimeout(12000);
  }
  await page.getByPlaceholder("Type any insurance business question").fill("Which agents need coaching this month?");
  await page.getByRole("button", { name: "Generate Insight" }).click();
  await page.waitForTimeout(36000);
  await page.getByRole("button", { name: "View Full Evidence" }).click();
  await page.waitForTimeout(30000);

  const video = page.video();
  await context.close();
  await browser.close();
  console.log(JSON.stringify({ video_path: video ? await video.path() : "" }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

