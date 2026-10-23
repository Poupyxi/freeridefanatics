// Dependency-free state/cleanup regression checks. Visual layout is tested in-browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/js/seasonal-home.js'), 'utf8');

function element() {
  const classes = new Set();
  return {
    dataset: {}, attributes: {}, listeners: {}, children: [], hidden: true,
    classList: {add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c), toggle(c, value) {value ? classes.add(c) : classes.delete(c);}},
    style: {setProperty() {}},
    addEventListener(type, fn) {this.listeners[type] = fn;},
    setAttribute(key, value) {this.attributes[key] = value;},
    appendChild(child) {if (child.fragment) this.children.push(...child.children); else this.children.push(child);},
    replaceChildren() {this.children = [];}
  };
}
function boot({stored, blocked = false, motion = false, present = true} = {}) {
  const page = element(), toggle = element(), weather = element(), status = element();
  const doc = element(), win = element(), reduced = element();
  let saved = stored, writes = 0, id = 0;
  const timers = new Map();
  page.querySelector = sel => ({'.season-switch': toggle, '.season-weather': weather, '#season-appearance-status': status}[sel]);
  doc.querySelector = () => present ? page : null;
  doc.hidden = false;
  doc.createElement = element;
  doc.createDocumentFragment = () => Object.assign(element(), {fragment: true});
  reduced.matches = motion;
  win.matchMedia = () => reduced;
  const storage = {getItem() {if (blocked) throw Error('blocked'); return saved;}, setItem(key, value) {if (blocked) throw Error('blocked'); saved = value; writes++;}};
  const context = {window: win, document: doc, localStorage: storage, setTimeout: fn => {timers.set(++id, fn); return id;}, clearTimeout: i => timers.delete(i)};
  vm.runInNewContext(source, context);
  return {page, toggle, weather, status, doc, win, reduced, timers, context, writes: () => writes, saved: () => saved};
}

let app = boot();
assert.equal(app.status.textContent, 'Summer');
assert.equal(app.toggle.hidden, false);
assert.equal(app.writes(), 0);
app.toggle.listeners.click();
assert.equal(app.status.textContent, 'Winter');
assert.equal(app.toggle.attributes['aria-checked'], 'true');
assert.equal(app.weather.children.length, 60);
assert.equal(app.saved(), 'winter');
app.toggle.listeners.click();
assert.equal(app.weather.children.length, 0);
assert.equal(app.timers.size, 0);
app.toggle.listeners.click();
assert.equal(app.weather.children.length, 60);
assert.equal(app.timers.size, 1);
[...app.timers.values()][0]();
assert.equal(app.weather.children.length, 0);
assert(app.page.classList.contains('season-winter'));
app.toggle.listeners.click();app.toggle.listeners.click();
app.doc.hidden = true;app.doc.listeners.visibilitychange();
assert.equal(app.weather.children.length, 0);
assert.equal(app.timers.size, 0);
app.win.listeners.storage({key: 'rf-preprod-home-appearance-v1', newValue: 'summer'});
assert.equal(app.status.textContent, 'Summer');
app.win.listeners.storage({key: 'other-key', newValue: 'winter'});
assert.equal(app.status.textContent, 'Summer');
assert.equal(boot({stored:'winter'}).status.textContent, 'Winter');
assert.equal(boot({stored:'invalid'}).status.textContent, 'Summer');
app = boot({blocked:true});app.toggle.listeners.click();
assert.equal(app.status.textContent, 'Winter');
app = boot({motion:true});app.toggle.listeners.click();
assert.equal(app.status.textContent, 'Winter');
assert.equal(app.weather.children.length, 0);
assert.equal(app.timers.size, 0);
app = boot();app.toggle.listeners.click();
app.reduced.matches = true;app.reduced.listeners.change();
assert.equal(app.weather.children.length, 0);
assert.equal(app.timers.size, 0);
vm.runInNewContext(source, app.context); // A second load must not attach extra listeners.
assert.equal(app.status.textContent, 'Winter');
assert.equal(boot({present:false}).toggle.hidden, true);
console.log('Season switch: state, persistence, blocked storage, rapid clicks, cleanup, reduced motion, off-page and duplicate-load guards passed.');
