import {tableShape, formatRefusal} from './structures.mjs';
const keys=['unit','layout','tiers','orient','moduleLongM','moduleShortM','moduleGapM','tableCols','modulesPerString'];
export function solarTableShape(input) {
  if (!input || typeof input!=='object' || Array.isArray(input) ||
      Object.keys(input).length!==keys.length || !keys.every(k=>Object.hasOwn(input,k)))
    throw new TypeError('exact named fields required');
  const {unit,layout,tiers,orient,moduleLongM,moduleShortM,moduleGapM,tableCols,modulesPerString}=input;
  if (unit!=='m' || layout!=='south' || !Number.isSafeInteger(tiers) || !['portrait','landscape'].includes(orient) || !['2:portrait','3:portrait','3:landscape'].includes(`${tiers}:${orient}`) || formatRefusal(layout,tiers,orient)!==null)
    throw new RangeError('only south 2P, 3P, 3L and metres supported');
  if (![moduleLongM,moduleShortM,moduleGapM].every(Number.isFinite) ||
      moduleShortM<=0 || moduleLongM<moduleShortM || moduleLongM>10 || moduleGapM<0 || moduleGapM>1)
    throw new RangeError('invalid dimensions; development envelope only');
  if (![tableCols,modulesPerString].every(n=>Number.isSafeInteger(n)&&n>=1&&n<=10000))
    throw new RangeError('invalid counts; development envelope only');
  return tableShape({tiers,orient,moduleLongM,moduleShortM,moduleGapM,tableCols},modulesPerString,layout);
}
