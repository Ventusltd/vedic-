"""One-off, internal solar geometry development proof; uses pinned PR13 ZIP helpers."""
import hashlib, importlib.util, json, pathlib, subprocess, tempfile, sys, zipfile, io
from pathlib import Path
source, factory, output = map(Path, sys.argv[1:])
here = Path(__file__).resolve().parent
def blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def sha(b):
    return hashlib.sha256(b).hexdigest()
raw=source.read_bytes()
assert blob(raw)=="52619f60fea35e05d7634d760b7c19b6712f9b97", "source pin mismatch"
assert blob(factory.read_bytes())=="63849940adf32580e5c3aab4ea9dc2b36a35c319", "factory pin mismatch"
spec=importlib.util.spec_from_file_location("pinned_factory",factory)
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
name="@ventus-internal/vedic-solar-shape"
payload={"structures.mjs":raw,"index.mjs":(here/"adapter.mjs").read_bytes(),
 "package.json":f.encoded({"name":name,"version":"0.2.0","type":"module","private":True,"license":"UNLICENSED","exports":{".":"./index.mjs"},"dependencies":{},"engines":{"node":">=18"}})}
manifest={"schema":"tacit4b.development-evidence.v1","name":name,"source":{"repo":"Ventusltd/globalgrid2050","commit":"2f4b7cb82ee154fa3c684cba634d45f2183c6e7d","path":"energy-transition-simulator/202609282123/mod/engine/structures.mjs","blob":blob(raw),"sha256":sha(raw)},"export":"solarTableShape","source_export":"tableShape","identity_complete":False,"independent_acceptance":False,"redistribution":"BLOCKED","runtime":"Node >=18","runtime_dependencies":[],"scope":"South 2P/3P portrait and 3L landscape geometry, synthetic input, metres, not terrain, energy or engineering approval","factory_commit":"2adc1fa9c52f1d242e601b1580927996e7cb31da","files":{k:sha(v) for k,v in sorted(payload.items())}}
payload["manifest.json"]=f.encoded(manifest)
archive=f.archive(payload)
assert archive==f.archive(dict(reversed(list(payload.items()))))
f.verify(archive,payload)
for changed in [{**payload,"index.mjs":b"tampered"}, {**payload,"extra":b"x"}, {k:v for k,v in payload.items() if k!="structures.mjs"}]:
    try: f.verify(f.archive(changed),payload)
    except ValueError: pass
    else: raise AssertionError("tamper accepted")
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    package=root/"node_modules"/name
    package.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        for k in payload: (package/k).write_bytes(z.read(k))
    script=root/"consumer.mjs"
    script.write_bytes((here/"consumer.mjs").read_bytes())
    result=json.loads(subprocess.check_output(["node","--no-addons",str(script)],cwd=root,text=True,timeout=20))
result.update(source_sha256=sha(raw),archive_sha256=sha(archive),archive_bytes=len(archive),reproducible=True,tamper_controls=3,independent_acceptance=False)
output.mkdir(parents=True,exist_ok=True)
(output/"manifest.json").write_bytes(f.encoded(manifest))
(output/"result.json").write_bytes(f.encoded(result))
print(json.dumps(result,sort_keys=True))
