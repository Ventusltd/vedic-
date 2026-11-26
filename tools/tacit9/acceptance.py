"""Independent TACIT 9 reference tests; not the TACIT 8 execution engine.

Run: python tools/tacit9/acceptance.py --source /path/to/pinned/v9-geodesy.js
Optional --rankings is an independently exported JSON list of query results.
Synthetic manual coordinates only; no GridAtlas runtime or Stars identity claim.
"""
import argparse
import copy
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path

PIN = {
    "repo": "Ventusltd/ventus-grid-engine",
    "commit": "487ec7bd38dfa5aecb1c75da53b4a866ab2101cb",
    "path": "engine/v9-geodesy.js",
    "blob": "14023f06d4ef2ea806437863bd35dee954c46b11",
}
EXPORTS = {"GG2050-VEDIC-000001": "distanceKm", "GG2050-VEDIC-000005": "initialBearingDeg"}
SPANS = {"distanceKm": [29, 47], "initialBearingDeg": [133, 139]}
DEPS = {"distanceKm": ["DEG", "EARTH_RADIUS_KM"], "initialBearingDeg": ["DEG"]}
R = 6378.137
EPS = 1e-12
FIXTURE = Path(__file__).with_name("heldout_queries.json")

def require(ok, why):
    if not ok:
        raise ValueError(why)

def sha256(raw):
    return hashlib.sha256(raw).hexdigest()

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def point(lon, lat):
    return {"longitude": lon, "latitude": lat}

def pair(a, b):
    return {"crs": "WGS84", "unit": "degree", "origin": point(*a), "destination": point(*b)}

def validate_inputs(x):
    require(isinstance(x, dict) and set(x) == {"crs", "unit", "origin", "destination"}, "input fields")
    require(x["crs"] == "WGS84" and x["unit"] == "degree", "unsupported CRS or unit")
    coords = []
    for p in (x["origin"], x["destination"]):
        require(isinstance(p, dict) and set(p) == {"longitude", "latitude"}, "named coordinates required")
        lon, lat = p["longitude"], p["latitude"]
        require(all(type(v) in (int, float) and math.isfinite(v) for v in (lon, lat)), "finite numeric coordinates")
        require(-180 <= lon <= 180 and -90 <= lat <= 90, "coordinate range")
        coords.append((lon, lat))
    return coords

def dot(a, b):
    return sum(x*y for x,y in zip(a,b))

def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

def vector(lon, lat):
    l, p = map(math.radians, (lon, lat))
    return (math.cos(p)*math.cos(l), math.cos(p)*math.sin(l), math.sin(p))

def oracle(x):
    """Independent vector angle and tangent projection, not haversine."""
    (lon,lat), (lon2,lat2) = validate_inputs(x)
    p,q = vector(lon,lat),vector(lon2,lat2)
    angle = math.atan2(math.hypot(*cross(p,q)), dot(p,q))
    require(EPS < angle < math.pi-EPS, "coincident or antipodal bearing undefined")
    require(abs(lat) < 90, "polar origin heading undefined")
    l,t = map(math.radians, (lon,lat))
    east = (-math.sin(l), math.cos(l), 0)
    north = (-math.sin(t)*math.cos(l), -math.sin(t)*math.sin(l), math.cos(t))
    return {"distance_km":R*angle, "initial_bearing_deg":math.degrees(math.atan2(dot(q,east),dot(q,north)))%360}

CASES = [
    ("equator-east", pair((0,0),(1,0))),
    ("equator-north", pair((0,0),(0,1))),
    ("equator-west", pair((1,0),(0,0))),
    ("latitude-60", pair((0,60),(1,60))),
    ("latitude-60-reverse", pair((1,60),(0,60))),
    ("dateline-east", pair((179,0),(-179,0))),
    ("dateline-west", pair((-179,0),(179,0))),
    ("southern-oblique", pair((12,-31),(26,-25))),
    ("short-separation", pair((-0.1,51.5),(-0.10001,51.50002))),
    ("long-oblique", pair((-73,40),(151,-33))),
    ("near-antipodal", pair((0,0),(179.99,0.01))),
]
def negative_inputs():
    good = pair((0,0),(1,1))
    yield "coincident", pair((0,0),(0,0))
    yield "dateline-coincident", pair((-180,0),(180,0))
    yield "antipodal", pair((0,0),(180,0))
    yield "polar-origin", pair((10,90),(1,1))
    for label,value in [("string","1"),("null",None),("boolean",True),("nan",float("nan")),("inf",float("inf")),("lon-range",181)]:
        x=copy.deepcopy(good); x["origin"]["longitude"]=value; yield label,x
    x=copy.deepcopy(good); x["origin"]["latitude"]=91; yield "lat-range",x
    x=copy.deepcopy(good); del x["origin"]["latitude"]; yield "missing-port",x
    x=copy.deepcopy(good); x["origin"]=[0,1]; yield "unlabelled-pair",x
    x=copy.deepcopy(good); x["origin"]={"lat":0,"lon":1}; yield "wrong-labels",x
    yield "wrong-unit",dict(good,unit="radian")
    yield "wrong-crs",dict(good,crs="EPSG:27700")
    yield "stale-selection",dict(good,selection_revision="old")
    yield "missing-destination",{k:v for k,v in good.items() if k!="destination"}

