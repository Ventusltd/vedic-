// Narrow nested-arrow/import check supplementing TACIT4b's existing Acorn parser.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {parse,version} from 'acorn';
const raw=readFileSync(process.argv[2]),tree=parse(raw.toString('utf8'),{ecmaVersion:'latest',sourceType:'module',locations:true});
const need=(v,m)=>{if(!v)throw Error(m)};
need(version==='8.15.0','parser version');
const imports=tree.body.filter(n=>n.type==='ImportDeclaration');
need(imports.length===1&&imports[0].source.value==='./v9-geodesy.js'&&imports[0].specifiers.length===1&&imports[0].specifiers[0].imported.name==='distanceKm'&&imports[0].specifiers[0].local.name==='distanceKm','import closure');
const index=tree.body.find(n=>n.type==='ExportNamedDeclaration'&&n.declaration?.id?.name==='index').declaration;
const ret=index.body.body.find(n=>n.type==='ReturnStatement');
const p=ret.argument.properties.find(n=>n.key.name==='nearest');
need(p.value.type==='ArrowFunctionExpression','nearest nested form');
const calls=[];
function walk(n){if(!n||typeof n!=='object')return;if(n.type==='ImportExpression'||(n.type==='CallExpression'&&['eval','require','Function'].includes(n.callee?.name)))throw Error('dynamic dependency');if(n.type==='CallExpression'&&n.callee?.type==='Identifier')calls.push({name:n.callee.name,line:n.loc.start.line});for(const [k,v] of Object.entries(n))if(k!=='loc')Array.isArray(v)?v.forEach(walk):walk(v);}
walk(tree);
need(calls.some(c=>c.name==='normalise'&&c.line===54)&&calls.some(c=>c.name==='distanceKm'&&c.line===81),'Spider call evidence');
console.log(JSON.stringify({module_sha256:createHash('sha256').update(raw).digest('hex'),nearest:{first:p.loc.start.line,last:p.loc.end.line,col0:p.loc.start.column,col1:p.loc.end.column,kind:'nested_property_not_export'},static_import:{from:'engine/v9-nearest-search.js',to:'engine/v9-geodesy.js',symbol:'distanceKm'},calls,scope:'static source; runtime not proven'}));
