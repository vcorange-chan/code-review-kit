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
  await page.locator('#collapse').click();
  await page.locator('#expand').click();
  const linearSteps = await page.locator('#card-1 [data-linear-step]').evaluateAll(elements=>({count:elements.length,open:elements.every(e=>e.open),text:elements.map(e=>e.textContent).join(' ')}));
  if (linearSteps.count !== 3 || !linearSteps.open || !/执行者|Executed by/.test(linearSteps.text)) throw new Error('Sequential blocks are not readable after expand');
  await page.locator('#card-1 .function-link').click();
  await page.locator('#card-1 .source a[data-snapshot]').first().click();
  await page.waitForSelector('.source-line.focused');
  if (!(await page.locator('.source-line.focused').textContent()).includes('pub fn accept')) throw new Error('Source navigation failed');
  await page.locator('#source-back').click();
  await page.locator('#collapse').click();
  const sourceHidden = await page.locator('#source-view').evaluate(element=>element.hidden);
  if (!sourceHidden) throw new Error('Return to flow failed');
  await page.locator('#card-5').evaluate(element => element.scrollIntoView({ behavior: 'instant', block: 'start' }));
  await mkdir(dirname(resolve(output)), { recursive: true });
  await page.screenshot({ path: output, animations: 'disabled' });
  console.log(JSON.stringify({ ...checks, linearBlocks:linearSteps.count, sourceNavigation:true, returnToFlow:true, language:await page.locator('html').getAttribute('lang'), screenshot: output }));
} finally {
  await browser.close();
}
