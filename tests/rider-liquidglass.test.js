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
assert(css.includes('.rider-page{padding-bottom:'), 'fixed menu must not cover the end of rider pages');
assert(css.includes('scroll-snap-type:x proximity'), 'mobile rider menu must snap horizontally');
assert(css.includes('touch-action:pan-x pan-y'), 'mobile rider menu must allow horizontal navigation and vertical page scrolling');
assert(css.includes('grid-auto-flow:column'), 'mobile rider page must lay out its sections horizontally');
assert(css.includes('scroll-snap-type:x mandatory'), 'mobile rider page must snap between horizontal panels');
assert(vendor.includes('var LiquidGlass = class'), 'vendored LiquidGlass bundle is incomplete');
assert(build.includes('if winter else "rider-page"'), 'summer rider pages must receive the rider-page marker');
assert(site.includes("track.scrollTo({left:Math.max(0, targetLeft), behavior:'smooth'})"), 'active item must scroll only inside the menu');
assert(!site.includes('invalidationPending'), 'glass must not recapture the page continuously while scrolling');
assert(site.includes("pageTrack.scrollTo({left:Math.max(0, slide.offsetLeft - pageTrack.offsetLeft), behavior:'smooth'})"), 'glass links must move the whole mobile rider page horizontally');
assert(site.includes("resultsPanel.className = 'rider-mobile-panel rider-mobile-results'"), 'mobile results heading and table must stay in one horizontal panel');

console.log('Rider LiquidGlass integration contract passed.');
