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
      const opener=page.locator('.ranking-share-trigger:not(.event-share-trigger):visible').first();
      await opener.click();
      await page.getByRole('status').filter({hasText:'images ready'}).waitFor();
      const centered=await page.locator('dialog').evaluate(el=>{const r=el.getBoundingClientRect();return Math.abs(r.x+r.width/2-innerWidth/2)<2&&Math.abs(r.y+r.height/2-innerHeight/2)<2;});
      assert(centered,'Desktop popup must be centered');
      assert((await page.getByRole('link',{name:'Share link on X (new tab)',exact:true}).getAttribute('href')).startsWith('https://x.com/intent/tweet?'));
      assert((await page.getByRole('link',{name:'Share link on LinkedIn (new tab)',exact:true}).getAttribute('href')).startsWith('https://www.linkedin.com/sharing/share-offsite/?'));
      await page.evaluate(()=>Object.defineProperty(navigator,'canShare',{value:()=>false,configurable:true}));
      await page.getByRole('button',{name:'Instagram',exact:true}).click();
      assert(await page.locator('.ranking-share-instagram-help').isVisible());
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
      assert(await page.locator('dialog').evaluate(el=>{const r=el.getBoundingClientRect();return Math.abs(r.x+r.width/2-innerWidth/2)<2&&Math.abs(r.y+r.height/2-innerHeight/2)<2;}),'Mobile popup must be centered');
      await page.keyboard.press('Escape');
      await page.locator('.ranking-share-dialog').waitFor({state:'detached'});
      assert.equal(await page.locator('dialog').count(),0);
      await page.setViewportSize({width:1280,height:900});
      console.log(path+': preview, pagination, square, selection, PNG download, mobile and close PASS');
    }
    await page.goto(base+'/competitions/uci-mtb-world-cup-dh-2026/rounds/leogang.html');
    // An event card remains available even with no ranking panels.
    await page.locator('.standings-block').evaluateAll(nodes=>nodes.forEach(node=>node.remove()));
    await page.getByRole('button',{name:'Share event ↗',exact:true}).click();
    await page.getByRole('status').filter({hasText:'images ready'}).waitFor();
    assert.equal(await page.locator('.ranking-share-gallery canvas').count(),1);
    await page.locator('.ranking-share-dialog select').selectOption('1080');
    await page.getByRole('status').filter({hasText:'images ready'}).waitFor();
    assert.deepEqual(await page.locator('.ranking-share-gallery canvas').evaluate(c=>[c.width,c.height]),[1080,1080]);
    const eventDownload=page.waitForEvent('download');
    await page.getByText('Download this image',{exact:true}).click();
    assert.equal((await eventDownload).suggestedFilename(),'ridersfanatics-event-01.png');
    await page.screenshot({path:'/tmp/event-share-preview.png'});
    assert.deepEqual(errors,[]);
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
