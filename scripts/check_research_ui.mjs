// CI-only browser verification of fictional generated output, never a runtime dependency.
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { mkdir } from 'node:fs/promises';
import assert from 'node:assert/strict';

const input = resolve(process.argv[2]);
const screenshot = resolve(process.argv[3]);
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1280,height:1000},deviceScaleFactor:1});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(pathToFileURL(input).href);
  assert.equal(await page.locator('[data-tab]').count(),3);
  await page.locator('#filter').fill('reduce_event');
  assert.equal(await page.locator('.candidate:not([hidden])').count(),1);
  await page.locator('.candidate:not([hidden]) [data-dossier]').click();
  assert.equal(await page.locator('#dossier').isVisible(),true);
  // First branch facet, first condition: open row, follow its original source line.
  const article = page.locator('.dossier').first();
  await article.locator('.facet').nth(1).locator('summary').first().click();
  const branch = article.locator('.facet').nth(1).locator('.inside > details').first();
  await branch.locator('summary').click();
  await branch.locator('[data-source-target]').click();
  assert.equal(await article.locator('.source').isVisible(),true);
  await page.locator('[data-tab="investigation"]').click();
  const record = page.locator('#investigation > details').nth(2);
  await record.locator('summary').first().click();
  await record.locator('[data-evidence-target]').click();
  assert.equal(await page.locator('#dossier').isVisible(),true);
  await page.locator('[data-tab="investigation"]').click();
  assert.ok((await page.locator('#investigation').textContent()).includes('旧请求的失败事件可能覆盖新请求状态'));
  assert.ok((await page.locator('#investigation').textContent()).includes('静态条件与预测相反'));
  assert.deepEqual(errors,[]);
  await mkdir(resolve(screenshot,'..'),{recursive:true});
  await page.screenshot({path:screenshot,fullPage:true});
  console.log(JSON.stringify({ok:true,views:3,filter:true,source_jump:true,evidence_jump:true,history:true,screenshot}));
} finally {
  await browser.close();
}
