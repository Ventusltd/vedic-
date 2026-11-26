"""Seventh-turn cold recovery consumer for existing evidence, not a graph producer."""
import argparse,copy,json,sys,urllib.request
from pathlib import Path
from tacit_a_closure import canonical,sha,blob,fetch,need,GRID,COMMIT,MODULES,VEDIC,T13
from tacit_a_stars import CANDIDATE_SHA,ZIP_SHA
from tacit_a_index_grain import member,C_SHA,C_ZIP,C_REPO
from tacit_a_bonds import download,identity,GRAIN_ZIP,GRAIN_SHA,B_ZIP,B_SHA
SPIDER="830e86ea65e98b03df7250d2dd55d2753799687a"
BOND_ZIP="649209e8723af1efd4c73f85ebd90b524a2312907d8a5e24759c8bf72ad1f72a"
BOND_SHA="821abf96d3e4c2f42e61d578dcefdfbda366c145b067f9cc9206fdaa91b6cf2d"
PINS={"genome":("species/genome-spider/data/genome.json","e32e00174fa6d3bd2565fa60dbf246b4dbe75ecb"),
"nodes":("species/genome-spider/data/nodes.json","6fb7867bf6bf3abce14930f72dbfe5f8a323d86c"),
"edges":("species/genome-spider/data/edges.json","55c31d741c2472c64552647f63a4c2744d3956d9"),
"receipt":("species/genome-spider/receipts/LATEST.json","a92448e75a6a0832291a0ec32450b776034ce439"),
"lineage":("species/genome-spider/data/gridatlas-lineage.json","dcf7c1362750fb4114145f3b1e3b460e69f5c1e7"),
"printer":("spider_printer_v1/data/topology.json","71e098e5095c444196095080efe74c37df4add25")}
VOCAB="a28d16cd73a2c612bc74982f25af1276839ce76e"
STARS="1cf9c7530c7d287ccf9b3cffd70f693fb83c8402"
def acquire(root):
    root.mkdir()
    for name,id in (("candidate",15137841195),("grain",15138598845),("ranking",15138469041),("bonds",15138897783)):download(root,name,id)
    fetch(VEDIC,T13,"tools/spider_evidence.py","9d46730b7346b6861a99b961b4ac70ef9e02b18b",root/"spider_evidence.py")
    fetch("Ventusltd/stars",STARS,"relationships/VOCABULARY.md",VOCAB,root/"vocabulary.md")
    for name,(p,b) in PINS.items():
        dest=root/p;dest.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/Ventusltd/spiders/{SPIDER}/{p}",timeout=60) as r:raw=r.read(32*1024**2+1)
        need(len(raw)<=32*1024**2 and blob(raw)==b,"SPIDER_PIN:"+name);dest.write_bytes(raw)
    for p,b in MODULES.items():fetch(GRID,COMMIT,p,b,root/Path(p).name)
def source_guard(s,raw):
    need(s["repo"]==GRID and s["commit"]==COMMIT and s["path"] in MODULES and s["blob"]==MODULES[s["path"]] and blob(raw)==s["blob"],"STALE_OR_MUTATED_SOURCE")
def property_guard(p):
    need(set(p)=={"source_occurrence","property","definition_version","value","unit","method","input_sha256","evidence_ref","state","unknown_reason"},"PROPERTY_CONTRACT")
    need(p["state"] in ("OBSERVED","DERIVED","UNKNOWN"),"PROPERTY_STATE")
    if p["state"]=="UNKNOWN":need(p["value"] is None and bool(p["unknown_reason"]),"UNKNOWN_VALUE_PROMOTION")
def relation_guard(edge):
    need(edge["type"] in ("calls","contains","static_module_reference","static_import") and edge["state"]=="STATIC_NOT_RUNTIME_TRACE","RELATIONSHIP_AUTHORITY")
