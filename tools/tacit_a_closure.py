"""Bounded fourth-turn evidence adapter; reuses TACIT10 joins, 2b/4b parsers and Spider validator.
No identity allocation, source redistribution, execution or admission."""
import argparse, copy, hashlib, json, subprocess, sys, urllib.request, zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
VEDIC="Ventusltd/vedic-"
GRID="Ventusltd/ventus-grid-engine"
COMMIT="487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"
EDITION="0ee52af60036f32358759a67836578dce6d7da51"
T10="70d08339226f052f0da64fcb1b7d59f53286b58c"
T2="6a673d7a91adeeb3cc69de8d0d8814279abc764e"
T3="dd13013c5944ba94115f62f0eeac67c34956eb2c"
T4="1a153127baedcdc89776331dc6beb2967d07f791"
T13="558257cbb5b9bea8b3fc16df84da7de5d8e86222"
KUIPER="eec3f1891294af9e93ce6613c10cdf71806802f2"
MODULES={"engine/voltage-drop.js":"85f48ecf7effabb47973b0a056f90e82b8196ef2",
"engine/v9-nearest-search.js":"d2ab3b111eb09f7af3df3a9fce9ad0a9dc1dea99",
"engine/v9-geodesy.js":"14023f06d4ef2ea806437863bd35dee954c46b11"}
ARTIFACTS={"identity":(15126683549,"c4b7a4d582b56af8380ae33ab0c64782ec33b1e05c99d88af83a3b494eb4ead5"),
"electrical":(15135454118,"50b94809b3457b23ebac633853fe8ad810e89bd12299a28a78ac3ab11e9b1f52"),
"nearest":(15136093168,"6d429b182ab62030c3bb92437077f326672760cc7ac8d67f24537a40e3e3213a")}
DICT="327803457f1528803278959ad7c107caed76489cfb2263db7143973a151b3c96"
NAMES={1:"distanceKm",5:"initialBearingDeg",15:"index",16:"nearest",24:"voltageDropVolts",25:"dropPercent",26:"lossesWatts",27:"annualLossKwh"}
def need(ok,reason):
    if not ok: raise ValueError(reason)
def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def fetch(repo,commit,path,pin,dest):
    with urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}",timeout=30) as r: b=r.read(2_000_001)
    need(len(b)<=2_000_000 and blob(b)==pin,"GIT_BLOB_MISMATCH:"+path)
    dest.write_bytes(b)
def acquire(root):
    root.mkdir()
    for p,b in MODULES.items(): fetch(GRID,COMMIT,p,b,root/Path(p).name)
    for c,p,b,name in [
        (T10,"tools/identity_bridge.py","f3e6519aab67d2bc9fbc818318abca478ca2ef7e","identity_bridge.py"),
        (T2,"packages/electrical/source-parse.mjs","a3f4cb6a46a64e9f63f44860e1a4374496ca3121","electrical-parse.mjs"),
        (T4,"tools/tacit4b/seed/parse.mjs","74f14940b0e6e33825ed38bda1bc6e7e35b24821","seed-parse.mjs")]:
        fetch(VEDIC,c,p,b,root/name)
    fetch(VEDIC,T13,"tools/spider_evidence.py","9d46730b7346b6861a99b961b4ac70ef9e02b18b",root/"spider_evidence.py")
    for path,pin in (("tools/edition_keys.py","2a7144e76c3701372266a79c20ba8a5b6c940a1b"),
                     ("cosmos/wafer.tsv","54dafc60dbd38ce949c683a3ec21697255e58eb1"),
                     ("cosmos/repos.tsv","c456212d863b85848f5976278db61648b9cf0269")):
        dest=root/"producer"/path;dest.parent.mkdir(parents=True,exist_ok=True)
        fetch("Ventusltd/kuiper-belt",KUIPER,path,pin,dest)
    repo=root/"roots"/"ventus-grid-engine";repo.mkdir(parents=True)
    subprocess.run(["git","init","-q",str(repo)],check=True,timeout=30)
    subprocess.run(["git","-C",str(repo),"fetch","--depth=1","https://github.com/"+GRID+".git",COMMIT],check=True,timeout=90)
    need(subprocess.check_output(["git","-C",str(repo),"rev-parse","FETCH_HEAD"],text=True).strip()==COMMIT,"FETCHED_COMMIT")
    for name,(i,d) in ARTIFACTS.items():
        with (root/(name+".zip")).open("xb") as f:
            subprocess.run(["gh","api",f"repos/{VEDIC}/actions/artifacts/{i}/zip"],stdout=f,check=True,timeout=90)
        need(sha((root/(name+".zip")).read_bytes())==d,"ARTIFACT_DIGEST:"+name)
