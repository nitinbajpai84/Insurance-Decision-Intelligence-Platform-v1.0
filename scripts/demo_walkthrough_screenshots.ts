import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const root = process.cwd();
const screenshotDir = path.join(root, "docs", "demo", "screenshots");
const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3000";

const steps = [
  ["01-home", "/"],
  ["02-campaign-effectiveness", "/?view=campaign"],
  ["03-agent-performance-tracking", "/?view=agent-performance"],
  ["04-policy-lapse-risk", "/?view=lapse-risk"],
  ["05-know-your-customer", "/?view=customer"],
  ["06-know-your-agent", "/?view=agent"],
  ["07-ai-intelligence", "/ai-intelligence"],
  ["08-insight-evidence-hub", "/insight-evidence-hub"]
] as const;

async function main() {
  await fs.mkdir(screenshotDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const screenshots: string[] = [];

  for (const [name, route] of steps) {
    await page.goto(`${frontendUrl}${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(5000);
    const file = path.join(screenshotDir, `${name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    screenshots.push(file);
  }

  await browser.close();
  await fs.writeFile(
    path.join(screenshotDir, "screenshot-index.json"),
    JSON.stringify({ created_at: new Date().toISOString(), screenshots }, null, 2)
  );
  console.log(JSON.stringify({ screenshots }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

