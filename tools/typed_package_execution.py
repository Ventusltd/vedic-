"""Bounded consumer of an exact admitted ORIENT archive, not an NLP engine."""
import argparse, io, json, math, os, subprocess, tempfile, zipfile
from pathlib import Path
import package_factory as f

ARCHIVE="e83937c040499a7060b03ca2c4969e4414cdca48cb7f28a3ef9039f002486787"
DESCRIPTOR="b45e61e955e0d0ddde15495f9be7c3fc4943c3193dd8f318a4249524f2fb5f53"
SCHEMA="vedic.typed-package-request.v1"
PORTS={"crs":"WGS84","unit":"degrees","distance":"km","bearing":"degrees"}

def request(q):
    f.keys(q,("schema","family","export","descriptor_sha256","archive_sha256","ports","input"))
    f.need(q["schema"]==SCHEMA,"REQUEST_SCHEMA")
    if q["family"]=="nearest-substation":
        raise f.Refusal("NEAREST_NOT_ADMITTED")
    f.need(q["family"]=="orient" and q["export"]=="orient","EXPORT_NOT_ADMITTED")
    f.need(q["descriptor_sha256"]==DESCRIPTOR and q["archive_sha256"]==ARCHIVE,"PATTERN_PIN")
    f.need(q["ports"]==PORTS,"PORT_MISMATCH")
    x=q["input"]
    f.keys(x,("crs","unit","point_a","point_b"))
    f.need(x["crs"]=="WGS84" and x["unit"]=="degrees","INPUT_UNITS")
    for p in (x["point_a"],x["point_b"]):
        f.keys(p,("longitude","latitude"))
        for k,b in (("longitude",180),("latitude",90)):
            v=p[k]
            f.need(type(v) in (float,int) and -b<=v<=b,"COORDINATE")
    return x

def execute(q,raw,receipt):
    x=request(q)
    f.need(f.sha(raw)==ARCHIVE,"ARCHIVE_PIN")
    f.need(receipt.get("schema")=="vedic.package-build-receipt.v1" and
           receipt.get("state")=="DEVELOPMENT_CHECKS_PASS" and
           receipt.get("archive_sha256")==ARCHIVE and
           receipt.get("descriptor_sha256")==DESCRIPTOR and
           receipt.get("archive_bytes")==len(raw) and
           receipt.get("reproducible") is True and receipt.get("redistribution")=="BLOCKED",
           "BUILD_RECEIPT")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        payload={i.filename:z.read(i) for i in z.infolist()}
    f.verify(raw,payload)
    m=f.strict(payload["manifest.json"])
    d=f.admit(m["descriptor"])
    f.need(f.sha(f.canonical(d))==DESCRIPTOR and m["descriptor_sha256"]==DESCRIPTOR
           and m["public_exports"]==["orient"] and m["input_pins"]==receipt.get("input_pins")
           and receipt.get("file_count")==len(payload),"MANIFEST_BINDING")
    with tempfile.TemporaryDirectory(prefix="vedic-typed-") as tmp:
        root=Path(tmp); package=root/"node_modules"/d["name"]; package.mkdir(parents=True)
        for k,v in payload.items(): (package/k).write_bytes(v)
        script="""import {orient} from '@ventus-internal/vedic-geodesy';
const x=JSON.parse(process.argv[2]);
console.log(JSON.stringify(orient(x)));
"""
        (root/"consumer.mjs").write_text(script,encoding="utf-8")
        try:
            out=f.strict(subprocess.check_output(["node","--no-addons","consumer.mjs",
                json.dumps(x,allow_nan=False)],cwd=root,text=True,timeout=20,
                env={"PATH":os.environ["PATH"]},stderr=subprocess.DEVNULL).encode())
        except subprocess.SubprocessError as e:
            raise f.Refusal("UPSTREAM_RESULT_REFUSED") from e
    f.keys(out,("distance_km","initial_bearing_deg"))
    f.need(type(out["distance_km"]) in (int,float) and math.isfinite(out["distance_km"])
           and out["distance_km"]>=0 and type(out["initial_bearing_deg"]) in (int,float)
           and 0<=out["initial_bearing_deg"]<360,"OUTPUT_PORT")
    # The exact admitted source receipt carries the producer identity evidence.
    # Do not assign new keys, conflate Git proof with wafer replay, or claim full Stars joins.
    sr=f.strict(payload["source-receipt.json"])
    pattern={"request":q,"descriptor_sha256":DESCRIPTOR,"archive_sha256":ARCHIVE,
             "source_receipt_sha256":f.sha(payload["source-receipt.json"]),"output":out,
             "identity_tier":sr["tier"],"independent_acceptance":False,"redistribution":"BLOCKED"}
    return {"state":"EXECUTED_ADMITTED_ORIENT_ONLY","pattern":pattern,
            "pattern_sha256":f.sha(f.canonical(pattern)),"nearest_composition":"NOT_ADMITTED"}

