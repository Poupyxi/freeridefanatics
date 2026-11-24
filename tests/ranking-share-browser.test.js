// Run against a preprod build served at RF_TEST_URL (default localhost:8786).
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.RF_CHROME?{executablePath:process.env.RF_CHROME}:{})});
 try{
  const context=await browser.newContext({viewport:{width:1280,height:900},acceptDownloads:true,permissions:['clipboard-read','clipboard-write']});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  // Exercise a 12-event 2027 calendar, including events beyond the old ten-row cap.
  await page.route('**/assets/js/ranking-share.js*',async route=>{
   const response=await route.fetch();
   const fixture=`{const source=document.getElementById('ranking-share-data');const d=JSON.parse(source.dataset.payload);d.title='UCI World Series CC 2027';d.season=2027;d.competitionCard.calendar=Array.from({length:12},(_,i)=>({name:'Calendar event '+(i+1),date:'2027-06-01',country:'FRA',discipline:'XC'}));source.dataset.payload=JSON.stringify(d);}`;
   await route.fulfill({response,body:fixture+await response.text()});
  });
  await page.addInitScript(()=>{window.drawnLabels=[];const original=CanvasRenderingContext2D.prototype.fillText;CanvasRenderingContext2D.prototype.fillText=function(text,...args){window.drawnLabels.push(text);return original.call(this,text,...args);};});
  await page.goto((process.env.RF_TEST_URL||'http://127.0.0.1:8786')+'/competitions/uci-mtb-world-cup-dh-2026.html');
  const opener=page.getByRole('button',{name:'Share competition as an image',exact:true});
  await opener.click();await page.locator('.ranking-share-actions > [role=status]').filter({hasText:'Aperçu intégral prêt'}).waitFor();
  assert(await page.evaluate(()=>window.drawnLabels.includes('Calendar event 12')),'Every calendar event is drawn');
  assert.equal(await page.locator('.ranking-share-controls select').count(),0,'No row or format selector');
  const canvas=page.locator('.ranking-share-gallery canvas');
  assert.deepEqual(await canvas.evaluate(c=>[c.width,c.height]),[1080,1350]);
  assert.equal(await page.locator('.ranking-share-social img').count(),4);
  assert(await page.locator('.ranking-share-social img').evaluateAll(imgs=>imgs.every(img=>img.complete&&img.naturalWidth>0)));
  await page.getByRole('button',{name:'Ajouter au calendrier',exact:true}).click();
  assert.equal(await page.locator('.ranking-share-calendar select').inputValue(),'all');
  const calendarDownload=page.waitForEvent('download');
  await page.getByRole('link',{name:'Google Calendar · importer',exact:true}).click();
  const downloaded=await calendarDownload;
  assert.equal(downloaded.suggestedFilename(),'ridersfanatics-calendrier.ics');
  const contents=require('node:fs').readFileSync(await downloaded.path(),'utf8');
  assert.equal((contents.match(/BEGIN:VEVENT/g)||[]).length,12);
  assert(await page.getByRole('link',{name:'Ouvrir Google Calendar ↗',exact:true}).isVisible());
  await page.locator('.ranking-share-calendar select').selectOption('0');
  const googleHref=await page.getByRole('link',{name:'Google Calendar',exact:true}).getAttribute('href');
  assert.equal(new URL(googleHref).searchParams.get('dates'),'20270601/20270602');
  assert.equal(new URL(await page.getByRole('link',{name:'Outlook',exact:true}).getAttribute('href')).searchParams.get('allday'),'true');
  const singleDownload=page.waitForEvent('download');await page.getByRole('button',{name:'Apple Calendar / fichier .ics',exact:true}).click();
  assert.equal((require('node:fs').readFileSync(await (await singleDownload).path(),'utf8').match(/BEGIN:VEVENT/g)||[]).length,1);
  await page.getByRole('button',{name:'Ajouter au calendrier',exact:true}).click();

  for(const label of ['WhatsApp','Facebook','X','Email'])assert(await page.getByRole('link',{name:'Partager via '+label,exact:true}).isVisible());
  await page.getByRole('button',{name:'Copier',exact:true}).click();
  assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),page.url());
  await page.evaluate(()=>{window.shared=null;Object.defineProperty(navigator,'canShare',{value:()=>true,configurable:true});Object.defineProperty(navigator,'share',{value:async p=>{window.shared=p;},configurable:true});});
  await page.getByRole('button',{name:'Plus',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.shared.files[0].type),'image/png');
  await page.getByRole('button',{name:'Instagram',exact:true}).click();
  await page.getByRole('button',{name:'1. Copier le texte',exact:true}).click();
  await page.getByRole('button',{name:'2. Partager l’image',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.shared.files.length),1);
  await page.evaluate(()=>Object.defineProperty(navigator,'canShare',{value:()=>false,configurable:true}));
  await page.getByRole('button',{name:'Plus',exact:true}).click();assert.equal(await page.evaluate(()=>window.shared.url),page.url());
  await page.getByRole('button',{name:'Instagram',exact:true}).click();
  let pending=page.waitForEvent('download');await page.getByRole('button',{name:'2. Télécharger l’image',exact:true}).click();assert.equal(await (await pending).failure(),null);
  assert(await page.locator('.ranking-share-instagram-help').isVisible());
  pending=page.waitForEvent('download');await page.getByRole('button',{name:'Créer un post',exact:true}).click();assert.equal(await (await pending).failure(),null);
  for(const width of [1280,390,320]){
   await page.setViewportSize({width,height:844});
   assert(await page.locator('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+2));
   assert(await canvas.evaluate(c=>{const r=c.getBoundingClientRect();return Math.abs(r.width/r.height-c.width/c.height)<.01&&getComputedStyle(c).objectFit==='contain';}),'Image keeps its entire aspect ratio');
   await page.screenshot({path:(process.env.RF_SCREENSHOTS||'/tmp')+'/share-'+width+'.png'});
  }
  await page.keyboard.press('Escape');await page.locator('dialog').waitFor({state:'detached'});assert(await opener.evaluate(e=>e===document.activeElement));
  await opener.click();await page.getByRole('button',{name:'Fermer',exact:true}).click();await page.locator('dialog').waitFor({state:'detached'});
  await page.locator('.ranking-share-ranking-trigger:visible').first().click();await page.locator('.ranking-share-actions > [role=status]').filter({hasText:'Aperçu intégral prêt'}).waitFor();
  const rows=await page.locator('.standings-block:visible').first().locator('[data-standing-row]').evaluateAll(nodes=>nodes.filter(n=>!n.closest('.standing-stage-breakdown')).length);
  assert.equal(await page.locator('.ranking-share-gallery canvas').count(),Math.ceil(rows/10));await page.keyboard.press('Escape');
  assert.deepEqual(errors,[]);console.log('PASS: calendar exports, dates, provider links, official logos, full preview, desktop/mobile, channels, clipboard, native files/link, Instagram fallback, post PNG, Escape, close and focus');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
