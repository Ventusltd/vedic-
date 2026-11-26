// Thin adapter; all ranking and distance calculations remain in pinned producer code.
import { index } from './engine/v9-nearest-search.js';
function fail(message) { throw new TypeError(message); }
function keys(obj, required, optional=[]) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) fail('object required');
  if (required.some(k=>!Object.hasOwn(obj,k)) ||
      Object.keys(obj).some(k=>!required.includes(k)&&!optional.includes(k))) fail('unexpected or missing field');
}
function coords(p) {
  keys(p,['longitude','latitude']);
  if (!Number.isFinite(p.longitude)||Math.abs(p.longitude)>180||
      !Number.isFinite(p.latitude)||Math.abs(p.latitude)>90) fail('invalid named coordinates');
  return {lon:p.longitude,lat:p.latitude};
}
export function nearestSubstation(input) {
  keys(input,['crs','query','records'],['minimumKv']);
  if(input.crs!=='EPSG:4326') fail('unsupported CRS');
  const q=coords(input.query);
  const min=Object.hasOwn(input,'minimumKv')?input.minimumKv:0;
  if(!Number.isFinite(min)||min<0) fail('minimumKv must be nonnegative numeric kV');
  if(!Array.isArray(input.records)||input.records.length>10000) fail('invalid records');
  const ids=new Set();
  const points=input.records.map(r=>{
    keys(r,['id','name','location','voltages_kv']);
    if(typeof r.id!=='string'||!r.id.trim()||ids.has(r.id)||typeof r.name!=='string'||!r.name.trim()) fail('invalid or duplicate identity');
    ids.add(r.id);
    if(!Array.isArray(r.voltages_kv)||r.voltages_kv.length>32||
       r.voltages_kv.some(v=>!Number.isFinite(v)||v<=0)) fail('explicit positive numeric kV required');
    return {id:r.id,name:r.name,location:coords(r.location),voltages_kv:[...r.voltages_kv]};
  });
  // Request all admitted results so even a non-winning nonfinite distance fails closed.
  const ranked=index(points).nearest(q.lon,q.lat,{minimumKv:min,limit:Math.max(2,points.length)});
  if(ranked.some(r=>!Number.isFinite(r.km)||r.km<0)) throw new RangeError('nonfinite producer distance');
  return ranked.length?{id:ranked[0].point.id,distance_km:ranked[0].km}:null;
}
