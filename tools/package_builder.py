"""Build and verify one private VEDIC package from exact producer evidence."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile

MODULE_SHA = "af9b5a8796b51a1e4368491b98961a197adec539f2fa0f3ed226552a876864bb"
MODULE_BLOB = "14023f06d4ef2ea806437863bd35dee954c46b11"
RECEIPT_SHA = "83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19"
LICENSE_BLOB = "d645695673349e3947e8e5ae42332d0ac3164cd7"
SOURCE = {"repo":"Ventusltd/ventus-grid-engine","commit":"487ec7bd38dfa5aecb1c75da53b4a866ab2101cb","path":"engine/v9-geodesy.js","blob":MODULE_BLOB}
PACKAGE = "@ventus-internal/vedic-geodesy"
VERSION = "0.1.0"
EDITION = "0ee52af60036f32358759a67836578dce6d7da51"

# Thin JS package interface implements TACIT8's named-coordinate contract.
# All numerical geometry is executed by the unchanged source module.
ADAPTER = """import {distanceKm, initialBearingDeg, EARTH_RADIUS_KM} from './v9-geodesy.mjs';
function exact(obj, keys) {
  return obj !== null && typeof obj === 'object' && !Array.isArray(obj) &&
    Object.keys(obj).length === keys.length && keys.every(k => Object.hasOwn(obj,k));
}
export function orient(input) {
  if (!exact(input,['crs','unit','point_a','point_b']) ||
      input.crs !== 'WGS84' || input.unit !== 'degrees') throw new TypeError('WGS84 degrees required');
  const args = [];
  for (const p of [input.point_a,input.point_b]) {
    if (!exact(p,['longitude','latitude']) || !Number.isFinite(p.longitude) ||
        !Number.isFinite(p.latitude) || Math.abs(p.longitude)>180 ||
        Math.abs(p.latitude)>90) throw new RangeError('invalid named coordinates');
    args.push(p.longitude,p.latitude);
  }
  const [a,b,c,d] = args, eps=1e-9;
  const delta = Math.abs(((c-a+180)%360+360)%360-180);
  if (Math.abs(b)>=90-eps || (delta<=eps && Math.abs(b-d)<=eps) ||
      (Math.abs(delta-180)<=eps && Math.abs(b+d)<=eps)) throw new RangeError('undefined initial bearing');
  if (EARTH_RADIUS_KM!==6378.137) throw new Error('radius mismatch');
  const distance_km=distanceKm(...args), initial_bearing_deg=initialBearingDeg(...args);
  if (!Number.isFinite(distance_km) || distance_km<0 || !Number.isFinite(initial_bearing_deg) ||
      initial_bearing_deg<0 || initial_bearing_deg>=360) throw new RangeError('invalid source output');
  return {distance_km,initial_bearing_deg};
}
"""
README = """# VEDIC Geodesy — internal research package 0.1.0

Offline Node >=18 ES module, no runtime dependencies. Extract the ZIP into
node_modules/@ventus-internal/vedic-geodesy in a clean project. Import:

    import {orient} from '@ventus-internal/vedic-geodesy';
    console.log(orient({crs:'WGS84',unit:'degrees',
      point_a:{longitude:0,latitude:0},point_b:{longitude:1,latitude:0}}));

Expected: distance_km approximately 111.31949079327356; initial_bearing_deg 90.
Spherical great-circle distance, not cable or road length. Coincident,
antipodal and polar-origin headings are refused (1e-9 degree tolerance).
Coordinate labels cannot prove that valid numbers were not accidentally swapped.

