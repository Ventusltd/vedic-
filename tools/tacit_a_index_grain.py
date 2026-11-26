"""Fifth-turn bounded indexing-grain diagnosis and immutable reviewed handoff."""
import argparse,json,sqlite3,sys,subprocess,zipfile
from contextlib import closing
from pathlib import Path
from tacit_a_closure import canonical,sha,blob,fetch,need,GRID,COMMIT,MODULES,VEDIC
from tacit_a_stars import acquire as acquire_stars, STARS_HEAD,CANDIDATE_SHA,ZIP_SHA,ASSET_PIN
from tacit_a_classification import classify,MAKER,TABLE_BLOB,CATALOGUE_BLOB
PARENT="911dca300809de076501259572686ba85f301bd0"
C_REPO="Ventusltd/neural-link-between-agents"
C_HEAD="3deafd5fd9183110f9d61eec05df255275cc1dd2"
C_ZIP="8d48284a1ed870d16d99504707c81e0650a23c24693a1e491a787e809bb08ffa"
C_SHA="76080746a09f0c3fa6693211147acfa98716be50caeb766f4ee01a68fc9ac303"
LIB="403c6034eb4fdf8c53cc108d2894e0fa5503b346"
FAMILIES={"electrical":("3526d5fc61fc79e4a843b525d66f4dd956643ac84b110244553bdcb7f5736c0a","c5b16903919c91337df664c8482095c3ac9dbd36df3bfb9b06991a43afd9c7f4"),
"nearest":("0aef7559f3b6a662d9556fc514ee4fbd7c5b37bcf31c2d9d58675fa05fbc30c9","3901fac7ad2612bed7690f6e7f71d7be272a2ed4287e537cfb0125f875768bd6"),
"orient":("a8d892cf69e96644e904c05f8dd400febc29e92467b93882a9951a8bb2b4619b","13367192a50f6f9bced5b3fdc7b989c482a8a3221f5e4ba59d5fbd98f020bbff")}
def acquire(root):
    acquire_stars(root)
    fetch("Ventusltd/stars",STARS_HEAD,"modular-star/lib.mjs",LIB,root/"producer-lib.mjs")
    fetch("Ventusltd/star-maker",MAKER,"elements/table.json",TABLE_BLOB,root/"table.json")
    fetch("Ventusltd/stars",STARS_HEAD,"modular-star/blocks-catalogue.json",CATALOGUE_BLOB,root/"catalogue.json")
    for p,b in MODULES.items():fetch(GRID,PARENT,p,b,root/("parent-"+Path(p).name))
    with (root/"c.zip").open("xb") as f:
        subprocess.run(["gh","api",f"repos/{C_REPO}/actions/artifacts/15138980638/zip"],stdout=f,check=True,timeout=90)
    need(sha((root/"c.zip").read_bytes())==C_ZIP,"C_ZIP")
def member(path,pin,name,digest):
    need(sha(path.read_bytes())==pin,"ZIP_PIN")
    with zipfile.ZipFile(path) as z:
        names=[x for x in z.namelist() if x==name or x.endswith("/"+name)]
        need(len(names)==1,"MEMBER")
        raw=z.read(names[0])
    need(sha(raw)==digest,"MEMBER_DIGEST:"+name)
    return json.loads(raw)
