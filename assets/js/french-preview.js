/* Preproduction-only French interface; no crawlable language URL variants. */
(function(){
  'use strict';
  var script=document.currentScript;
  var root=new URL('../../',script.src);
  var originals=new WeakMap(), attributes=new WeakMap(), language='en', catalog={};
  function excluded(node){return node.parentElement && node.parentElement.closest('script,style,svg,code,pre,[translate="no"],.header-language-menu,.logo,.rider-meta a,.equip-item h4,.winter-brand-thumb');}
  function phrase(value){var key=value.trim();return catalog[key] ? value.replace(key,catalog[key]) : value;}
  function render(){
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
    var label=language==='fr'?'🇫🇷 FR ⌄':'🇬🇧 EN ⌄';
    if(summary && summary.textContent!==label)summary.textContent=label;
  }
  function select(value){language=value;try{localStorage.setItem('rf-preview-language',value);}catch(e){} render();}
  Promise.all(['fr.json','fr-overrides.json'].map(function(file){return fetch(new URL('assets/i18n/'+file,root)).then(function(r){if(!r.ok)throw Error('French catalog unavailable');return r.json();});})).then(function(data){
    catalog=Object.assign({},data[0],data[1],{'CAN':'CAN','USA':'USA','Amazon':'Amazon','Pro':'Pro','Home':'Accueil','Points':'Points','Round':'Manche','Rounds':'Manches','Rider':'Athlète','Riders':'Athlètes','riders':'athlètes','Share setup':'Partager les équipements','Share competition':'Partager la compétition','Add calendar':'Ajouter au calendrier','Details':'Détails','Skis & Snowboards':'Skis et snowboards','Random skier':'Skieur au hasard','Random snowboarder':'Snowboardeur au hasard','Equipment':'Équipements','Global ranking':'Classement général','Qualifier':'Qualifications','Final':'Finale','Coming soon':'À venir','Used by':'Utilisé par'});
    try{language=localStorage.getItem('rf-preview-language')==='fr'?'fr':'en';}catch(e){}
    document.addEventListener('click',function(event){var link=event.target.closest('.header-language-menu a');if(!link)return;var code=link.getAttribute('lang');if(code==='fr'||code==='en'){event.preventDefault();select(code);link.closest('details').open=false;}},true);
    render();
    var pending=false;new MutationObserver(function(){if(pending)return;pending=true;requestAnimationFrame(function(){pending=false;render();});}).observe(document.body,{childList:true,subtree:true});
  }).catch(function(error){console.warn(error.message);});
})();
