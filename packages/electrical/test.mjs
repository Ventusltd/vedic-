import test from 'node:test';
import assert from 'node:assert/strict';
import * as adapter from './adapter.mjs';
import * as original from './voltage-drop.mjs';

const wire={mode:'ac-rms',phases:'three',currentA:100,lengthM:1000,resistanceOhmPerKm:0.2,resistanceBasis:'caller-specified-operating-resistance'};
const drop={...wire,reactanceOhmPerKm:0,powerFactor:1,powerFactorBasis:'lagging-or-unity'};
const annual={peakLossWatts:6000,lossLoadFactor:0.5,hours:8760,factorBasis:'loss-load-factor'};
const percent={mode:'ac-rms',phases:'three',nominalVoltageBasis:'line-to-line',dropVolts:20,nominalVolts:400};
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<=1e-10*Math.max(1,Math.abs(expected)),JSON.stringify({actual,expected}));
test('exact public exports',()=>assert.deepEqual(Object.keys(adapter).sort(),['annualLossKwh','dropPercent','lossesWatts','voltageDropVolts']));
test('balanced AC drop',()=>close(adapter.voltageDropVolts(drop).value,20*Math.sqrt(3)));
test('single phase AC drop',()=>close(adapter.voltageDropVolts({...drop,phases:'single'}).value,40));
test('lagging PF and reactance',()=>close(adapter.voltageDropVolts({...drop,powerFactor:0.8,reactanceOhmPerKm:0.1}).value,22*Math.sqrt(3)));
test('three-phase loss',()=>close(adapter.lossesWatts(wire).value,6000));
test('single-phase loss',()=>close(adapter.lossesWatts({...wire,phases:'single'}).value,4000));
test('I squared scaling',()=>close(adapter.lossesWatts({...wire,currentA:200}).value,24000));
test('length scaling',()=>close(adapter.lossesWatts({...wire,lengthM:500}).value,3000));
test('annual energy loss',()=>close(adapter.annualLossKwh(annual).value,26280));
test('annual hours scaling',()=>close(adapter.annualLossKwh({...annual,hours:4380}).value,13140));
test('drop percentage',()=>close(adapter.dropPercent(percent).value,5));
test('exact original parity',()=>{
 const {mode,resistanceBasis,powerFactorBasis,...d}=drop;
 const {mode:m,resistanceBasis:r,...w}=wire;
 const {factorBasis,...a}=annual;
 assert.deepEqual(adapter.voltageDropVolts(drop),original.voltageDropVolts(d));
 assert.deepEqual(adapter.lossesWatts(wire),original.lossesWatts(w));
 assert.deepEqual(adapter.annualLossKwh(annual),original.annualLossKwh(a));
 assert.deepEqual(adapter.dropPercent(percent),original.dropPercent({dropVolts:20,nominalVolts:400}));
});
for(const [name,fn,input] of [
 ['DC',adapter.voltageDropVolts,{...drop,mode:'dc'}],
 ['leading PF',adapter.voltageDropVolts,{...drop,powerFactorBasis:'leading'}],
 ['zero current',adapter.lossesWatts,{...wire,currentA:0}],
 ['negative length',adapter.lossesWatts,{...wire,lengthM:-1}],
 ['infinite current',adapter.lossesWatts,{...wire,currentA:Infinity}],
 ['NaN R',adapter.lossesWatts,{...wire,resistanceOhmPerKm:NaN}],
 ['string current',adapter.lossesWatts,{...wire,currentA:'100'}],
 ['null',adapter.lossesWatts,null],
 ['PF percent',adapter.voltageDropVolts,{...drop,powerFactor:80}],
 ['negative X',adapter.voltageDropVolts,{...drop,reactanceOhmPerKm:-1}],
 ['missing phase',adapter.lossesWatts,(({phases,...rest})=>rest)(wire)],
 ['wrong unit field',adapter.lossesWatts,(({lengthM,...rest})=>({...rest,lengthKm:1}))(wire)],
 ['unknown key',adapter.lossesWatts,{...wire,parallel:2}],
 ['ordinary load factor',adapter.annualLossKwh,{...annual,factorBasis:'load-factor'}],
 ['excess annual hours',adapter.annualLossKwh,{...annual,hours:9000}],
 ['zero voltage',adapter.dropPercent,{...percent,nominalVolts:0}],
 ['wrong voltage basis',adapter.dropPercent,{...percent,nominalVoltageBasis:'across-supply'}],
 ['overflow',adapter.lossesWatts,{...wire,currentA:1e200}]
]) test('refuse '+name,()=>assert.throws(()=>fn(input),/INVALID_INPUT|NONFINITE_RESULT/));

