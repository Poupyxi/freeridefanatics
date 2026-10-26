/* Keep the preproduction season preference consistent across the whole site. */
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

  function updatePage(season) {
    updateLinks(season);
    updateScopes(season);
    document.body.classList.toggle('season-winter', season === 'winter');
    var toggle = document.querySelector('.season-switch');
    if (!toggle) return;
    toggle.hidden = false;
    toggle.setAttribute('aria-checked', String(season === 'winter'));
    toggle.setAttribute('aria-label', season === 'winter' ?
      'Switch to Summer season' : 'Switch to Winter season');
  }

  function counterpart(pathname, season) {
    for (var index = 0; index < routeNames.length; index++) {
      var name = routeNames[index];
      if (season === 'winter' && pathname === summerRoutes[name].split('#')[0]) return winterRoutes[name];
      if (season === 'summer' && pathname === winterRoutes[name].split('#')[0]) return summerRoutes[name];
    }
    return '';
  }

  function sectionDestination(pathname, season) {
    var exact = counterpart(pathname, season);
    if (exact) return exact;
    var winter = season === 'winter';
    var normalized = pathname.replace(/^\/winter(?=\/)/, '');
    if (normalized === '/riders' || normalized.indexOf('/riders/') === 0) {
      return winter ? winterRoutes.riders : summerRoutes.riders;
    }
    if (normalized === '/competitions' || normalized.indexOf('/competitions/') === 0) {
      return winter ? winterRoutes.competitions : summerRoutes.competitions;
    }
    if (normalized === '/equipment' || normalized.indexOf('/equipment/') === 0) {
      return winter ? winterRoutes.equipment : summerRoutes.equipment;
    }
    return '';
  }

  var season = preference();
  updatePage(season);
  var destination = counterpart(window.location.pathname, season);
  if (destination) {
    window.location.replace(destination);
    return;
  }

  var toggle = document.querySelector('.season-switch');
  var homepageAnimationOwnsToggle = Boolean(document.querySelector('.season-weather'));
  if (toggle && !homepageAnimationOwnsToggle) {
    toggle.addEventListener('click', function () {
      var nextSeason = preference() === 'winter' ? 'summer' : 'winter';
      setPreference(nextSeason);
      updatePage(nextSeason);
      var nextDestination = sectionDestination(window.location.pathname, nextSeason);
      if (nextDestination) window.location.assign(nextDestination);
    });
  }

  window.addEventListener('rf-season-change', function (event) {
    var nextSeason = event.detail === 'winter' ? 'winter' : 'summer';
    updatePage(nextSeason);
  });
  window.addEventListener('storage', function (event) {
    if (event.key === storageKey) {
      var nextSeason = event.newValue === 'winter' ? 'winter' : 'summer';
      updatePage(nextSeason);
    }
  });
})();
