"""Bounded VEDIC intent-to-plan consumer. No new maths, source allocator or public UI."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from stars_retrieval import Index, load_library, PRODUCER_BLOB, EXPECTED_COUNT, git_blob, require
from semantic_retrieval import curated_records

ORIENT = "GG2050-VEDIC-000006"
MEASURE = "GG2050-VEDIC-000001"
BEARING = "GG2050-VEDIC-000005"
BLOB = "14023f06d4ef2ea806437863bd35dee954c46b11"
REPO = "Ventusltd/ventus-grid-engine"
COMMIT = "487ec7bd38dfa5aecb1c75da53b4a866ab2101cb"
PATH = "engine/v9-geodesy.js"
SPECS = {MEASURE: ("distanceKm", 29, 47, "distance_km"),
         BEARING: ("initialBearingDeg", 133, 139, "initial_bearing_deg")}
# Deliberately bounded positive grammar. Novel vocabulary is reviewed, not executed.
import re
ALLOWED = set("calculate compute find measure determine tell show give me the a an and both initial "
              "distance bearing direction heading straight line great circle spherical between two "
              "points locations coordinates from to point of in kilometres kilometers km degrees "
              "please what is are how far apart their with geographic geographical".split())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, "duplicate JSON key")
            out[k] = v
        return out
    def bad_constant(s):
        raise ValueError("non-finite JSON number: " + s)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def propose(query, curated, compiled):
    require(isinstance(query, str) and 0 < len(query) <= 1024, "invalid instruction")
    words = set(re.findall(r"[a-z]+", query.lower()))
    distance = bool(words & {"distance", "far"})
    bearing = bool(words & {"bearing", "direction", "heading"})
    unknown = sorted(words - ALLOWED)
    requested = (["distance_km"] if distance else []) + (["initial_bearing_deg"] if bearing else [])
    c = curated.query(query, 10)
    p = compiled.query(query, 5)
    ids = [r["gg_id"] for r in c["results"]]
    # Explicit output contract, not a top-score execution trigger.
    admitted = distance and bearing and not unknown and ORIENT in ids and not re.search(r"[^a-zA-Z\s?,.\-]", query)
    state = "PLAN_PROPOSED" if admitted else "ABSTAIN"
    reasons = [] if admitted else ["outside bounded two-output coordinate intent or unsupported vocabulary"]
    return {"schema": "vedic.intent-proposal.v1", "instruction": query,
            "requested_outputs": requested, "unknown_words": unknown, "state": state,
            "reasons": reasons, "curated_ranked_ids": ids,
            "curated_candidates": c["results"], "compiled_candidates": p["results"],
            "candidate_id": ORIENT if admitted else None,
            "cross_cohort_scores_comparable": False, "probabilities_calibrated": False,
            "execution_authorized_by_ranking": False}


def coordinates(data):
    require(isinstance(data, dict) and set(data) == {"crs","unit","point_a","point_b"}, "invalid coordinate schema")
    require(data["crs"] == "WGS84" and data["unit"] == "degrees", "unsupported CRS/unit")
    pts = []
    for key in ("point_a","point_b"):
        pt = data[key]
        require(isinstance(pt,dict) and set(pt)=={"longitude","latitude"}, "named longitude/latitude required")
        lon,lat = pt["longitude"],pt["latitude"]
        require(type(lon) in (int,float) and type(lat) in (int,float), "numeric coordinates required")
        require(-180<=lon<=180 and -90<=lat<=90, "coordinate out of range")
        pts.append((lon,lat))
    (a,b),(c,d) = pts
    delta = abs((c-a+180)%360-180)
    eps=1e-9
    require(abs(b)<90-eps, "polar-origin heading undefined")
    require(not (delta<=eps and abs(b-d)<=eps), "coincident heading undefined")
    require(not (abs(delta-180)<=eps and abs(b+d)<=eps), "antipodal heading undefined")
    return [a,b,c,d]


def source_check(raw, receipt_raw, receipt_sha):
    require(sha(receipt_raw)==receipt_sha,"identity receipt digest mismatch")
    require(git_blob(raw)==BLOB,"source Git blob mismatch")
    receipt=strict_json(receipt_raw)
    require(receipt.get("composition")==ORIENT,"wrong composition receipt")
    entries=receipt.get("components",[])
    require(len(entries)==2 and {e.get("gg_id") for e in entries}==set(SPECS),"missing/duplicate component receipt")
    lines=raw.splitlines(keepends=True)
    results=[]
    for e in entries:
        mid=e["gg_id"]
        name,first,last,output=SPECS[mid]
        pin={"repo":REPO,"commit":COMMIT,"path":PATH,"blob":BLOB,"first":first,"last":last}
        require(e.get("source")==pin and e.get("git_blob_verified") is True,"source receipt pin mismatch")
        require(e.get("git_span_sha256")==sha(b"".join(lines[first-1:last])),"span digest mismatch")
        # Do not turn producer claims into a stronger proof; receipt is reported as supplied.
        results.append({"gg_id":mid,"export":name,"output":output,"source":pin,
                        "stars_reported":e.get("stars"),"kuiper_reported":e.get("kuiper")})
    return sorted(results,key=lambda x:x["gg_id"])


def plan(intent, data, source_records):
    require(intent.get("state")=="PLAN_PROPOSED" and intent.get("candidate_id")==ORIENT,"intent abstained")
    args=coordinates(data)
    require([x["gg_id"] for x in source_records]==[MEASURE,BEARING],"unverified node set")
    return {"schema":"vedic.orient-dag.v1","composition":ORIENT,"args":args,
            "inputs":{"crs":"WGS84","unit":"degrees","order":["lon_a","lat_a","lon_b","lat_b"]},
            "nodes":[{"id":r["gg_id"],"export":r["export"],"inputs":["lon_a","lat_a","lon_b","lat_b"],
                      "output":r["output"],"source":r["source"]} for r in source_records],
            "outputs":{"distance_km":"km","initial_bearing_deg":"degrees"},
            "dependencies":["EARTH_RADIUS_KM","DEG","Math"],"effects":"pure reviewed module",
            "tier":"GIT_SOURCE_VERIFIED_ONLY","permanent_identity_complete":False}


def execute(raw, graph, node="node"):
    require(git_blob(raw)==BLOB,"source changed before execution")
    require(graph.get("composition")==ORIENT and
            [(n["id"],n["export"],n["output"]) for n in graph["nodes"]]==
            [(MEASURE,"distanceKm","distance_km"),(BEARING,"initialBearingDeg","initial_bearing_deg")],
            "unadmitted DAG")
    # Static glue; original module imported from private temp directory.
    glue = """import {distanceKm, initialBearingDeg, EARTH_RADIUS_KM} from './geodesy.mjs';
