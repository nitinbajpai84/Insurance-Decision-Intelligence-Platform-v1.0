import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(new URL("../frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const root = process.cwd();
const artifactDir = path.join(root, "docs", "demo");
const screenshotDir = path.join(artifactDir, "screenshots");
const videoDir = path.join(artifactDir, "videos");
const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3000";

await fs.mkdir(screenshotDir, { recursive: true });
await fs.mkdir(videoDir, { recursive: true });

async function pause(page, ms) {
  await page.waitForTimeout(ms);
}

async function snap(page, name) {
  const file = path.join(screenshotDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  return file;
}

async function clickNav(page, label, waitMs = 12000) {
  const button = page.getByRole("button", { name: label }).first();
  await button.waitFor({ state: "visible", timeout: 20000 });
  await button.click();
  await pause(page, waitMs);
}

async function gotoRoute(page, route, waitMs = 12000) {
  console.log(`Opening ${route}`);
  await page.goto(`${frontendUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await pause(page, waitMs);
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    recordVideo: {
      dir: videoDir,
      size: { width: 1280, height: 720 }
    }
  });
  const page = await context.newPage();
  const screenshots = [];

  page.setDefaultTimeout(45000);

  await gotoRoute(page, "/", 15000);
  screenshots.push(await snap(page, "01-home-executive-command-center"));

  await gotoRoute(page, "/?view=campaign", 18000);
  screenshots.push(await snap(page, "02-campaign-effectiveness"));

  await gotoRoute(page, "/?view=agent-performance", 18000);
  screenshots.push(await snap(page, "03-agent-performance-tracking"));

  await gotoRoute(page, "/?view=lapse-risk", 18000);
  screenshots.push(await snap(page, "04-policy-lapse-risk"));

  await gotoRoute(page, "/?view=customer", 9000);
  screenshots.push(await snap(page, "05-know-your-customer"));

  await gotoRoute(page, "/?view=agent", 9000);
  screenshots.push(await snap(page, "06-know-your-agent"));

  await gotoRoute(page, "/ai-intelligence", 8000);
  const selects = page.locator("select");
  const selectCount = await selects.count();
  if (selectCount > 0) {
    await selects.nth(selectCount - 1).selectOption({ label: "Agency Manager" }).catch(() => {});
  }
  const questionInput = page.getByPlaceholder("Type any insurance business question");
  await questionInput.fill("Which agents need coaching this month?");
  await pause(page, 2500);
  await page.getByRole("button", { name: "Generate Insight" }).click();
  await pause(page, 30000);
  screenshots.push(await snap(page, "07-ai-intelligence-validated-answer"));

  const evidenceButton = page.getByRole("button", { name: "View Full Evidence" });
  await evidenceButton.waitFor({ state: "visible", timeout: 30000 });
  await evidenceButton.click();
  await pause(page, 12000);
  screenshots.push(await snap(page, "08-insight-evidence-hub-top"));
  await page.mouse.wheel(0, 1050);
  await pause(page, 12000);
  screenshots.push(await snap(page, "09-insight-evidence-hub-architecture"));

  await gotoRoute(page, "/", 9000);
  screenshots.push(await snap(page, "10-closing-home"));

  const video = page.video();
  await context.close();
  await browser.close();

  const videoPath = video ? await video.path() : "";
  const finalVideoPath = path.join(videoDir, `insurance-intelligence-3-minute-demo-${new Date().toISOString().replace(/[:.]/g, "-")}.webm`);
  if (videoPath) {
    await fs.copyFile(videoPath, finalVideoPath);
  }

  const manifest = {
    created_at: new Date().toISOString(),
    frontend_url: frontendUrl,
    duration_target_seconds: 180,
    video_path: finalVideoPath,
    screenshots,
    storyline: [
      "Home",
      "Campaign Effectiveness",
      "Agent Performance Tracking",
      "Policy Lapse Risk",
      "Know Your Customer",
      "Know Your Agent",
      "AI Intelligence",
      "Insight Evidence Hub",
      "Closing Home"
    ]
  };
  await fs.writeFile(path.join(artifactDir, "demo_video_manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(JSON.stringify(manifest, null, 2));
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
