"""Sparse current Modular Star / Periodic Table crosswalk, candidate evidence only.
Reuses TACIT10 stars_join, existing modular_snapshot and producer family membership.
No scanner, no permanent allocation, no source distribution, no runtime admission."""
import argparse, hashlib, json, sqlite3, subprocess, sys, zipfile
from contextlib import closing
from pathlib import Path
from tacit_a_closure import canonical, sha, blob, fetch, need, VEDIC, T10, GRID, COMMIT, MODULES
from modular_snapshot import metadata, unpack_snapshot, gh, PRODUCER, TAG, ASSET
STARS_HEAD="1cf9c7530c7d287ccf9b3cffd70f693fb83c8402"
ASSET_PIN={"release_id":388112262,"asset_id":796582323,"size":113072051,
    "updated_at":"2026-11-26T15:46:10Z","digest":"sha256:2379a68bd54096b94efcb13fb557aa8eaad68c756b5b3fdf09a64a51da5414c1"}
BLOCK_PINS={"blocks/blocks.json":"f255fa0dc24786dd0c760cdf1e3f5d6cfaeb126a",
    "blocks/families.json":"fb53509f6a5c3ba4c15e1d5c60aab58750ab8699",
    "blocks/graph.json":"0effdf62ccf1472480464843e8e4b15ec560f1bd"}
ARTIFACT=15137841195
ZIP_SHA="c1ea563a7be0c1343d547d5678f46b86952a73bc8d5346d330a0faf8e7667772"
CANDIDATE_SHA="5f5cc4c75515ca0059fb67e2f511c4b22d7e048096916cff569ecd630578a831"
EXPECTED={1,5,15,16,24,25,26,27}
def acquire(root):
    root.mkdir()
    fetch(VEDIC,T10,"tools/identity_bridge.py","f3e6519aab67d2bc9fbc818318abca478ca2ef7e",root/"identity_bridge.py")
    for p,b in MODULES.items(): fetch(GRID,COMMIT,p,b,root/Path(p).name)
    # Existing raw helper has a 2 MB bound. Producer block catalogue may exceed it:
    # use a separate strict 32 MB cap, verify the exact Git blob before parsing.
    import urllib.request
    for p,b in BLOCK_PINS.items():
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{PRODUCER}/{STARS_HEAD}/{p}",timeout=60) as r: raw=r.read(32*1024**2+1)
        need(len(raw)<=32*1024**2 and blob(raw)==b,"BLOCK_GIT_PIN:"+p)
        (root/Path(p).name).write_bytes(raw)
    before=metadata()
    need(before==ASSET_PIN,"STARS_ASSET_CHANGED_REPIN_REQUIRED")
    gh("release","download",TAG,"--repo",PRODUCER,"--pattern",ASSET,"--dir",str(root))
    after=metadata()
    need(after==ASSET_PIN,"STARS_ASSET_CHANGED_REPIN_REQUIRED")
    hashes=unpack_snapshot(root/ASSET,root/"modular.sqlite",before,after)
    (root/"snapshot.json").write_bytes(canonical(hashes)+b"\n")
    with (root/"candidate.zip").open("xb") as f:
        subprocess.run(["gh","api",f"repos/{VEDIC}/actions/artifacts/{ARTIFACT}/zip"],stdout=f,check=True,timeout=90)
    need(sha((root/"candidate.zip").read_bytes())==ZIP_SHA,"CANDIDATE_ARTIFACT_DIGEST")
def membership(family, mapping, blocks, graph, stars_state):
    # No crosswalk from same-blob/different occurrence or guessed element.
    if stars_state!="EXACT_INDEXED_PHYSICAL_SPAN" or family is None:
        return {"state":"UNKNOWN_EXACT_FAMILY_REQUIRED","symbol":None,"number":None,"category":None}
    hits=[symbol for symbol,ids in mapping.items() if family in ids]
    need(len(hits)<=1,"DUPLICATE_FAMILY_MEMBERSHIP")
    if not hits:return {"state":"UNKNOWN_FAMILY_NOT_IN_PINNED_TABLE","symbol":None,"number":None,"category":None}
    symbol=hits[0]
    matches=[x for x in blocks if x["symbol"]==symbol]
    need(len(matches)<=1,"DUPLICATE_BLOCK_SYMBOL")
    if not matches:return {"state":"FAMILY_LIST_ONLY_BLOCK_METADATA_UNKNOWN","symbol":symbol,"number":None,"category":None}
    block=matches[0]; number=block["number"];cat=block["category"]
    need(type(number) is int and number>0,"BLOCK_NUMBER")
    nodes={n["id"] for n in graph["nodes"]}
    need("block:"+symbol in nodes and "category:"+cat in nodes,"BLOCK_GRAPH_NODE")
    links=[e for e in graph["edges"] if e["from"]=="category:"+cat and e["to"]=="block:"+symbol and e["type"]=="contains"]
    need(len(links)==1,"BLOCK_GRAPH_CATEGORY_JOIN")
    return {"state":"PINNED_PRODUCER_FAMILY_MEMBERSHIP","symbol":symbol,"number":number,"category":cat}