const args = JSON.parse(process.argv[2]);
if (EARTH_RADIUS_KM !== 6378.137) throw Error('radius mismatch');
const distance_km = distanceKm(...args), initial_bearing_deg = initialBearingDeg(...args);
if (!Number.isFinite(distance_km) || !Number.isFinite(initial_bearing_deg)) throw Error('nonfinite output');
console.log(JSON.stringify({distance_km,initial_bearing_deg}));"""
    with tempfile.TemporaryDirectory(prefix="vedic-orient-") as tmp:
        p=Path(tmp)
        (p/"geodesy.mjs").write_bytes(raw)
        (p/"run.mjs").write_text(glue,encoding="utf-8")
        result=subprocess.run([node,"--no-addons",str(p/"run.mjs"),json.dumps(graph["args"],allow_nan=False)],
                              check=True,capture_output=True,text=True,timeout=10,cwd=tmp)
    out=strict_json(result.stdout)
    require(set(out)=={"distance_km","initial_bearing_deg"} and
            all(type(v) in (int,float) and math.isfinite(v) for v in out.values()) and
            out["distance_km"]>=0 and 0<=out["initial_bearing_deg"]<360,"invalid output")
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ("dictionary","translations","library","inputs","module","receipt","output"):
        p.add_argument("--"+arg,type=Path,required=True)
    p.add_argument("--receipt-sha",required=True)
    p.add_argument("--instruction",required=True)
    a=p.parse_args()
    d=strict_json(a.dictionary.read_bytes())
    t=strict_json(a.translations.read_bytes())
    cr=curated_records(d,t)
    pr=load_library(a.library.read_bytes(),PRODUCER_BLOB,EXPECTED_COUNT)
    intent=propose(a.instruction,Index(cr,prefer_coverage=True),Index(pr))
    result={"schema":"vedic.execution-receipt.v1","intent":intent,
            "curated_count":len(cr),"compiled_count":len(pr),"dictionary_sha256":sha(a.dictionary.read_bytes()),
            "identity_receipt_sha256":a.receipt_sha,"gridatlas_selection_verified":False,
            "independent_audit_verified":False,"permanent_identity_complete":False}
    if intent["state"]=="PLAN_PROPOSED":
        raw=a.module.read_bytes()
        sources=source_check(raw,a.receipt.read_bytes(),a.receipt_sha)
        data=strict_json(a.inputs.read_bytes())
        graph=plan(intent,data,sources)
        out=execute(raw,graph)
        result.update(state="EXECUTED_GIT_SOURCE_TIER",plan=graph,inputs=data,outputs=out,
                      source_records=sources,source_sha256=sha(raw),
                      node_version=subprocess.check_output(["node","--version"],text=True).strip())
    else:
        result["state"]="ABSTAIN"
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True,allow_nan=False);f.write("\n")
    print(json.dumps({k:result.get(k) for k in ("state","curated_count","compiled_count","outputs")}))


if __name__=="__main__":
    main()
