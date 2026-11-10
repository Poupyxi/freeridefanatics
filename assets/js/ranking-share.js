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
      whatsapp: 'https://wa.me/?' + new URLSearchParams({text:title+' '+url}),
      facebook: 'https://www.facebook.com/sharer/sharer.php?' + new URLSearchParams({u:url}),
      email: 'mailto:?' + new URLSearchParams({subject:title,body:url}).toString().replace(/\+/g,'%20'),
    };
  }
  // Source dates have no start time: preserve the local date as an all-day event.
  function calendarDate(value) {
    const day=String(value || '').slice(0,10);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day) || day.startsWith('9999-'))return null;
    const date=new Date(day+'T00:00:00Z');
    return Number.isFinite(date.getTime()) && date.toISOString().slice(0,10)===day ? day : null;
  }
  function calendarEvents(items, title, url) {
    return items.flatMap(item=>{
      const start=calendarDate(item.date);if(!start)return [];
      const last=calendarDate(item.endDate)||start;
      const end=new Date((last<start?start:last)+'T00:00:00Z');end.setUTCDate(end.getUTCDate()+1);
      return [{title:item.name || title,start,end:end.toISOString().slice(0,10),location:item.location || '',
        description:title+'\n'+url,url,cancelled:/cancelled|canceled|annulé/i.test(item.status || '')}];
    });
  }
  function calendarLinks(event) {
    return {
      google:'https://calendar.google.com/calendar/render?'+new URLSearchParams({action:'TEMPLATE',text:event.title,dates:event.start.replace(/-/g,'')+'/'+event.end.replace(/-/g,''),details:event.description,location:event.location}),
      outlook:'https://outlook.live.com/calendar/0/deeplink/compose?'+new URLSearchParams({path:'/calendar/action/compose',rru:'addevent',subject:event.title,startdt:event.start,enddt:event.end,allday:'true',body:event.description,location:event.location}),
    };
  }
  function calendarFile(events, now=new Date()) {
    const escape=value=>String(value).replace(/\\/g,'\\\\').replace(/\r\n|\r|\n/g,'\\n').replace(/;/g,'\\;').replace(/,/g,'\\,');
    const stamp=now.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}Z$/,'Z');
    const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//RidersFanatics//Calendar//FR','CALSCALE:GREGORIAN'];
    events.forEach(event=>lines.push('BEGIN:VEVENT',
      'UID:'+encodeURIComponent(new URL(event.url).pathname+'|'+event.title)+'@ridersfanatics.com',
      'DTSTAMP:'+stamp,'DTSTART;VALUE=DATE:'+event.start.replace(/-/g,''),'DTEND;VALUE=DATE:'+event.end.replace(/-/g,''),
      'SUMMARY:'+escape(event.title),'DESCRIPTION:'+escape(event.description),'LOCATION:'+escape(event.location),
      'URL:'+event.url,...(event.cancelled?['STATUS:CANCELLED']:[]),'TRANSP:TRANSPARENT','END:VEVENT'));
    lines.push('END:VCALENDAR');
    // RFC 5545: fold at 75 octets, without splitting a UTF-8 character.
    const encoder=new TextEncoder();
    return lines.map(line=>{let folded='',length=0;for(const char of line){const size=encoder.encode(char).length;if(length+size>75){folded+='\r\n ';length=1;}folded+=char;length+=size;}return folded;}).join('\r\n')+'\r\n';
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
  if (typeof module !== 'undefined') module.exports = {chunks, handle, flag, socialLinks, eventNation, calendarDate, calendarEvents, calendarLinks, calendarFile};
  if (typeof document === 'undefined') return;
  const source = document.getElementById('ranking-share-data');
  if (!source) return;
  let data = JSON.parse(source.dataset.payload);
  const socialAssets=new URL('../img/social/',document.currentScript.src);
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
    const nations=[['nové město','CZE'],['czech','CZE'],['mona yongpyong','KOR'],['mona pyongyong','KOR'],['yongpyong','KOR'],['south korea','KOR'],['korea','KOR'],['loudenvielle','FRA'],['les gets','FRA'],['france','FRA'],['leogang','AUT'],['austria','AUT'],['la thuile','ITA'],['val di sole','ITA'],['italy','ITA'],['pal arinsal','AND'],['andorra','AND'],['lenzerheide','SUI'],['switzerland','SUI'],['lake placid','USA'],['soldier hollow','USA'],['midway','USA'],['utah','USA'],['united states','USA'],['whistler','CAN'],['british columbia','CAN'],['canada','CAN']];
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
  async function drawCompetition(height,context,calendarOverride){
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d'),card=data.competitionCard||{},calendar=(calendarOverride || card.calendar || []);
    const gradient=ctx.createLinearGradient(0,0,0,height);gradient.addColorStop(0,'#111214');gradient.addColorStop(.55,'#1b1816');gradient.addColorStop(1,'#090a0b');ctx.fillStyle=gradient;ctx.fillRect(0,0,1080,height);
    ctx.fillStyle='#27211d';ctx.beginPath();ctx.moveTo(0,height*.62);ctx.lineTo(210,height*.36);ctx.lineTo(390,height*.58);ctx.lineTo(620,height*.29);ctx.lineTo(880,height*.61);ctx.lineTo(1080,height*.4);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    ctx.fillStyle='#171515';ctx.beginPath();ctx.moveTo(0,height*.75);ctx.lineTo(260,height*.5);ctx.lineTo(450,height*.7);ctx.lineTo(720,height*.46);ctx.lineTo(1080,height*.73);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    const compact=height===1080,panelTop=compact?38:52,panelHeight=compact?138:178;
    ctx.fillStyle='#0d0e10ee';ctx.beginPath();ctx.roundRect(54,panelTop,972,panelHeight,18);ctx.fill();
    const logo=await loadImage(context.logo);
    if(logo){const scale=Math.min(650/logo.width,(panelHeight-34)/logo.height);const w=logo.width*scale,h=logo.height*scale;ctx.drawImage(logo,540-w/2,panelTop+(panelHeight-h)/2,w,h);}
    else{ctx.fillStyle='#fff';fit(ctx,'COMPETITION',140,panelTop+panelHeight/2+15,800,54,true);}
    const title=String(context.title||'').replace(new RegExp('\\s+'+String(data.season||'')+'$'),'').toUpperCase();
    const titleTop=panelTop+panelHeight+(compact?58:72),titleSize=compact?37:48;
    ctx.fillStyle='#b4491c';ctx.fillRect(34,titleTop-35,5,86);ctx.fillStyle='#e8dfd1';ctx.fillRect(1041,titleTop-35,5,86);
    ctx.fillStyle='#f5f1e9';ctx.textAlign='center';lines(ctx,String(data.season||'')+' '+title+' CALENDAR',540,titleTop,960,titleSize,titleSize+6,2,true);ctx.textAlign='left';
    const listTop=titleTop+(compact?104:128),footerY=height-58,rowHeight=Math.min(compact?58:75,(footerY-listTop-18)/Math.max(calendar.length,1));
    calendar.forEach((item,index)=>{const y=listTop+index*rowHeight,baseline=y+rowHeight*.66,nation=eventNation(item);ctx.fillStyle=index%2?'#121112cc':'#211c19dd';ctx.fillRect(48,y,984,rowHeight-3);ctx.font=(compact?24:30)+'px Arial, sans-serif';ctx.fillText(flag(nation),68,baseline);ctx.fillStyle='#f5f1e9';fit(ctx,nation,124,baseline,72,compact?18:21,true);ctx.fillStyle='#c9c0b5';fit(ctx,compactDate(item.date),205,baseline,145,compact?18:22);ctx.fillStyle='#f5f1e9';fit(ctx,String(item.name||item.location||'Event').replace(/\s*-\s*20\d{2}\s*$/,''),365,baseline,510,compact?21:27,true);ctx.fillStyle='#c9c0b5';fit(ctx,disciplineCode(item.discipline||card.discipline),925,baseline,82,compact?17:20);});
    if(!calendar.length){ctx.fillStyle='#fff';fit(ctx,'CALENDAR COMING SOON',120,listTop+90,840,44,true);}
    ctx.fillStyle='#b4491c';ctx.fillRect(48,height-94,54,5);ctx.fillStyle='#e8dfd1';ctx.fillRect(102,height-94,54,5);
    ctx.fillStyle='#f5f1e9';fit(ctx,context.handle||'@ridersfanatics',48,height-50,510,20,true);ctx.fillStyle='#a99f94';fit(ctx,'RIDERSFANATICS.COM',760,height-50,270,17,true);
    return canvas;
  }
  function canShareFiles(files){
    try{return !!(files.length && navigator.share && navigator.canShare && navigator.canShare({files}));}catch(_){return false;}
  }
  async function open(panel, opener) {
    if(document.querySelector('.ranking-share-dialog'))return;

    const isEvent=!panel;
    const rows = isEvent ? [] : readRows(panel);
    if (!isEvent && !rows.length) return;
    const event = isEvent ? {} : data.events[panel.dataset.competition] || {};
    const context = {title:event.name || data.title, logo:event.logo || data.logo,
      handle:handle(event.instagram || data.instagram), team:panel?.dataset.standings === 'Teams',
      subtitle:isEvent ? [data.eventCard.date,data.eventCard.location,data.eventCard.status].filter(Boolean).join(' · ') : [panel.dataset.standings, panel.dataset.standingStage || (event.name ? 'Event ranking' : 'Overall ranking'), data.season].filter(Boolean).join(' · ')};
    const calendarShare=data.shareKind==='competition'||data.shareKind==='year';
    const yearPages=chunks(data.competitionCard?.calendar || []);
    const allPages = isEvent ? (data.shareKind==='year' ? (yearPages.length ? yearPages : [[]]) : [[]]) : chunks(rows), urls = [], calendarUrls=[];
    const dialog = el('dialog'); dialog.className='ranking-share-dialog';
    const header=el('header','',dialog);header.className='ranking-share-header';
    const heading=el('h2','Partager '+(isEvent ? (calendarShare ? 'le calendrier' : 'l’événement') : 'le classement'),header);
    heading.id='ranking-share-title';dialog.setAttribute('aria-labelledby',heading.id);
    const close=el('button','×',header);close.type='button';close.className='ranking-share-close';close.setAttribute('aria-label','Fermer');
    const layout=el('div','',dialog);layout.className='ranking-share-layout';
    const gallery=el('div','',layout);gallery.className='ranking-share-gallery';
    const actions=el('div','',layout);actions.className='ranking-share-actions';
    el('p','Partagez votre passion.',actions);
    const status=el('p','',actions);status.setAttribute('role','status');
    const social=el('nav','',actions);social.className='ranking-share-social';social.setAttribute('aria-label','Options de partage');
    const pageUrl=data.shareUrl ? new URL(data.shareUrl,location.href).href : location.href.split('#')[0];
    const copyLink=el('button','Copier le lien',social);copyLink.type='button';
    const links=socialLinks(pageUrl,context.title+' — '+context.subtitle);
    [['WhatsApp',links.whatsapp],['Facebook',links.facebook],['X',links.x],['Email',links.email]].forEach(([name,url])=>{
      const link=el('a',name,social);link.href=url;
      if(name!=='Email'){link.target='_blank';link.rel='noopener noreferrer';}
      link.setAttribute('aria-label','Partager via '+name);
    });
    const instagram=el('button','Instagram',social);instagram.type='button';instagram.className='ranking-share-instagram';
    const share=el('button','Plus',social);share.type='button';
    const logoFiles={'WhatsApp':'whatsapp.png','Facebook':'facebook.jpg','X':'x.png','Instagram':'instagram.png'};
    const symbols={'Copier le lien':'M10 13a5 5 0 0 0 7 .5l3-3a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7-.5l-3 3a5 5 0 0 0 7 7l2-2','Email':'M3 5h18v14H3z M3 5l9 7 9-7','Plus':'M12 4v16 M4 12h16'};
    [...social.children].forEach(control=>{
      const label=control.textContent;control.textContent='';
      const logo=logoFiles[label];
      if(logo){const img=el('img','',control);img.src=new URL(logo,socialAssets).href;img.alt='';img.width=56;img.height=56;img.className='ranking-share-logo';}
      else{const icon=el('span','',control);icon.className='ranking-share-symbol';icon.setAttribute('aria-hidden','true');const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','26');svg.setAttribute('height','26');svg.setAttribute('fill','none');svg.setAttribute('stroke','currentColor');svg.setAttribute('stroke-width','1.8');svg.setAttribute('stroke-linecap','round');svg.setAttribute('stroke-linejoin','round');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',symbols[label]);svg.append(path);icon.append(svg);}
      el('span',label,control);
    });
    const calendarItems=isEvent && data.shareKind==='event' ? [{...data.eventCard,name:context.title}]
      : event.name ? [event] : data.competitionCard?.calendar || [];
    const dated=calendarEvents(calendarItems,context.title,pageUrl);
    const calendarToggle=el('button','Ajouter au calendrier',actions);calendarToggle.type='button';calendarToggle.className='ranking-share-calendar-toggle';
    const calendarPanel=el('section','',actions);calendarPanel.id='ranking-share-calendar';calendarPanel.className='ranking-share-calendar';calendarPanel.hidden=true;
    calendarToggle.setAttribute('aria-controls',calendarPanel.id);calendarToggle.setAttribute('aria-expanded','false');
    calendarToggle.onclick=()=>{calendarPanel.hidden=!calendarPanel.hidden;calendarToggle.setAttribute('aria-expanded',String(!calendarPanel.hidden));};
    if(!dated.length){el('p','Les dates ne sont pas encore confirmées. L’ajout sera disponible dès leur publication.',calendarPanel);}
    else {
      const label=el('label','À ajouter',calendarPanel),selection=el('select','',label);
      if(dated.length>1){const all=el('option','Toute la compétition ('+dated.length+' événements)',selection);all.value='all';}
      dated.forEach((item,i)=>{const option=el('option',item.start+' · '+item.title,selection);option.value=String(i);});
      const choices=el('div','',calendarPanel);choices.className='ranking-share-calendar-options';
      const google=el('a','Google Calendar',choices),outlook=el('a','Outlook',choices),ics=el('button','Apple Calendar / fichier .ics',choices);ics.type='button';
      [google,outlook].forEach(link=>{link.target='_blank';link.rel='noopener noreferrer';});
      const help=el('p','',calendarPanel);help.setAttribute('role','status');
      const importLink=el('a','',calendarPanel);importLink.hidden=true;importLink.target='_blank';importLink.rel='noopener noreferrer';
      const chosenEvents=()=>selection.value==='all'?dated:[dated[Number(selection.value)]];
      function downloadCalendar(){
        const url=URL.createObjectURL(new Blob([calendarFile(chosenEvents())],{type:'text/calendar;charset=utf-8'}));
        calendarUrls.push(url);const a=el('a');a.href=url;a.download='ridersfanatics-calendrier.ics';document.body.append(a);a.click();a.remove();
      }
      function updateCalendar(){
        const all=selection.value==='all',item=chosenEvents()[0],links=calendarLinks(item);
        google.href=all?'https://calendar.google.com/calendar/u/0/r/settings/export':links.google;
        outlook.href=all?'https://outlook.live.com/calendar/0/':links.outlook;
        google.textContent=all?'Google Calendar · importer':'Google Calendar';outlook.textContent=all?'Outlook · importer':'Outlook';
        importLink.hidden=true;
        help.textContent='Journées entières, sans horaire annoncé. '+(all?'Le fichier contient tous les événements datés. Importez-le dans votre agenda. ':'Confirmez l’ajout dans votre agenda. ')+'Les imports ne se mettent pas à jour automatiquement.';
      }
      [google,outlook].forEach(link=>{link.onclick=e=>{
        if(selection.value!=='all')return;
        e.preventDefault();downloadCalendar();
        help.textContent=link===google?'Fichier téléchargé. Dans Google Calendar sur ordinateur : Paramètres → Importer et exporter → choisissez le fichier .ics.':'Fichier téléchargé. Dans Outlook : Ajouter un calendrier → Charger à partir d’un fichier → choisissez le fichier .ics.';
        importLink.href=link.href;importLink.textContent=link===google?'Ouvrir Google Calendar ↗':'Ouvrir Outlook ↗';importLink.hidden=false;
      };});
      ics.onclick=()=>{downloadCalendar();help.textContent='Ouvrez le fichier .ics dans Apple Calendar ou importez-le dans votre agenda (Outlook, Google Calendar, Thunderbird…). Confirmez l’ajout. Cet import ne se met pas à jour automatiquement.';};
      selection.onchange=updateCalendar;updateCalendar();
    }
    const urlLabel=el('label','Lien à partager',actions);urlLabel.htmlFor='ranking-share-url';
    const urlRow=el('div','',actions);urlRow.className='ranking-share-url';
    const urlInput=el('input','',urlRow);urlInput.id='ranking-share-url';urlInput.type='url';urlInput.readOnly=true;urlInput.value=pageUrl;
    const copyUrl=el('button','Copier',urlRow);copyUrl.type='button';
    copyLink.onclick=copyUrl.onclick=async()=>{try{await navigator.clipboard.writeText(pageUrl);status.textContent='Lien copié.';}catch(_){urlInput.focus();urlInput.select();status.textContent='Sélectionnez et copiez le lien manuellement.';}};
    if(location.hostname.startsWith('preprod.'))el('p','Ce lien de préproduction est protégé par un mot de passe.',actions);
    const download=el('button','Créer un post',actions);download.type='button';download.className='ranking-share-create';
    const post=el('section','',actions);post.hidden=true;post.className='ranking-share-post';post.id='ranking-share-post';
    social.after(post);instagram.setAttribute('aria-controls',post.id);instagram.setAttribute('aria-expanded','false');
    const postHeading=el('h3','Préparer votre post Instagram',post);postHeading.tabIndex=-1;
    el('p','Copiez le texte, puis partagez l’image. Dans Instagram, collez le texte avant de publier.',post);
    const captionLabel=el('label','Texte à publier',post),caption=el('textarea','',captionLabel);
    caption.value=[context.title+' — '+context.subtitle,context.handle,pageUrl,'#RidersFanatics'].filter(Boolean).join('\n');
    caption.rows=3;
    const copy=el('button','1. Copier le texte',post);copy.type='button';
    const postStatus=el('p','',post);postStatus.setAttribute('role','status');postStatus.className='ranking-share-post-status';
    copy.onclick=async()=>{try{await navigator.clipboard.writeText(caption.value);copy.textContent='✓ Texte copié';postStatus.textContent='Texte copié. Partagez maintenant l’image, puis collez le texte dans Instagram.';}catch(_){caption.focus();caption.select();caption.setSelectionRange(0,caption.value.length);postStatus.textContent='La copie automatique est indisponible. Appuyez longuement sur le texte sélectionné, puis choisissez Copier.';}};
    caption.addEventListener('input',()=>{copy.textContent='1. Copier le texte';postStatus.textContent='Texte modifié : copiez-le à nouveau avant de publier.';});
    const instagramShare=el('button','2. Partager l’image',post);instagramShare.type='button';instagramShare.className='ranking-share-instagram-send';
    const instagramHelp=el('div','',post);instagramHelp.className='ranking-share-instagram-help';
    el('p','Choisissez Instagram dans le menu du téléphone. Si Instagram n’apparaît pas, enregistrez l’image, puis ouvrez Instagram pour l’ajouter à votre publication.',instagramHelp);
    const saveImage=el('button','Télécharger l’image',instagramHelp);saveImage.type='button';
    const instagramLink=el('a','Ouvrir Instagram ↗',instagramHelp);instagramLink.href='https://www.instagram.com/';instagramLink.target='_blank';instagramLink.rel='noopener noreferrer';
    function showPost(){
      post.hidden=false;instagram.setAttribute('aria-expanded','true');
      postHeading.focus({preventScroll:true});post.scrollIntoView({block:'start',behavior:'instant'});
      instagramShare.textContent=canShareFiles(selected().map(item=>item.file))?'2. Partager l’image':'2. Télécharger l’image';
    }
    let rendered=[], version=0;
    function selected() { return rendered.filter(item=>item.checkbox.checked); }
    function release() { urls.splice(0).forEach(url=>URL.revokeObjectURL(url)); }
    const scrollPosition={x:window.scrollX,y:window.scrollY};
    const bodyKeys=['position','top','left','right','width','overflow'];
    const bodyStyles=bodyKeys.map(key=>[key,document.body.style.getPropertyValue(key),document.body.style.getPropertyPriority(key)]);
    function dispose() {
      version++;release();calendarUrls.forEach(url=>URL.revokeObjectURL(url));dialog.remove();
      bodyStyles.forEach(([key,value,priority])=>value?document.body.style.setProperty(key,value,priority):document.body.style.removeProperty(key));
      window.scrollTo({left:scrollPosition.x,top:scrollPosition.y,behavior:'instant'});opener.focus({preventScroll:true});
    }
    close.onclick=()=>dialog.close(); dialog.addEventListener('close',dispose,{once:true});
    dialog.addEventListener('click', e=>{ if(e.target===dialog){ const b=dialog.getBoundingClientRect(); if(e.clientX<b.left||e.clientX>b.right||e.clientY<b.top||e.clientY>b.bottom)dialog.close(); } });
    async function render() {
      const token=++version;
      const previous=rendered.map(item=>item.checkbox.checked);
      share.disabled=download.disabled=instagram.disabled=true; status.textContent='Préparation de l’image…';
      release(); rendered=[]; gallery.replaceChildren();
      try {
        const pages=allPages;
        for(let i=0;i<pages.length;i++) {
          const canvas=isEvent ? (calendarShare ? await drawCompetition(1350,context,pages[i]) : await drawEvent(1350,context)) : await draw(pages[i],i,pages.length,1350,context);
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          if(token!==version)return;
          if(!blob)throw new Error('Image generation failed');
          const item=el('div','',gallery), choice=el('label','',item), checkbox=el('input','',choice);
          checkbox.type='checkbox'; checkbox.checked=previous[i] ?? true;
          choice.append(document.createTextNode(' Image '+(i+1)));choice.hidden=isEvent&&pages.length===1;
          const url=URL.createObjectURL(blob); urls.push(url);
          canvas.setAttribute('role','img'); canvas.setAttribute('aria-label',isEvent ? context.title+' — event card' : context.title+' — entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)); const preview=el('a','',item);preview.href=url;preview.target='_blank';preview.rel='noopener';preview.className='ranking-share-preview';preview.setAttribute('aria-label','Agrandir l’image '+(i+1)+' (nouvel onglet)');preview.append(canvas);
          const file=new File([blob],'ridersfanatics-'+(isEvent ? 'event' : 'ranking')+'-'+String(i+1).padStart(2,'0')+'.png',{type:'image/png'});
          const link=el('a','Télécharger l’image',item); link.href=url; link.download=file.name;
          const hint=el('span','Touchez l’aperçu pour l’agrandir',item);hint.className='ranking-share-preview-hint';
          rendered.push({checkbox,file,url});
        }
        status.textContent='Aperçu intégral prêt — '+pages.length+' image(s).';
        share.disabled=download.disabled=instagram.disabled=false;
      } catch (_) { if(token===version)status.textContent='Impossible de préparer l’image. Rechargez la page pour réessayer.'; }
    }
    function downloadImages(){
      const chosen=selected();if(!chosen.length){postStatus.textContent='Sélectionnez au moins une image dans l’aperçu.';return;}
      chosen.forEach(item=>{const a=el('a');a.href=item.url;a.download=item.file.name;document.body.append(a);a.click();a.remove();});
      postStatus.textContent='Téléchargement demandé. Retrouvez l’image dans vos téléchargements et ajoutez-la dans Instagram. Si nécessaire, enregistrez-la d’abord dans Photos.';
    }
    download.onclick=()=>{showPost();downloadImages();};saveImage.onclick=downloadImages;
    let sharing=false;
    async function nativeShare(payload,feedback){
      if(sharing)return;
      sharing=true;share.disabled=instagramShare.disabled=true;
      try{await navigator.share(payload);feedback.textContent=feedback===postStatus?'Image transmise au menu de partage. Dans Instagram, collez le texte puis confirmez la publication.':'Contenu transmis au menu de partage.';}
      catch(e){feedback.textContent=e.name==='AbortError'?'Partage annulé. Vous pouvez réessayer quand vous voulez.':'Le partage n’a pas abouti. Utilisez Télécharger l’image, puis ouvrez Instagram.';}
      finally{sharing=false;share.disabled=instagramShare.disabled=false;}
    }
    share.onclick=()=>{
      const files=selected().map(item=>item.file);if(!files.length){status.textContent='Sélectionnez au moins une image.';return;}
      if(!navigator.share){showPost();postStatus.textContent='Le partage du téléphone est indisponible. Téléchargez l’image ou copiez le lien.';return;}
      // Invoke the share sheet directly from this tap, without an awaited copy operation.
      nativeShare(canShareFiles(files)?{files,title:context.title,text:caption.value}:{url:pageUrl,title:context.title},status);
    };
    instagram.onclick=showPost;
    instagramShare.onclick=()=>{
      const files=selected().map(item=>item.file);
      if(!files.length){postStatus.textContent='Sélectionnez au moins une image dans l’aperçu.';return;}
      if(!canShareFiles(files)){downloadImages();return;}
      nativeShare({files},postStatus);
    };
    Object.assign(document.body.style,{position:'fixed',top:-scrollPosition.y+'px',left:-scrollPosition.x+'px',right:'0',width:'100%',overflow:'hidden'});
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
  document.querySelectorAll('[data-year-share-payload]').forEach(host=>{
    let payload;
    try{payload=JSON.parse(host.dataset.yearSharePayload || '');}catch(_){return;}
    const button=el('button','Share '+payload.season);button.type='button';
    button.className='ranking-share-trigger competition-year-share-trigger';
    button.setAttribute('aria-label','Share all '+payload.season+' competitions and add them to a calendar');
    button.onclick=()=>{data=payload;open(null,button);};
    host.append(button);
  });
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
