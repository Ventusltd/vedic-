"""Sixth-turn typed bond evidence adapter, not an execution or admission engine."""
import argparse,copy,json,subprocess
from pathlib import Path
from tacit_a_closure import canonical,sha,fetch,blob,need,GRID,COMMIT,MODULES,VEDIC
from tacit_a_stars import CANDIDATE_SHA,ZIP_SHA
from tacit_a_index_grain import member,FAMILIES,C_SHA
GRAIN_ZIP="cfc3470709f148e153672d56c69d7b4946d8fac56bc49e02767c5abcffbbb19c"
GRAIN_SHA="fde99809878734986324896b5f9a464c538b4e2bb318d2950c704fd3aa14014c"
B_HEAD="b4108fd17686f05c13326efdfaa8fd29c893b532"
B_ZIP="6c316fd5eda0b5df597049666244251339a306577a9145c0c997c3e1fe3d638b"
B_SHA="5c71125c76e2495f88d447f60f2f93d13f36198641e8bb4379964c45e7e2be51"
PORT_PIN="d90c557d09ce06564abab45718aeea21dd03c7b3"
ORIENT_PIN="68c4e6d7265202e4bc3f8109de78e578755686f1"
def download(root,name,id):
    with (root/(name+".zip")).open("xb") as f:
        subprocess.run(["gh","api",f"repos/{VEDIC}/actions/artifacts/{id}/zip"],stdout=f,check=True,timeout=90)
def acquire(root):
    root.mkdir()
    for name,id in (("candidate",15137841195),("grain",15138598845),("ranking",15138469041)):download(root,name,id)
    fetch(VEDIC,"6a673d7a91adeeb3cc69de8d0d8814279abc764e","packages/electrical/typed-ports.json",PORT_PIN,root/"ports.json")
    fetch(VEDIC,"2ccc717933f97e7d191dae85360559a12de7ed21","packages/factory/orient-execution.json",ORIENT_PIN,root/"orient.json")
def identity(row):
    return (row["meaning_id"],tuple(row["source"][k] for k in ("repo","commit","path","blob","first","last")),row["kuiper"]["key"])
def typed(quantity,unit,**meta):return {"quantity":quantity,"unit":unit,**meta}
def compatible(a,b):
    need(a.get("quantity")==b.get("quantity"),"QUANTITY_MISMATCH")
    need(a.get("unit")==b.get("unit"),"UNIT_MISMATCH")
    need(a.get("crs")==b.get("crs"),"CRS_MISMATCH")
