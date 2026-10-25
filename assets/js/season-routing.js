/* Keep the preproduction season preference consistent across directory pages. */
(function () {
  'use strict';
  var storageKey = 'rf-preprod-home-appearance-v1';
  var routeNames = ['competitions', 'riders', 'equipment'];
  var summerRoutes = {
    competitions: '/competitions.html',
    riders: '/riders.html#grid',
    equipment: '/equipment.html'
  };
  var winterRoutes = {
    competitions: '/winter/competitions.html',
    riders: '/winter/riders.html#grid',
    equipment: '/winter/equipment.html'
  };

  function preference() {
    try { return localStorage.getItem(storageKey) === 'winter' ? 'winter' : 'summer'; }
    catch (_) { return 'summer'; }
  }

  function setPreference(value) {
    try { localStorage.setItem(storageKey, value); } catch (_) {}
  }

  function updateLinks(season) {
    var routes = season === 'winter' ? winterRoutes : summerRoutes;
    var links = document.querySelectorAll('[data-season-route]');
    for (var index = 0; index < links.length; index++) {
      var name = links[index].dataset.seasonRoute;
      if (routes[name]) links[index].setAttribute('href', routes[name]);
    }
  }

  function updateScopes(season) {
    var scoped = document.querySelectorAll('[data-season-scope]');
    for (var index = 0; index < scoped.length; index++) {
      scoped[index].hidden = scoped[index].dataset.seasonScope !== season;
    }
  }

  function counterpart(pathname, season) {
    for (var index = 0; index < routeNames.length; index++) {
      var name = routeNames[index];
      if (season === 'winter' && pathname === summerRoutes[name].split('#')[0]) return winterRoutes[name];
      if (season === 'summer' && pathname === winterRoutes[name].split('#')[0]) return summerRoutes[name];
    }
    return '';
  }

  var season = preference();
  updateLinks(season);
  updateScopes(season);
  var destination = counterpart(window.location.pathname, season);
  if (destination) {
    window.location.replace(destination);
    return;
  }

  var winterPage = document.body.classList.contains('winter-data-page');
  var toggle = document.querySelector('.season-switch');
  if (winterPage && toggle) {
    toggle.hidden = false;
    toggle.setAttribute('aria-checked', 'true');
    toggle.addEventListener('click', function () {
      setPreference('summer');
      var summerDestination = counterpart(window.location.pathname, 'summer') || '/';
      window.location.assign(summerDestination);
    });
  }

  window.addEventListener('rf-season-change', function (event) {
    var nextSeason = event.detail === 'winter' ? 'winter' : 'summer';
    updateLinks(nextSeason);
    updateScopes(nextSeason);
  });
  window.addEventListener('storage', function (event) {
    if (event.key === storageKey) {
      var nextSeason = event.newValue === 'winter' ? 'winter' : 'summer';
      updateLinks(nextSeason);
      updateScopes(nextSeason);
    }
  });
})();