def reference_receipt(raw):
    """Audit-side synthetic receipt, not a producer Kuiper/Stars receipt."""
    return {"source":dict(PIN), "module_sha256":sha256(raw), "exports":dict(EXPORTS),
            "spans":copy.deepcopy(SPANS), "dependencies":copy.deepcopy(DEPS),
            "stars_state":"OCCURRENCE_NOT_INDEXED", "identity_complete":False}

def validate_receipt(r, raw, expected_digest):
    require(sha256(canonical(r)) == expected_digest, "receipt digest mismatch")
    require(r["source"] == PIN and blob(raw) == PIN["blob"], "wrong pinned Git source")
    require(r["module_sha256"] == sha256(raw), "module digest mismatch")
    require(r["exports"] == EXPORTS and r["spans"] == SPANS and r["dependencies"] == DEPS, "export/span/dependency mismatch")
    require(r["stars_state"] == "OCCURRENCE_NOT_INDEXED" and r["identity_complete"] is False, "unproven permanent identity")

def reference_plan():
    return {"tier":"GIT_SOURCE_VERIFIED_ONLY", "nodes":[
        {"id":"inputs","deps":[]},
        {"id":"measure","deps":["inputs"],"export":"distanceKm","unit":"km"},
        {"id":"bearing","deps":["inputs"],"export":"initialBearingDeg","unit":"degree"},
        {"id":"output","deps":["measure","bearing"]}]}

def validate_plan(plan):
    """Strict audit-side expected graph, deliberately not peer implementation."""
    require(plan == reference_plan(), "unexpected plan, dependencies, port, unit, tier or cycle")

def refuse(fn, *args):
    try:
        fn(*args)
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError("mutation unexpectedly accepted")

def execute_source(raw, cases):
    require(blob(raw)==PIN["blob"], "refuse unpinned source before Node import")
    # Only the exact approved pure module is imported; no arbitrary source or user JS.
    runner = """import {distanceKm, initialBearingDeg} from './pinned.mjs';
import fs from 'node:fs';
const inputs=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(inputs.map(a=>({distance_km:distanceKm(...a),initial_bearing_deg:initialBearingDeg(...a)}))));
"""
    with tempfile.TemporaryDirectory() as td:
        d=Path(td)
        (d/"pinned.mjs").write_bytes(raw)
        (d/"run.mjs").write_text(runner,encoding="utf-8")
        args=[sum((list(p) for p in validate_inputs(x)),[]) for _,x in cases]
        result=subprocess.run(["node",str(d/"run.mjs")],input=json.dumps(args),text=True,
                              capture_output=True,check=True,timeout=20,cwd=d)
        return json.loads(result.stdout)

def close_result(actual, expected):
    require(set(actual)==set(expected), "output fields")
    require(all(type(v) in (float,int) and math.isfinite(v) for v in actual.values()), "nonfinite output")
    # 1e-6 km (~1 mm) allows expected floating point loss near antipodes.
    require(abs(actual["distance_km"]-expected["distance_km"])<=1e-6, "distance tolerance")
    error=abs((actual["initial_bearing_deg"]-expected["initial_bearing_deg"]+180)%360-180)
    require(error<=1e-7, "bearing tolerance")

