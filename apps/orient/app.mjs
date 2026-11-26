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

const activationState=document.querySelector('#activation-state'), activationEvidence=document.querySelector('#activation-evidence');
let generation=0;
function invalidateActivation(){generation++;activationState.textContent='Inputs changed. Activate again.';activationEvidence.textContent='';}
for(const el of [form,document.querySelector('#instruction'),document.querySelector('#kuiper-key')])el.addEventListener('input',invalidateActivation);
document.querySelector('#activate').addEventListener('click',async()=>{
  const token=++generation;
  activationState.textContent='Resolving…';activationEvidence.textContent='';
  try{
    const inputs={crs:'WGS84',unit:'degrees',point_a:point('a'),point_b:point('b')};
    const response=await fetch('/activate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instruction:document.querySelector('#instruction').value,key:document.querySelector('#kuiper-key').value.trim(),inputs})});
    if(!response.ok)throw Error('Local activation bridge unavailable');
    const reply=await response.json();if(token!==generation)return;
    if(reply.state!=='PLAN_PROPOSED'){activationState.textContent='REFUSED: '+reply.reason;return;}
    const graph=reply.graph;
    if(reply.selected_meaning!=='GG2050-VEDIC-000006'||graph.schema!=='vedic.orient-dag.v1'||graph.composition!==reply.selected_meaning||JSON.stringify(graph.args)!==JSON.stringify([inputs.point_a.longitude,inputs.point_a.latitude,inputs.point_b.longitude,inputs.point_b.latitude])||graph.outputs.distance_km!=='km'||graph.outputs.initial_bearing_deg!=='degrees'||graph.nodes.length!==2||graph.nodes[0].export!=='distanceKm'||graph.nodes[1].export!=='initialBearingDeg')throw Error('Unsupported typed plan');
    const out=orient(inputs);
    activationState.textContent='EXECUTED_INTERNAL: '+out.distance_km.toFixed(9)+' km; '+out.initial_bearing_deg.toFixed(6)+'° initial bearing';
    activationEvidence.textContent=JSON.stringify({meaning:reply.selected_meaning,compiler:reply.compiler_commit,source_records:reply.rows,dependencies:graph.dependencies,ports:graph.outputs,key_tier:reply.key_tier,identity_complete:reply.identity_complete,rights:reply.rights},null,2);
  }catch(error){if(token===generation)activationState.textContent='REFUSED: '+error.message;}
});