def member(root,archive,name):
    i,d=ARTIFACTS[archive]; raw=(root/(archive+".zip")).read_bytes()
    need(sha(raw)==d,"ARTIFACT_DIGEST:"+archive)
    with zipfile.ZipFile(root/(archive+".zip")) as z:
        hits=[x for x in z.infolist() if x.filename==name or x.filename.endswith("/"+name)]
        need(len(hits)==1 and hits[0].file_size<=20_000_000,"ARTIFACT_MEMBER:"+name)
        return z.read(hits[0])
def replay(root):
    sys.path.insert(0,str(root.resolve()))
    from identity_bridge import request
    raw=(BASE/"data/dictionary.json").read_bytes(); need(sha(raw)==DICT,"DICTIONARY_DIGEST")
    tr={x["id"]:x["source"] for x in json.loads((BASE/"data/translation-geodesy.json").read_text())["records"]}
    requests=[request(m.get("source") or tr[m["translation_ref"]],m["gg_id"]) for m in json.loads(raw)["entries"] if m["number"] in NAMES]
    need(len(requests)==len(NAMES),"REPLAY_COHORT")
    q=root/"fresh-requests.json";q.write_bytes(canonical(requests)+b"\n")
    subprocess.run([sys.executable,str(root/"producer/tools/edition_keys.py"),"--bodies",str(q),"--roots",str(root/"roots"),"--out",str(root/"fresh-producer.json")],check=True,timeout=120)
def normalized_producer(raw):
    """Remove only volatile execution metadata and source text, not identity fields."""
    data=json.loads(raw)
    for k in ("seconds","command"): data["summary"].pop(k,None)
    for body in data["bodies"]: body.pop("line_text",None)
    return canonical(data)
def project(result, out):
    """Review candidates only, deliberately not a reviewed factory schema."""
    family_ids={"electrical":{24,25,26,27},"nearest":{15,16,1},"orient":{1,5}}
    out.mkdir(exist_ok=False)
    manifest={}
    for family,ids in family_ids.items():
        rows=[r for r in result["entries"] if int(r["meaning_id"][-6:]) in ids]
        need(len(rows)==len(ids),"FAMILY_CENSUS")
        modules={r["source"]["path"]:{"blob":r["source"]["blob"],"sha256":r["module_sha256"]} for r in rows}
        receipt={"schema":"vedic.tacit-a.source-review-candidate.v1","family":family,
          "source_commit":COMMIT,"dictionary_commit":EDITION,"modules":modules,"entries":rows,
          "producer_commit":KUIPER,"producer_normalized_sha256":result["fresh_producer_normalized_sha256"],
          "candidate_state":"REFUSED_REVIEW_PENDING","identity_complete":False,"independent_acceptance":False,"rights":"BLOCKED"}
        if family=="electrical":
            closure={"static_imports":[],"internal_dependencies":result["electrical_internal_dependencies"],
              "typed_bonds":[{"from":"voltageDropVolts.value","to":"dropPercent.dropVolts","condition":"positive result and same phase/voltage basis"},
                {"from":"lossesWatts.value","to":"annualLossKwh.peakLossWatts","condition":"explicit peak current and loss-load-factor context"}]}
        elif family=="nearest":
            closure={"static_imports":[result["nearest_closure"]["static_import"]],"internal_dependencies":result["nearest_closure"]["calls"],
              "typed_bonds":result["nearest_typed_bond"]["edges"]}
        else:
            closure={"static_imports":[],"internal_dependencies":None,"typed_bonds":[],"note":"Existing ORIENT admission unchanged; no new authority"}
        closure.update(schema="vedic.tacit-a.closure-review-candidate.v1",family=family,modules=modules,
             source_commit=COMMIT,candidate_state="REFUSED_REVIEW_PENDING",execution_edges=[],runtime_verified=False,
             independent_acceptance=False,review_required="TACIT13")
        for kind,data in (("source",receipt),("closure",closure)):
            raw=canonical(data)+b"\n";name=family+"-"+kind+".json"
            (out/name).write_bytes(raw);manifest[name]=sha(raw)
    (out/"manifest.json").write_bytes(canonical({"schema":"vedic.tacit-a.family-review-manifest.v1",
      "files":manifest,"status":"CANDIDATE_ONLY","authority":"NO_ADMISSION","review_required":["TACIT10","TACIT13"]})+b"\n")