def score_rankings(path):
    """Optional adapter: each row {id, ranked_ids, executed_ids, abstained}.
    A negative can rank related words but may not execute geodesy.
    """
    fixtures=json.loads(FIXTURE.read_bytes())["cases"]
    rows=json.loads(Path(path).read_bytes())
    observed={r["id"]:r for r in rows}
    require(len(rows)==len(observed) and set(observed)=={f["id"] for f in fixtures}, "query coverage mismatch")
    totals={k:0 for k in (1,3,5)}
    n=0; unsafe=[]; ambiguity=[]; wrong_selection=[]; abstentions=0
    for f in fixtures:
        r=observed[f["id"]]
        ranks=r["ranked_ids"]; executed=r["executed_ids"]
        require(type(r["abstained"]) is bool and isinstance(ranks,list) and isinstance(executed,list), "result schema")
        abstentions+=r["abstained"]
        if f["expect"]=="NO_GEODESY_EXECUTION" and set(executed)&{"GG2050-VEDIC-000001","GG2050-VEDIC-000005","GG2050-VEDIC-000006"}:
            unsafe.append(f["id"])
        if f["expect"]=="AMBIGUOUS" and (not r["abstained"] or executed):
            ambiguity.append(f["id"])
        if f.get("top") and f["expect"]!="AMBIGUOUS":
            n+=1
            for k in totals:
                totals[k]+=bool(set(ranks[:k])&set(f["top"]))
            if executed and not set(executed)<=set(f["top"]):
                wrong_selection.append(f["id"])
    return {"labelled":n,"top_k":totals,"all_queries":len(fixtures),"abstentions":abstentions,
            "unsafe_negative_execution":unsafe,"ambiguity_failure":ambiguity,"wrong_selection":wrong_selection}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--rankings",type=Path)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    raw=a.source.read_bytes()
    r=reference_receipt(raw); digest=sha256(canonical(r))
    validate_receipt(r,raw,digest)
    mutations=[]
    for field,value in [("repo","other/repo"),("commit","0"*40),("path","engine/wrong.js"),("blob","0"*40)]:
        m=copy.deepcopy(r);m["source"][field]=value
        refuse(validate_receipt,m,raw,sha256(canonical(m))); mutations.append(field)
    for field,value in [("module_sha256","0"*64),("exports",{}),("spans",{"distanceKm":[29,139]}),
                        ("dependencies",{}),("identity_complete",True),("stars_state","VERIFIED")]:
        m=copy.deepcopy(r);m[field]=value
        refuse(validate_receipt,m,raw,sha256(canonical(m))); mutations.append(field)
    refuse(validate_receipt,r,raw+b"\n",digest);mutations.append("changed_module_bytes")
    refuse(validate_receipt,r,raw,"0"*64);mutations.append("receipt_digest")
    plan=reference_plan();validate_plan(plan)
    for label,change in [
        ("cycle",lambda p:p["nodes"][0]["deps"].append("output")),
        ("missing_dependency",lambda p:p["nodes"][1].update(deps=[])),
        ("wrong_export",lambda p:p["nodes"][2].update(export="unknown")),
        ("wrong_output_unit",lambda p:p["nodes"][1].update(unit="m")),
        ("missing_port",lambda p:p["nodes"].pop(2)),
        ("false_full_tier",lambda p:p.update(tier="PERMANENT_IDENTITY_COMPLETE")),
        ("duplicate_node",lambda p:p["nodes"].append(p["nodes"][1]))]:
        m=copy.deepcopy(plan);change(m);refuse(validate_plan,m);mutations.append(label)
    negatives=[]
    for label,x in negative_inputs():
        refuse(oracle,x);negatives.append(label)
    actual=execute_source(raw,CASES)
    require(len(actual)==len(CASES),"output count")
    measurements=[]
    for (label,x),out in zip(CASES,actual):
        expected=oracle(x);close_result(out,expected)
        measurements.append({"case":label,"input":x,"oracle":expected,"original_module":out})
    # Valid numeric axis swaps cannot be detected through bounds alone.
    x=oracle(pair((0,60),(1,60))); y=oracle(pair((60,0),(60,1)))
    require(abs(x["distance_km"]-y["distance_km"])>50,"axis swap discriminator")
    report={"schema":"tacit9.audit.v1","source":PIN,"module_sha256":sha256(raw),
            "query_fixture_sha256":sha256(FIXTURE.read_bytes()),"query_fixture_count":len(json.loads(FIXTURE.read_bytes())["cases"]),
            "numeric_original_module_pass":len(measurements),"measurements":measurements,
            "audit_reference_input_rejections":negatives,"audit_reference_mutation_rejections":mutations,
            "peer_intent":"NOT_TESTED","peer_graph_and_execution":"NOT_TESTED",
            "stars_occurrence_identity":"UNRESOLVED","live_selection":"NOT_TESTED",
            "verdict":"PINNED_SOURCE_NUMERICAL_PARITY_ONLY"}
    if a.rankings:
        report["peer_query_metrics"]=score_rankings(a.rankings)
    a.report.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="measurements"},indent=2))
    if a.rankings:
        m=report["peer_query_metrics"]
        require(not (m["unsafe_negative_execution"] or m["ambiguity_failure"] or m["wrong_selection"]),"peer selection safety failed")

if __name__=="__main__":
    main()
