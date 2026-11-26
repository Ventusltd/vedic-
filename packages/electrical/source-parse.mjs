// Additive family-specific adaptation of TACIT10 PR12 orient_parse.mjs.
// Acorn parses original bytes without evaluating the module.
import {readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parse} from 'acorn';
const [input,output]=process.argv.slice(2);
const raw=readFileSync(input), text=raw.toString('utf8');
const sha=b=>createHash('sha256').update(b).digest('hex');
if(sha(raw)!=='8c3d99ca10b0d02722b54c6da21ebf1acb77936fe440cbd413b457266a994287')throw Error('wrong source');
const tree=parse(text,{ecmaVersion:'latest',sourceType:'module',locations:true});
const expected={
 voltageDropVolts:['PHASE_FACTOR','nonNegative','phasesOf','positive','ratio','schema'],
 dropPercent:['positive','schema'],
 lossesWatts:['phasesOf','positive','schema'],
 annualLossKwh:['positive','ratio','schema'],
 positive:[],nonNegative:[],ratio:['positive'],phasesOf:[]
};
const funcs={},constants={},exports=[],imports=[];
function walk(n,visit,parent=null,key=null){
 if(!n||typeof n!=='object')return;
 if(typeof n.type==='string')visit(n,parent,key);
 for(const [k,v] of Object.entries(n)) if(k!=='loc'){
  if(Array.isArray(v))v.forEach(x=>walk(x,visit,n,k)); else walk(v,visit,n,k);
 }
}
for(const item of tree.body){
 const exported=item.type==='ExportNamedDeclaration';
 if(item.type==='ImportDeclaration'||(exported&&item.source)||item.type==='ExportAllDeclaration')imports.push(item.source?.value??'unknown');
 const n=exported?item.declaration:item;
 if(n?.type==='VariableDeclaration'){
  if(n.kind!=='const')throw Error('unexpected top-level mutable variable');
  for(const d of n.declarations){
   if(d.id.type!=='Identifier'||!d.init)throw Error('unexpected constant shape');
   constants[d.id.name]={exported,first:d.loc.start.line,last:d.loc.end.line,sha256:sha(Buffer.from(text.slice(d.init.start,d.init.end)))};
   if(exported)exports.push(d.id.name);
  }
 }else if(n?.type==='FunctionDeclaration'){
  const name=n.id.name;
  if(!Object.hasOwn(expected,name)||funcs[name])throw Error('unexpected or duplicate function');
  if(exported)exports.push(name);
  const names=new Set(),declared=new Set();
  function binding(p){if(p.type==='Identifier')declared.add(p.name);
   else if(p.type==='AssignmentPattern')binding(p.left);
   else if(p.type==='ObjectPattern')p.properties.forEach(x=>binding(x.value));
   else throw Error('unsupported binding');}
  n.params.forEach(binding);
  walk(n.body,(o,p,k)=>{
   if(o.type==='VariableDeclarator')binding(o.id);
   if(o.type==='Identifier'&&!(p?.type==='MemberExpression'&&k==='property'&&!p.computed)&&!(p?.type==='Property'&&k==='key'&&!p.computed&&!p.shorthand))names.add(o.name);
  });
  const dependencies=[...names].filter(x=>Object.hasOwn(expected,x)||['schema','PHASE_FACTOR','NOT_COMPUTED'].includes(x)).filter(x=>!declared.has(x)).sort();
  if(JSON.stringify(dependencies)!==JSON.stringify(expected[name]))throw Error('dependency mismatch '+name+' '+JSON.stringify(dependencies));
  funcs[name]={exported,first:n.loc.start.line,last:n.loc.end.line,col0:n.loc.start.column,col1:n.loc.end.column,export_first:item.loc.start.line,export_col0:item.loc.start.column,ast_sha256:sha(Buffer.from(text.slice(n.start,n.end))),module_dependencies:dependencies,parameters:n.params.map(p=>p.type==='ObjectPattern'?p.properties.map(x=>x.key.name):p.name)};
 }else throw Error('unsupported top-level statement');
}
walk(tree,n=>{if(n.type==='ImportExpression'||(n.type==='CallExpression'&&['require','eval','Function'].includes(n.callee?.name)))throw Error('dynamic execution/dependency');});
if(imports.length||Object.keys(funcs).length!==8||Object.keys(constants).sort().join(',')!=='NOT_COMPUTED,PHASE_FACTOR,schema')throw Error('module closure mismatch');
writeFileSync(output,JSON.stringify({parser:'acorn strict module; family-specific static analysis',module_sha256:sha(raw),imports,exports:exports.sort(),functions:funcs,constants},null,2)+'\n',{flag:'wx'});
