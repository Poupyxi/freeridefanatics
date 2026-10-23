/* Preproduction homepage appearance only; no data, routing or sport filtering. */
(function () {
  'use strict';
  var page = document.querySelector('.seasonal-home');
  if (!page || page.dataset.seasonReady) return;
  var toggle = page.querySelector('.season-switch');
  var weather = page.querySelector('.season-weather');
  var status = page.querySelector('#season-appearance-status');
  if (!toggle || !weather || !status) return;
  page.dataset.seasonReady = 'true';
  var preference = 'summer';
  var storageKey = 'rf-preprod-home-appearance-v1';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var timer;
  try {
    if (localStorage.getItem(storageKey) === 'winter') preference = 'winter';
  } catch (_) { /* Private browsing can disallow storage. */ }

  function clearWeather() {
    clearTimeout(timer);
    weather.replaceChildren();
    page.classList.remove('season-changing');
  }

  function apply(season, animate) {
    preference = season;
    clearWeather();
    var winter = season === 'winter';
    page.classList.toggle('season-instant', !animate || reduced.matches);
    page.classList.toggle('season-winter', winter);
    toggle.setAttribute('aria-checked', String(winter));
    status.textContent = winter ? 'Winter' : 'Summer';
    if (!animate || reduced.matches || !winter || document.hidden) return;
    void page.offsetWidth;
    page.classList.add('season-changing');
    var snow = document.createDocumentFragment();
    for (var i = 0; i < 60; i++) {
      var flake = document.createElement('span');
      flake.className = 'season-flake';
      flake.style.setProperty('--x', (Math.random() * 100) + '%');
      flake.style.setProperty('--size', (2 + Math.random() * 5) + 'px');
      flake.style.setProperty('--duration', (2 + Math.random() * 1.3) + 's');
      flake.style.setProperty('--delay', (Math.random() * 0.6) + 's');
      flake.style.setProperty('--drift', (Math.random() * 60 - 30) + 'px');
      snow.appendChild(flake);
    }
    weather.appendChild(snow);
    timer = setTimeout(clearWeather, 4100);
  }

  apply(preference, false);
  toggle.hidden = false;
  toggle.addEventListener('click', function () {
    apply(preference === 'summer' ? 'winter' : 'summer', true);
    try { localStorage.setItem(storageKey, preference); } catch (_) {}
  });
  reduced.addEventListener('change', function () { apply(preference, false); });
  document.addEventListener('visibilitychange', function () {
    if (document.hidden) clearWeather();
  });
  window.addEventListener('pagehide', clearWeather);
  window.addEventListener('storage', function (event) {
    if (event.key === storageKey) apply(event.newValue === 'winter' ? 'winter' : 'summer', false);
  });
})();
