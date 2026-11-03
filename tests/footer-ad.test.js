const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('assets/js/footer-ad.js', 'utf8');
function run({host = 'ridersfanatics.com', preview = false, cmp = true, width = 800} = {}) {
  let consent, intersect, button, reloads = 0;
  const scripts = [];
  const unit = {getAttribute: name => name === 'data-ad-client' ? 'ca-pub-6372404738608947' : '7556439197', getBoundingClientRect: () => ({width}), replaceChildren() {}};
  const window = {IntersectionObserver: true};
  if (cmp) {
    window.__tcfapi = (command, version, callback) => {consent = callback;};
    window.googlefc = {showRevocationMessage() {window.reopened = true;}};
  }
  vm.runInNewContext(source, {window, location: {hostname: host, reload() {reloads++;}},
    document: {head: {appendChild(node) {scripts.push(node);}}, querySelector(selector) {return selector === 'ins.rider-ad-unit' ? (preview ? null : unit) : {appendChild(node) {button = node;}};}, createElement() {return {addEventListener(event, fn) {this[event] = fn;}};}},
    IntersectionObserver: function (callback) {intersect = callback; this.observe = () => {};}});
  return {window, scripts, get button() {return button;}, get reloads() {return reloads;}, see() {intersect([{isIntersecting: true}]);}, consent(data, success = true) {consent(data, success);}};
}
const granted = () => ({cmpStatus: 'loaded', eventStatus: 'useractioncomplete', tcString: 'test-consent', vendor: {consents: {755: true}}, purpose: {consents: {1:true,2:true,3:true,4:true,7:true,9:true,10:true}}});
for (const host of ['localhost', '127.0.0.1', 'preprod.ridersfanatics.com']) {
  const p = run({host}); assert.equal(p.scripts.length, 0); assert.equal(p.window.adsbygoogle, undefined);
}
assert.equal(run({preview:true}).scripts.length, 0);
const noCmp = run({cmp:false}); noCmp.see(); assert.equal(noCmp.scripts.length, 0);
const p = run(); p.see(); assert.equal(p.scripts.length,0);
p.consent({...granted(), vendor:{consents:{755:false}}}); assert.equal(p.scripts.length,0);
p.consent(granted(), false); assert.equal(p.scripts.length,0);
p.consent({...granted(), publisher:{restrictions:{1:{755:0}}}}); assert.equal(p.scripts.length,0);
p.consent(granted()); p.see(); p.consent(granted());
assert.equal(p.scripts.length,1); assert.equal(p.window.adsbygoogle.length,1);
assert.equal(p.button.hidden,false); p.button.click(); assert.equal(p.window.reopened,true);
p.consent({...granted(),eventStatus:'cmpuishown'}); assert.equal(p.reloads,0);
p.consent({...granted(),vendor:{consents:{755:false}}}); assert.equal(p.reloads,1);
const delayed = run(); delayed.consent(granted()); assert.equal(delayed.scripts.length,0); delayed.see(); assert.equal(delayed.scripts.length,1);
const hidden = run({width:0}); hidden.consent(granted()); hidden.see(); assert.equal(hidden.scripts.length,0);
console.log('Passed: preview isolation, missing CMP, refusal, consent, restrictions, lazy load, once, settings and withdrawal.');
