import {orient} from './package/index.mjs';
const form=document.querySelector('#coords');
const result=document.querySelector('#result');
const button=document.querySelector('#calculate');
const evidence=document.querySelector('#evidence');
function value(id){
  const field=document.getElementById(id);
  if(field.value.trim()==='' || !Number.isFinite(field.valueAsNumber)) throw new TypeError('Enter all four numerical coordinates.');
  return field.valueAsNumber;
}
function point(prefix){return {longitude:value(prefix+'-lon'),latitude:value(prefix+'-lat')};}
form.addEventListener('input',()=>{result.textContent='Inputs changed. Calculate again.';});
form.addEventListener('submit',event=>{
  event.preventDefault();
  result.textContent='';
  try{
    const out=orient({crs:'WGS84',unit:'degrees',point_a:point('a'),point_b:point('b')});
    result.textContent=out.distance_km.toFixed(9)+' km\n'+out.initial_bearing_deg.toFixed(6)+'° initial bearing';
  }catch(error){result.textContent='Cannot calculate: '+error.message;}
});
try {
  const response=await fetch('./catalogue.json');
  if(!response.ok) throw new Error('Missing package catalogue');
  const {packages:[p]}=await response.json();
  evidence.textContent=p.name+' '+p.version+' | source '+p.source.commit+' | '+p.identity_tier;
  result.textContent='Enter coordinates or calculate the synthetic example.';
  button.disabled=false;
}catch(error){result.textContent='Package metadata unavailable: '+error.message;}

// No admission means no executable electrical path, even on synthetic submit.
document.querySelector('#electrical').addEventListener('submit',event=>{event.preventDefault();document.querySelector('#electrical-result').textContent='Unavailable: no admitted electrical package.';});
