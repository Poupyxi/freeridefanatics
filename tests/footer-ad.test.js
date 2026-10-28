const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/js/footer-ad.js', 'utf8');
function run(hostname, width = 800) {
  let callback, disconnected = false, button, mutationCallback, removed = false;
  const unit = {getBoundingClientRect: () => ({width})};
  const window = {};
  const context = {window, location: {hostname}, document: {
    body: {},
    querySelector: selector => selector === '.rider-ad-unit' ? unit : {appendChild: node => {button = node;}},
    querySelectorAll: selector => selector === '.google-revocation-link-placeholder' ? [{remove: () => {removed = true;}}] : [],
    createElement: () => ({addEventListener(name, fn) {this[name] = fn;}})
  }, IntersectionObserver: function (fn) {callback = fn; this.observe = () => {}; this.disconnect = () => {disconnected = true;};}, MutationObserver: function (fn) {mutationCallback = fn; this.observe = () => {};}};
  window.IntersectionObserver = context.IntersectionObserver;
  window.MutationObserver = context.MutationObserver;
  vm.runInNewContext(source, context);
  return {window, get button() {return button;}, intersect: () => callback([{isIntersecting: true}]), mutate: () => mutationCallback(), get disconnected() {return disconnected;}, get removed() {return removed;}};
}
for (const host of ['localhost','127.0.0.1','preprod.ridersfanatics.com']) {
  assert.equal(run(host).window.adsbygoogle, undefined);
}
const page = run('ridersfanatics.com');
assert.equal(page.window.adsbygoogle, undefined);
page.intersect(); page.intersect();
assert.equal(page.window.adsbygoogle.length, 1);
assert.equal(page.disconnected, true);
assert.equal(page.button.hidden, true);
assert.equal(page.button.textContent, 'Privacy and cookie settings');
assert.equal(page.removed, true);
page.window.__tcfapi = (command, version, fn) => fn({gdprApplies: true}, true);
page.window.googlefc.callbackQueue[0].CONSENT_API_READY();
assert.equal(page.button.hidden, false);
let reopened = false;
page.window.googlefc.showRevocationMessage = () => {reopened = true;};
page.button.click(); assert.equal(reopened, true);
const hidden = run('ridersfanatics.com', 0); hidden.intersect();
assert.equal(hidden.window.adsbygoogle, undefined);
assert.equal(hidden.disconnected, false);
console.log('Footer ad checks passed: production-only, lazy, once, visible size, consent preferences.');
