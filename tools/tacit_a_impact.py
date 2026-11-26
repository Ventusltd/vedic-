"""Ninth-turn extension of the exact v1 typed manifest, never an identity or runtime registry."""
import argparse,ast,copy,importlib.util,json,subprocess,sys,zipfile
from pathlib import Path
from tacit_a_closure import canonical,sha,blob,fetch,need,GRID,COMMIT,MODULES,VEDIC,T3,T13
from tacit_a_index_grain import member,C_REPO,C_SHA,FAMILIES
from tacit_a_bonds import download,identity,compatible,B_SHA
from tacit_a_recovery import BOND_ZIP,BOND_SHA,source_guard,property_guard,relation_guard
REPAIR_ZIP="f2a66617149a4b51e95dbdc908dd78ea9ff5db94e9946e259ad297888d46d04f"
REPAIR_SHA="e76464f5f4c70f25cf24b42ffa2ac199d5b8b3eced4189484fe5af159b1a211c"
B_HEAD="827dc15ffebc236954ee4aa40ba0141cd7c23fa4"
B_ZIP="73aa6fd35d71cefb9f60148bc14a5105ab35bbf013c48b6bf555002a0c1d7158"
B_INTAKE="536358fe3271c87fcd13118b9f467415509a6af1b6a998437925846b8a6f7fe1"
B_ELECTRICAL="c8598fb9719ca84f8e36fdab24eee4b3c45ffc1e489527a3661b2fbfad307b47"
C_RANK_ZIP="c5b746fa68438f43c7b96ac062604db9955152584d904ef1994cd4e92657f7f2"
C_RANK_SHA="f73a064c910e69334a4b1a2c57f1cb86642b51843d6a59ff149c4a9c561b1e90"
C_ELEC_ZIP="22f5266e2fb2d7a014231befa31251c611301e9e6abd463d9aab8b5ee8143cd4"
C_ELEC_SHA="20d577d7b4e74cbdc0059dd3ea4950ecc3c0e11ed1c0cafe0b328dfdce5b1e67"
D_HEAD="4859abbdd7166ecab566ecc86337b56e0bd75125"
D_REPO="Ventusltd/kuiper-belt"
PINS={"kuiper_select.py":(D_REPO,D_HEAD,"tools/kuiper_select.py","409208484604ab88a94b377a009548f2a2b67964"),
 "tacit_b_bond_intake.py":(VEDIC,B_HEAD,"tools/tacit_b_bond_intake.py","d8e5639e00d0bb2dee42075bac23695ca4df3d27"),
 "factory/tools/package_factory.py":(VEDIC,"2ccc717933f97e7d191dae85360559a12de7ed21","tools/package_factory.py","23247de65fde04a400bb30874fc7e81cca4b7ebe"),
 "kuiper_bond.py":(VEDIC,T3,"packages/nearest-candidate/kuiper_bond.py","58bf06469a952b663459e9c2e277d93b51058dca"),
 "tacit_b_composition.py":(VEDIC,"b4108fd17686f05c13326efdfaa8fd29c893b532","tools/tacit_b_composition.py","a97a9c4297e45b6befbff1cc4130c395a831332a"),
 "spider_evidence.py":(VEDIC,T13,"tools/spider_evidence.py","9d46730b7346b6861a99b961b4ac70ef9e02b18b")}
def acquire(root):
    root.mkdir()
    for n,i in (("bonds",15138897783),("repair",15141151895),("b",15138544629)):download(root,n,i)
    for n,i in (("c-ranking",15138009925),("c-electrical",15140305069)):
        with (root/(n+".zip")).open("xb") as f:subprocess.run(["gh","api",f"repos/{C_REPO}/actions/artifacts/{i}/zip"],stdout=f,check=True,timeout=90)
    for path,info in PINS.items():
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);fetch(*info,dest)
    for p,b in MODULES.items():fetch(GRID,COMMIT,p,b,root/Path(p).name)
