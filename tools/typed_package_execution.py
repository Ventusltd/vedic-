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

def main():
    p=argparse.ArgumentParser()
    for k in ("archive","receipt","request"): p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args()
    try:
        print(f.canonical(execute(f.strict(a.request.read_bytes()),a.archive.read_bytes(),f.strict(a.receipt.read_bytes()))).decode(),end="")
    except (ValueError,KeyError,OSError) as e:
        print(json.dumps({"state":"REFUSED","reason":str(e)}));raise SystemExit(1)
if __name__=="__main__":main()
