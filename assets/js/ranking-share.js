(function () {
  'use strict';
  function chunks(rows) {
    return Array.from({length: Math.ceil(rows.length / 10)}, (_, i) => rows.slice(i * 10, i * 10 + 10));
  }
  function handle(value) {
    const text = String(value || '').trim().replace(/^https?:\/\/(www\.)?instagram\.com\//i, '').replace(/^@/, '').replace(/\/$/, '');
    return /^[\w.]{1,30}$/.test(text) ? '@' + text : '';
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
  if (typeof module !== 'undefined') module.exports = {chunks, handle, flag};
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
      const metric = row.querySelector('.round-points, .total, .clean-standing-row > b');
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
  async function open(panel, opener) {
    const rows = readRows(panel);
    if (!rows.length) return;
    const event = data.events[panel.dataset.competition] || {};
    const context = {title:event.name || data.title, logo:event.logo || data.logo,
      handle:handle(event.instagram || data.instagram), team:panel.dataset.standings === 'Teams',
      subtitle:[panel.dataset.standings, panel.dataset.standingStage || (event.name ? 'Event ranking' : 'Overall ranking'), data.season].filter(Boolean).join(' · ')};
    const pages = chunks(rows), urls = [];
    const dialog = el('dialog'); dialog.className='ranking-share-dialog';
    const heading = el('h2','Share ranking',dialog); heading.id='ranking-share-title'; dialog.setAttribute('aria-labelledby',heading.id);
    const close = el('button','Close ×',dialog); close.type='button'; close.className='ranking-share-close';
    el('p','Choose your format and the pages to include. Each image contains up to 10 ranked entries.',dialog);
    const label = el('label','Format ',dialog), select = el('select','',label);
    [['1350','Portrait · 1080 × 1350'],['1080','Square · 1080 × 1080']].forEach(([value,name]) => { const option=el('option',name,select); option.value=value; });
    const status=el('p','',dialog); status.setAttribute('role','status');
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
      share.disabled=download.disabled=true; status.textContent='Generating images…';
      release(); rendered=[]; gallery.replaceChildren();
      try {
        for(let i=0;i<pages.length;i++) {
          const canvas=await draw(pages[i],i,pages.length,Number(select.value),context);
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          if(token!==version)return;
          if(!blob)throw new Error('Image generation failed');
          const item=el('div','',gallery), choice=el('label','',item), checkbox=el('input','',choice);
          checkbox.type='checkbox'; checkbox.checked=previous[i] ?? true;
          choice.append(document.createTextNode(' Entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)));
          const url=URL.createObjectURL(blob); urls.push(url);
          canvas.setAttribute('role','img'); canvas.setAttribute('aria-label',context.title+' — entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)); item.append(canvas);
          const file=new File([blob],'ridersfanatics-ranking-'+String(i+1).padStart(2,'0')+'.png',{type:'image/png'});
          const link=el('a','Download this image',item); link.href=url; link.download=file.name;
          rendered.push({checkbox,file,url});
        }
        status.textContent=pages.length+' images ready. Select only the pages you want.';
        share.disabled=download.disabled=false;
      } catch (_) { if(token===version)status.textContent='Could not generate the images. Try another format or reload the page.'; }
    }
    download.onclick=()=>{ const chosen=selected(); if(!chosen.length){status.textContent='Select at least one image.';return;}
      chosen.forEach(item=>{const a=el('a');a.href=item.url;a.download=item.file.name;document.body.append(a);a.click();a.remove();});
      status.textContent='Download requested. If your browser blocks multiple downloads, use “Download this image” below each preview.'; };
    share.onclick=async()=>{const files=selected().map(item=>item.file);if(!files.length){status.textContent='Select at least one image.';return;}
      if(!navigator.canShare || !navigator.canShare({files})){status.textContent='File sharing is unavailable in this browser. Download the images and copy the caption instead.';return;}
      try{await navigator.share({files,title:context.title,text:caption.value});status.textContent='Images shared.';}catch(e){status.textContent=e.name==='AbortError'?'Sharing cancelled.':'Sharing failed. Download the images instead.';}};
    select.onchange=render;
    document.body.append(dialog);dialog.showModal();await render();
  }
  document.querySelectorAll('main .standings-block').forEach(panel=>{
    if (!readRows(panel).length) return;
    const button=el('button','Share ranking ↗');button.type='button';button.className='ranking-share-trigger';
    button.onclick=()=>open(panel,button);panel.prepend(button);
  });
  if(!document.querySelector('.ranking-share-trigger')){
    const main=document.querySelector('main .wrap');
    if(main){const button=el('button','Share ranking — results not yet available',main);button.type='button';button.disabled=true;button.className='ranking-share-trigger';}
  }
}());