def from_peer_execution(peer):
    """TACIT8 v1 plan receipt adapter. Never treats ranking as authorisation."""
    f.need(peer.get("schema")=="vedic.execution-receipt.v1" and
           peer.get("state")=="EXECUTED_GIT_SOURCE_TIER","PEER_EXECUTION_STATE")
    intent=peer["intent"]
    f.need(intent.get("state")=="PLAN_PROPOSED" and
           intent.get("candidate_id")=="GG2050-VEDIC-000006" and
           intent.get("execution_authorized_by_ranking") is False,"PEER_INTENT")
    x=peer["inputs"]
    q={"schema":SCHEMA,"family":"orient","export":"orient",
       "descriptor_sha256":DESCRIPTOR,"archive_sha256":ARCHIVE,
       "ports":dict(PORTS),"input":x}
    request(q)
    args=[x[p][k] for p in ("point_a","point_b") for k in ("longitude","latitude")]
    source={"repo":"Ventusltd/ventus-grid-engine","commit":"487ec7bd38dfa5aecb1c75da53b4a866ab2101cb",
            "path":"engine/v9-geodesy.js","blob":"14023f06d4ef2ea806437863bd35dee954c46b11"}
    order=["lon_a","lat_a","lon_b","lat_b"]
    expected={"schema":"vedic.orient-dag.v1","composition":"GG2050-VEDIC-000006","args":args,
              "inputs":{"crs":"WGS84","unit":"degrees","order":order},
              "nodes":[{"id":mid,"export":export,"inputs":order,"output":out,
                        "source":{**source,"first":first,"last":last}}
                       for mid,export,out,first,last in [
                           ("GG2050-VEDIC-000001","distanceKm","distance_km",29,47),
                           ("GG2050-VEDIC-000005","initialBearingDeg","initial_bearing_deg",133,139)]],
              "outputs":{"distance_km":"km","initial_bearing_deg":"degrees"},
              "dependencies":["EARTH_RADIUS_KM","DEG","Math"],"effects":"pure reviewed module",
              "tier":"GIT_SOURCE_VERIFIED_ONLY","permanent_identity_complete":False}
    f.need(peer["plan"]==expected,"PEER_DAG_MISMATCH")
    f.need(peer.get("source_sha256")=="af9b5a8796b51a1e4368491b98961a197adec539f2fa0f3ed226552a876864bb",
           "PEER_SOURCE")
    return q

def execute_peer(peer_raw, raw, receipt):
    peer=f.strict(peer_raw)
    result=execute(from_peer_execution(peer),raw,receipt)
    out=result["pattern"]["output"]
    # Old Node22 source execution and current Node18 package may differ at
    # floating-point roundoff; compare explicit quantities with tolerance.
    f.keys(peer["outputs"],("distance_km","initial_bearing_deg"))
    f.need(all(type(peer["outputs"][k]) in (int,float) and
               abs(out[k]-peer["outputs"][k])<=1e-9 for k in out),"PEER_PARITY")
    result["pattern"]["peer_receipt_sha256"]=f.sha(peer_raw)
    result["pattern"]["peer_plan"]=peer["plan"]
    result["pattern_sha256"]=f.sha(f.canonical(result["pattern"]))
    result["peer_parity"]="MATCH_WITHIN_1E-9"
    return result

def main():
    p=argparse.ArgumentParser()
    for k in ("archive","receipt"): p.add_argument("--"+k,type=Path,required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument("--request",type=Path);source.add_argument("--peer-execution",type=Path)
    a=p.parse_args()
    try:
        raw=a.archive.read_bytes();receipt=f.strict(a.receipt.read_bytes())
        result=execute_peer(a.peer_execution.read_bytes(),raw,receipt) if a.peer_execution else execute(f.strict(a.request.read_bytes()),raw,receipt)
        print(f.canonical(result).decode(),end="")
    except (ValueError,KeyError,OSError) as e:
        print(json.dumps({"state":"REFUSED","reason":str(e)}));raise SystemExit(1)
if __name__=="__main__":main()
