// Optional documentation task. Playwright is installed only in the preview CI job.
// This script never runs the code being reviewed or calls a model.
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [report, output] = process.argv.slice(2);
if (!report || !output) throw new Error('Usage: node scripts/capture_demo.mjs REPORT.html IMAGE.png');
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1180 }, colorScheme: 'light' });
  await page.goto(pathToFileURL(resolve(report)).href);
  await page.waitForSelector('path.resume', { state: 'attached' });
  await page.evaluate(() => document.fonts.ready);
  const checks = await page.evaluate(() => ({
    cards: document.querySelectorAll('.stage').length,
    success: document.querySelectorAll('path.success').length,
    resume: document.querySelectorAll('path.resume').length,
    straight: [...document.querySelectorAll('path.success')].every(p => /^M[\d.]+ [\d.]+V[\d.]+$/.test(p.getAttribute('d'))),
    current: [...document.querySelectorAll('.stage')].every(s => s.dataset.status === 'current'),
  }));
  if (checks.cards !== 14 || checks.success !== 43 || checks.resume !== 5 || !checks.straight || !checks.current) {
    throw new Error(JSON.stringify(checks));
  }
  await page.locator('#card-5').evaluate(element => element.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await mkdir(dirname(resolve(output)), { recursive: true });
  await page.screenshot({ path: output, animations: 'disabled' });
  console.log(JSON.stringify({ ...checks, screenshot: output }));
} finally {
  await browser.close();
}
