const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/js/season-routing.js'), 'utf8');

function boot({stored = 'summer', path = '/', winterPage = false} = {}) {
  const listeners = {};
  const links = ['competitions', 'riders', 'equipment'].map(name => ({
    dataset: {seasonRoute: name}, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; }
  }));
  const scopes = ['summer', 'winter'].map(name => ({dataset: {seasonScope: name}, hidden: name === 'winter'}));
  const toggle = {hidden: true, attributes: {}, listeners: {}, setAttribute(k, v) {this.attributes[k] = v;}, addEventListener(k, fn) {this.listeners[k] = fn;}};
  let replaced = '', assigned = '', saved = stored;
  const document = {
    body: {classList: {contains: value => winterPage && value === 'winter-data-page'}},
    querySelectorAll: selector => selector === '[data-season-route]' ? links : scopes,
    querySelector: selector => selector === '.season-switch' ? toggle : null,
  };
  const window = {
    location: {pathname: path, replace: value => {replaced = value;}, assign: value => {assigned = value;}},
    addEventListener: (type, fn) => {listeners[type] = fn;},
  };
  const localStorage = {getItem: () => saved, setItem: (_key, value) => {saved = value;}};
  vm.runInNewContext(source, {window, document, localStorage});
  return {links, scopes, toggle, listeners, replaced: () => replaced, assigned: () => assigned, saved: () => saved};
}

let app = boot({stored: 'winter'});
assert.equal(app.links[0].attributes.href, '/winter/competitions.html');
assert.equal(app.links[1].attributes.href, '/winter/riders.html#grid');
assert.equal(app.scopes[0].hidden, true);
assert.equal(app.scopes[1].hidden, false);

app = boot({stored: 'winter', path: '/riders.html'});
assert.equal(app.replaced(), '/winter/riders.html#grid');

app = boot({stored: 'winter', path: '/winter/equipment.html', winterPage: true});
assert.equal(app.toggle.hidden, false);
assert.equal(app.toggle.attributes['aria-checked'], 'true');
app.toggle.listeners.click();
assert.equal(app.saved(), 'summer');
assert.equal(app.assigned(), '/equipment.html');

console.log('Season routing: links, redirects, scopes and Winter-to-Summer toggle passed.');
