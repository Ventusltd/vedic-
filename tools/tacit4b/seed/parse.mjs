// Bounded adaptation of TACIT10's formal Acorn module parse; no source execution.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parse,version} from 'acorn';
if(version!=='8.15.0') throw Error('parser version mismatch');
const raw=readFileSync(process.argv[2]), text=raw.toString('utf8');
if(!Buffer.from(text,'utf8').equals(raw)) throw Error('invalid UTF8');
const tree=parse(text,{ecmaVersion:'latest',sourceType:'module',locations:true});
const exports=[], imports=[], dynamic=[];
const span=n=>({first:n.loc.start.line,last:n.loc.end.line,col0:n.loc.start.column,col1:n.loc.end.column,span_sha256:createHash('sha256').update(text.slice(n.start,n.end),'utf8').digest('hex')});
for(const item of tree.body){
 if(item.type==='ImportDeclaration'){imports.push(item.source.value);continue;}
 if(item.type==='ExportAllDeclaration'||item.type==='ExportDefaultDeclaration')throw Error('unsupported export form');
 if(item.type!=='ExportNamedDeclaration')continue;
 if(item.source||item.specifiers.length)throw Error('unsupported re-export');
 const n=item.declaration;
 if(n.type==='FunctionDeclaration')exports.push({name:n.id.name,kind:'function',...span(n)});
 else if(n.type==='VariableDeclaration')for(const d of n.declarations){if(d.id.type!=='Identifier')throw Error('unsupported binding');exports.push({name:d.id.name,kind:n.kind,...span(d)});}
 else throw Error('unsupported declaration');
}
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='ImportExpression')dynamic.push('dynamic-import');for(const [k,v] of Object.entries(n))if(k!=='loc')Array.isArray(v)?v.forEach(walk):walk(v);}
walk(tree);
if(dynamic.length||new Set(exports.map(e=>e.name)).size!==exports.length)throw Error('unsupported imports or duplicate exports');
console.log(JSON.stringify({parser:'acorn@8.15.0',module_sha256:createHash('sha256').update(raw).digest('hex'),exports,imports:[...new Set(imports)].sort()}));
