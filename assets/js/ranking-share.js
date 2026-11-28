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
  const MEDALS=['#d4a537','#b8bcc2','#b8743d'];
  function centered(ctx,label,x,y,width,size,weight){
    let font=size;
    do{ctx.font=weight+' '+font+'px Arial, sans-serif';font--;}while(ctx.measureText(label).width>width&&font>14);
    ctx.textAlign='center';ctx.fillText(label,x,y);ctx.textAlign='left';
  }
  function rightText(ctx,label,x,y,width,size,weight){
    let font=size;
    do{ctx.font=weight+' '+font+'px Arial, sans-serif';font--;}while(ctx.measureText(label).width>width&&font>14);
    ctx.textAlign='right';ctx.fillText(label,x,y);ctx.textAlign='left';
  }
  function drawLogo(ctx,img,x,y,maxWidth,maxHeight,align){
    if(!img)return;
    const scale=Math.min(maxWidth/img.width,maxHeight/img.height),w=img.width*scale,h=img.height*scale;
    ctx.drawImage(img,align==='right'?x-w:x,y+(maxHeight-h)/2,w,h);
  }
  function portrait(ctx,img,cx,cy,radius,ring,name){
    ctx.save();ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.closePath();ctx.fillStyle='#2c2724';ctx.fill();ctx.clip();
    if(img){const side=Math.min(img.width,img.height);ctx.drawImage(img,(img.width-side)/2,(img.height-side)/2,side,side,cx-radius,cy-radius,radius*2,radius*2);}
    else{ctx.fillStyle='#a99f94';centered(ctx,String(name||'?').charAt(0),cx,cy+radius*.35,radius,radius,700);}
    ctx.restore();
    if(ring){ctx.strokeStyle=ring;ctx.lineWidth=4;ctx.beginPath();ctx.arc(cx,cy,radius+2,0,Math.PI*2);ctx.stroke();}
  }
  function points(value){const number=Number(String(value||'').replace(/[^\d.-]/g,''));return String(value||'').trim()&&Number.isFinite(number)?number:null;}
  function gapLabel(lead,value,metric){
    if(metric!=='PTS')return '';
    const first=points(lead),current=points(value);
    if(first===null||current===null)return '';
    return first===current?'=':'−'+(first-current);
  }
  // Dark mountain backdrop shared with the competition card, with the top three as a podium on the first image.
  async function draw(rows, index, count, height, context) {
    const canvas = document.createElement('canvas'); canvas.width = 1080; canvas.height = height;
    const ctx = canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    const gradient=ctx.createLinearGradient(0,0,0,height);gradient.addColorStop(0,'#111214');gradient.addColorStop(.55,'#1b1816');gradient.addColorStop(1,'#090a0b');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,1080,height);
    ctx.fillStyle='#231e1a';ctx.beginPath();ctx.moveTo(0,height*.45);ctx.lineTo(210,height*.25);ctx.lineTo(390,height*.4);ctx.lineTo(620,height*.18);ctx.lineTo(880,height*.42);ctx.lineTo(1080,height*.28);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    ctx.fillStyle='#191614';ctx.beginPath();ctx.moveTo(0,height*.62);ctx.lineTo(260,height*.44);ctx.lineTo(450,height*.58);ctx.lineTo(720,height*.4);ctx.lineTo(1080,height*.6);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    const [logo,brand,images]=await Promise.all([loadImage(context.logo),loadImage(context.brandLogo),Promise.all(rows.map(row=>loadImage(row.photo)))]);
    ctx.fillStyle='#f5f1e9';ctx.beginPath();ctx.roundRect(54,36,300,84,14);ctx.fill();
    if(logo)drawLogo(ctx,logo,68,44,272,68);else{ctx.fillStyle='#17181b';fit(ctx,'COMPETITION',74,92,260,24,true);}
    if(brand)drawLogo(ctx,brand,1026,26,104,104,'right');else{ctx.fillStyle='#f5f1e9';rightText(ctx,'RIDERSFANATICS',1026,92,300,24,700);}
    ctx.fillStyle='#f5f1e9';centered(ctx,context.title.toUpperCase(),540,178,960,44,800);
    ctx.fillStyle='#c9c0b5';centered(ctx,context.subtitle.toUpperCase(),540,214,960,22,600);
    ctx.fillStyle='#b4491c';ctx.fillRect(486,236,54,5);ctx.fillStyle='#e8dfd1';ctx.fillRect(540,236,54,5);
    const metric=rows.find(row=>row.metric)?.metric||'';
    const podium=index===0&&!context.team&&rows.length>=3?3:0;
    if(podium){
      [[0,540,362,96],[1,240,400,80],[2,840,420,74]].forEach(([i,cx,cy,radius])=>{
        const row=rows[i];
        ctx.save();ctx.shadowColor='rgba(0,0,0,.55)';ctx.shadowBlur=30;ctx.fillStyle='#000';ctx.beginPath();ctx.arc(cx,cy,radius,0,Math.PI*2);ctx.fill();ctx.restore();
        portrait(ctx,images[i],cx,cy,radius,MEDALS[i],row.name);
        ctx.fillStyle=MEDALS[i];ctx.beginPath();ctx.arc(cx+radius*.72,cy+radius*.72,24,0,Math.PI*2);ctx.fill();
        ctx.fillStyle='#17181b';centered(ctx,String(row.rank||i+1).replace(/^0+/,''),cx+radius*.72,cy+radius*.72+10,40,28,800);
        ctx.fillStyle='#f5f1e9';centered(ctx,(flag(row.country)+' '+row.name).trim(),cx,cy+radius+52,300,i?27:31,700);
        ctx.fillStyle=MEDALS[i];centered(ctx,row.value+(metric==='PTS'?' PTS':''),cx,cy+radius+88,300,i?24:28,800);
      });
    }
    const list=rows.slice(podium),top=podium?668:276,footer=height-118;
    const rowHeight=Math.min(podium?78:86,(footer-top)/Math.max(list.length,1));
    list.forEach((row,k)=>{
      const i=k+podium,y=top+k*rowHeight,cy=y+rowHeight/2,baseline=cy+11,medal=index===0&&i<3?MEDALS[i]:'';
      ctx.fillStyle=medal?'#2a2420ee':(k%2?'#151416dd':'#1f1b19dd');ctx.beginPath();ctx.roundRect(54,y+4,972,rowHeight-8,12);ctx.fill();
      if(medal){ctx.fillStyle=medal;ctx.fillRect(54,y+4,8,rowHeight-8);}
      ctx.fillStyle=medal||'#a99f94';fit(ctx,String(row.rank).padStart(2,'0'),80,baseline,70,30,true);
      portrait(ctx,images[i],180,cy,Math.min(28,rowHeight*.36),medal||'#3a3430',row.name);
      ctx.font='28px Arial';ctx.fillText(flag(row.country),226,baseline);
      ctx.fillStyle='#f5f1e9';fit(ctx,row.name,276,baseline,540,29,true);
      const gap=i===0&&index===0&&metric==='PTS'?'LEADER':gapLabel(context.lead,row.value,metric);
      if(gap){ctx.fillStyle='#8f867c';rightText(ctx,gap,880,baseline,120,20,700);}
      ctx.fillStyle='#f5f1e9';rightText(ctx,row.value,1004,baseline,metric==='TIME'?200:120,30,800);
    });
    ctx.fillStyle='#b4491c';ctx.fillRect(54,height-94,54,5);ctx.fillStyle='#e8dfd1';ctx.fillRect(108,height-94,54,5);
    ctx.fillStyle='#f5f1e9';fit(ctx,['@ridersfanatics',context.handle].filter(Boolean).join('  ·  '),54,height-50,560,22,true);
    ctx.fillStyle='#a99f94';rightText(ctx,'RIDERSFANATICS.COM · '+(index+1)+' / '+count,1026,height-50,420,18,700);
    return canvas;
  }
  const FR_MONTHS=['JANV.','FÉV.','MARS','AVR.','MAI','JUIN','JUIL.','AOÛT','SEPT.','OCT.','NOV.','DÉC.'];
  function parseDay(value){
    const day=String(value||'').slice(0,10);
    if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||day.startsWith('9999-'))return null;
    return {iso:day,year:day.slice(0,4),month:Number(day.slice(5,7))-1,day:Number(day.slice(8,10))};
  }
  function dateRange(start,end){
    const a=parseDay(start),b=parseDay(end);
    if(!a)return 'DATE À CONFIRMER';
    if(!b||b.iso<=a.iso)return a.day+' '+FR_MONTHS[a.month]+' '+a.year;
    if(a.month===b.month&&a.year===b.year)return a.day+' – '+b.day+' '+FR_MONTHS[a.month]+' '+a.year;
    return a.day+' '+FR_MONTHS[a.month]+' – '+b.day+' '+FR_MONTHS[b.month]+' '+b.year;
  }
  function frenchStatus(value){
    const status=String(value||'').toLowerCase();
    if(/cancel|annul/.test(status))return 'ANNULÉ';
    if(status.includes('results available'))return 'RÉSULTATS DISPONIBLES';
    if(status.includes('results pending'))return 'RÉSULTATS EN ATTENTE';
    if(status.includes('coming soon'))return 'À VENIR';
    if(status.includes('in progress'))return 'EN COURS';
    if(status.includes('ended'))return 'TERMINÉ';
    return value?String(value).toUpperCase():'À CONFIRMER';
  }
  function plural(count,word){return count+' '+word+(count===1?'':'s');}
  function mountainBackdrop(ctx,height){
    const gradient=ctx.createLinearGradient(0,0,0,height);gradient.addColorStop(0,'#111214');gradient.addColorStop(.55,'#1b1816');gradient.addColorStop(1,'#090a0b');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,1080,height);
    ctx.fillStyle='#231e1a';ctx.beginPath();ctx.moveTo(0,height*.45);ctx.lineTo(210,height*.25);ctx.lineTo(390,height*.4);ctx.lineTo(620,height*.18);ctx.lineTo(880,height*.42);ctx.lineTo(1080,height*.28);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
    ctx.fillStyle='#191614';ctx.beginPath();ctx.moveTo(0,height*.62);ctx.lineTo(260,height*.44);ctx.lineTo(450,height*.58);ctx.lineTo(720,height*.4);ctx.lineTo(1080,height*.6);ctx.lineTo(1080,height);ctx.lineTo(0,height);ctx.fill();
  }
  function accent(ctx,x,y){ctx.fillStyle='#b4491c';ctx.fillRect(x,y,54,5);ctx.fillStyle='#e8dfd1';ctx.fillRect(x+54,y,54,5);}
  function darkFooter(ctx,height,context,page){
    accent(ctx,54,height-94);
    ctx.fillStyle='#f5f1e9';fit(ctx,['@ridersfanatics',context.handle&&context.handle!=='@ridersfanatics'?context.handle:''].filter(Boolean).join('  ·  '),54,height-50,560,22,true);
    ctx.fillStyle='#a99f94';rightText(ctx,'RIDERSFANATICS.COM'+(page?' · '+page:''),1026,height-50,420,18,700);
  }
  async function darkHeader(ctx,context,title,subtitle){
    const [logo,brand]=await Promise.all([loadImage(context.logo),loadImage(context.brandLogo)]);
    if(logo&&context.logo!==context.brandLogo){ctx.fillStyle='#f5f1e9';ctx.beginPath();ctx.roundRect(54,36,300,84,14);ctx.fill();drawLogo(ctx,logo,68,44,272,68);}
    if(brand)drawLogo(ctx,brand,1026,26,104,104,'right');
    ctx.fillStyle='#f5f1e9';centered(ctx,title.toUpperCase(),540,178,960,44,800);
    ctx.fillStyle='#c9c0b5';centered(ctx,subtitle.toUpperCase(),540,214,960,22,600);
    accent(ctx,486,236);
  }
  async function drawEvent(height, context) {
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    mountainBackdrop(ctx,height);
    const card=data.eventCard||{};
    const [logo,brand]=await Promise.all([loadImage(context.logo),loadImage(context.brandLogo)]);
    if(brand)drawLogo(ctx,brand,1026,26,104,104,'right');
    ctx.fillStyle='#f5f1e9';ctx.beginPath();ctx.roundRect(190,170,700,220,22);ctx.fill();
    if(logo){const scale=Math.min(620/logo.width,170/logo.height),w=logo.width*scale,h=logo.height*scale;ctx.drawImage(logo,540-w/2,195+(170-h)/2,w,h);}else{ctx.fillStyle='#17181b';centered(ctx,'COMPÉTITION',540,300,600,48,800);}
    ctx.fillStyle='#a99f94';centered(ctx,[card.discipline,data.season].filter(Boolean).join(' · ').toUpperCase(),540,470,900,24,700);
    const name=String(context.title||card.name||'Événement').replace(/\s*-\s*20\d{2}\s*$/,'').toUpperCase();
    ctx.fillStyle='#f5f1e9';ctx.textAlign='center';const count=lines(ctx,name,540,560,960,name.length>14?72:96,name.length>14?80:100,2,true);ctx.textAlign='left';
    const flagY=560+(count-1)*(name.length>14?80:100)+90;
    const nation=eventNation(card);ctx.font='64px Arial';ctx.textAlign='center';ctx.fillText(flag(nation),540,flagY);ctx.textAlign='left';
    accent(ctx,486,flagY+40);
    const top=flagY+100;
    [['DATES',dateRange(card.date,card.endDate)],['LIEU',card.location||'À confirmer'],['STATUT',frenchStatus(card.status)]].forEach(([label,value],i)=>{
      const y=top+i*120;if(y+96>height-120)return;
      ctx.fillStyle='#1f1b19ee';ctx.beginPath();ctx.roundRect(140,y,800,96,16);ctx.fill();
      ctx.fillStyle='#b4491c';fit(ctx,label,180,y+58,200,20,true);ctx.fillStyle='#f5f1e9';rightText(ctx,value,900,y+60,520,34,800);
    });
    darkFooter(ctx,height,context);
    return canvas;
  }
  async function drawCompetition(height,context,calendarOverride){
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d'),card=data.competitionCard||{},full=card.calendar||[],calendar=calendarOverride&&calendarOverride.length?calendarOverride:full;
    ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';mountainBackdrop(ctx,height);
    const isCompetition=data.shareKind==='competition';
    const title=isCompetition?String(context.title||'').replace(new RegExp('\\s+'+String(data.season||'')+'$'),''):String(context.title||'Calendrier');
    const discipline=isCompetition&&card.discipline?' · '+card.discipline:'';
    await darkHeader(ctx,context,title,'Calendrier '+(data.season||'')+' · '+plural(full.length,isCompetition?'manche':'événement')+discipline);
    const today=new Date().toISOString().slice(0,10);
    const next=full.find(item=>{const start=parseDay(item.date);return start&&(parseDay(item.endDate)||start).iso>=today&&!/cancel|annul/i.test(item.status||'');});
    const top=280,bottom=height-130,rowHeight=Math.min(110,(bottom-top)/Math.max(calendar.length,1)),compact=rowHeight<90;
    calendar.forEach((item,index)=>{
      const y=top+index*rowHeight,cy=y+rowHeight/2,start=parseDay(item.date),end=parseDay(item.endDate),nation=eventNation(item);
      const cancelled=/cancel|annul/i.test(item.status||''),ended=!!start&&(end||start).iso<today,isNext=item===next;
      ctx.globalAlpha=ended||cancelled?.55:1;
      ctx.fillStyle=isNext?'#3a2416':(index%2?'#151416dd':'#1f1b19dd');ctx.beginPath();ctx.roundRect(54,y+4,972,rowHeight-8,14);ctx.fill();
      if(isNext){ctx.strokeStyle='#b4491c';ctx.lineWidth=3;ctx.stroke();}
      ctx.fillStyle=isNext?'#b4491c':'#2c2724';ctx.beginPath();ctx.roundRect(72,y+(compact?10:18),104,rowHeight-(compact?20:36),10);ctx.fill();
      ctx.fillStyle='#f5f1e9';
      if(start){centered(ctx,String(start.day).padStart(2,'0')+(end&&end.iso>start.iso&&end.month===start.month?'–'+String(end.day).padStart(2,'0'):''),124,cy+(compact?2:-2),92,compact?24:30,800);centered(ctx,FR_MONTHS[start.month],124,cy+(compact?20:24),92,compact?14:18,700);}
      else centered(ctx,'À VENIR',124,cy+7,92,16,800);
      ctx.font=(compact?30:38)+'px Arial';ctx.fillText(flag(nation),198,cy+(compact?10:13));
      const label=String(item.name||item.location||'Événement').replace(/\s*-\s*20\d{2}\s*$/,'');
      ctx.fillStyle='#f5f1e9';fit(ctx,label,262,cy+(compact?2:4),500,compact?26:34,true);
      const meta=isCompetition?'MANCHE '+(full.indexOf(item)+1)+' · '+nation:[item.location,disciplineCode(item.discipline||card.discipline)].filter(Boolean).join(' · ').toUpperCase();
      ctx.fillStyle='#a99f94';fit(ctx,meta,262,cy+(compact?24:32),500,compact?15:18,true);
      if(isNext){ctx.fillStyle='#b4491c';ctx.beginPath();ctx.roundRect(806,cy-22,196,44,22);ctx.fill();ctx.fillStyle='#f5f1e9';centered(ctx,'PROCHAINE',904,cy+8,170,20,800);}
      else{ctx.fillStyle='#a99f94';rightText(ctx,cancelled?'ANNULÉ':(ended?'TERMINÉ':disciplineCode(item.discipline||card.discipline)),1000,cy+8,170,20,700);}
      ctx.globalAlpha=1;
    });
    if(!calendar.length){ctx.fillStyle='#f5f1e9';centered(ctx,'CALENDRIER À VENIR',540,height/2,840,48,800);ctx.fillStyle='#a99f94';centered(ctx,'Les dates seront publiées dès leur confirmation.',540,height/2+50,840,24,400);}
    darkFooter(ctx,height,context);
    return canvas;
  }
  async function drawSeason(height,context,titles){
    const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height;
    const ctx=canvas.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';mountainBackdrop(ctx,height);
    const brand=await loadImage(context.logo||context.brandLogo);
    if(brand)drawLogo(ctx,brand,455,40,170,170);
    const season=String(data.season||String(context.title||'').match(/20\d{2}/)?.[0]||'');
    ctx.fillStyle='#f5f1e9';centered(ctx,('Saison '+season).trim().toUpperCase(),540,282,960,64,800);
    ctx.fillStyle='#c9c0b5';centered(ctx,'LES COMPÉTITIONS SUIVIES PAR RIDERSFANATICS',540,322,960,22,600);
    accent(ctx,486,346);
    const list=(titles||[]).slice(0,10).map(item=>typeof item==='string'?{title:item,logo:''}:item);
    const logos=await Promise.all(list.map(item=>loadImage(item.logo)));
    const top=392,bottom=height-120,gap=22,single=list.length===1,rows=single?1:Math.ceil(list.length/2);
    const cardHeight=Math.min(270,(bottom-top-gap*(rows-1))/Math.max(rows,1)),logoHeight=cardHeight*.52;
    list.forEach((item,i)=>{
      const width=single?972:474,x=single?54:54+(i%2)*(width+24),y=top+Math.floor(single?0:i/2)*(cardHeight+gap);
      ctx.fillStyle='#1f1b19ee';ctx.beginPath();ctx.roundRect(x,y,width,cardHeight,18);ctx.fill();
      ctx.fillStyle='#f5f1e9';ctx.beginPath();ctx.roundRect(x+18,y+18,width-36,logoHeight,12);ctx.fill();
      if(logos[i]){const img=logos[i],scale=Math.min((width-80)/img.width,(logoHeight-24)/img.height),w=img.width*scale,h=img.height*scale;ctx.drawImage(img,x+width/2-w/2,y+18+(logoHeight-h)/2,w,h);}
      else{ctx.fillStyle='#17181b';centered(ctx,String(item.title||'Compétition').toUpperCase(),x+width/2,y+18+logoHeight/2+10,width-80,28,800);}
      const textTop=y+18+logoHeight,space=cardHeight-18-logoHeight;
      ctx.fillStyle='#f5f1e9';fit(ctx,String(item.title||'Compétition'),x+24,textTop+space*.48,width-48,Math.min(28,space*.32),true);
      if(item.events){ctx.fillStyle='#a99f94';fit(ctx,plural(item.events,'événement').toUpperCase(),x+24,textTop+space*.8,width-48,Math.min(18,space*.2),true);}
    });
    darkFooter(ctx,height,{handle:''});
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
      brandLogo:data.brandLogo || new URL('../img/brand/freeride-fanatics-summer.png',socialAssets).href, lead:rows[0]?.value || '',
      subtitle:isEvent ? [data.eventCard.date,data.eventCard.location,data.eventCard.status].filter(Boolean).join(' · ') : [panel.dataset.standings, panel.dataset.standingStage || (event.name ? 'Event ranking' : 'Overall ranking'), data.season].filter(Boolean).join(' · ')};
    const seasonShare=data.shareKind==='season';
    const calendarShare=data.shareKind==='competition'||data.shareKind==='year';
    const yearPages=chunks(data.competitionCard?.calendar || []);
    const seasonPages=chunks(data.seasonCompetitions || data.seasonTitles || []);
    const allPages = isEvent ? (seasonShare ? (seasonPages.length ? seasonPages : [[]]) : (data.shareKind==='year' ? (yearPages.length ? yearPages : [[]]) : [[]])) : chunks(rows), urls = [], calendarUrls=[];
    const dialog = el('dialog'); dialog.className='ranking-share-dialog';
    const header=el('header','',dialog);header.className='ranking-share-header';
    const heading=el('h2','Partager '+(isEvent ? (seasonShare ? 'la saison' : (calendarShare ? 'le calendrier' : 'l’événement')) : 'le classement'),header);
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
    const calendarToggle=el('button','Ajouter au calendrier',actions);calendarToggle.type='button';calendarToggle.className='ranking-share-calendar-toggle';calendarToggle.hidden=seasonShare;
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
          const canvas=isEvent ? (seasonShare ? await drawSeason(1350,context,pages[i]) : (calendarShare ? await drawCompetition(1350,context,pages[i]) : await drawEvent(1350,context))) : await draw(pages[i],i,pages.length,1350,context);
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          if(token!==version)return;
          if(!blob)throw new Error('Image generation failed');
          const item=el('div','',gallery), choice=el('label','',item), checkbox=el('input','',choice);
          checkbox.type='checkbox'; checkbox.checked=previous[i] ?? true;
          choice.append(document.createTextNode(' Image '+(i+1)));choice.hidden=isEvent&&pages.length===1;
          const url=URL.createObjectURL(blob); urls.push(url);
          canvas.setAttribute('role','img'); canvas.setAttribute('aria-label',isEvent ? context.title+' — event card' : context.title+' — entries '+(i*10+1)+'–'+Math.min((i+1)*10,rows.length)); const preview=el('a','',item);preview.href=url;preview.target='_blank';preview.rel='noopener';preview.className='ranking-share-preview';preview.setAttribute('aria-label','Agrandir l’image '+(i+1)+' (nouvel onglet)');preview.append(canvas);
          const file=new File([blob],'ridersfanatics-'+(seasonShare ? 'season' : (isEvent ? 'event' : 'ranking'))+'-'+String(i+1).padStart(2,'0')+'.png',{type:'image/png'});
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
  function downloadCalendarItems(items, title) {
    const events=calendarEvents(items, title, location.href);
    if(!events.length){window.alert('No confirmed dates are available for this calendar yet.');return;}
    const url=URL.createObjectURL(new Blob([calendarFile(events)],{type:'text/calendar;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download=(title||'ridersfanatics-calendar').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')+'.ics';
    document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
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
      const calendar=el('button','Add calendar');calendar.type='button';calendar.className='ranking-share-trigger calendar-trigger';calendar.setAttribute('aria-label',isCompetition ? 'Add the season calendar' : 'Add this event to your calendar');
      calendar.onclick=()=>downloadCalendarItems(isCompetition ? (data.competitionCard?.calendar || []) : [{...(data.eventCard || {}),name:data.eventCard?.name || data.title}],isCompetition ? data.title+' season' : data.title);host.append(calendar);
    }
  }
  document.querySelectorAll('[data-year-share-payload]').forEach(host=>{
    let payload;
    try{payload=JSON.parse(host.dataset.yearSharePayload || '');}catch(_){return;}
    const season=el('button','Share season');season.type='button';
    season.className='ranking-share-trigger competition-year-share-trigger';
    season.setAttribute('aria-label','Share the '+payload.season+' competition titles');
    season.onclick=()=>{data={...payload,shareKind:'season'};open(null,season);};
    host.append(season);
    const calendar=el('button','Share calendar');calendar.type='button';calendar.className='ranking-share-trigger calendar-trigger';calendar.setAttribute('aria-label','Share the '+payload.season+' calendar');
    calendar.onclick=()=>{data=payload;open(null,calendar);};host.append(calendar);
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
