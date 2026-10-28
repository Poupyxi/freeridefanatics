(function () {
  'use strict';
  // Never request live advertisements on localhost or preproduction.
  if (!/^(www\.)?ridersfanatics\.com$/.test(location.hostname)) return;
  var unit = document.querySelector('.footer-ad-unit');
  if (!unit) return;
  var requested = false;
  function requestAd() {
    if (requested || !unit.getBoundingClientRect().width) return;
    requested = true;
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      if (entries.some(function (entry) { return entry.isIntersecting; })) {
        requestAd();
        if (requested) observer.disconnect();
      }
    }, {rootMargin: '300px'});
    observer.observe(unit);
  } else {
    requestAd();
  }
  // Use Google's supported callback so visitors can revisit their ad choices.
  var links = document.querySelector('.footer-links');
  if (links) {
    var preferences = document.createElement('button');
    preferences.type = 'button';
    preferences.className = 'footer-consent-link';
    preferences.textContent = 'Advertising preferences';
    preferences.hidden = true;
    preferences.addEventListener('click', function () {
      if (typeof window.googlefc.showRevocationMessage === 'function') {
        window.googlefc.showRevocationMessage();
      }
    });
    links.appendChild(preferences);
    window.googlefc = window.googlefc || {};
    window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
    window.googlefc.callbackQueue.push({CONSENT_API_READY: function () {
      if (typeof window.__tcfapi !== 'function') return;
      window.__tcfapi('addEventListener', 2, function (data, success) {
        preferences.hidden = !(success && data && data.gdprApplies);
      });
    }});
  }
})();
