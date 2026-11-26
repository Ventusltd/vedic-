import * as source from './voltage-drop.mjs';

const positive = v => typeof v === 'number' && Number.isFinite(v) && v > 0;
const nonnegative = v => typeof v === 'number' && Number.isFinite(v) && v >= 0;
const ratio = v => positive(v) && v <= 1;
const phases = v => v === 'three' || v === 'single';
const mode = v => v === 'ac-rms';
const basis = v => v === 'lagging-or-unity';
const resistanceBasis = v => v === 'caller-specified-operating-resistance';
function validate(input, fields) {
  if (!input || Object.getPrototypeOf(input) !== Object.prototype ||
      Object.keys(input).length !== Object.keys(fields).length ||
      Object.keys(fields).some(k => !Object.hasOwn(input,k) || !fields[k](input[k])))
    throw new TypeError('INVALID_INPUT: explicit named quantities and supported mode required');
}
function result(r) {
  if (![r.value, ...['resistiveVolts','reactiveVolts'].filter(k=>Object.hasOwn(r,k)).map(k=>r[k])].every(Number.isFinite))
    throw new RangeError('NONFINITE_RESULT');
  return r;
}
const conductor = { mode, phases, currentA:positive, lengthM:positive,
 resistanceOhmPerKm:positive, resistanceBasis };
export function voltageDropVolts(input) {
  validate(input,{...conductor,reactanceOhmPerKm:nonnegative,powerFactor:ratio,powerFactorBasis:basis});
  const {mode, resistanceBasis, powerFactorBasis,...args}=input;
  return result(source.voltageDropVolts(args));
}
export function dropPercent(input) {
  validate(input,{mode,phases,nominalVoltageBasis:v=>v==='line-to-line'||v==='across-supply',
    dropVolts:positive,nominalVolts:positive});
  if (input.nominalVoltageBasis !== (input.phases==='three'?'line-to-line':'across-supply'))
    throw new TypeError('INVALID_INPUT: incompatible nominal voltage basis');
  return result(source.dropPercent({dropVolts:input.dropVolts,nominalVolts:input.nominalVolts}));
}
export function lossesWatts(input) {
  validate(input,conductor);
  const {mode,resistanceBasis,...args}=input;
  return result(source.lossesWatts(args));
}
export function annualLossKwh(input) {
  validate(input,{peakLossWatts:positive,lossLoadFactor:ratio,hours:v=>positive(v)&&v<=8784,
    factorBasis:v=>v==='loss-load-factor'});
  const {factorBasis,...args}=input;
  return result(source.annualLossKwh(args));
}
