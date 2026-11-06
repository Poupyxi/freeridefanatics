(function () {
  'use strict';
  function chunks(rows) {
    return Array.from({length: Math.ceil(rows.length / 10)}, (_, i) => rows.slice(i * 10, i * 10 + 10));
  }
  function handle(value) {
    const text = String(value || '').trim().replace(/^https?:\/\/(www\.)?instagram\.com\//i, '').replace(/^@/, '').replace(/\/$/, '');
    return /^[\w.]{1,30}$/.test(text) ? '@' + text : '';
  }
  function socialLinks(url, title) {
    return {
      x: 'https://x.com/intent/tweet?' + new URLSearchParams({text:title,url}),
      linkedin: 'https://www.linkedin.com/sharing/share-offsite/?' + new URLSearchParams({url}),
    };
  }
  const codes = {FRA:'FR',CAN:'CA',GBR:'GB',USA:'US',AUS:'AU',NZL:'NZ',GER:'DE',DEU:'DE',ITA:'IT',ESP:'ES',SUI:'CH',CHE:'CH',AUT:'AT',BEL:'BE',NED:'NL',NLD:'NL',NOR:'NO',SWE:'SE',DEN:'DK',DNK:'DK',FIN:'FI',POL:'PL',CZE:'CZ',SVK:'SK',SLO:'SI',SVN:'SI',POR:'PT',PRT:'PT',RSA:'ZA',ZAF:'ZA',JPN:'JP',KOR:'KR',BRA:'BR',ARG:'AR',CHI:'CL',CHL:'CL',COL:'CO',ECU:'EC',MEX:'MX',PER:'PE',IRL:'IE',ISR:'IL',UKR:'UA',HUN:'HU',CRO:'HR',HRV:'HR',EST:'EE',LAT:'LV',LVA:'LV',LTU:'LT',ROU:'RO',BUL:'BG',BGR:'BG',GRE:'GR',GRC:'GR',TUR:'TR',CHN:'CN',TPE:'TW',HKG:'HK',INA:'ID',IDN:'ID',MAS:'MY',MYS:'MY',THA:'TH',PHI:'PH',PHL:'PH',IND:'IN',NEP:'NP',NPL:'NP',VEN:'VE',URU:'UY',URY:'UY',CRC:'CR',CRI:'CR',GUA:'GT',GTM:'GT',BOL:'BO',AND:'AD',LUX:'LU',ISL:'IS',RUS:'RU',SRB:'RS',BIH:'BA',MKD:'MK',KAZ:'KZ',GEO:'GE',ARM:'AM',CYP:'CY',MLT:'MT',LIE:'LI',MON:'MC',MCO:'MC'};
  function flag(value) {
    let code = String(value || '').toUpperCase().trim();
    const aliases = {'GREAT BRITAIN':'GB','NEW ZELANDE':'NZ','AMERICAN SAMOA':'AS','ROUMANIA':'RO','CROATIE':'HR'};
    if (code === 'SCOTLAND') return '🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}';
    code = aliases[code] || code;
    code = codes[code] || code;
    if (!/^[A-Z]{2}$/.test(code) && typeof Intl !== 'undefined' && Intl.DisplayNames) {
      const names = new Intl.DisplayNames(['en'], {type:'region'});
      for (const iso of new Set(Object.values(codes))) if (names.of(iso).toUpperCase() === code) { code = iso; break; }
    }
    return /^[A-Z]{2}$/.test(code) ? [...code].map(c => String.fromCodePoint(127397 + c.charCodeAt(0))).join('') : '';
  }
  if (typeof module !== 'undefined') module.exports = {chunks, handle, flag, socialLinks};
  if (typeof document === 'undefined') return;
  const source = document.getElementById('ranking-share-data');
  if (!source) return;
  const data = JSON.parse(source.dataset.payload);
  const text = (node) => node ? node.textContent.trim() : '';
  const assets = new Map();
  function loadImage(url) {
    if (!url) return Promise.resolve(null);
    const absolute = new URL(url, location.href);
    if (absolute.origin !== location.origin) return Promise.resolve(null);
    if (!assets.has(absolute.href)) assets.set(absolute.href, new Promise(resolve => {
      const img = new Image();
      const timer = setTimeout(() => resolve(null), 8000);
      img.onload = () => { clearTimeout(timer); resolve(img); };
      img.onerror = () => { clearTimeout(timer); resolve(null); };
      img.src = absolute.href;
    }));
    return assets.get(absolute.href);
  }
  function readRows(panel) {
    return [...panel.querySelectorAll('[data-standing-row]')].filter(row => !row.closest('.standing-stage-breakdown')).map(row => {
      const link = row.matches('a') ? row : row.querySelector('a[href*="/riders/"]');
      const slug = link ? new URL(link.href).pathname.split('/').pop().replace(/\.html$/, '') : '';
      const rider = data.riders[slug] || {};
      const name = text(row.querySelector('.clean-standing-name strong, th a, .who a, .team-identity strong')) || text(row.querySelector('th, .who'));
      const metric = row.querySelector('.round-points, .total') || (row.matches('.clean-standing-row') ? row.querySelector(':scope > b') : null);
      const time = row.querySelector('.round-time');
      const metricText = metric ? text(metric).replace(/\s*pts$/, '') : text(time);
      return {rank: text(row.querySelector('.clean-standing-rank, .round-place, .pos')), name,
        country: rider.country || '', photo: rider.photo || '', value: metricText,
        metric: metric ? (metric.classList.contains('standing-time') ? 'TIME' : 'PTS') : (time ? 'TIME' : '')};
    }).filter(row => row.name);
  }
  function el(tag, content, parent) {
    const node = document.createElement(tag);
    if (content) node.textContent = content;
    if (parent) parent.append(node);
    return node;
  }
  function fit(ctx, label, x, y, width, size, bold = false) {
    let font = size;
    do { ctx.font = (bold ? '700 ' : '400 ') + font + 'px Arial, sans-serif'; font--; }
    while (ctx.measureText(label).width > width && font > 16);
    ctx.fillText(label, x, y, width);
  }
  function lines(ctx,label,x,y,width,size,lineHeight,maxLines=2,bold=false){
    ctx.font=(bold?'800 ':'400 ')+size+'px Arial, sans-serif';
    const words=String(label||'').trim().split(/\s+/), output=[];
    let current='';
    words.forEach(word=>{const candidate=current?current+' '+word:word;if(ctx.measureText(candidate).width<=width||!current)current=candidate;else{output.push(current);current=word;}});
    if(current)output.push(current);
    const visible=output.slice(0,maxLines);
    if(output.length>maxLines)visible[maxLines-1]=visible[maxLines-1].replace(/[.…]*$/,'')+'…';
    visible.forEach((line,index)=>ctx.fillText(line,x,y+index*lineHeight,width));
    return visible.length;
  }
  function prettyDate(value){
    if(!value)return 'DATE TBA';
    const date=new Date(String(value).slice(0,10)+'T12:00:00Z');
    if(Number.isNaN(date.getTime()))return String(value).toUpperCase();
    return new Intl.DateTimeFormat('en',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}).format(date).toUpperCase();
  }
  function compactDate(value){
    if(!value)return 'TBA';
    const date=new Date(String(value).slice(0,10)+'T12:00:00Z');
    if(Number.isNaN(date.getTime()))return String(value).toUpperCase();
    return new Intl.DateTimeFormat('en',{day:'2-digit',month:'short',timeZone:'UTC'}).format(date).toUpperCase();
  }
  function eventNation(item){
    const explicit=String(item.country||'').trim();
    if(explicit)return explicit.toUpperCase();
    const value=(String(item.name||'')+' '+String(item.location||'')).toLowerCase();
    const nations=[['nové město','CZE'],['czech','CZE'],['loudenvielle','FRA'],['les gets','FRA'],['france','FRA'],['leogang','AUT'],['austria','AUT'],['la thuile','ITA'],['val di sole','ITA'],['italy','ITA'],['pal arinsal','AND'],['andorra','AND'],['lenzerheide','SUI'],['switzerland','SUI'],['soldier hollow','USA'],['midway','USA'],['utah','USA'],['united states','USA'],['whistler','CAN'],['british columbia','CAN'],['canada','CAN']];
    return nations.find(([label])=>value.includes(label))?.[1]||'—';
  }
  function disciplineCode(value){
    const text=String(value||'').toLowerCase();
    if(text.includes('downhill'))return 'DHI';
    if(text.includes('cross'))return 'XC';
    if(text.includes('snowboard'))return 'SNB';
    if(text.includes('ski'))return 'SKI';
    return String(value||'EVENT').replace(/bike\s*/i,'').slice(0,8).toUpperCase();
  }
  async function draw(rows, index, count, height, context) {
    const canvas = document.createElement('canvas'); canvas.width = 1080; canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#f5f1e9'; ctx.fillRect(0, 0, 1080, height);
    ctx.fillStyle = '#17181b';
    const logo = await loadImage(context.logo);
    if (logo) {
      const scale = Math.min(270 / logo.width, 120 / logo.height);
      ctx.drawImage(logo, 54, 40, logo.width * scale, logo.height * scale);
    } else fit(ctx, 'COMPETITION', 54, 95, 300, 24, true);
    fit(ctx, 'RIDERSFANATICS', 690, 85, 336, 26, true);
    ctx.fillStyle = '#b4491c'; ctx.fillRect(54, 180, 7, 110);
    ctx.fillStyle = '#17181b';
    fit(ctx, context.title.toUpperCase(), 82, 217, 944, 46, true);
    fit(ctx, context.subtitle.toUpperCase(), 82, 268, 944, 26);
    const top = 330, rowHeight = (height - top - 104) / 10;
    const metric = rows.find(row => row.metric)?.metric || '';
    fit(ctx, '#', 64, top - 17, 85, 23, true);
    fit(ctx, context.team ? 'TEAM' : 'RIDER', 260, top - 17, 530, 23, true);
    fit(ctx, metric, 866, top - 17, 170, 23, true);
    const images = await Promise.all(rows.map(row => loadImage(row.photo)));
    rows.forEach((row, i) => {
      const y = top + i * rowHeight, baseline = y + rowHeight * .64;
      ctx.strokeStyle = '#aca79f'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(54,y); ctx.lineTo(1026,y); ctx.stroke();
      ctx.fillStyle = index === 0 && i < 3 ? '#b4491c' : '#17181b';
      fit(ctx, row.rank, 64, baseline, 98, 31, true);
      const radius = Math.min(25, rowHeight * .34), cy = y + rowHeight / 2;
      ctx.save(); ctx.beginPath(); ctx.arc(200, cy, radius, 0, Math.PI * 2); ctx.clip();
      const img = images[i];
      if (img) { const side = Math.min(img.width, img.height); ctx.drawImage(img,(img.width-side)/2,(img.height-side)/2,side,side,200-radius,cy-radius,radius*2,radius*2); }
      else { ctx.fillStyle = '#ddd8ce'; ctx.fillRect(170,y,60,rowHeight); ctx.fillStyle='#777'; fit(ctx,row.name.charAt(0),190,baseline,26,23,true); }
      ctx.restore();
      ctx.fillStyle = '#17181b';
      ctx.font = '30px Arial'; ctx.fillText(flag(row.country), 246, baseline);
      fit(ctx,row.name,306,baseline,530,30,true);
      fit(ctx,row.value,866,baseline,160,29);
    });
    ctx.fillStyle='#b4491c'; ctx.fillRect(54,height-76,972,3);
    ctx.fillStyle='#17181b'; fit(ctx,context.handle || 'ridersfanatics.com',54,height-36,760,23);
    fit(ctx,(index+1)+' / '+count,900,height-36,130,23);
    return canvas;
  }
  async function drawEvent(height, context) {
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d');
    ctx.fillStyle='#f5f1e9';ctx.fillRect(0,0,1080,height);
    ctx.fillStyle='#17181b';fit(ctx,'RIDERSFANATICS / EVENTS',64,80,950,26,true);
    ctx.strokeStyle='#ccc5b9';ctx.lineWidth=1;
    for(let y=120;y<height-100;y+=64){ctx.beginPath();ctx.moveTo(64,y);ctx.lineTo(1016,y);ctx.stroke();}
    const logo=await loadImage(context.logo);
    if(logo){const scale=Math.min(650/logo.width,260/logo.height);ctx.drawImage(logo,64,150,logo.width*scale,logo.height*scale);}
    ctx.fillStyle='#b4491c';ctx.fillRect(64,455,8,110);
    ctx.fillStyle='#17181b';fit(ctx,context.title.toUpperCase(),94,505,920,60,true);
    fit(ctx,String(data.season || ''),94,553,920,30);
    const card=data.eventCard;
    const details=[['DATE',card.date || 'To be announced'],['LOCATION',card.location || 'To be announced'],['DISCIPLINE',card.discipline || 'To be announced'],['STATUS',card.status]];
    details.forEach(([label,value],i)=>{const y=635+i*80;ctx.fillStyle='#b4491c';fit(ctx,label,64,y,210,20,true);ctx.fillStyle='#17181b';fit(ctx,value,285,y,730,30,true);});
    ctx.fillStyle='#b4491c';ctx.fillRect(64,height-120,952,3);
    ctx.fillStyle='#17181b';fit(ctx,context.handle || 'ridersfanatics.com',64,height-75,950,26,true);
    fit(ctx,location.host+location.pathname,64,height-35,950,18);
    return canvas;
  }
  async function drawCompetition(height,context){
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d'),card=data.competitionCard||{},calendar=(card.calendar||[]).slice(0,10);
    const gradient=ctx.createLinearGradient(0,0,0,height);gradient.addColorStop(0,'#050607');gradient.addColorStop(.55,'#101315');gradient.addColorStop(1,'#030405');ctx.fillStyle=gradient;ctx.fillRect(0,0,1080,height);
    ctx.fillStyle='#14191b';ctx.beginPath();ctx.moveTo(0,height*.62);ctx.lineTo(210,height*.36);ctx.lineTo(390,height*.58);ctx.lineTo(620,height*.29);ctx.lineTo(880,height*.61);ctx.lineTo(1080,height*.4);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    ctx.fillStyle='#0b0e10';ctx.beginPath();ctx.moveTo(0,height*.75);ctx.lineTo(260,height*.5);ctx.lineTo(450,height*.7);ctx.lineTo(720,height*.46);ctx.lineTo(1080,height*.73);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    const compact=height===1080,panelTop=compact?38:52,panelHeight=compact?138:178;
    ctx.fillStyle='#090b0ce8';ctx.beginPath();ctx.roundRect(54,panelTop,972,panelHeight,18);ctx.fill();
    const logo=await loadImage(context.logo);
    if(logo){const scale=Math.min(650/logo.width,(panelHeight-34)/logo.height);const w=logo.width*scale,h=logo.height*scale;ctx.drawImage(logo,540-w/2,panelTop+(panelHeight-h)/2,w,h);}
    else{ctx.fillStyle='#fff';fit(ctx,'COMPETITION',140,panelTop+panelHeight/2+15,800,54,true);}
    const title=String(context.title||'').replace(new RegExp('\\s+'+String(data.season||'')+'$'),'').toUpperCase();
    const titleTop=panelTop+panelHeight+(compact?58:72),titleSize=compact?37:48;
    ctx.fillStyle='#95e100';ctx.fillRect(34,titleTop-35,5,86);ctx.fillStyle='#f20b58';ctx.fillRect(1041,titleTop-35,5,86);
    ctx.fillStyle='#fff';ctx.textAlign='center';lines(ctx,String(data.season||'')+' '+title+' CALENDAR',540,titleTop,960,titleSize,titleSize+6,2,true);ctx.textAlign='left';
    const listTop=titleTop+(compact?104:128),footerY=height-58,rowHeight=Math.min(compact?58:75,(footerY-listTop-18)/Math.max(calendar.length,1));
    calendar.forEach((item,index)=>{const y=listTop+index*rowHeight,baseline=y+rowHeight*.66,nation=eventNation(item);ctx.fillStyle=index%2?'#090b0caa':'#171b1dcc';ctx.fillRect(48,y,984,rowHeight-3);ctx.font=(compact?24:30)+'px Arial, sans-serif';ctx.fillText(flag(nation),68,baseline);ctx.fillStyle='#fff';fit(ctx,nation,124,baseline,72,compact?18:21,true);ctx.fillStyle='#d9dcde';fit(ctx,compactDate(item.date),205,baseline,145,compact?18:22);ctx.fillStyle='#fff';fit(ctx,String(item.name||item.location||'Event').replace(/\s*-\s*20\d{2}\s*$/,''),365,baseline,510,compact?21:27,true);ctx.fillStyle='#d9dcde';fit(ctx,disciplineCode(item.discipline||card.discipline),925,baseline,82,compact?17:20);});
    if(!calendar.length){ctx.fillStyle='#fff';fit(ctx,'CALENDAR COMING SOON',120,listTop+90,840,44,true);}
    ctx.fillStyle='#95e100';ctx.fillRect(48,height-94,54,5);ctx.fillStyle='#f20b58';ctx.fillRect(102,height-94,54,5);
    ctx.fillStyle='#fff';fit(ctx,context.handle||'@ridersfanatics',48,height-50,510,20,true);ctx.fillStyle='#aeb2b4';fit(ctx,'RIDERSFANATICS.COM',760,height-50,270,17,true);
    return canvas;
  }
  async function open(panel, opener) {
    const isEvent=!panel;
    const rows = isEvent ? [] : readRows(panel);
    if (!isEvent && !rows.length) return;
    const event = isEvent ? {} : data.events[panel.dataset.competition] || {};
    const context = {title:event.name || data.title, logo:event.logo || data.logo,
      handle:handle(event.instagram || data.instagram), team:panel?.dataset.standings === 'Teams',
      subtitle:isEvent ? [data.eventCard.date,data.eventCard.location,data.eventCard.status].filter(Boolean).join(' · ') : [panel.dataset.standings, panel.dataset.standingStage || (event.name ? 'Event ranking' : 'Overall ranking'), data.season].filter(Boolean).join(' · ')};
    const allPages = isEvent ? [[]] : chunks(rows), urls = [];
    const dialog = el('dialog'); dialog.className='ranking-share-dialog';
    const heading = el('h2',isEvent ? (data.shareKind === 'competition' ? 'Share competition' : 'Share event') : 'Share ranking',dialog); heading.id='ranking-share-title'; dialog.setAttribute('aria-labelledby',heading.id);
    const close = el('button','Close ×',dialog); close.type='button'; close.className='ranking-share-close';
    el('p',isEvent ? 'Share the event card, even before results are available.' : 'Choose how much of the ranking to prepare. Each image contains up to 10 entries.',dialog);
    const controls=el('div','',dialog);controls.className='ranking-share-controls';
    const label = el('label','Format ',controls), select = el('select','',label);
    [['1350','Portrait · 1080 × 1350'],['1080','Square · 1080 × 1080']].forEach(([value,name]) => { const option=el('option',name,select); option.value=value; });
    let range=null;
    if(!isEvent && allPages.length>1){
      const rangeLabel=el('label','Entries ',controls);range=el('select','',rangeLabel);
      const choices=[[1,'Top 10']];
      if(allPages.length>1)choices.push([2,'Top 20']);
      choices.push([allPages.length,'Full ranking · '+rows.length]);
      choices.forEach(([value,name])=>{const option=el('option',name,range);option.value=String(value);});
      range.value=String(Math.min(2,allPages.length));
    }
    const status=el('p','',dialog); status.setAttribute('role','status');
    const social=el('nav','',dialog); social.className='ranking-share-social'; social.setAttribute('aria-label','Share on social media');
    const links=socialLinks(location.href.split('#')[0],context.title+' — '+context.subtitle);
    [['X',links.x],['LinkedIn',links.linkedin]].forEach(([name,url])=>{
      const link=el('a',name+' ↗',social);link.href=url;link.target='_blank';link.rel='noopener noreferrer';
      link.setAttribute('aria-label','Share link on '+name+' (new tab)');
    });
    const instagram=el('button','Instagram',social); instagram.type='button';
    el('p','X and LinkedIn open a link-sharing composer. To publish the ranking images, download them and attach them to your post, or use your phone’s image-sharing menu. Instagram handles are not reused as X handles.',dialog);
    if(location.hostname.startsWith('preprod.')) el('p','Preview: this page link is password-protected. Downloaded images can still be shared.',dialog);
    const instagramHelp=el('div','',dialog);instagramHelp.hidden=true;instagramHelp.className='ranking-share-instagram-help';
    el('p','Download the selected images, copy the caption, then create an Instagram post and select the images in order. On a compatible phone, choose Instagram from the sharing menu.',instagramHelp);
    const instagramLink=el('a','Open Instagram ↗',instagramHelp);instagramLink.href='https://www.instagram.com/';instagramLink.target='_blank';instagramLink.rel='noopener noreferrer';
    const gallery=el('div','',dialog); gallery.className='ranking-share-gallery';
    const captionLabel=el('label','Instagram caption',dialog), caption=el('textarea','',captionLabel);
    caption.value=[context.title+' — '+context.subtitle,context.handle,location.href.split('#')[0],'#RidersFanatics'].filter(Boolean).join('\n');
    el('p','The @handle is included in the caption. Instagram mentions are activated when you publish there; this button does not post automatically.',dialog);
    const copy=el('button','Copy caption',dialog); copy.type='button';
    copy.onclick=async()=>{ try { await navigator.clipboard.writeText(caption.value); status.textContent='Caption copied.'; } catch (_) { caption.focus(); caption.select(); status.textContent='Select and copy the caption manually.'; } };
    const share=el('button','Share selected images',dialog); share.type='button';
    const download=el('button','Download selected images',dialog); download.type='button';
    let rendered=[], version=0;
    function selected() { return rendered.filter(item=>item.checkbox.checked); }
    function release() { urls.splice(0).forEach(url=>URL.revokeObjectURL(url)); }
    function dispose() { version++; release(); dialog.remove(); opener.focus(); }
    close.onclick=()=>dialog.close(); dialog.addEventListener('close',dispose,{once:true});
    dialog.addEventListener('click', e=>{ if(e.target===dialog){ const b=dialog.getBoundingClientRect(); if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)dialog.close(); } });
    async function render() {
      const token=++version;
      const previous=rendered.map(item=>item.checkbox.checked);
      share.disabled=download.disabled=instagram.disabled=true; status.textContent='Generating images…';
      release(); rendered=[]; gallery.replaceChildren();
      try {
        const pages=allPages.slice(0,range ? Number(range.value) : allPages.length);
        for(let i=0;i<pages.length;i++) {
          const canvas=isEvent ? (data.shareKind==='competition' ? await drawCompetition(Number(select.value),context) : await drawEvent(Number(select.value),context)) : await draw(pages[i],i,pages.length,Number(select.value),context);
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          if(token!==version)return;
          if(!blob)throw new Error('Image generation failed');
          const item=el('div','',gallery), choice=el('label','',item), checkbox=el('input','',choice);
          checkbox.type='checkbox'; checkbox.checked=previous[i] ?? true;
          choice.append(document.createTextNode(isEvent ? ' Event card' : ' Entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)));
          const url=URL.createObjectURL(blob); urls.push(url);
          canvas.setAttribute('role','img'); canvas.setAttribute('aria-label',isEvent ? context.title+' — event card' : context.title+' — entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)); item.append(canvas);
          const file=new File([blob],'ridersfanatics-'+(isEvent ? 'event' : 'ranking')+'-'+String(i+1).padStart(2,'0')+'.png',{type:'image/png'});
          const link=el('a','Download this image',item); link.href=url; link.download=file.name;
          rendered.push({checkbox,file,url});
        }
        status.textContent=pages.length+' images ready. Select only the pages you want.';
        share.disabled=download.disabled=instagram.disabled=false;
      } catch (_) { if(token===version)status.textContent='Could not generate the images. Try another format or reload the page.'; }
    }
    download.onclick=()=>{ const chosen=selected(); if(!chosen.length){status.textContent='Select at least one image.';return;}
      chosen.forEach(item=>{const a=el('a');a.href=item.url;a.download=item.file.name;document.body.append(a);a.click();a.remove();});
      status.textContent='Download requested. If your browser blocks multiple downloads, use “Download this image” below each preview.'; };
    share.onclick=async()=>{const files=selected().map(item=>item.file);if(!files.length){status.textContent='Select at least one image.';return;}
      if(!navigator.canShare || !navigator.canShare({files})){status.textContent='File sharing is unavailable in this browser. Download the images and copy the caption instead.';return;}
      try{await navigator.share({files,title:context.title,text:caption.value});status.textContent='Images shared.';}catch(e){status.textContent=e.name==='AbortError'?'Sharing cancelled.':'Sharing failed. Download the images instead.';}};
    instagram.onclick=async()=>{
      const files=selected().map(item=>item.file);
      if(!files.length){status.textContent='Select at least one image.';return;}
      instagramHelp.hidden=false;
      if(navigator.share && navigator.canShare && navigator.canShare({files})) {
        try { await navigator.share({files}); status.textContent='Images handed to the sharing menu. Paste the caption in Instagram to finish your post.'; }
        catch(e){status.textContent=e.name==='AbortError'?'Sharing cancelled.':'Could not share the images. Download them and open Instagram instead.';}
      } else {
        status.textContent='Instagram image sharing is unavailable in this browser. Download the images, copy the caption, then open Instagram.';
        instagramHelp.scrollIntoView({block:'nearest'});
      }
    };
    select.onchange=render;if(range)range.onchange=render;
    document.body.append(dialog);dialog.showModal();await render();
  }
  if(data.eventCard){
    const isCompetition=data.shareKind === 'competition';
    const countHeading=isCompetition ? document.querySelector('#events .section-head h2') : null;
    const host=countHeading?.parentElement || document.querySelector('.round-hero .wrap') || document.querySelector('main .wrap');
    if(host){
      host.classList.add(isCompetition ? 'ranking-share-count-host' : 'ranking-share-event-host');
      const button=el('button',isCompetition ? 'Share' : 'Share event');button.type='button';
      button.className='ranking-share-trigger event-share-trigger'+(isCompetition?' competition-share-trigger':'');
      button.setAttribute('aria-label',(isCompetition ? 'Share competition' : 'Share event')+' as an image');
      button.onclick=()=>open(null,button);host.append(button);
    }
  }
  document.querySelectorAll('main .standings-toolbar').forEach(toolbar=>{
    const section=toolbar.closest('section') || toolbar.parentElement;
    const panels=[...section.querySelectorAll('.standings-block')].filter(panel=>readRows(panel).length);
    if(!panels.length)return;
    const button=el('button','Share ranking');button.type='button';button.className='ranking-share-trigger ranking-share-ranking-trigger';
    button.setAttribute('aria-label','Share the currently displayed ranking as images');
    button.onclick=()=>{
      const panel=panels.find(item=>!item.hidden && getComputedStyle(item).display!=='none') || panels[0];
      open(panel,button);
    };
    toolbar.classList.add('ranking-share-toolbar-host');toolbar.append(button);
  });
}());