def raw_member(path,pin,name,digest):
    need(sha(path.read_bytes())==pin,"ZIP_PIN")
    with zipfile.ZipFile(path) as z:
        hits=[x for x in z.infolist() if x.filename==name or x.filename.endswith("/"+name)]
        need(len(hits)==1 and hits[0].file_size<=2_000_000,"MEMBER")
        raw=z.read(hits[0])
    need(sha(raw)==digest,"MEMBER_DIGEST:"+name)
    return raw
def occurrence(s):return tuple(s[k] for k in ("repo","commit","path","blob","first","last"))
def source_ref(r):return {"meaning_id":r["meaning_id"],"source":r["source"],"kuiper_key":r["kuiper"]["key"]}
def adapter(root,path,name):
    repo,commit,source_path,oid=PINS[path];raw=(root/path).read_bytes()
    need(blob(raw)==oid,"ADAPTER_PIN")
    matches=[x for x in ast.parse(raw).body if isinstance(x,ast.FunctionDef) and x.name==name]
    need(len(matches)==1,"ADAPTER_FUNCTION")
    x=matches[0]
    return {"repo":repo,"commit":commit,"path":source_path,"blob":oid,"sha256":sha(raw),"first":x.lineno,"last":x.end_lineno,"export":name,"kuiper_key":None,"state":"EXACT_ADAPTER_SOURCE_NOT_ADDRESS_ALLOCATED"}
def impact(m,event):
    # Bounded reverse traversal: source occurrence -> module -> static importing module -> patterns -> evidence.
    kind=event.get("kind")
    allowed={"source":{"kind","source","new_blob"},"closure":{"kind","family","old_sha256","new_sha256"},"property":{"kind","source","property","old_sha256","new_sha256"},"presentation":{"kind","source","field"}}
    need(kind in allowed and set(event)==allowed[kind],"EVENT_FIELDS")
    rows=m["source_entries"]
    if kind in ("source","property","presentation"):
        s=event["source"];matches=[r for r in rows if occurrence(r["source"])==occurrence(s)]
        need(len(matches)==1 and matches[0]["source"]==s,"UNKNOWN_OR_STALE_OCCURRENCE")
        r=matches[0]
    if kind=="presentation":
        need(event["field"] in ("display_colour","classification_description"),"NOT_PRESENTATION")
        return {"kind":kind,"affected_patterns":[],"affected_receipts":[],"addresses_changed":False,"state":"PRESENTATION_ONLY"}
    if kind=="source":
        new=event["new_blob"];need(isinstance(new,str) and len(new)==40 and all(c in "0123456789abcdef" for c in new),"NEW_BLOB")
        if new==s["blob"]:return {"kind":kind,"affected_patterns":[],"affected_receipts":[],"addresses_changed":False,"state":"UNCHANGED"}
        modules={s["path"]}
        # Only this observed static import is admitted to the dependency map, not Printer URLs.
        todo=list(modules)
        while todo:
            p=todo.pop()
            for e in m["module_dependencies"]:
                if e["target"]==p and e["source"] not in modules:
                    modules.add(e["source"]);todo.append(e["source"])
        affected=[p for p in m["patterns"] if any(x["source"]["path"] in modules for x in p["sources"])]
        why="SOURCE_PIN_CHANGED"
    elif kind=="closure":
        family=event["family"];need(family in m["family_reviews"],"UNKNOWN_FAMILY")
        need(event["old_sha256"]==m["family_reviews"][family]["closure_sha256"],"STALE_CLOSURE_EVENT")
        new=event["new_sha256"];need(isinstance(new,str) and len(new)==64 and all(c in "0123456789abcdef" for c in new),"NEW_CLOSURE_HASH")
        affected=[p for p in m["patterns"] if family in p["families"]] if new!=event["old_sha256"] else []
        why="CLOSURE_PIN_CHANGED"
    else:
        props=[p for p in m["properties"] if p["source_occurrence"]==s and p["property"]==event["property"]]
        need(len(props)==1,"UNKNOWN_PROPERTY")
        need(sha(canonical(props[0]))==event["old_sha256"],"STALE_PROPERTY_EVENT")
        new=event["new_sha256"];need(isinstance(new,str) and len(new)==64 and all(c in "0123456789abcdef" for c in new),"NEW_PROPERTY_HASH")
        affected=[p for p in m["patterns"] if any(x["source"]==s for x in p["sources"])] if new!=event["old_sha256"] else []
        why="PROPERTY_OVERLAY_CHANGED_REVIEW_SELECTION"
    receipts=sorted({d for p in affected for d in p["receipts"]})
    return {"kind":kind,"affected_patterns":sorted(p["operation"] for p in affected),"affected_receipts":[{"sha256":d,"state":"STALE_FOR_NEW_INPUT_HISTORICAL_PRESERVED"} for d in receipts],"addresses_changed":False,"state":why if affected else "UNCHANGED"}