def verify(root,out):
    sys.path.insert(0,str(root.resolve()))
    from identity_bridge import stars_join,digest
    raw=(root/"candidate.zip").read_bytes()
    need(sha(raw)==ZIP_SHA,"CANDIDATE_ARTIFACT_DIGEST")
    with zipfile.ZipFile(root/"candidate.zip") as z: candidate_raw=z.read("candidate.json")
    need(sha(candidate_raw)==CANDIDATE_SHA,"CANDIDATE_DIGEST")
    candidate=json.loads(candidate_raw)
    rows=candidate["entries"];need({int(r["meaning_id"][-6:]) for r in rows}==EXPECTED and len(rows)==8,"CENSUS")
    snapshot=json.loads((root/"snapshot.json").read_text())
    need(snapshot["compressed_sha256"]==ASSET_PIN["digest"].split(":")[1] and snapshot["asset_digest_verified"] is True,"ASSET_PIN")
    dbpath=root/"modular.sqlite";dbsha=digest(dbpath)
    need(dbsha==snapshot["database_sha256"],"DB_DIGEST")
    need(not any(Path(str(dbpath)+s).exists() for s in ("-wal","-journal")),"DB_SIDECAR")
    docs={}
    for p,b in BLOCK_PINS.items():
        data=(root/Path(p).name).read_bytes();need(blob(data)==b,"BLOCK_PIN")
        docs[p]=json.loads(data)
    mapping=docs["blocks/families.json"];blocks=docs["blocks/blocks.json"]["blocks"];graph=docs["blocks/graph.json"]
    need(graph["schema"]=="periodic-table-graph.v1","GRAPH_SCHEMA")
    need(all(isinstance(v,list) and len(v)==len(set(v)) for v in mapping.values()),"DUPLICATE_FAMILY_IN_BLOCK")
    need(len({b["number"] for b in blocks})==len({b["symbol"] for b in blocks})==len(blocks),"DUPLICATE_BLOCK_ID")
    check=[];results=[]
    def test(name,ok):need(ok,name);check.append(name)
    def reject(name,fn):
        try:fn()
        except ValueError:check.append(name)
        else:raise AssertionError("EXPECTED_REFUSAL:"+name)
    with closing(sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        test("database integrity",db.execute("PRAGMA quick_check").fetchall()==[("ok",)])
        for r in rows:
            s=r["source"];p=s["path"];b=(root/Path(p).name).read_bytes()
            test(r["meaning_id"]+" source pin",s["repo"]==GRID and s["commit"]==COMMIT and blob(b)==s["blob"]==MODULES[p] and sha(b)==r["module_sha256"])
            span=sha(b"".join(b.splitlines(keepends=True)[s["first"]-1:s["last"]]))
            test(r["meaning_id"]+" physical span",span==r["physical_span_sha256"])
            parser=r["formal_parser_span"]
            # For RANK the parser locates a Property node, not a standalone exported function.
            # Column pins are meaningful only for the matching producer AST form; do not guess.
            ss={**s,"col0":parser["col0"],"col1":parser["col1"]}
            stars=stars_join(db,ss)
            test(r["meaning_id"]+" indexed span parity",stars.get("span_sha256") in (None,span))
            prior=r["stars"]
            # A previously exact permanent ID must remain exact; no silent identity reassignment.
            for field in ("tablet_id","line_ids","element_id","family_id"):
                if prior.get(field) is not None:
                    # Earlier lookup lacked AST columns. Ambiguity must be recorded, not guessed.
                    if stars.get(field) is not None:test(r["meaning_id"]+" permanent "+field,stars[field]==prior[field])
            periodic=membership(stars["family_id"],mapping,blocks,graph,stars["state"])
            results.append({"meaning_id":r["meaning_id"],"word":r["word"],"source":ss,"kuiper":r["kuiper"],
                "physical_span_sha256":span,"prior_stars":prior,"current_stars":stars,"periodic":periodic,
                "classification_candidate":r["classification"],"admission":"REFUSED_REVIEW_PENDING"})
        s=results[0]["source"]
        for field,value in (("commit","0"*40),("path","nonexistent.js")):
            bad=stars_join(db,{**s,field:value})
            test("same blob wrong "+field,bad["state"]=="OCCURRENCE_NOT_INDEXED" and bad["tablet_id"] is None)
    test("database bytes unchanged",digest(dbpath)==dbsha)
    test("unknown cannot join table",membership(123,mapping,blocks,graph,"OCCURRENCE_NOT_INDEXED")["number"] is None)
    reject("duplicate family refusal",lambda:membership(999999999,{"a":[999999999],"b":[999999999]},blocks,graph,"EXACT_INDEXED_PHYSICAL_SPAN"))
    reject("missing category graph edge refusal",lambda:membership(999999999,{"a":[999999999]},[{"symbol":"a","number":1,"category":"geodesy"}],{"nodes":[],"edges":[]},"EXACT_INDEXED_PHYSICAL_SPAN"))
    exact=sum(r["current_stars"]["tablet_id"] is not None for r in results)
    elements=sum(r["current_stars"]["element_id"] is not None for r in results)
    periodic=sum(r["periodic"]["state"]=="PINNED_PRODUCER_FAMILY_MEMBERSHIP" for r in results)
    report={"schema":"vedic.tacit-a.stars-periodic-crosswalk-candidate.v1","source_candidate_sha256":CANDIDATE_SHA,
      "stars_asset":ASSET_PIN,"snapshot":snapshot,"periodic_commit":STARS_HEAD,"periodic_git_blobs":BLOCK_PINS,
      "entries":results,"exact_occurrences":exact,"exact_elements":elements,"exact_periodic_memberships":periodic,
      "tests":check,"test_count":len(check),"independent_acceptance":False,"rights":"BLOCKED",
      "admission":"REFUSED_REVIEW_PENDING","scope":"exact physical occurrence and pinned published family membership only; no runtime edge inference"}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"checks":len(check),"exact_occurrences":exact,"exact_elements":elements,"exact_periodic_memberships":periodic,"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",required=True,type=Path);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)
