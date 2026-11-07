// Mobile layout + Instagram contract checks. Native app delivery is mocked.
const assert=require('node:assert/strict');
const {chromium,webkit}=require('playwright');
(async()=>{
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch({headless:true});
  try{
   const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2,acceptDownloads:true});
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>{
    window.copied='';window.shared=null;window.shareMode='ok';window.copyDenied=false;
    Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{if(window.copyDenied)throw new Error('denied');window.copied=text;}},configurable:true});
    Object.defineProperty(navigator,'canShare',{value:()=>{if(window.shareMode==='throws')throw new Error('unsupported');return window.shareMode!=='unsupported';},configurable:true});
    Object.defineProperty(navigator,'share',{value:async payload=>{if(window.shareMode==='cancel')throw new DOMException('cancel','AbortError');if(window.shareMode==='failed')throw new DOMException('denied','NotAllowedError');window.shared=payload;window.activeTap=navigator.userActivation?.isActive;},configurable:true});
   });
   await page.goto((process.env.RF_TEST_URL||'http://127.0.0.1:8786')+'/competitions/uci-mtb-world-cup-dh-2026.html');
   const opener=page.getByRole('button',{name:'Share competition as an image',exact:true});
   await opener.scrollIntoViewIfNeeded();const scrollBefore=await page.evaluate(()=>window.scrollY);
   await opener.tap();await page.locator('.ranking-share-actions > [role=status]').filter({hasText:'Aperçu intégral prêt'}).waitFor();
   assert.equal(await page.evaluate(()=>document.body.style.position),'fixed');
   for(const [width,height] of [[320,568],[375,667],[390,844],[412,915],[844,390],[390,400]]){
    await page.setViewportSize({width,height});
    await page.locator('.ranking-share-layout').evaluate(e=>e.scrollTop=0);
    assert(await page.locator('dialog').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'No horizontal overflow');
    assert(await page.locator('.ranking-share-layout').evaluate(e=>e.scrollWidth<=e.clientWidth+1),'Content fits');
    assert(await page.locator('.ranking-share-gallery canvas').evaluate(e=>{const r=e.getBoundingClientRect();return Math.abs(r.width/r.height-e.width/e.height)<.01;}),'Full image ratio');
    const close=page.getByRole('button',{name:'Fermer',exact:true});
    assert(await close.evaluate(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44&&r.top>=0&&r.bottom<=innerHeight;}),'Close visible and touch-sized');
    assert(await page.locator('.ranking-share-social > *').evaluateAll(nodes=>nodes.every(e=>{const r=e.getBoundingClientRect();return r.width>=44&&r.height>=44;})),'Social touch targets');
    await page.locator('.ranking-share-layout').evaluate(e=>e.scrollTop=e.scrollHeight);
    assert(await close.evaluate(e=>e.getBoundingClientRect().top>=0&&e.getBoundingClientRect().bottom<=innerHeight),'Close stays visible after scrolling');
   }
   await page.setViewportSize({width:390,height:844});
   await page.locator('.ranking-share-layout').evaluate(e=>e.scrollTop=0);
   await page.screenshot({path:'/tmp/mobile-'+engine.name()+'-preview.png'});
   const enlargedPromise=context.waitForEvent('page');await page.getByRole('link',{name:'Agrandir l’image 1 (nouvel onglet)',exact:true}).tap();const enlarged=await enlargedPromise;await enlarged.waitForLoadState();assert.equal(await enlarged.locator('img').evaluate(e=>e.naturalWidth),1080);await enlarged.close();
   let downloads=0;page.on('download',()=>downloads++);
   await page.getByRole('button',{name:'Instagram',exact:true}).tap();
   assert.equal(await page.evaluate(()=>window.shared),null,'Opening instructions does not prematurely share');
   assert.equal(downloads,0,'No automatic download');
   assert(await page.locator('.ranking-share-post h3').evaluate(e=>document.activeElement===e));
   const copy=page.getByRole('button',{name:'1. Copier le texte',exact:true});await copy.tap();
   assert.equal(await page.evaluate(()=>window.copied),await page.locator('.ranking-share-post textarea').inputValue());
   await page.getByRole('button',{name:'2. Partager l’image',exact:true}).tap();
   assert.equal(await page.evaluate(()=>window.shared.files[0].type),'image/png');
   assert.equal(await page.evaluate(()=>window.shared.text),undefined,'Image-only share avoids Instagram caption loss');
   assert.equal(await page.evaluate(()=>window.activeTap),true,'Native share keeps the tap activation');
   await page.screenshot({path:'/tmp/mobile-'+engine.name()+'-instagram.png'});
   for(const mode of ['cancel','failed']){
    await page.evaluate(mode=>window.shareMode=mode,mode);
    await page.getByRole('button',{name:'2. Partager l’image',exact:true}).tap();
    await page.locator('.ranking-share-post-status').filter({hasText:mode==='cancel'?'annulé':'n’a pas abouti'}).waitFor();
    assert.equal(downloads,0,'Cancellation/failure never downloads silently');
    assert(await page.getByRole('button',{name:'2. Partager l’image',exact:true}).isEnabled());
   }
   await page.evaluate(()=>{window.copyDenied=true;window.shareMode='throws';});
   await page.locator('.ranking-share-post textarea').fill('Mon texte modifié');
   await page.getByRole('button',{name:'1. Copier le texte',exact:true}).tap();
   assert(await page.locator('.ranking-share-post textarea').evaluate(e=>e.selectionStart===0&&e.selectionEnd===e.value.length));
   assert.equal(await page.locator('.ranking-share-post textarea').evaluate(e=>getComputedStyle(e).fontSize),'16px');
   await page.getByRole('button',{name:'Instagram',exact:true}).tap();
   const download=page.waitForEvent('download');await page.getByRole('button',{name:'2. Télécharger l’image',exact:true}).tap();assert.equal(await (await download).failure(),null);
   await page.getByRole('button',{name:'Fermer',exact:true}).tap();await page.locator('dialog').waitFor({state:'detached'});
   assert.equal(await page.evaluate(()=>document.body.style.position),'');
   assert(Math.abs(await page.evaluate(()=>window.scrollY)-scrollBefore)<2,'Background scroll restored');
   assert(await opener.evaluate(e=>e===document.activeElement));
   assert.deepEqual(errors,[]);console.log(engine.name()+': mobile portrait/landscape, reduced height, touch targets, close, scroll lock, caption copy/manual fallback, share activation/cancel/error/download PASS');
  }finally{await browser.close();}
 }
})().catch(e=>{console.error(e);process.exit(1);});
