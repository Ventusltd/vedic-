// Audit-side parser controls; not the peer's boundary validator.
'use strict';
const fs = require('node:fs');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const acorn = require(process.argv[3]);
const raw = fs.readFileSync(process.argv[2]);
const blob = crypto.createHash('sha1').update('blob '+raw.length+'\0').update(raw).digest('hex');
assert.equal(blob,'14023f06d4ef2ea806437863bd35dee954c46b11');
function functions(source) {
  const tree = acorn.parse(source,{ecmaVersion:'latest',sourceType:'module',locations:true});
  const found=[];
  function walk(n) {
    if (!n || typeof n!=='object') return;
    if(n.type==='FunctionDeclaration') found.push({name:n.id.name,start:n.loc.start,end:n.loc.end});
    for(const [k,v] of Object.entries(n)) {
      if(['loc','start','end'].includes(k)) continue;
      if(Array.isArray(v)) v.forEach(walk); else walk(v);
    }
  }
  walk(tree); return found;
}
const actual=functions(raw.toString('utf8'));
for(const [name,first,last] of [['distanceKm',29,47],['initialBearingDeg',133,139]]) {
  const f=actual.filter(x=>x.name===name);
  assert.equal(f.length,1);
  assert.equal(f[0].start.line,first);
  assert.equal(f[0].end.line,last);
}
const synthetic='function f(){return 1;}\nfunction g(){ function f(){return 2;} return f(); }\nconst x=1;\nfunction h(){return 3;}';
const fixtures=functions(synthetic);
const exact=(name,sl,sc,el,ec)=>fixtures.filter(f=>f.name===name&&f.start.line===sl&&f.start.column===sc&&f.end.line===el&&f.end.column===ec).length===1;
const f=fixtures.filter(x=>x.name==='f');
assert.equal(f.length,2);
assert(exact('f',1,0,1,23));
assert(!exact('f',1,0,2,synthetic.split('\n')[1].length));
assert(!exact('f',1,0,3,10));
assert(!exact('f',2,0,2,synthetic.split('\n')[1].length));
assert(exact('f',f[1].start.line,f[1].start.column,f[1].end.line,f[1].end.column));
assert(!exact('f',f[1].start.line,f[1].start.column+1,f[1].end.line,f[1].end.column));
console.log(JSON.stringify({source_blob:blob,source_functions:actual.filter(x=>['distanceKm','initialBearingDeg'].includes(x.name)),synthetic_controls:6,scope:'AUDIT_SIDE_AST_ONLY'}));
