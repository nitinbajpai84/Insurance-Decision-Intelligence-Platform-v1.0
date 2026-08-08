import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const root = process.cwd();
const artifactDir = path.join(root, "demo_artifacts");
const screenshotDir = path.join(artifactDir, "screenshots");
const videoDir = path.join(artifactDir, "videos");

await fs.mkdir(screenshotDir, { recursive: true });
await fs.mkdir(videoDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  recordVideo: {
    dir: videoDir,
    size: { width: 1280, height: 720 }
  }
});
const page = await context.newPage();

async function pause(ms = 6500) {
  await page.waitForTimeout(ms);
}

async function snap(name) {
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: false });
}

async function clickNav(label) {
  const button = page.getByRole("button", { name: label }).first();
  await button.waitFor({ state: "visible", timeout: 20000 });
  await button.click();
  await pause();
}

await page.goto("http://127.0.0.1:3000", { waitUntil: "domcontentloaded" });
await pause(8000);
await snap("01-home");

await clickNav("Know Your Customer");
await snap("02-know-your-customer");

await clickNav("Know Your Agent");
await snap("03-know-your-agent");

await clickNav("Campaign Effectiveness");
await snap("04-campaign-effectiveness");

await clickNav("Agent Performance Tracking");
await snap("05-agent-performance-tracking");

await clickNav("Policy Lapse Risk");
await snap("06-policy-lapse-risk");

await clickNav("AI Intelligence");
await pause(3000);
const selects = page.locator("select");
const selectCount = await selects.count();
if (selectCount > 0) {
  await selects.nth(selectCount - 1).selectOption({ label: "Agency Manager" }).catch(() => {});
}
const questionInput = page.getByPlaceholder("Type any insurance business question");
await questionInput.fill("Which agents need coaching this month?");
await page.getByRole("button", { name: "Generate Insight" }).click();
await page.waitForTimeout(26000);
await snap("07-ai-intelligence-validated-answer");

await page.getByRole("button", { name: "View Full Evidence" }).click();
await page.waitForTimeout(9000);
await snap("08-insight-evidence-hub");

await clickNav("Agent Performance Tracking");
await pause(6000);
await clickNav("AI Intelligence");
await pause(8000);

const video = page.video();
await context.close();
await browser.close();

const videoPath = video ? await video.path() : "";
const manifest = {
  created_at: new Date().toISOString(),
  video_path: videoPath,
  screenshots: (await fs.readdir(screenshotDir)).map((file) => path.join(screenshotDir, file))
};
await fs.writeFile(path.join(artifactDir, "demo_manifest.json"), JSON.stringify(manifest, null, 2));
console.log(JSON.stringify(manifest, null, 2));
