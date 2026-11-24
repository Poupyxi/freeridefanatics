// ErrorDocument preserves the missing URL; always use root-relative assets.
(function(){
  if(location.pathname.indexOf('/winter/')!==0)return;
  document.querySelectorAll('[data-not-found-route]').forEach(function(link){
    link.href='/winter/'+link.dataset.notFoundRoute+'.html';
  });
})();
