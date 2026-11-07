(function () {
  'use strict';
  // Bootstrap the queue and hidden presence frame before Google's Funding
  // Choices script loads. The external CMP remains the source of truth for
  // the consent UI and TCF string.
  window.googlefc = window.googlefc || {};
  window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
  function signalGooglefcPresent() {
    if (window.frames.googlefcPresent) return;
    if (!document.body) {
      window.setTimeout(signalGooglefcPresent, 0);
      return;
    }
    var frame = document.createElement('iframe');
    frame.style = 'width:0;height:0;border:none;z-index:-1000;left:-1000px;top:-1000px;display:none;';
    frame.name = 'googlefcPresent';
    document.body.appendChild(frame);
  }
  signalGooglefcPresent();
}());
