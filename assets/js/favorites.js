(function(){
  var grid = document.getElementById('favorite-product-grid');
  var search = document.getElementById('favorite-search');
  var count = document.getElementById('favorite-count');
  var empty = document.getElementById('favorite-empty');
  var filters = Array.prototype.slice.call(document.querySelectorAll('[data-filter]'));
  if(!grid || !search || !count || !empty || !filters.length) return;

  var cards = Array.prototype.slice.call(grid.querySelectorAll('.favorite-product-card'));
  var activeFilter = 'all';

  function refresh(){
    var query = search.value.trim().toLowerCase();
    var visible = 0;
    cards.forEach(function(card){
      var categoryMatch = activeFilter === 'all' || card.dataset.category === activeFilter;
      var searchMatch = !query || (card.dataset.search || '').toLowerCase().indexOf(query) !== -1;
      card.hidden = !(categoryMatch && searchMatch);
      if(!card.hidden) visible += 1;
    });
    count.textContent = visible;
    empty.hidden = visible !== 0;
  }

  filters.forEach(function(button){
    button.addEventListener('click', function(){
      activeFilter = button.dataset.filter;
      filters.forEach(function(item){
        var selected = item === button;
        item.classList.toggle('is-active', selected);
        item.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      refresh();
    });
  });
  search.addEventListener('input', refresh);
})();