Original Grid Engine module retained byte for byte. Only orient is admitted
through the package export map; other original functions are not package claims.
Source receipt is evidence of Git recovery, not independent runtime acceptance.
Permanent Modular Star occurrence unresolved. Root Apache-2.0 licence retained
for provenance, but producer manifest is private/UNLICENSED. Redistribution
and npm/public release are blocked pending owner/licence review.
"""
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def blob(raw):
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def require(ok, msg):
    if not ok:
        raise ValueError(msg)

def encoded(obj):
    return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()

def inputs(module,receipt,licence):
    require(sha(module)==MODULE_SHA and blob(module)==MODULE_BLOB,"source pin mismatch")
    require(sha(receipt)==RECEIPT_SHA,"externally pinned receipt mismatch")
    require(blob(licence)==LICENSE_BLOB,"licence provenance mismatch")
    r=json.loads(receipt)
    require(r["schema"]=="vedic.orient-module-receipt.v1" and r["source"]==SOURCE and
        r["module_sha256"]==MODULE_SHA and r["dictionary_commit"]==EDITION and
        r["composition"]=="GG2050-VEDIC-000006" and r["identity_complete"] is False and
        r["execution_verified"] is False and r["tier"]=="GIT_SOURCE_VERIFIED_STARS_INCOMPLETE",
        "unexpected producer receipt")
    require(sorted((e["gg_id"],e["export"]) for e in r["components"])==
        [("GG2050-VEDIC-000001","distanceKm"),("GG2050-VEDIC-000005","initialBearingDeg")],
        "unexpected source exports")
    return r

def files(module,receipt,licence):
    r=inputs(module,receipt,licence)
    payload={"package.json":encoded({"name":PACKAGE,"version":VERSION,"type":"module",
        "private":True,"license":"UNLICENSED","engines":{"node":">=18"},
        "exports":{".":"./index.mjs"},"dependencies":{}}),
        "index.mjs":ADAPTER.encode(),"v9-geodesy.mjs":module,
        "source-receipt.json":receipt,"README.md":README.encode(),"UPSTREAM-LICENSE":licence}
    manifest={"schema":"vedic.package-manifest.v1","name":PACKAGE,"version":VERSION,
        "source":SOURCE,"source_sha256":MODULE_SHA,"receipt_sha256":RECEIPT_SHA,
        "dictionary_commit":EDITION,"identity_tier":r["tier"],
        "identity_complete":False,"independent_acceptance":False,"redistribution":"BLOCKED",
        "public_exports":["orient"],"runtime":"Node >=18","runtime_dependencies":[],
        "input":{"crs":"WGS84","unit":"degrees","points":["point_a","point_b"],
        "fields":["longitude","latitude"]},
        "outputs":{"distance_km":"km","initial_bearing_deg":"degrees"},
        "vedic_ids":["GG2050-VEDIC-000006","GG2050-VEDIC-000001","GG2050-VEDIC-000005"],
        "build_command":"python tools/package_builder.py --module MODULE --receipt RECEIPT --licence LICENSE --out ARCHIVE",
        "obligations":["independent package acceptance","exact Stars occurrence","licence scope"],
        "files":{k:sha(v) for k,v in sorted(payload.items())}}
    payload["manifest.json"]=encoded(manifest)
    return payload

def archive(payload):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_STORED) as z:
        for name,raw in sorted(payload.items()):
            i=zipfile.ZipInfo(name,(1980,1,1,0,0,0))
            i.create_system=3
            i.external_attr=0o100644<<16
            z.writestr(i,raw)
    return buf.getvalue()

def verify(raw,expected):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(z.namelist()==sorted(expected),"unexpected/duplicate archive entries")
        for name,content in expected.items():
            require(z.read(name)==content,"archive bytes mismatch: "+name)
        m=json.loads(z.read("manifest.json"))
        require(m["files"]=={k:sha(v) for k,v in expected.items() if k!="manifest.json"},
            "manifest file digest mismatch")

def runtime(raw,expected):
    verify(raw,expected)
    with tempfile.TemporaryDirectory(prefix="vedic-package-consumer-") as tmp:
        root=Path(tmp)
        package=root/"node_modules"/PACKAGE
        package.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in expected:
                (package/name).write_bytes(z.read(name))
        script=root/"consumer.mjs"
        script.write_text("""import assert from 'node:assert/strict';
import * as api from '@ventus-internal/vedic-geodesy';
assert.deepEqual(Object.keys(api),['orient']);
const point=(longitude,latitude)=>({longitude,latitude});
const input=(a,b)=>({crs:'WGS84',unit:'degrees',point_a:a,point_b:b});
const a=api.orient(input(point(0,0),point(1,0)));
assert.ok(Math.abs(a.distance_km-111.31949079327356)<1e-9);
assert.equal(a.initial_bearing_deg,90);
const reverse=api.orient(input(point(1,0),point(0,0)));
assert.equal(reverse.initial_bearing_deg,270);
assert.ok(Math.abs(reverse.distance_km-a.distance_km)<1e-9);
for (const bad of [null,{},input(point(0,0),point(0,0)),input(point(0,0),point(180,0)),
 input(point(0,90),point(1,0)),input(point(181,0),point(0,0)),
 input(point(NaN,0),point(0,0)),input(point('0',0),point(1,0)),
 input({lat:0,lon:0},point(1,0)),{...input(point(0,0),point(1,0)),unit:'radians'}]) {
 assert.throws(()=>api.orient(bad));
}
console.log(JSON.stringify({state:'PACKAGE_DEVELOPMENT_CHECKS_PASS',known_answer:a,invalid_cases:10}));
""",encoding="utf-8")
        return json.loads(subprocess.check_output(["node","--no-addons",str(script)],cwd=root,text=True,timeout=20))

def rejected(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("tamper accepted")

def main():
    p=argparse.ArgumentParser()
    for name in ("module","receipt","licence","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    module,receipt,licence=(x.read_bytes() for x in (a.module,a.receipt,a.licence))
    payload=files(module,receipt,licence)
    raw=archive(payload)
    require(raw==archive(files(module,receipt,licence)),"non-reproducible archive")
    rejected(lambda: files(module+b" ",receipt,licence))
    rejected(lambda: files(module,receipt+b" ",licence))
    rejected(lambda: files(module,receipt,licence+b" "))
    rejected(lambda: verify(archive({**payload,"unexpected":"x".encode()}),payload))
    rejected(lambda: verify(archive({k:v for k,v in payload.items() if k!="index.mjs"}),payload))
    rejected(lambda: verify(archive({**payload,"index.mjs":b"altered"}),payload))
    evidence=runtime(raw,payload)
    evidence.update(archive_sha256=sha(raw),archive_bytes=len(raw),reproducible=True,
        file_count=len(payload),tamper_controls=6,independent_acceptance=False)
    with a.out.open("xb") as f:
        f.write(raw)
    print(json.dumps(evidence,sort_keys=True))

if __name__=="__main__":
    main()
