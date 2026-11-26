/* Preproduction-only French/Spanish/Chinese interface; no crawlable language URL variants. */
(function(){
  'use strict';
  var script=document.currentScript;
  var root=new URL('../../',script.src);
  var originals=new WeakMap(), attributes=new WeakMap(), language='en', catalog={}, catalogs={};
  function isTranslatablePage(){
    var path=location.pathname.replace(/^\/winter(?=\/|$)/,'');
    return /^\/(?:competitions(?:\/|\.html)|equipment(?:\/|\.html))/.test(path);
  }
  function excluded(node){return node.parentElement && node.parentElement.closest('script,style,svg,code,pre,[translate="no"],.header-language-menu,.logo,.rider-meta a,.equip-item h4,.winter-brand-thumb');}
  function phrase(value){var key=value.trim();return catalog[key] ? value.replace(key,catalog[key]) : value;}
  function render(){
    if(!isTranslatablePage())return;
    document.documentElement.lang=language;
    var walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT),node;
    while((node=walker.nextNode())){
      if(excluded(node))continue;
      if(!originals.has(node))originals.set(node,node.nodeValue);
      var value=originals.get(node),translated=language==='fr'?phrase(value):value;
      if(node.nodeValue!==translated)node.nodeValue=translated;
    }
    document.querySelectorAll('[aria-label],[placeholder],[title]').forEach(function(el){
      if(el.closest('[translate="no"],.header-language'))return;
      var saved=attributes.get(el)||{};
      ['aria-label','placeholder','title'].forEach(function(name){
        if(!el.hasAttribute(name))return;
        if(!(name in saved))saved[name]=el.getAttribute(name);
        var value=language==='fr'?phrase(saved[name]):saved[name];
        if(el.getAttribute(name)!==value)el.setAttribute(name,value);
      });attributes.set(el,saved);
    });
    var summary=document.querySelector('.header-language summary');
    var label=language==='fr'?'🇫🇷 FR ⌄':language==='es'?'🇪🇸 ES ⌄':language==='zh-cn'?'🇨🇳 ZH ⌄':'🇬🇧 EN ⌄';
    if(summary && summary.textContent!==label)summary.textContent=label;
  }
  function select(value){language=value;catalog=catalogs[value]||{};try{localStorage.setItem('rf-preview-language',value);}catch(e){} render();}
  Promise.all(['fr.json','fr-overrides.json','es.json','es-overrides.json','zh-cn.json','zh-cn-overrides.json'].map(function(file){return fetch(new URL('assets/i18n/'+file,root)).then(function(r){if(!r.ok)throw Error('Language catalog unavailable');return r.json();});})).then(function(data){
    catalogs.fr=Object.assign({},data[0],data[1],{'CAN':'CAN','USA':'USA','Amazon':'Amazon','Pro':'Pro','Home':'Accueil','Points':'Points','Round':'Manche','Rounds':'Manches','Rider':'Pilote','Riders':'Pilotes','riders':'pilotes','Share setup':'Partager les équipements','Share competition':'Partager la compétition','Add calendar':'Ajouter au calendrier','Details':'Détails','Skis & Snowboards':'Skis et snowboards','Random skier':'Skieur au hasard','Random snowboarder':'Snowboardeur au hasard','Equipment':'Équipement','Global ranking':'Classement général','Qualifier':'Qualifications','Final':'Finale','Coming soon':'À venir','Used by':'Utilisé par'});
    catalogs.es=Object.assign({},data[2],data[3],{'CAN':'CAN','USA':'EE. UU.','Amazon':'Amazon','Pro':'Pro','Home':'Inicio','Points':'Puntos','Round':'Ronda','Rounds':'Rondas','Rider':'Piloto','Riders':'Pilotos','riders':'pilotos','Share setup':'Compartir el equipamiento','Share competition':'Compartir la competición','Add calendar':'Añadir al calendario','Details':'Detalles','Skis & Snowboards':'Esquís y snowboards','Random skier':'Esquiador aleatorio','Random snowboarder':'Snowboarder aleatorio','Equipment':'Equipamiento','Global ranking':'Clasificación general','Qualifier':'Clasificación','Final':'Final','Coming soon':'Próximamente','Used by':'Usado por'});
    catalogs['zh-cn']=Object.assign({},data[4],data[5],{'CAN':'CAN','USA':'美国','Amazon':'Amazon','Pro':'职业','Home':'首页','Points':'积分','Round':'分站','Rounds':'分站赛','Rider':'车手','Riders':'车手','riders':'车手','Share setup':'分享装备','Share competition':'分享比赛','Add calendar':'添加到日历','Details':'详情','Skis & Snowboards':'滑雪板与单板滑雪板','Random skier':'随机滑雪者','Random snowboarder':'随机单板滑雪者','Equipment':'装备','Global ranking':'总排名','Qualifier':'资格赛','Final':'决赛','Coming soon':'即将开始','Used by':'使用者'});
    try{var saved=localStorage.getItem('rf-preview-language');language=saved==='fr'||saved==='es'||saved==='zh-cn'?saved:'en';}catch(e){}
    catalog=catalogs[language]||{};
    document.addEventListener('click',function(event){var link=event.target.closest('.header-language-menu a');if(!link)return;var code=link.getAttribute('lang').toLowerCase();if(code==='fr'||code==='es'||code==='en'||code==='zh-cn'){event.preventDefault();select(code);link.closest('details').open=false;}},true);
    render();
    var pending=false;new MutationObserver(function(){if(pending)return;pending=true;requestAnimationFrame(function(){pending=false;render();});}).observe(document.body,{childList:true,subtree:true});
  }).catch(function(error){console.warn(error.message);});
})();