def verify(root,out):
    a=member(root/"candidate.zip",ZIP_SHA,"candidate.json",CANDIDATE_SHA)
    grain=member(root/"grain.zip",GRAIN_ZIP,"index-grain.json",GRAIN_SHA)
    b=member(root/"ranking.zip",B_ZIP,"tacit-b-ranking.json",B_SHA)
    need(grain["candidate_sha256"]==CANDIDATE_SHA and grain["c_review_sha256"]==C_SHA,"REVIEW_CHAIN")
    ports_raw=(root/"ports.json").read_bytes();orient_raw=(root/"orient.json").read_bytes()
    need(blob(ports_raw)==PORT_PIN and blob(orient_raw)==ORIENT_PIN,"PORT_SOURCE_PIN")
    e=json.loads(ports_raw);o=json.loads(orient_raw)
    rows={r["function"]:r for r in a["entries"]};g={r["function"]:r for r in grain["entries"]}
    tests=[]
    def test(n,ok):need(ok,n);tests.append(n)
    def reject(n,fn):
        try:fn()
        except ValueError:tests.append(n)
        else:raise AssertionError("EXPECTED_REFUSAL:"+n)
    test("eight identities unchanged",len(rows)==len(g)==8 and all(identity(r)==identity(g[k]) for k,r in rows.items()))
    for f,(sd,cd) in FAMILIES.items():
        review=grain["reviewed_families"][f]
        test(f+" immutable reviewed source/closure",review["source_sha256"]==sd and review["closure_sha256"]==cd)
    for name,contract in e["functions"].items():test(name+" actual typed ports",rows[name]["typed_ports"]==contract)
    rank=b["ranking"]
    test("observed B pre-admission state",rank["state"]=="PRE_ADMISSION_PRODUCER_EXECUTED" and rank["admission"] is False and b["nearest_archive"] is None and b["factory_admission"]=="FAMILY_NOT_ADMITTED")
    for name in ("v9-nearest-search.js","v9-geodesy.js"):
        pin=rank["source_pins"][name]
        path="engine/"+name
        target=next(r for r in rows.values() if r["source"]["path"]==path)
        test(name+" B execution source pin",pin["repo"]==GRID and pin["commit"]==COMMIT and pin["path"]==path and pin["git_blob"]==MODULES[path] and pin["sha256"]==target["module_sha256"])
    test("B request digest",sha(canonical(rank["request"]))==rank["request_sha256"])
    test("B receipt digest",sha(canonical({k:v for k,v in rank.items() if k!="receipt_sha256"}))==rank["receipt_sha256"])
    test("actual typed state",rank["request"]["crs"]=="EPSG:4326" and rank["distance_unit"]=="km" and rank["threshold_unit"]=="kV" and o["ports"]=={"crs":"WGS84","unit":"degrees","distance":"km","bearing":"degrees"})
    point=typed("named_geographic_point","degrees",crs="WGS84",fields=["longitude","latitude"])
    nearest={"inputs":{"origin":typed("named_geographic_point","degrees",crs="EPSG:4326"),"records":typed("ordered_caller_substation_dataset","record",crs="EPSG:4326"),"minimumKv":typed("declared_voltage_threshold","kV")},
      "outputs":{"id":typed("selected_unique_record_id","id"),"distance_km":typed("spherical_geographical_distance","km")},
      "constraints":["actual pinned producer ranking receipt replay","stable exact-distance tie caller order","null result refuses composition","no capacity or route inference"]}
    lookup={"inputs":{"id":nearest["outputs"]["id"],"request":nearest["inputs"]["records"],"ranking_receipt":typed("replayed_producer_ranking_receipt","sha256")},
      "outputs":{"point_a":point,"point_b":point},"constraints":["unique ID in same ordered request","EPSG:4326 named lon/lat maps to WGS84 named lon/lat without projection","verify threshold, actual rank, receipt and source pins"]}
    orient={"inputs":{"point_a":point,"point_b":point},"outputs":{"distance_km":nearest["outputs"]["distance_km"],"initial_bearing_deg":typed("initial_geographical_bearing","degrees")},"archive_sha256":o["archive_sha256"],"constraints":["admitted ORIENT only","coincident/antipodal limitations"]}
    compatible(nearest["outputs"]["id"],lookup["inputs"]["id"]);tests.append("id bond")
    for k in ("point_a","point_b"):compatible(lookup["outputs"][k],orient["inputs"][k]);tests.append(k+" bond")
    functions=e["functions"]
    compatible(functions["voltageDropVolts"]["output"]["value"],functions["dropPercent"]["input"]["dropVolts"]);tests.append("voltage bond")
    refusals=[("distance is not route length",nearest["outputs"]["distance_km"],functions["voltageDropVolts"]["input"]["lengthM"]),
      ("energy is not power",functions["annualLossKwh"]["output"]["value"],functions["annualLossKwh"]["input"]["peakLossWatts"]),
      ("ordinary factor not loss factor",typed("ordinary_load_factor","1"),functions["annualLossKwh"]["input"]["lossLoadFactor"]),
      ("peak context cannot be inferred",functions["lossesWatts"]["output"]["value"],functions["annualLossKwh"]["input"]["peakLossWatts"]),
      ("same quantity wrong unit",typed("ac_voltage_drop","kV"),functions["dropPercent"]["input"]["dropVolts"]),
      ("wrong coordinate reference",typed("named_geographic_point","degrees",crs="EPSG:27700"),point)]
    for n,f,t in refusals:reject(n,lambda f=f,t=t:compatible(f,t))
    static=a["source_dependency_graph"]
    test("static graph remains static",static["execution_edges"]==[] and all(x["state"]=="STATIC_NOT_RUNTIME_TRACE" for x in static["edges"]))
    bonds=[{"from":"nearestSubstation.id","to":"selected_location.id","type":"candidate_typed_data_bond","conditions":lookup["constraints"]},
      {"from":"selected_location.point_a","to":"orient.point_a","type":"candidate_typed_data_bond","conditions":lookup["constraints"]},
      {"from":"selected_location.point_b","to":"orient.point_b","type":"candidate_typed_data_bond","conditions":lookup["constraints"]}]
    bonds += [{**x,"type":"candidate_typed_data_bond"} for x in e["relationships"]]
    props=[]
    def prop(r,k,val,unit,method,digest,state="DERIVED",reason=None):
        return {"source_occurrence":r["source"],"property":k,"definition_version":"tacit-a-bonds-v1","value":val,"unit":unit,"method":method,"input_sha256":digest,"evidence_ref":"source/closure candidate "+CANDIDATE_SHA,"state":state,"unknown_reason":reason}
    for name,r in rows.items():
        p=g[name]["producer_ast"]
        props += [prop(r,"producer_needs",p["needs"],None,"pinned Stars extractAny",GRAIN_SHA),prop(r,"producer_standalone",p["standalone"],None,"pinned Stars static analysis; not proof of runtime purity",GRAIN_SHA),prop(r,"runtime_effects",None,None,"no effect trace",CANDIDATE_SHA,"UNKNOWN","RUNTIME_EFFECT_TRACE_NOT_PROVEN"),prop(r,"typed_ports",functions[name] if name in functions else nearest if name in ("index","nearest") else orient,None,"pinned typed contracts",sha(ports_raw) if name in functions else B_SHA)]
        mutated=copy.deepcopy(r);mutated["classification"]={"symbol":"changed presentation"};mutated["properties"]=[props[-1]]
        test(name+" properties do not change occurrence",identity(mutated)==identity(r))
    test("ten-field property contract",all(len(x)==10 and x["state"] in ("OBSERVED","DERIVED","UNKNOWN") for x in props))
    report={"schema":"vedic.tacit-a.typed-bond-manifest.v1","source_candidate_sha256":CANDIDATE_SHA,"grain_sha256":GRAIN_SHA,"c_review_sha256":C_SHA,"b_ranking_sha256":B_SHA,"b_head":B_HEAD,
      "source_entries":[{"meaning_id":r["meaning_id"],"source":r["source"],"kuiper":r["kuiper"],"module_classification":g[k]["module_classification"]} for k,r in rows.items()],
      "family_reviews":grain["reviewed_families"],"nearest":nearest,"selected_location":lookup,"orient":orient,"electrical":functions,
      "static_source_graph":static,"typed_bonds":bonds,"incompatible_bonds":[{"reason":n,"from":f,"to":t} for n,f,t in refusals],
      "properties":props,"runtime_observation":{"state":"B_PRE_ADMISSION_EVIDENCE_NOT_INDEPENDENT_RUNTIME_ACCEPTANCE","ranking_receipt_sha256":rank["receipt_sha256"],"request_sha256":rank["request_sha256"],"result":rank["result"],"independent_acceptance":False},
      "dynamic_dependencies":"UNKNOWN_NO_GENERAL_RUNTIME_TRACE","admission":"UNCHANGED","redistribution":"BLOCKED","tests":tests}
    out.write_bytes(canonical(report)+b"\n")
    print(json.dumps({"checks":len(tests),"properties":len(props),"typed_bonds":len(bonds),"refusals":len(refusals),"sha256":sha(out.read_bytes())},sort_keys=True))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("mode",choices=["acquire","verify"]);p.add_argument("--root",type=Path,required=True);p.add_argument("--out",type=Path);a=p.parse_args()
    if a.mode=="acquire":acquire(a.root)
    else:verify(a.root,a.out)
