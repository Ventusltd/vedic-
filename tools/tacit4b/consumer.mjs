import assert from 'node:assert/strict';
import * as api from '@ventus-internal/vedic-solar-shape';
import {tableShape} from './node_modules/@ventus-internal/vedic-solar-shape/structures.mjs';
assert.deepEqual(Object.keys(api),['solarTableShape']);
const direct=await import('./node_modules/@ventus-internal/vedic-solar-shape/index.mjs');
assert.equal(direct.solarTableShape,api.solarTableShape);
const input={unit:'m',layout:'south',tiers:2,orient:'portrait',moduleLongM:2.384,moduleShortM:1.134,moduleGapM:0.02,tableCols:30,modulesPerString:30};
const a=api.solarTableShape(input);
assert.deepEqual({...a,slope:0},{tiers:2,orient:'portrait',along:1.134,up:2.384,slope:0,cols:30,modules:60});
assert.ok(Math.abs(a.slope-4.788)<1e-12);
const b=api.solarTableShape({...input,moduleLongM:2,moduleShortM:1,moduleGapM:0,tableCols:1});
assert.deepEqual(b,{tiers:2,orient:'portrait',along:1,up:2,slope:4,cols:1,modules:2});
const c=api.solarTableShape({...input,tiers:3,tableCols:12});
assert.equal(c.modules,36); assert.ok(Math.abs(c.slope-7.192)<1e-12);
const d=api.solarTableShape({...input,tiers:3,orient:'landscape',tableCols:12});
assert.equal(d.modules,36); assert.equal(d.along,2.384); assert.equal(d.up,1.134); assert.ok(Math.abs(d.slope-3.442)<1e-12);
for(const i of [input,{...input,tableCols:17,modulesPerString:28},{...input,tiers:3,tableCols:12},{...input,tiers:3,orient:'landscape',tableCols:12}]){
  const {modulesPerString,layout,...p}=i;
  assert.deepEqual(api.solarTableShape(i),tableShape(p,modulesPerString,layout));
}
const bad=[null,{}, {...input,unit:'mm'}, {...input,layout:'tracker'}, {...input,orient:'landscape'}, {...input,tiers:4}, {...input,moduleLongM:NaN}, {...input,moduleShortM:0}, {...input,moduleGapM:-1}, {...input,tableCols:0}, {...input,tableCols:1.5}, {...input,modulesPerString:'30'}, {...input,moduleLongM:Infinity}, {...input,moduleLongM:0.5}, {...input,extra:1}];
for(const i of bad) assert.throws(()=>api.solarTableShape(i));
console.log(JSON.stringify({state:'PACKAGE_DEVELOPMENT_CHECKS_PASS',known_answer:a,alternate_answers:[c,d],known_answer_cases:4,source_parity_cases:4,invalid_cases:bad.length,direct_and_name_import:true}));