def verify(root,out):
    b=member(root/"bonds.zip",BOND_ZIP,"bonds.json",BOND_SHA)
    repair=member(root/"repair.zip",REPAIR_ZIP,"repair.json",REPAIR_SHA)
    abc=member(root/"b.zip",B_ZIP,"tacit-b-abc-bonds.json",B_INTAKE)
    cr=member(root/"c-ranking.zip",C_RANK_ZIP,"ranking-review.json",C_RANK_SHA)
    ce=member(root/"c-electrical.zip",C_ELEC_ZIP,"sixth-review.json",C_ELEC_SHA)
    tests=[]
    def test(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except (ValueError,KeyError):tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    for path,info in PINS.items():need(blob((root/path).read_bytes())==info[-1],"PEER_PIN")
    test("repair rollback and cohort",repair["namespace_restored"] and repair["permanent_allocations"]==0 and len(repair["rows"])==8)
    test("independent execution states",cr["counts"]=={"PASS":33,"FAIL":0,"OPEN":1} and ce["counts"]=={"PASS":28,"FAIL":0,"OPEN":2} and not cr["formal_admission"] and not ce["formal_admission"])
    test("actual B intake original",abc["a_manifest_sha256"]==BOND_SHA and abc["c_review_sha256"]==C_SHA and abc["b_ranking_sha256"]==B_SHA and abc["b_electrical_sha256"]==B_ELECTRICAL)
    # Execute the original B v1 intake against exact original artifact; preserve member bytes.
    for n,d in (("tacit-b-ranking.json",B_SHA),("tacit-b-reviewed-intake.json","3bbc8f816deb978e338287ae4b33a365d3c1cb0f37a8d073dbd96eacc548fd41"),("tacit-b-electrical.json",B_ELECTRICAL)):
        (root/n).write_bytes(raw_member(root/"b.zip",B_ZIP,n,d))
    cmd=[sys.executable,str(root/"tacit_b_bond_intake.py"),"--factory",str(root/"factory"),"--archive",str(root/"bonds.zip"),"--ranking",str(root/"tacit-b-ranking.json"),"--review",str(root/"tacit-b-reviewed-intake.json"),"--electrical",str(root/"tacit-b-electrical.json"),"--out",str(root/"b-replay.json")]
    subprocess.run(cmd,check=True,timeout=30);test("original B consumer byte parity",sha((root/"b-replay.json").read_bytes())==B_INTAKE)
    sys.path.insert(0,str(root.resolve()))
    from kuiper_select import Space,load
    from spider_evidence import validate_named
    d=Space(load(root/"bonds.zip"))
    rows=b["source_entries"];by={int(r["meaning_id"][-6:]):r for r in rows}
    test("D original v1 exact cohort",len(d.by_key)==len(rows)==8 and len(b["properties"])==32)
    test("D VEDIC/predicate parity",tuple(sorted(k for i in (1,5) for k in d.select(meaning=by[i]["meaning_id"])))==d.select(module="Vg"))
    test("D unknown property parity",len(d.select(property_name="runtime_effects",state="UNKNOWN"))==8 and not d.select(property_name="runtime_effects",state="OBSERVED"))
    repair_by={r["meaning_id"]:r for r in repair["rows"]}
    for r in rows:
        source_guard(r["source"],(root/Path(r["source"]["path"]).name).read_bytes())
        test(r["meaning_id"]+" repair identity",identity(r)==identity(repair_by[r["meaning_id"]]))
    for p in b["properties"]:property_guard(p)
    graph=b["static_source_graph"];validate_named(graph["nodes"],graph["edges"])
    for e in graph["edges"]:relation_guard(e)
    imports=[x for x in graph["edges"] if x["type"]=="static_import"]
    test("single actual static module import",len(imports)==1 and imports[0]["from"]=="module:nearest" and imports[0]["to"]=="module:geodesy")
    moddeps=[{"source":"engine/v9-nearest-search.js","target":"engine/v9-geodesy.js","evidence":imports[0]}]
    refs=lambda *ids:[source_ref(by[i]) for i in ids]
    rank=json.loads((root/"tacit-b-ranking.json").read_bytes())["ranking"]
    selected_adapters=[adapter(root,"kuiper_bond.py","selected_location"),adapter(root,"tacit_b_composition.py","validate_selected_contract")]
    nodes={
      "nearestSubstation":{"sources":refs(15,16),"adapter":rank["source_pins"]["index.mjs"],"ports":b["nearest"]},
      "selected_location":{"sources":[],"adapters":selected_adapters,"ports":b["selected_location"]},
      "orient":{"sources":refs(1,5),"archive_sha256":b["orient"]["archive_sha256"],"ports":b["orient"]}}
    for i,n in ((24,"voltageDropVolts"),(25,"dropPercent"),(26,"lossesWatts"),(27,"annualLossKwh")):
        p=b["electrical"][n];nodes[n]={"sources":refs(i),"ports":{"inputs":p["input"],"outputs":p["output"]}}
    def edge(x):
        fo,fp=x["from"].split(".");to,tp=x["to"].split(".")
        need(fo in nodes and to in nodes,"MISSING_ENDPOINT")
        source=nodes[fo]["ports"]["outputs"][fp];target=nodes[to]["ports"]["inputs"][tp]
        family=("electrical",) if fo in b["electrical"] else ("nearest","orient")
        if (fo,to)==("lossesWatts","annualLossKwh"):
            need(source["unit"]==target["unit"]=="W" and source["quantity"]!=target["quantity"],"PEAK_CONTEXT")
            reason="Same W unit, different quantity; explicit peak model current and loss-load-factor required; not automatic compatibility"
        else:
            compatible(source,target);reason="Exact typed quantity/unit/CRS; caller constraints still required"
        need(x["type"]=="candidate_typed_data_bond","BOND_SCOPE")
        return {"from":x["from"],"to":x["to"],"direction":"source_output_to_target_input","source_endpoint":nodes[fo],"target_endpoint":nodes[to],
          "source_port":source,"target_port":target,"reason":reason,"required_data":x.get("conditions",x.get("condition")),
          "family_receipts":{f:{"source_sha256":b["family_reviews"][f]["source_sha256"],"closure_sha256":b["family_reviews"][f]["closure_sha256"]} for f in family},
          "relationship_state":"CONDITIONAL_CANDIDATE","review_state":"ORIGINAL_STATIC_CLOSURE_REVIEWED_NOT_RUNTIME_AUTHORITY","runtime_evidence_sha256":B_ELECTRICAL if family==("electrical",) else B_SHA,
          "independent_runtime_evidence_sha256":C_ELEC_SHA if family==("electrical",) else C_RANK_SHA,"formal_admission":"UNCHANGED"}
    edges=[edge(x) for x in b["typed_bonds"]]
    test("all five existing conditional bonds",len(edges)==5)
    reject("missing endpoint",lambda:edge({**b["typed_bonds"][0],"to":"fake.id"}))
    reject("runtime promotion",lambda:edge({**b["typed_bonds"][0],"type":"runtime_verified"}))
    for q in b["incompatible_bonds"]:reject(q["reason"],lambda q=q:compatible(q["from"],q["to"]))
    def pattern(op,ids,families,receipts):
        sources=refs(*ids)
        return {"operation":op,"keys":[str(k) for k in sorted(x["kuiper_key"] for x in sources)],"sources":sources,"families":families,"receipts":sorted(receipts),"state":"INTERNAL_ORIENT_EXISTING" if op=="orient" else "PRE_ADMISSION"}
    patterns=[pattern("orient",(1,5),["orient"],[b["orient"]["archive_sha256"],B_INTAKE,C_SHA]),pattern("nearest-orient",(1,5,15,16),["nearest","orient"],[B_SHA,B_INTAKE,C_RANK_SHA,BOND_SHA]),pattern("electrical",(24,25,26,27),["electrical"],[B_ELECTRICAL,B_INTAKE,C_ELEC_SHA,BOND_SHA])]
    test("D/B proposed envelope exact keys",patterns[0]["keys"]==[str(k) for k in d.select(module="Vg")] and patterns[1]["keys"]==[str(k) for k in sorted(d.select(module="Vg")+d.select(module="Vn"))] and patterns[2]["keys"]==[str(k) for k in d.select(module="Vd")])
    m={"schema":"vedic.tacit-a.bond-impact-sidecar.v1","base_manifest_sha256":BOND_SHA,"repair_sha256":REPAIR_SHA,"source_entries":rows,"properties":b["properties"],
      "family_reviews":b["family_reviews"],"module_dependencies":moddeps,"patterns":patterns,"bond_details":edges,"incompatible_bonds":b["incompatible_bonds"],
      "b_intake_sha256":B_INTAKE,"d_original_selection_head":D_HEAD,"c_independent_runtime_receipts":[C_RANK_SHA,C_ELEC_SHA],"authority":"EVIDENCE_ONLY","redistribution":"BLOCKED","live_consumer":False}
    s=by[1]["source"];event={"kind":"source","source":s,"new_blob":"0"*40}
    test("geodesy mutation impacts both geographical patterns",impact(m,event)["affected_patterns"]==["nearest-orient","orient"])
    test("nearest mutation only nearest pattern",impact(m,{**event,"source":by[15]["source"]})["affected_patterns"]==["nearest-orient"])
    test("electrical mutation isolated",impact(m,{**event,"source":by[24]["source"]})["affected_patterns"]==["electrical"])
    test("unchanged source not stale",impact(m,{**event,"new_blob":s["blob"]})["affected_patterns"]==[])
    reject("same blob wrong path",lambda:impact(m,{**event,"source":{**s,"path":"engine/elsewhere.js"}}))
    reject("wrong revision",lambda:impact(m,{**event,"source":{**s,"commit":"0"*40}}))
    closure={"kind":"closure","family":"orient","old_sha256":FAMILIES["orient"][1],"new_sha256":"0"*64}
    test("ORIENT closure propagates",impact(m,closure)["affected_patterns"]==["nearest-orient","orient"])
    reject("stale closure event",lambda:impact(m,{**closure,"old_sha256":"1"*64}))
    prop=next(p for p in b["properties"] if p["source_occurrence"]==s and p["property"]=="typed_ports")
    pe={"kind":"property","source":s,"property":"typed_ports","old_sha256":sha(canonical(prop)),"new_sha256":"0"*64}
    test("property overlay change flags dependent selection not key mutation",impact(m,pe)["affected_patterns"]==["nearest-orient","orient"] and not impact(m,pe)["addresses_changed"])
    reject("unknown property",lambda:impact(m,{**pe,"property":"invented"}))
    unknown=next(p for p in b["properties"] if p["state"]=="UNKNOWN");reject("unknown property promotion",lambda:property_guard({**unknown,"value":True}))
    for field in ("display_colour","classification_description"):
        test(field+" does not invalidate source",impact(m,{"kind":"presentation","source":s,"field":field})["affected_patterns"]==[])
    m["impact_examples"]=[{"event":ev,"result":impact(m,ev)} for ev in (event,closure,pe,{"kind":"presentation","source":s,"field":"display_colour"})]
    m["tests"]=tests
    out.write_bytes(canonical(m)+b"\n")
    print(json.dumps({"checks":len(tests),"bonds":len(edges),"patterns":len(patterns),"base_manifest_sha256":BOND_SHA,"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify","impact"]);p.add_argument("--root",type=Path);p.add_argument("--out",type=Path);p.add_argument("--manifest",type=Path);p.add_argument("--event",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    elif a.mode=="verify":verify(a.root,a.out)
    else:print(canonical(impact(json.loads(a.manifest.read_bytes()),json.loads(a.event.read_bytes()))).decode())
