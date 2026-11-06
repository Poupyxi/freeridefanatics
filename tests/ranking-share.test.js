'use strict';
const assert = require('node:assert/strict');
const {chunks,handle,flag,socialLinks,eventNation} = require('../assets/js/ranking-share.js');
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
assert.equal(flag('KOR'),'🇰🇷');
assert.equal(flag('USA'),'🇺🇸');
assert.equal(eventNation({name:'Mona Yongpyong, South Korea (May)'}),'KOR');
assert.equal(eventNation({name:'Mona Pyongyong'}),'KOR');
assert.equal(eventNation({name:'Lake Placid'}),'USA');
assert.equal(flag('unknown'),'');
const links=socialLinks('https://preprod.ridersfanatics.com/test.html?a=1&b=2','Final / Men & Women');
assert.equal(new URL(links.x).searchParams.get('text'),'Final / Men & Women');
assert.equal(new URL(links.linkedin).searchParams.get('url'),'https://preprod.ridersfanatics.com/test.html?a=1&b=2');
console.log('Ranking share pagination, handles and flags: PASS');
