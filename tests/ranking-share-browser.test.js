// Run against a preprod build served at RF_TEST_URL (default localhost:8786).
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.RF_CHROME ? {executablePath:process.env.RF_CHROME} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900},acceptDownloads:true});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    const base=process.env.RF_TEST_URL || 'http://127.0.0.1:8786';
    for(const path of ['/competitions/uci-mtb-world-cup-dh-2026.html','/competitions/uci-mtb-world-cup-dh-2026/rounds/leogang.html','/competitions/uci-mtb-world-cup-dh-2026/standings.html']) {
      await page.goto(base+path);
      const opener=page.locator('.ranking-share-trigger:visible').first();
      await opener.click();
      await page.getByRole('status').filter({hasText:'images ready'}).waitFor();
      const canvas=page.locator('.ranking-share-gallery canvas').first();
      assert.deepEqual(await canvas.evaluate(c=>[c.width,c.height]),[1080,1350]);
      const rows=await opener.locator('..').locator('[data-standing-row]').evaluateAll(rows=>rows.filter(row=>!row.closest('.standing-stage-breakdown')).length);
      assert.equal(await page.locator('.ranking-share-gallery canvas').count(),Math.ceil(rows/10));
      await page.locator('.ranking-share-gallery input').first().uncheck();
      await page.locator('.ranking-share-dialog select').selectOption('1080');
      await page.getByRole('status').filter({hasText:'images ready'}).waitFor();
      assert.deepEqual(await canvas.evaluate(c=>[c.width,c.height]),[1080,1080]);
      assert.equal(await page.locator('.ranking-share-gallery input').first().isChecked(),false);
      const downloadPromise=page.waitForEvent('download');
      await page.getByText('Download this image',{exact:true}).first().click();
      const download=await downloadPromise;
      assert.equal(download.suggestedFilename(),'ridersfanatics-ranking-01.png');
      assert.equal(await download.failure(),null);
      await page.setViewportSize({width:390,height:844});
      assert(await page.locator('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+2));
      await page.keyboard.press('Escape');
      await page.locator('.ranking-share-dialog').waitFor({state:'detached'});
      assert.equal(await page.locator('dialog').count(),0);
      await page.setViewportSize({width:1280,height:900});
      console.log(path+': preview, pagination, square, selection, PNG download, mobile and close PASS');
    }
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
