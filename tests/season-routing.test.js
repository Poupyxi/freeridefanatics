const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/js/season-routing.js'), 'utf8');

function boot({stored = 'summer', path = '/', homepageAnimation = false} = {}) {
  const listeners = {};
  const links = ['competitions', 'riders', 'equipment'].map(name => ({
    dataset: {seasonRoute: name}, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; }
  }));
  const scopes = ['summer', 'winter'].map(name => ({dataset: {seasonScope: name}, hidden: name === 'winter'}));
  const toggle = {hidden: true, attributes: {}, listeners: {}, setAttribute(k, v) {this.attributes[k] = v;}, addEventListener(k, fn) {this.listeners[k] = fn;}};
  const bodyClasses = new Set();
  let replaced = '', assigned = '', saved = stored;
  const document = {
    body: {classList: {
      contains: value => bodyClasses.has(value),
      toggle(value, active) {active ? bodyClasses.add(value) : bodyClasses.delete(value);}
    }},
    querySelectorAll: selector => selector === '[data-season-route]' ? links : scopes,
    querySelector: selector => selector === '.season-switch' ? toggle :
      (selector === '.season-weather' && homepageAnimation ? {} : null),
  };
  const window = {
    location: {pathname: path, replace: value => {replaced = value;}, assign: value => {assigned = value;}},
    addEventListener: (type, fn) => {listeners[type] = fn;},
  };
  const localStorage = {getItem: () => saved, setItem: (_key, value) => {saved = value;}};
  vm.runInNewContext(source, {window, document, localStorage});
  return {links, scopes, toggle, listeners, bodyClasses, replaced: () => replaced, assigned: () => assigned, saved: () => saved};
}

let app = boot({stored: 'winter'});
assert.equal(app.links[0].attributes.href, '/winter/competitions.html');
assert.equal(app.links[1].attributes.href, '/winter/riders.html#grid');
assert.equal(app.scopes[0].hidden, true);
assert.equal(app.scopes[1].hidden, false);
assert.equal(app.toggle.hidden, false);
assert.equal(app.toggle.attributes['aria-checked'], 'true');
assert.equal(app.toggle.attributes['aria-label'], 'Switch to Summer season');
assert(app.bodyClasses.has('season-winter'));

app = boot({stored: 'winter', path: '/riders.html'});
assert.equal(app.replaced(), '/winter/riders.html#grid');

app = boot({stored: 'winter', path: '/winter/equipment.html'});
assert.equal(app.toggle.hidden, false);
assert.equal(app.toggle.attributes['aria-checked'], 'true');
app.toggle.listeners.click();
assert.equal(app.saved(), 'summer');
assert.equal(app.assigned(), '/equipment.html');

app = boot({stored: 'summer', path: '/riders/example.html'});
app.toggle.listeners.click();
assert.equal(app.saved(), 'winter');
assert.equal(app.assigned(), '/winter/riders.html#grid');

app = boot({stored: 'summer', path: '/privacy.html'});
app.toggle.listeners.click();
assert.equal(app.saved(), 'winter');
assert.equal(app.assigned(), '');
assert(app.bodyClasses.has('season-winter'));

app = boot({stored: 'summer', homepageAnimation: true});
assert.equal(app.toggle.listeners.click, undefined);

console.log('Season routing: global toggle, persistence, routes and safe fallbacks passed.');
