// Run the existing producer parser, not a replacement index.
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {extractAny,gitBlobId}=await import(pathToFileURL(resolve('producer-lib.mjs')));
const out={};
for(const file of ['voltage-drop.js','v9-nearest-search.js','v9-geodesy.js']){
 const b=readFileSync(resolve(root,file));const p=extractAny('js',b);
 out['engine/'+file]={blob:gitBlobId(b),issue:p.issue,functions:p.functions.map(f=>({first:f.first,last:f.last,col0:f.col0,col1:f.col1,name:f.name,kind:f.kind,needs:f.needs,standalone:f.standalone,family_fingerprint:f.family.toString('hex')}))};
}
console.log(JSON.stringify(out));