test('unity PF excludes reactance even when X is large',()=>close(adapter.voltageDropVolts({...drop,reactanceOhmPerKm:20}).value,20*Math.sqrt(3)));
test('lagging PF split of resistive and reactive terms',()=>{
 const r=adapter.voltageDropVolts({...drop,powerFactor:0.8,reactanceOhmPerKm:0.1});
 close(r.resistiveVolts,16*Math.sqrt(3)); close(r.reactiveVolts,6*Math.sqrt(3)); assert.equal(r.unit,'V');
});
test('single phase lagging PF uses both conductors',()=>close(adapter.voltageDropVolts({...drop,phases:'single',powerFactor:0.8,reactanceOhmPerKm:0.1}).value,44));
test('one-way length and per-conductor R: 250m at 0.32 ohm/km',()=>{
 const w={...wire,currentA:120,lengthM:250,resistanceOhmPerKm:0.32};
 close(adapter.lossesWatts(w).value,3456); close(adapter.lossesWatts({...w,phases:'single'}).value,2304);
});
test('R scaling at fixed load',()=>close(adapter.lossesWatts({...wire,resistanceOhmPerKm:0.4}).value,12000));
test('nominal voltage basis single phase',()=>close(adapter.dropPercent({...percent,phases:'single',nominalVoltageBasis:'across-supply',nominalVolts:230,dropVolts:11.5}).value,5));
test('annual loss factor uses supplied squared-current factor',()=>{
 const r=adapter.annualLossKwh({...annual,lossLoadFactor:0.25});
 close(r.value,13140); assert.equal(r.unit,'kWh');
});
test('leap year explicit hours',()=>close(adapter.annualLossKwh({...annual,hours:8784}).value,26352));
for(const [name,fn,input] of [
 ['zero drop current',adapter.voltageDropVolts,{...drop,currentA:0}],
 ['zero one-way length',adapter.lossesWatts,{...wire,lengthM:0}],
 ['zero resistance',adapter.lossesWatts,{...wire,resistanceOhmPerKm:0}],
 ['zero drop',adapter.dropPercent,{...percent,dropVolts:0}],
 ['zero peak loss',adapter.annualLossKwh,{...annual,peakLossWatts:0}],
 ['zero loss factor',adapter.annualLossKwh,{...annual,lossLoadFactor:0}],
 ['zero PF',adapter.voltageDropVolts,{...drop,powerFactor:0}],
 ['zero hours',adapter.annualLossKwh,{...annual,hours:0}],
 ['loop resistance basis',adapter.lossesWatts,{...wire,resistanceBasis:'total-loop-resistance'}],
 ['line-neutral nominal basis',adapter.dropPercent,{...percent,nominalVoltageBasis:'line-to-neutral'}],
 ['loss factor over unity',adapter.annualLossKwh,{...annual,lossLoadFactor:1.001}],
 ['no explicit X',adapter.voltageDropVolts,(({reactanceOhmPerKm,...rest})=>rest)(drop)],
 ['no explicit hours',adapter.annualLossKwh,(({hours,...rest})=>rest)(annual)]
]) test('source-domain refusal '+name,()=>assert.throws(()=>fn(input),/INVALID_INPUT/));