def verify(root,out):
    sys.path.insert(0,str(root.resolve()))
    from spider_evidence import read_pinned,graph_summary,validate_named
    a=member(root/"candidate.zip",ZIP_SHA,"candidate.json",CANDIDATE_SHA)
    g=member(root/"grain.zip",GRAIN_ZIP,"index-grain.json",GRAIN_SHA)
    b=member(root/"bonds.zip",BOND_ZIP,"bonds.json",BOND_SHA)
    rank=member(root/"ranking.zip",B_ZIP,"tacit-b-ranking.json",B_SHA)
    need(b["source_candidate_sha256"]==CANDIDATE_SHA and b["grain_sha256"]==GRAIN_SHA and b["c_review_sha256"]==C_SHA and b["b_ranking_sha256"]==B_SHA,"EVIDENCE_CHAIN")
    tests=[]
    def test(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except ValueError:tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    data={k:read_pinned(root,*pin) for k,pin in PINS.items()}
    historic=graph_summary(data,"ventus-grid-engine")
    vocab=(root/"vocabulary.md").read_bytes();test("vocabulary pin",blob(vocab)==VOCAB)
    test("existing vocabulary",all(x.encode() in vocab for x in ("depends-on","contains","found-in","implements","proven","should-import")))
    test("historical projection verified",historic["spider"]["projection_verified"] and historic["state"]=="HISTORICAL_CONTEXT_ONLY")
    test("Printer URL references only",historic["printer"]["relationship"]=="URL_REFERENCE_ONLY" and historic["execution_edges"]==[])
    # Existing local graph evidence is separate from the historical estate-level graph.
    graph=b["static_source_graph"];validate_named(graph["nodes"],graph["edges"])
    test("same reviewed source graph",graph==a["source_dependency_graph"] and graph["execution_edges"]==[])
    for e in graph["edges"]:relation_guard(e)
    reject("Printer reference is not a call",lambda:relation_guard({**graph["edges"][0],"type":"reference"}))
    reject("should-import not execution",lambda:relation_guard({**graph["edges"][0],"type":"should-import"}))
    reject("runtime overreach",lambda:relation_guard({**graph["edges"][0],"state":"EXECUTED"}))
    reject("dangling graph",lambda:validate_named(graph["nodes"],graph["edges"]+[{"from":"nonexistent","to":graph["nodes"][0]["id"],"type":"calls"}]))
    # Resolve by exact occurrence; presentation never changes identity.
    by_id={r["meaning_id"]:r for r in a["entries"]};gr={r["meaning_id"]:r for r in g["entries"]}
    rows=[]
    for r in b["source_entries"]:
        s=r["source"];raw=(root/Path(s["path"]).name).read_bytes();source_guard(s,raw)
        old=by_id[r["meaning_id"]];prior=gr[r["meaning_id"]]
        test(r["meaning_id"]+" identity",identity(r)==identity(old)==identity(prior) and sha(raw)==old["module_sha256"])
        test(r["meaning_id"]+" classification",r["module_classification"]==prior["module_classification"])
        mut={**r,"module_classification":{"symbol":"presentation-only"}}
        test(r["meaning_id"]+" property stability",identity(mut)==identity(r))
        rows.append({**r,"word":old["word"],"function":old["function"],"stars":prior["existing_stars"],"indexing_gap":prior["reason"],"producer_ast":prior["producer_ast"]})
    s=rows[0]["source"];raw=(root/Path(s["path"]).name).read_bytes()
    reject("source mutation",lambda:source_guard(s,raw+b" "))
    reject("stale revision",lambda:source_guard({**s,"commit":"0"*40},raw))
    for p in b["properties"]:property_guard(p)
    unknown=next(p for p in b["properties"] if p["state"]=="UNKNOWN")
    reject("unknown property promotion",lambda:property_guard({**unknown,"value":True}))
    reject("unknown state",lambda:property_guard({**unknown,"state":"VERIFIED"}))
    test("pre-admission preserved",rank["factory_admission"]=="FAMILY_NOT_ADMITTED" and b["runtime_observation"]["independent_acceptance"] is False and b["redistribution"]=="BLOCKED")
    # Do not manufacture renderer IDs or emit new cartridges. Expose bounded read-only evidence.
    summary={"genome_nodes":historic["genome"]["node_count"],"genome_edges":historic["genome"]["edge_count"],"printer_nodes":historic["printer"]["node_count"],"printer_edges":historic["printer"]["edge_count"],
      "genome_focus_present":historic["genome"]["focus_present"],"printer_focus_present":historic["printer"]["focus_present"],"execution_edges":0,"projection_verified":True,
      "live_integration":False,"state":"CANDIDATE_READ_ONLY_HISTORICAL_CONTEXT"}
    capsule={"schema":"vedic.tacit-a.cold-recovery.v1","source_candidate_sha256":CANDIDATE_SHA,"index_grain_sha256":GRAIN_SHA,"typed_bonds_sha256":BOND_SHA,"c_independent_review_sha256":C_SHA,"b_ranking_sha256":B_SHA,
      "source_entries":rows,"family_reviews":b["family_reviews"],"typed_bonds":b["typed_bonds"],"incompatible_bonds":b["incompatible_bonds"],"properties":b["properties"],"static_source_graph":graph,
      "spider_current_commit":SPIDER,"spider_pins":PINS,"spider_channels":summary,"periodic_state":"PRODUCER_MODULE_CLASSIFICATION_ONLY","runtime_observation":b["runtime_observation"],
      "next_producer_task":"Owner-approved sparse ingestFile of three exact pinned historical paths; do not reassign existing permanent numbers; verify original AST columns and family membership on new immutable producer snapshot.",
      "commands":["python tools/tacit_a_recovery.py acquire --root DIR","python tools/tacit_a_recovery.py verify --root DIR --out capsule.json"],
      "tests":tests,"admission":"UNCHANGED","rights":"BLOCKED","live_integration":False}
    out.write_bytes(canonical(capsule)+b"\n")
    print(json.dumps({"checks":len(tests),"addresses":len(rows),"graph":summary,"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)
