(function () {
  'use strict';
  // Preview never loads Google, reads consent, or stores an advertising choice.
  if (!/^(www\.)?ridersfanatics\.com$/.test(location.hostname)) return;
  var unit = document.querySelector('ins.rider-ad-unit');
  if (!unit) return;
  var client = unit.getAttribute('data-ad-client');
  var slot = unit.getAttribute('data-ad-slot');
  if (!/^ca-pub-\d{16}$/.test(client || '') || !/^\d{10}$/.test(slot || '')) return;
  var allowed = false, visible = false, loaded = false, requested = false;
  var links = document.querySelector('.footer-links');
  var preferences = document.createElement('button');
  preferences.type = 'button';
  preferences.className = 'footer-consent-link';
  preferences.textContent = 'Privacy and cookie settings';
  preferences.hidden = true;
  preferences.addEventListener('click', function () {
    if (window.googlefc && typeof window.googlefc.showRevocationMessage === 'function') {
      window.googlefc.showRevocationMessage();
    }
  });
  if (links) links.appendChild(preferences);

  function requestAd() {
    if (!allowed || !visible || requested || !unit.getBoundingClientRect().width) return;
    if (!loaded) {
      loaded = true;
      var script = document.createElement('script');
      script.async = true;
      script.crossOrigin = 'anonymous';
      script.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + encodeURIComponent(client);
      document.head.appendChild(script);
    }
    requested = true;
    (window.adsbygoogle = window.adsbygoogle || []).push({});
  }
  function hasConsent(data, success) {
    // Deliberately require explicit consent everywhere, including unknown regions.
    if (!success || !data || data.cmpStatus !== 'loaded' || !data.tcString ||
        !['tcloaded', 'useractioncomplete'].includes(data.eventStatus)) return false;
    var purposes = [1, 2, 3, 4, 7, 9, 10];
    if (!data.vendor || !data.vendor.consents || data.vendor.consents[755] !== true) return false;
    return purposes.every(function (purpose) {
      var restriction = data.publisher && data.publisher.restrictions && data.publisher.restrictions[purpose];
      return data.purpose && data.purpose.consents && data.purpose.consents[purpose] === true &&
        (!restriction || restriction[755] === undefined || restriction[755] === 1);
    });
  }
  var subscribed = false;
  function subscribe() {
    if (subscribed || typeof window.__tcfapi !== 'function' ||
        typeof window.googlefc.showRevocationMessage !== 'function') return;
    subscribed = true;
    preferences.hidden = false;
    window.__tcfapi('addEventListener', 2, function (data, success) {
      // Opening preferences isn't a revocation. Wait for the completed choice.
      if (success && data && data.eventStatus === 'cmpuishown') return;
      allowed = hasConsent(data, success);
      if (!allowed && loaded) {
        unit.replaceChildren();
        location.reload(); // Unload third-party timers/frames after withdrawal.
        return;
      }
      requestAd();
    });
  }
  window.googlefc = window.googlefc || {};
  window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
  window.googlefc.callbackQueue.push({CONSENT_API_READY: subscribe});
  subscribe();
  if ('IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      visible = entries.some(function (entry) { return entry.isIntersecting; });
      requestAd();
    }, {rootMargin: '300px'});
    observer.observe(unit);
  } else {
    visible = true;
    requestAd();
  }
  // Keep the CMP's own revocation control as an additional accessible entry point.
})();