def verify(root,out):
    sys.path.insert(0,str(root.resolve()))
    from identity_bridge import kuiper_join
    from validate_graph import validate,validate_aliases
    from spider_evidence import validate_named
    read=lambda p:(root/Path(p).name).read_bytes()
    for p,b in MODULES.items(): need(blob(read(p))==b,"MODULE_BLOB:"+p)
    d=(BASE/"data/dictionary.json").read_bytes(); need(sha(d)==DICT,"DICTIONARY_DIGEST")
    dictionary=json.loads(d); trans=json.loads((BASE/"data/translation-geodesy.json").read_text())
    tr={x["id"]:x["source"] for x in trans["records"]}
    meanings={x["number"]:x for x in dictionary["entries"]}; need(len(meanings)==50,"DICTIONARY_CENSUS")
    raw=member(root,"identity","kuiper-producer.json"); producer=json.loads(raw)
    identity=json.loads(member(root,"identity","identity-bridge.json"))
    fresh_raw=(root/"fresh-producer.json").read_bytes(); fresh=json.loads(fresh_raw)
    need(identity["kuiper_producer_commit"]==KUIPER and sha((root/"producer/cosmos/wafer.tsv").read_bytes())==identity["kuiper_wafer_sha256"],"PRODUCER_WAFER_PIN")
    need(len(fresh["bodies"])==len(NAMES),"FRESH_REPLAY_COHORT")
    second_raw=(root/"fresh-producer-second.json").read_bytes()
    normalized=normalized_producer(fresh_raw)
    need(normalized==normalized_producer(second_raw),"FRESH_PRODUCER_NORMALIZED_PARITY")
    orient_raw=member(root,"identity","source-receipt/receipt.json")
    need(sha(orient_raw)=="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19","ORIENT_RECEIPT_DIGEST")
    orient=json.loads(orient_raw)
    need(orient["dictionary_commit"]==EDITION and orient["dictionary_sha256"]==DICT and sha(raw)==identity["kuiper_receipt_sha256"]==orient["kuiper_receipt_sha256"],"PRODUCER_RECEIPT_PIN")
    electrical=json.loads(member(root,"electrical","candidate-source-proof.json"))
    redacted=member(root,"electrical","kuiper-producer-redacted.json")
    need(sha(redacted)==electrical["redacted_producer_receipt_sha256"],"ELECTRICAL_RECEIPT_DIGEST")
    need(electrical["dictionary_commit"]==EDITION and electrical["dictionary_sha256"]==DICT and electrical["kuiper_producer_commit"]==identity["kuiper_producer_commit"],"ELECTRICAL_EDITION")
    er={x["meaning_id"]:x for x in electrical["components"]}
    nearest=json.loads(member(root,"nearest","tacit3b-kuiper-bond.json"))
    need(nearest["dictionary_commit"]==EDITION and nearest["producer_receipt_sha256"]==sha(raw),"NEAREST_EDITION")
    nr={x["gg_id"]:x for x in nearest["entries"]}
    ir={x["gg_id"]:x for x in identity["entries"]}; need(len(ir)==50,"IDENTITY_CENSUS")
    ep=json.loads((root/"electrical-parser.json").read_text())
    need(ep==json.loads(member(root,"electrical","parser.json")),"ELECTRICAL_PARSER_PARITY")
    gp=json.loads((root/"geodesy-parser.json").read_text()); np=json.loads((root/"nearest-parser.json").read_text())
    nested=json.loads((root/"nearest-closure.json").read_text())
    need(ep["imports"]==gp["imports"]==[] and np["imports"]==["./v9-geodesy.js"],"MISSING_OR_UNEXPECTED_DEPENDENCY")
    for p,parsed in (("engine/voltage-drop.js",ep),("engine/v9-geodesy.js",gp),("engine/v9-nearest-search.js",np)):
        need(parsed["module_sha256"]==sha(read(p)),"PARSER_SOURCE_DIGEST")
    need(nested["module_sha256"]==sha(read("engine/v9-nearest-search.js")),"NESTED_SOURCE_DIGEST")
    graph=json.loads((BASE/"data/nearest-spider.json").read_text())
    graph_counts=validate(graph,lambda repo,commit,path:read(path) if repo==GRID and commit==COMMIT else b"")
    validate_aliases(graph,trans)
    rows=[]; tests=["two fresh normalized producer replays match"]
    def check(name,condition): need(condition,name); tests.append(name)
    def reject(name,fn):
        try: fn()
        except ValueError: tests.append(name)
        else: raise AssertionError("EXPECTED_REFUSAL:"+name)
    for n,name in NAMES.items():
        m=meanings[n]; mid=m["gg_id"]; s=m.get("source") or tr[m["translation_ref"]]; r=ir[mid]
        check(mid+" occurrence",s==r["source"] and s["repo"]==GRID and s["commit"]==COMMIT and MODULES[s["path"]]==s["blob"])
        b=read(s["path"]); lines=b.splitlines(keepends=True)
        span=sha(b"".join(lines[s["first"]-1:s["last"]]))
        joined=kuiper_join(s,producer)
        check(mid+" producer",joined==r["kuiper"] and type(joined["key"]) is int)
        check(mid+" fresh producer parity",kuiper_join(s,fresh)==joined)
        if n>=24:
            peer=er[mid]; parser=ep["functions"][name]
            check(mid+" electrical peer",peer["kuiper"]==joined==kuiper_join(s,json.loads(redacted)) and peer["physical_span_sha256"]==span and all(peer["source"][k]==v for k,v in s.items()))
            check(mid+" typed peer",peer["typed_ports"]["meaning_id"]==mid)
            deps=parser["module_dependencies"]
        else:
            peer=nr[mid]
            check(mid+" geospatial peer",peer["kuiper"]==joined and peer["span_sha256"]==span and peer["source"]==s)
            parser=nested["nearest"] if n==16 else next(e for e in (np if n==15 else gp)["exports"] if e["name"]==name)
            deps=None
        check(mid+" formal span",(parser["first"],parser["last"])==(s["first"],s["last"]))
        stars=r["stars"]; check(mid+" Stars span",stars.get("span_sha256") in (None,span))
        rows.append({"meaning_id":mid,"word":m["word"],"function":name,"source":s,"physical_span_sha256":span,
          "module_sha256":sha(b),"formal_parser_span":parser,"kuiper":joined,"stars":stars,
          "classification":{"state":m["classification_state"],"periodic_block_candidate":m["periodic_block_candidate"],"vedic_class_candidate":m["vedic_class_candidate"]},
          "module_dependencies":deps,"typed_ports":peer.get("typed_ports"),"acceptance":"UNKNOWN_REVIEW_PENDING"})
    by_key={r["kuiper"]["key"]:r["meaning_id"] for r in rows}
    by_occ={tuple(r["source"][k] for k in ("repo","commit","path","blob","first","last")):r["meaning_id"] for r in rows}
    check("reverse joins",len(by_key)==len(by_occ)==len(rows)==8)
    for r in rows:
        s=r["source"]; check(r["meaning_id"]+" reverse",by_key[r["kuiper"]["key"]]==by_occ[tuple(s[k] for k in ("repo","commit","path","blob","first","last"))]==r["meaning_id"])
    s=rows[0]["source"]
    for field,value in (("commit","0"*40),("path","other.js"),("blob","0"*40)):
        check("wrong "+field,kuiper_join(dict(s,**{field:value}),producer)["key"] is None)
    missing=copy.deepcopy(producer); missing["bodies"]=[b for b in missing["bodies"] if b.get("key")!=rows[0]["kuiper"]["key"]]
    check("missing key",kuiper_join(s,missing)["key"] is None)
    def module_pin(b,p): need(blob(b)==MODULES[p],"MODULE_BLOB")
    reject("wrong digest",lambda:module_pin(read(s["path"])+b" ",s["path"]))
    def dependency(paths): need(set(paths)==set(MODULES),"MISSING_DEPENDENCY")
    dependency(MODULES); reject("missing dependency",lambda:dependency([s["path"]]))
    def compatible(a,b): need(a==b,"INCOMPATIBLE_TYPED_PORT")
    typed={r["function"]:r["typed_ports"] for r in rows if r["typed_ports"]}
    compatible(typed["voltageDropVolts"]["output"]["value"],{k:v for k,v in typed["dropPercent"]["input"]["dropVolts"].items() if k in ("quantity","unit")})
    reject("power not energy",lambda:compatible(typed["annualLossKwh"]["output"]["value"],typed["lossesWatts"]["output"]["value"]))
    reject("peak context not inferred",lambda:compatible(typed["lossesWatts"]["output"]["value"],{k:v for k,v in typed["annualLossKwh"]["input"]["peakLossWatts"].items() if k in ("quantity","unit")}))
    def admit(state): need(state=="INDEPENDENTLY_ACCEPTED","UNKNOWN_NOT_ADMITTED")
    reject("unknown cannot admit",lambda:admit("UNKNOWN"))
    # Reuse TACIT13's endpoint validator; source dependencies and semantic/typed bonds remain distinct.
    nodes=[{"id":"electrical:"+k} for k in sorted(set(ep["functions"])|set(ep["constants"]))]
    nodes += [{"id":n["id"]} for n in graph["nodes"]]
    nodes += [{"id":"module:nearest"},{"id":"module:geodesy"}]
    edges=[]
    for k,v in ep["functions"].items():
        for dep in v["module_dependencies"]:
            edges.append({"from":"electrical:"+k,"to":"electrical:"+dep,"type":"static_module_reference","source_sha256":ep["module_sha256"],"state":"STATIC_NOT_RUNTIME_TRACE"})
    for e in graph["edges"]:
        edges.append({"from":e["from"],"to":e["to"],"type":e["type"],"source_sha256":np["module_sha256"],"state":"STATIC_NOT_RUNTIME_TRACE"})
    edges.append({"from":"module:nearest","to":"module:geodesy","type":"static_import","source_sha256":np["module_sha256"],"state":"STATIC_NOT_RUNTIME_TRACE"})
    validate_named(nodes,edges); tests.append("TACIT13 endpoint validation")
    reject("dangling Spider edge",lambda:validate_named(nodes,edges+[{"from":"module:nearest","to":"missing","type":"static_import"}]))
    reject("duplicate Spider node",lambda:validate_named(nodes+[nodes[0]],edges))
    edge_types={"static_module_reference","calls","contains","static_import"}
    def validate_edge_types(es):
        need(all(e["type"] in edge_types and e["state"]=="STATIC_NOT_RUNTIME_TRACE" for e in es),"EDGE_AUTHORITY")
    validate_edge_types(edges); tests.append("source edge authority")
    reject("Printer reference not execution edge",lambda:validate_edge_types(edges+[dict(edges[0],type="reference")]))
    reject("static edge not runtime trace",lambda:validate_edge_types(edges+[dict(edges[0],state="EXECUTED")]))
    # Preserve 4b sidecar field names, no new identity or property semantics.
    properties=[]
    for r in rows:
        for prop,val,unit,method in (("module_sha256",r["module_sha256"],None,"sha256_exact_git_blob"),("formal_span_lines",r["source"]["last"]-r["source"]["first"]+1,"lines","acorn_physical_range")):
            properties.append({"source_occurrence":r["source"],"property":prop,"definition_version":"tacit-a-v1","value":val,"unit":unit,"method":method,"input_sha256":r["module_sha256"],"evidence_ref":"TACIT A candidate replay","state":"DERIVED","unknown_reason":None})
    result={"schema":"vedic.tacit-a-candidate-closure.v1","dictionary_commit":EDITION,"dictionary_sha256":DICT,
      "producer_commit":identity["kuiper_producer_commit"],"producer_receipt_sha256":sha(raw),"artifact_pins":ARTIFACTS,
      "entries":rows,"reverse_key_to_meaning":by_key,"properties":properties,"spider_graph_counts":graph_counts,
      "fresh_producer_normalized_sha256":sha(normalized),"fresh_pinned_producer_replay":True,
      "source_dependency_graph":{"nodes":nodes,"edges":edges,"validator_commit":T13,"execution_edges":[],"printer_relationship":"URL_REFERENCE_ONLY_NOT_EXECUTABLE","periodic_membership":"UNKNOWN"},
      "nearest_typed_bond":nearest["graph"],
      "nearest_closure":nested,"electrical_internal_dependencies":{k:v["module_dependencies"] for k,v in ep["functions"].items()},
      "closure_state":"BOUNDED_STATIC_SOURCE_ONLY","unresolved":["independent TACIT10 acceptance","independent TACIT13 acceptance","exact Periodic Table membership","unresolved Stars occurrences","dynamic runtime behavior not proven","rights conflict private/UNLICENSED vs root licence"],
      "rights":"BLOCKED","admission":"REFUSED_REVIEW_PENDING","wafer_replayed":False,"runtime_verified":False,
      "tests":tests,"test_count":len(tests)}
    out.write_bytes(canonical(result)+b"\n")
    project(result,out.with_suffix(".families"))
    out.with_suffix(".audit.json").write_bytes(canonical({"schema":"vedic.tacit-a.replay-audit.v1",
       "raw_receipt_sha256":[sha(fresh_raw),sha(second_raw)],"normalized_receipt_sha256":sha(normalized),
       "volatile_fields_excluded":["summary.seconds","summary.command","bodies[].line_text"]})+b"\n")
    print(json.dumps({"test_count":len(tests),"keys":by_key,"sha256":sha(out.read_bytes()),"admission":result["admission"]},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","replay","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    elif a.mode=="replay":replay(a.root)
    else:verify(a.root,a.out)
