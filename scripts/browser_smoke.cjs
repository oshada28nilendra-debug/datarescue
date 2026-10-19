/* Optional development-only check: node + Playwright Chromium, not a runtime dependency. */
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.DATARESCUE_PLAYWRIGHT || 'playwright');

(async () => {
  const root = path.resolve(process.argv[2] || 'delivery/offline-demo');
  const browser = await chromium.launch({headless:true, args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}, acceptDownloads:true});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(pathToFileURL(path.join(root,'plan/review.html')).href);
    const count = await page.locator('select').count();
    assert.equal(count, 5);
    assert.deepEqual(await page.locator('select').evaluateAll(nodes => nodes.map(n=>n.value)), Array(count).fill('reject'));
    await page.locator('select').nth(0).selectOption('accept');
    await page.locator('select').nth(1).selectOption('modify');
    assert.equal(await page.locator('textarea').nth(1).isEnabled(), true);
    const decisionPromise = page.waitForEvent('download');
    await page.getByRole('button',{name:'Download decisions for preview'}).click();
    const decisionsDownload = await decisionPromise;
    const review = JSON.parse(fs.readFileSync(await decisionsDownload.path(),'utf8'));
    assert.equal(review.decisions[0].decision, 'accept');
    assert.equal(review.decisions[1].decision, 'modify');
    assert.equal(review.decisions[2].decision, 'reject');
    assert.equal(review.decisions[1].operation.kind, 'replace_exact');
    await page.screenshot({path:path.join(root,'review-screenshot.png'),fullPage:true});
    await page.goto(pathToFileURL(path.join(root,'preview/preview.html')).href);
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button',{name:'Download explicit approval'}).click();
    assert.equal(await page.locator('input[type=checkbox]').isChecked(), false);
    await page.locator('input[type=checkbox]').check();
    const approvalPromise = page.waitForEvent('download');
    await page.getByRole('button',{name:'Download explicit approval'}).click();
    const approvalDownload = await approvalPromise;
    const approval = JSON.parse(fs.readFileSync(await approvalDownload.path(),'utf8'));
    const preview = JSON.parse(fs.readFileSync(path.join(root,'preview/preview.json'),'utf8'));
    assert.equal(approval.approve, true);
    assert.equal(approval.preview_digest, preview.digest);
    assert.deepEqual(errors, []);
    await page.screenshot({path:path.join(root,'preview-screenshot.png'),fullPage:true});
    const evidence = {result:'passed', browser:await browser.version(), proposals:count,
      checks:['default reject','accept/reject/modify decisions download','operation editor enablement',
        'unchecked approval blocked','explicit digest-bound approval download','no browser page errors'],
      limitation:'Headless synthetic fixture check, not user research or accessibility certification'};
    fs.writeFileSync(path.join(root,'browser-verification.json'),JSON.stringify(evidence,null,2)+'\n');
    console.log(JSON.stringify(evidence));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
