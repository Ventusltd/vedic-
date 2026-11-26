// Bounded non-allocation rehearsal of the original Modular Star ingestFile.
import {readFileSync,writeFileSync,copyFileSync,mkdtempSync,rmSync} from 'node:fs';
import {join,resolve,basename} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
const root=resolve(process.argv[2]), output=process.argv[3];
const {openDb,ingestFile,extractAny,gitBlobId,rebuildTablet}=await import(pathToFileURL(resolve('producer-lib.mjs')));
const sha=b=>createHash('sha256').update(b).digest('hex');
const need=(x,msg)=>{if(!x)throw Error(msg)};
const stable=x=>JSON.stringify(x,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
const equal=(a,b)=>stable(a)===stable(b);
const tests=[];
const check=(name,ok)=>{need(ok,name);tests.push(name)};
const reject=(name,fn)=>{let caught=false;try{fn()}catch(e){caught=true}check(name,caught)};
const repo='Ventusltd/ventus-grid-engine', commit='487ec7bd38dfa5aecb1c75da53b4a866ab2101cb',parent='911dca300809de076501259572686ba85f301bd0';
const grainRaw=readFileSync(join(root,'grain.json'));
const grainSha='fde99809878734986324896b5f9a464c538b4e2bb318d2950c704fd3aa14014c';
need(sha(grainRaw)===grainSha,'INDEX_GRAIN_PIN');
const grain=JSON.parse(grainRaw), snapshot=JSON.parse(readFileSync(join(root,'snapshot.json')));
const original=join(root,'modular.sqlite'), beforeHash=sha(readFileSync(original));
need(beforeHash===snapshot.database_sha256,'DB_PIN');
const git=(...args)=>execFileSync('git',['-C',join(root,'git'),...args],{encoding:'utf8',timeout:30000}).trim();
const ancestry=git('cat-file','-p',commit).split('\n').filter(x=>x.startsWith('parent ')).map(x=>x.slice(7));
const allowed=new Map(grain.entries.map(r=>[r.source.path,r.source.blob]));
const tuple=x=>[x.repo,x.commit,x.path].join('\u0000');
const plan=[...allowed].sort(([a],[b])=>a.localeCompare(b)).map(([path,blob])=>({repo,commit,path,blob,parent,seen:'2026-11-26T00:00:00Z'}));
function guard(p,parents,treeBlob,parentBlob){
 need(p.repo===repo&&p.commit===commit&&allowed.get(p.path)===p.blob,'EXACT_TUPLE');
 need(parents.length===1&&parents[0]===p.parent&&p.parent===parent,'SINGLE_PINNED_PARENT');
 need(treeBlob===p.blob&&parentBlob===p.blob,'EXACT_UNCHANGED_PATH');
}
function batch(ps){need(new Set(ps.map(tuple)).size===ps.length&&ps.length===allowed.size,'DUPLICATE_OR_MISSING_OCCURRENCE')}
function astPick(r,fs){const s=r.source,p=r.producer_ast;const m=fs.filter(f=>f.name===r.function&&f.first===s.first&&f.last===s.last&&f.col0===p.col0&&f.col1===p.col1&&f.family.toString('hex')===p.family_fingerprint);need(m.length===1,'STALE_AST_SPAN');return m[0]}
batch(plan);check('three unique historical paths',plan.length===3);
check('single exact Git parent',equal(ancestry,[parent]));
check('target revision absent in historical receipt',grain.historical_commit_recorded===0);
for(const p of plan){guard(p,ancestry,git('rev-parse',commit+':'+p.path),git('rev-parse',parent+':'+p.path));tests.push('exact unchanged Git path '+p.path)}
const p=plan[0];
reject('duplicate proposed occurrence',()=>batch([p,p,plan[2]]));
reject('same blob different path',()=>guard({...p,path:'engine/elsewhere.js'},ancestry,p.blob,p.blob));
reject('wrong repository',()=>guard({...p,repo:'Ventusltd/gridatlas'},ancestry,p.blob,p.blob));
reject('missing revision',()=>guard({...p,commit:'0'.repeat(40)},ancestry,p.blob,p.blob));
reject('merge ambiguity',()=>guard(p,[parent,'0'.repeat(40)],p.blob,p.blob));
reject('changed parent path',()=>guard(p,ancestry,p.blob,'0'.repeat(40)));
reject('mutated target blob',()=>guard(p,ancestry,'0'.repeat(40),p.blob));
const dir=mkdtempSync(join(tmpdir(),'tacit-a-dry-')), disposable=join(dir,'copy.sqlite');
let ctx, report;
try {
 copyFileSync(original,disposable);
 ctx=openDb(disposable);
 const db=ctx.db;
 const counters=()=>Object.fromEntries(['line','tablet','element','family','tablet_element','occurrence','scan','commit_info'].map(t=>[t,Number(db.prepare('SELECT count(*) AS n FROM '+t).get().n)]));
 const sequences=()=>db.prepare('SELECT name,seq FROM sqlite_sequence ORDER BY name').all().map(x=>[x.name,Number(x.seq)]);
 const exact=q=>db.prepare('SELECT o.tablet,t.git_blob FROM occurrence o JOIN tablet t ON o.tablet=t.n WHERE o.repo=? AND o.commit_sha=? AND o.path=?').get(q.repo,q.commit,q.path);
 const noOverwrite=q=>{need(!exact(q),'EXISTING_OCCURRENCE_NO_OVERWRITE')};
 const start=counters(), seq=sequences();
 check('actual historical revision absent',Number(db.prepare('SELECT count(*) AS n FROM commit_info WHERE repo=? AND sha=?').get(repo,commit).n)===0);
 const files=[],rows=[];
 db.exec('BEGIN IMMEDIATE');
 try {
   for(const q of plan){
     noOverwrite(q);
     const bytes=readFileSync(join(root,basename(q.path)));
     need(gitBlobId(bytes)===q.blob,'FILE_BLOB');
     const parsed=extractAny('js',bytes);need(!parsed.issue,'PRODUCER_PARSE');
     const targets=grain.entries.filter(r=>r.source.path===q.path);
     for(const r of targets){astPick(r,parsed.functions);tests.push(r.word+' original parser match')}
     const r=targets[0];reject(r.word+' stale parser offset',()=>astPick({...r,producer_ast:{...r.producer_ast,col0:r.producer_ast.col0+1}},parsed.functions));
     const prior=db.prepare('SELECT n FROM tablet WHERE git_blob=?').get(q.blob);
     const existingOther=prior?Number(db.prepare('SELECT count(*) AS n FROM occurrence WHERE tablet=?').get(prior.n).n):0;
     const t=ingestFile(ctx,{repo:q.repo,commit:q.commit,path:q.path,bytes,oid:q.blob,seen:q.seen});
     const inserted=exact(q);check(q.path+' temporary exact join',inserted&&inserted.git_blob===q.blob&&Number(inserted.tablet)===t);
     check(q.path+' reconstruction parity',gitBlobId(rebuildTablet(ctx,t))===q.blob);
     if(prior)check(q.path+' existing tablet retained',Number(prior.n)===t);
     reject(q.path+' existing tuple overwrite',()=>noOverwrite({...q,blob:'0'.repeat(40)}));
     const actual=Number(db.prepare('SELECT count(*) AS n FROM tablet_element WHERE tablet=?').get(t).n);
     files.push({input:{repo:q.repo,commit:q.commit,path:q.path,blob:q.blob,parent:q.parent},parent_unchanged:true,existing_content_tablet:!!prior,other_occurrence_count:existingOther,original_parser_callable_count:parsed.functions.length,temporary_indexed_element_count:actual,target_callable_count:targets.length,exact_occurrence_before:'MISSING',temporary_occurrence:'REHEARSED_ONLY'});
     for(const target of targets){
       const f=astPick(target,parsed.functions);
       const matches=db.prepare('SELECT count(*) AS n FROM tablet_element WHERE tablet=? AND first=? AND last=? AND col0=? AND col1=? AND name=?').get(t,f.first,f.last,f.col0,f.col1,f.name).n;
       rows.push({meaning_id:target.meaning_id,word:target.word,source:target.source,kuiper:target.kuiper,module_classification:target.module_classification,producer_ast:target.producer_ast,exact_occurrence_status:'MISSING_IN_PINNED_PRODUCER',temporary_ast_match_count:Number(matches),permanent_ids_allocated:false});
     }
   }
   const during=counters();
   check('temporary occurrence delta exactly three',during.occurrence-start.occurrence===3);
   check('no commit inventory mark',during.commit_info===start.commit_info&&during.scan===start.scan);
   check('all eight target spans verified',rows.length===8);
   const deltas=Object.fromEntries(Object.keys(start).map(k=>[k,during[k]-start[k]]));
   report={files,rows,namespace_before:start,temporary_count_delta:deltas};
 } finally {db.exec('ROLLBACK')}
 check('all namespace counters restored',equal(counters(),start));
 check('all SQLite sequence counters restored',equal(sequences(),seq));
 check('all three occurrences still missing',plan.every(x=>!exact(x)));
 ctx.db.close();ctx=null;
 check('disposable database bytes restored',sha(readFileSync(disposable))===beforeHash);
 check('original database bytes unchanged',sha(readFileSync(original))===beforeHash);
 report={schema:'vedic.tacit-a.historical-repair-dry-run.v1',grain_sha256:grainSha,source_repo:repo,source_commit:commit,source_parent:parent,producer_snapshot:snapshot,producer_lib_blob:grain.producer_lib_blob,...report,namespace_restored:true,permanent_allocations:0,mode:'DISPOSABLE_TRANSACTION_ROLLED_BACK',owner_decision:{required:true,repository:'Ventusltd/stars',operation:'original ingestFile for three exact Git tuples only; inspect prior tablet and AST match; preserve all existing IDs; do not mark whole revision scanned',paths:plan.map(q=>q.path),source_commit:commit,expected_new_occurrences:3,rights:'NO_REDISTRIBUTION',state:'NOT_AUTHORISED_FOR_PRODUCTION'},tests};
 const out=stable(report)+'\n';writeFileSync(output,out);console.log(JSON.stringify({checks:tests.length,paths:filesCount(report),target_spans:report.rows.length,temporary_deltas:report.temporary_count_delta,parser_callable_counts:report.files.map(x=>[x.input.path,x.original_parser_callable_count]),sha256:sha(out)}));
} finally {if(ctx)ctx.db.close();rmSync(dir,{recursive:true,force:true})}
function filesCount(r){return r.files.length}
