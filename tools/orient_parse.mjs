// Strict Acorn parse of original module; does not execute it.
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parse} from 'acorn';
const [input,output]=process.argv.slice(2);
const raw=readFileSync(input),text=raw.toString('utf8');
const tree=parse(text,{ecmaVersion:'latest',sourceType:'module',locations:true});
const need={distanceKm:['DEG','EARTH_RADIUS_KM'],initialBearingDeg:['DEG']};
const functions={},constants={};
for(const item of tree.body){
  const n=item.type==='ExportNamedDeclaration'?item.declaration:item;
  if(n?.type==='VariableDeclaration'&&n.kind==='const'){
    for(const d of n.declarations)if(['DEG','EARTH_RADIUS_KM'].includes(d.id.name))
      constants[d.id.name]={scope:'module',exported:item.type==='ExportNamedDeclaration',expression:text.slice(d.init.start,d.init.end)};
  }
  if(item.type==='ExportNamedDeclaration'&&n?.type==='FunctionDeclaration'&&Object.hasOwn(need,n.id.name)){
    if(functions[n.id.name])throw Error('duplicate export');
    const names=new Set(),declared=new Set(n.params.map(p=>p.name));
    const visit=o=>{if(!o||typeof o!=='object')return;if(o.type==='Identifier')names.add(o.name);
      if(o.type==='VariableDeclarator'&&o.id.type==='Identifier')declared.add(o.id.name);
      for(const [k,v] of Object.entries(o))if(k!=='loc')Array.isArray(v)?v.forEach(visit):visit(v);};
    visit(n.body);
    const refs=need[n.id.name];
    if(refs.some(r=>!names.has(r)||declared.has(r)))throw Error('module dependency missing or shadowed');
    functions[n.id.name]={first:n.loc.start.line,last:n.loc.end.line,col0:n.loc.start.column,col1:n.loc.end.column,
      scope:'top-level exported declaration',parameters:n.params.map(p=>p.name),module_dependencies:refs};
  }
}
if(constants.DEG?.expression!=='Math.PI / 180'||constants.EARTH_RADIUS_KM?.expression!=='6378.137'||Object.keys(functions).length!==2)throw Error('missing or changed module declarations');
writeFileSync(output,JSON.stringify({parser:'acorn strict module',module_sha256:createHash('sha256').update(raw).digest('hex'),constants,functions},null,2)+'\n',{flag:'wx'});
