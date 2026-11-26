import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import vm from 'node:vm';

const atlas='afffa9781f6130529ae93052604cd3d98d172a35';
const engine='7c2a7b42905674fdcd3aa4bb50af14bc352a7747';
const a='E:/VEDIC/offline/gridatlas', e='E:/VEDIC/offline/ventus-grid-engine';
const modulePath='atlas/modules/202609011950-geodesy.js';
const sandboxPath='atlas/cartridges/202609012045-sld-sandbox-v9-8.js';
function gitRaw(repo,commit,path) {
 return execFileSync('git',['--no-replace-objects','-C',repo,'cat-file','blob',commit+':'+path]);
}
const gitBlob=r=>createHash('sha1').update('blob '+r.length+'\0').update(r).digest('hex');
function extract(raw,start,end,name,constants={}){
 const code=raw.toString('utf8').split(/\r?\n/).slice(start-1,end).join('\n').replace(/^export /,'');
 assert.match(code,new RegExp('function\\s+'+name+'\\('));
 return vm.runInNewContext(code+'\n'+name,constants,{timeout:1000});
}
const canonical=gitRaw(a,atlas,modulePath), sandbox=gitRaw(a,atlas,sandboxPath);
const oldEngine=gitRaw(e,engine,'engine/v9-geodesy.js');
const constants={DEG:Math.PI/180,EARTH_RADIUS_KM:6378.137,R_ATLAS:6378.137};
const pairs=[];
const dist=extract(canonical,24,42,'distanceKm',constants);
const historicalDist=extract(sandbox,36,42,'distanceKm',constants);
let diff;
for(let i=1;i<100&&!diff;i++){
 const args=[-2,53,-2+i/2048,53+i/4096];
 const x=dist(...args),y=historicalDist(...args);
 if(!Object.is(x,y))diff={coordinates:args,canonical_km:x,variant_km:y};
}
assert.ok(diff);
pairs.push({families:[511,32987],classification:'numerical_drift',evidence:diff});
const dest=extract(oldEngine,121,131,'destinationPoint',constants);
const oldDest=extract(sandbox,3631,3641,'destinationPoint',constants);
const templateCases=[[0,0,0,0],[-2,53,115,45],[178,30,350,90]];
for(const args of templateCases)assert.deepEqual(Array.from(dest(...args)),Array.from(oldDest(...args)));
pairs.push({families:[8769,33124],classification:'bounded_sample_parity',cases:templateCases.length,
            evidence:'Equal constants and same observed outputs on zero-distance, ordinary and date-line cases.'});
const ref='2f4b7cb82ee154fa3c684cba634d45f2183c6e7d';
const remotePath='pipelinenews_intelligence/202608311558/assets/202608311558-grid-proximity.mjs';
const remote=await fetch('https://raw.githubusercontent.com/Ventusltd/globalgrid2050/'+ref+'/'+remotePath);
assert.ok(remote.ok);
const proximity=Buffer.from(await remote.arrayBuffer());
assert.equal(gitBlob(proximity),'c275c42a00b0ea40c33b4e03440f1b97c0c0bd54');
const bearing=extract(canonical,128,134,'initialBearingDeg',constants);
const other=extract(proximity,591,597,'bearingDeg');
for(const args of [[-2,53,-1,54],[0,0,-1,0],[178,31,-179,31],[1,2,1,2]])assert.equal(bearing(...args),other(...args));
pairs.push({families:[8770,1936],classification:'bounded_sample_parity',cases:4,
            evidence:'Same degree convention and equal tested ordinary, westward, date-line and coincident results.'});
const byFamilyFiles=[
 [80283, 'engine/electrification-demand.js',126,136,'averagePowerGw'],
 [80271, 'engine/diversified-demand.js',134,153,'averageOverWindowGw'],
 [80284, 'engine/electrification-demand.js',144,158,'peakFromLoadFactorGw'],
 [80285, 'engine/electrification-demand.js',166,182,'loadFactorFromPeak']
];
const modules={};
for(const name of new Set(byFamilyFiles.map(x=>x[1]))){
 const raw=gitRaw(e,engine,name);
 assert.ok(!/^\s*import\s/m.test(raw.toString()));
 modules[name]=await import('data:text/javascript;base64,'+raw.toString('base64'));
}
const demand=modules['engine/electrification-demand.js'],window=modules['engine/diversified-demand.js'];
assert.equal(demand.averagePowerGw({annualTwh:8.76}).value,window.averageOverWindowGw({annualTwh:8.76,windowHoursPerDay:24}).value);
assert.equal(window.averageOverWindowGw({annualTwh:8.76,windowHoursPerDay:12}).value,2);
pairs.push({families:[80283,80271],classification:'conditional_variant',cases:2, evidence:'Equal when the window is 24 hours, distinct at 12 hours.'});
assert.equal(demand.peakFromLoadFactorGw({averageGw:7,loadFactor:.5}).value,14);
assert.equal(demand.loadFactorFromPeak({averageGw:7,peakGw:14}).value,.5);
pairs.push({families:[80284,80285],classification:'distinct_inverse_contracts',cases:2, evidence:'One returns peak power in GW, the other returns a dimensionless load factor.'});
const c=[-2,53,-1,54];
assert.ok(dist(...c)>0 && bearing(...c)>=0 && bearing(...c)<360);
pairs.push({families:[511,8770],classification:'complementary_not_interchangeable',
            evidence:'Same two positions yield two distinct quantities, distance in kilometres and initial bearing in degrees.'});
console.log(JSON.stringify({snapshot:"family-similarity canonical witness v1",pairs,
          blob_map:{[modulePath]:gitBlob(canonical),[sandboxPath]:gitBlob(sandbox),
            'engine/v9-geodesy.js':gitBlob(oldEngine),[remotePath]:gitBlob(proximity)}},null,2));
