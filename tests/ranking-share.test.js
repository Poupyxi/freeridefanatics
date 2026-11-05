'use strict';
const assert = require('node:assert/strict');
const {chunks,handle,flag} = require('../assets/js/ranking-share.js');
for (const n of [0,1,10,11,20,21,100]) {
  const rows=Array.from({length:n},(_,i)=>i);
  const pages=chunks(rows);
  assert.equal(pages.length,Math.ceil(n/10));
  assert.deepEqual(pages.flat(),rows);
  assert(pages.every(page=>page.length<=10));
}
assert.equal(handle('https://www.instagram.com/uci_mountainbike/'),'@uci_mountainbike');
assert.equal(handle('@redbull'),'@redbull');
assert.equal(handle(''),'');
assert.equal(handle('<script>'),'');
assert.equal(flag('FRA'),'🇫🇷');
assert.equal(flag('France'),'🇫🇷');
assert.equal(flag('CA'),'🇨🇦');
assert.equal(flag('unknown'),'');
console.log('Ranking share pagination, handles and flags: PASS');