def verify(root,out):
    sys.path.insert(0,str(root.resolve()))
    from identity_bridge import stars_join,digest
    a=member(root/"candidate.zip",ZIP_SHA,"candidate.json",CANDIDATE_SHA)
    c=member(root/"c.zip",C_ZIP,"a-review.json",C_SHA)
    need(c["candidate_sha256"]==CANDIDATE_SHA and c["result"]=="BOUNDED_EVIDENCE_HONOURED" and c["formal_factory_admission"] is False,"C_REVIEW_BOUNDARY")
    rows=a["entries"];need(len(rows)==8,"COHORT")
    tests=[];result=[]
    def test(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError,StopIteration):tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    def source_guard(r):
        s=r["source"];p=s["path"]
        need(s["repo"]==GRID and s["commit"]==COMMIT and MODULES[p]==s["blob"],"SOURCE_TUPLE")
        b=(root/Path(p).name).read_bytes()
        need(blob(b)==s["blob"] and sha(b)==r["module_sha256"],"SOURCE_BYTES")
        need(1<=s["first"]<=s["last"]<=len(b.splitlines()),"SPAN")
        need(sha(b"".join(b.splitlines(keepends=True)[s["first"]-1:s["last"]]))==r["physical_span_sha256"],"SPAN_HASH")
        return b
    def pick(r,parsed):
        s=r["source"]
        candidates=[p for p in parsed if p["first"]==s["first"] and p["last"]==s["last"] and p["name"]==r["function"]]
        need(len(candidates)==1,"PRODUCER_AST_SPAN_NAME")
        return candidates[0]
    table=json.loads((root/"table.json").read_bytes());cat=json.loads((root/"catalogue.json").read_bytes())
    test("classification pins",blob((root/"table.json").read_bytes())==TABLE_BLOB and blob((root/"catalogue.json").read_bytes())==CATALOGUE_BLOB)
    dbpath=root/"modular.sqlite";snapshot=json.loads((root/"snapshot.json").read_bytes());dbsha=digest(dbpath)
    test("DB pin",dbsha==snapshot["database_sha256"] and snapshot["compressed_sha256"]==ASSET_PIN["digest"].split(":")[1])
    ast=json.loads((root/"producer-ast.json").read_bytes())
    with closing(sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        scan=db.execute("SELECT repo,commit_sha,issue FROM scan WHERE lower(repo)=lower(?)",(GRID,)).fetchall()
        hist=db.execute("SELECT count(*) FROM commit_info WHERE repo=? AND sha=?",(GRID,COMMIT)).fetchone()[0] if "commit_info" in tables else None
        for r in rows:
            s=r["source"];p=s["path"];b=source_guard(r)
            test(r["word"]+" parent identical blob",blob((root/("parent-"+Path(p).name)).read_bytes())==s["blob"])
            test(r["word"]+" producer parser source",ast[p]["blob"]==s["blob"] and ast[p]["issue"] is None)
            parsed=pick(r,ast[p]["functions"]);tests.append(r["word"]+" producer function AST")
            exact=stars_join(db,{**s,"col0":parsed["col0"],"col1":parsed["col1"]})
            # Existing producer indexes changed paths in history, full tree at current scan.
            # Exact same blob elsewhere is a diagnostic, never identity substitution.
            diag=exact.get("absence_diagnostic",{})
            reason="EXACT_OCCURRENCE_FOUND" if exact["tablet_id"] is not None else "HISTORICAL_UNCHANGED_PATH_NOT_INDEXED" if hist==1 else "REVISION_NOT_RECORDED_OR_UNCHANGED_PATH"
            result.append({"meaning_id":r["meaning_id"],"word":r["word"],"function":r["function"],"source":s,"kuiper":r["kuiper"],"module_classification":classify(s,table,cat),
              "producer_ast":parsed,"existing_stars":exact,"reason":reason,
              "proposed_occurrence_input":{"repo":GRID,"commit":COMMIT,"path":p,"blob":s["blob"],"state":"DRY_RUN_ONLY_NO_INSERT"} if exact["tablet_id"] is None else None})
        r=rows[0];s=r["source"]
        for field,value in (("repo","Ventusltd/gridatlas"),("commit","0"*40),("path","engine/other.js"),("first",0)):
            reject("wrong "+field,lambda:source_guard({**r,"source":{**s,field:value}}))
        reject("wrong export",lambda:pick({**r,"function":"notAnExport"},ast[s["path"]]["functions"]))
        test("wrong revision no identity",stars_join(db,{**s,"commit":"0"*40})["tablet_id"] is None)
    test("DB unchanged",digest(dbpath)==dbsha)
    # Keep exact reviewed bytes, never mutate candidate receipt to imply admission.
    reviews={}
    for family,(sd,cd) in FAMILIES.items():
        sr=member(root/"candidate.zip",ZIP_SHA,"family-review/"+family+"-source.json",sd)
        cl=member(root/"candidate.zip",ZIP_SHA,"family-review/"+family+"-closure.json",cd)
        review=c["source_and_closure"][family]
        test(family+" review pins",review["source_candidate_sha256"]==sd and review["closure_candidate_sha256"]==cd and review["source"]["verdict"]==review["closure"]["verdict"]=="HONOURED")
        test(family+" authority",sr["candidate_state"]==cl["candidate_state"]=="REFUSED_REVIEW_PENDING" and not cl["runtime_verified"] and not sr["independent_acceptance"])
        if family=="nearest":
            def closure_guard(x):need(x["static_imports"]==[a["nearest_closure"]["static_import"]],"MISSING_EDGE")
            closure_guard(cl);reject("missing import",lambda:closure_guard({**cl,"static_imports":[]}))
        reviews[family]={"source_sha256":sd,"closure_sha256":cd,"review":review}
    def admission(x):need(x=="FORMALLY_ADMITTED","UNKNOWN_NOT_ADMITTED")
    reject("unknown promotion",lambda:admission("UNKNOWN"))
    report={"schema":"vedic.tacit-a.index-grain-review-handoff.v1","candidate_sha256":CANDIDATE_SHA,"c_review_sha256":C_SHA,"c_review_head":C_HEAD,
      "producer_snapshot":snapshot,"producer_lib_blob":LIB,"source_parent":PARENT,"historical_commit_recorded":hist,"current_scan":scan,"entries":result,
      "reviewed_families":reviews,"remedy":"Submit exact unchanged-path occurrence to existing ingestFile only with owner allocation authority; no changes performed; AST span may differ from semantic property span.",
      "tests":tests,"admission":"REFUSED_REVIEW_PENDING","rights":"BLOCKED"}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"checks":len(tests),"historical_commit_recorded":hist,"scan":scan,"reasons":{r["word"]:r["reason"] for r in result},"ast":{r["word"]:[r["producer_ast"]["first"],r["producer_ast"]["last"],r["producer_ast"]["col0"],r["producer_ast"]["col1"]] for r in result},"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)
