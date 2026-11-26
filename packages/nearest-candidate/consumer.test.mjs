import assert from 'node:assert/strict';
import { nearestSubstation as nearest } from '@ventus-internal/vedic-nearest';
const p=(longitude,latitude)=>({longitude,latitude});
const rec=(id,longitude,latitude,voltages_kv=[132])=>({id,name:'Synthetic '+id,location:p(longitude,latitude),voltages_kv});
const run=(records,minimumKv=0,query=p(0,0))=>nearest({crs:'EPSG:4326',query,records,minimumKv});
let passed=0;
function test(name,fn){fn();passed++;console.error('PASS '+name);}
function close(actual,expected,tol=1e-8){assert.ok(Math.abs(actual-expected)<tol,JSON.stringify({actual,expected,tol}));}
test('known equatorial point / nearest not first',()=>{const x=run([rec('far',3,0),rec('near',1,0)]);assert.equal(x.id,'near');close(x.distance_km,111.31949079327356);});
test('exact distance tie preserves caller order',()=>{const a=rec('east',1,0),b=rec('west',-1,0);assert.equal(run([a,b]).id,'east');assert.equal(run([b,a]).id,'west');});
test('declared maximum voltage filter inclusive',()=>assert.equal(run([rec('low',.1,0,[33]),rec('high',2,0,[33,132])],132).id,'high'));
test('empty and no eligible records',()=>{assert.equal(run([]),null);assert.equal(run([rec('unknown',0,0,[])]),null);assert.equal(run([rec('low',0,0,[33])],132),null);});
test('single coincident record',()=>assert.deepEqual(run([rec('same',0,0)]),{id:'same',distance_km:0}));
test('antimeridian shortest arc',()=>close(run([rec('cross',-179.9,0)],0,p(179.9,0)).distance_km,22.2638981586547));
test('far equatorial antipode',()=>close(run([rec('far',180,0)]).distance_km,20037.508342789244));
test('valid named coordinates high latitude',()=>assert.equal(run([rec('north',0,89),rec('south',0,-89)],0,p(0,90)).id,'north'));
test('no mutation of caller inputs',()=>{const x=[rec('a',1,0)];const before=JSON.stringify(x);run(x);assert.equal(JSON.stringify(x),before);});
test('reject malformed and duplicate identity',()=>{assert.throws(()=>run([rec('a',0,0),rec('a',1,1)]));assert.throws(()=>run([{...rec('a',0,0),id:''}]));});
test('reject missing location and unsupported geometry',()=>{assert.throws(()=>run([{...rec('a',0,0),location:null}]));assert.throws(()=>run([{...rec('a',0,0),location:{type:'Point',coordinates:[0,0]}}]));});
test('reject invalid coordinates and mixed names',()=>{assert.throws(()=>run([],0,p(0,91)));assert.throws(()=>run([],0,p(181,0)));assert.throws(()=>run([],0,{longitude:0,latitude:0,lat:0}));assert.throws(()=>run([],0,p('0',0)));});
test('reject unknown CRS and unrecognised voltage units',()=>{assert.throws(()=>nearest({crs:'EPSG:27700',query:p(0,0),records:[]}));assert.throws(()=>run([rec('a',0,0,['132kV'])]));assert.throws(()=>run([rec('a',0,0,[0])]));assert.throws(()=>run([], -1));});
test('repeat deterministic',()=>{const x=[rec('a',1,0),rec('b',2,0)];assert.equal(JSON.stringify(run(x)),JSON.stringify(run(x)));});
test('unknown closer than eligible is excluded',()=>assert.equal(run([rec('unknown',0,0,[]),rec('known',1,0,[132])],132).id,'known'));
test('above declared maximum is excluded',()=>assert.equal(run([rec('a',0,0,[33,132])],132.0001),null));
test('missing voltage is not zero or unknown array',()=>{const {voltages_kv,...r}=rec('a',0,0);assert.throws(()=>run([r]));assert.throws(()=>run([rec('a',0,0,null)]));});
test('reject volts-labelled record and missing named axis',()=>{assert.throws(()=>run([{...rec('a',0,0),voltage:132000}]));assert.throws(()=>run([],0,{longitude:0}));});
test('tie remains stable after voltage exclusion',()=>assert.equal(run([rec('excluded',0,0,[]),rec('west',-1,0),rec('east',1,0)],132).id,'west'));
test('consumer handoff fixture',()=>{const f={"provenance":"synthetic","input":{"crs":"EPSG:4326","query":{"longitude":0,"latitude":0},"minimumKv":132,"records":[{"id":"low","name":"Synthetic low","location":{"longitude":0.1,"latitude":0},"voltages_kv":[33]},{"id":"eligible","name":"Synthetic eligible","location":{"longitude":1,"latitude":0},"voltages_kv":[132]},{"id":"far","name":"Synthetic far","location":{"longitude":2,"latitude":0},"voltages_kv":[275]}]},"expected":{"id":"eligible","distance_km":111.31949079327356},"tolerance_km":1e-8,"warning":"Geometric proximity only; no grid connection availability or route implication."};const x=nearest(f.input);assert.equal(x.id,f.expected.id);close(x.distance_km,f.expected.distance_km,f.tolerance_km);});
console.log(JSON.stringify({state:'PACKAGE_DEVELOPMENT_CHECKS_PASS',tests_passed:passed,example:run([rec('far',3,0),rec('near',1,0)]),fixture_provenance:'synthetic'}));
