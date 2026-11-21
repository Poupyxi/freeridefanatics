const fs = require('fs');
const assert = require('assert');

const site = fs.readFileSync('assets/js/site.js', 'utf8');
const css = fs.readFileSync('assets/css/style.css', 'utf8');
const vendor = fs.readFileSync('assets/vendor/liquidglass/index.js', 'utf8');
const build = fs.readFileSync('build.py', 'utf8');

assert(site.includes("../vendor/liquidglass/index.js"), 'rider menu must load the local LiquidGlass module');
assert(site.includes('module.LiquidGlass.init({root:main, glassElements:[nav]})'), 'rider menu must initialise one WebGL glass element');
assert(site.includes("prefers-reduced-transparency: reduce"), 'rider menu must preserve a reduced-transparency fallback');
assert(site.includes('navigator.connection && navigator.connection.saveData'), 'rider menu must avoid WebGL in data-saver mode');
assert(css.includes('.rider-glass-menu.is-liquidglass-ready'), 'WebGL-ready styling is missing');
assert(css.includes('.rider-glass-menu-track'), 'scrollable menu track is missing');
assert(vendor.includes('var LiquidGlass = class'), 'vendored LiquidGlass bundle is incomplete');
assert(build.includes('if winter else "rider-page"'), 'summer rider pages must receive the rider-page marker');

console.log('Rider LiquidGlass integration contract passed.');
