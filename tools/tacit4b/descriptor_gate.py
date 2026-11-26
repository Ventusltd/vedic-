"""Prove unmodified shared factory refuses missing source receipt and licence; no fake pins."""
import importlib.util, json, sys
from pathlib import Path
factory, descriptor, source, out = map(Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location("shared_factory",factory)
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
assert f.digest(factory.read_bytes(),"git-blob-sha1")=="9512aa3c6db77ea32d54619ed484119d3cb08d7d"
d=f.strict(descriptor.read_bytes())
assert set(d)==set(f.TOP)
local=Path(__file__).resolve().parent
paths={"module":source,"adapter":local/"adapter.mjs","consumer":local/"consumer.mjs"}
for i in d["inputs"]:
    assert f.digest(paths[i["role"]].read_bytes(),i["algorithm"])==i["digest"]
assert {"receipt","licence"}.isdisjoint(paths)
try: f.admit(d)
except f.Refusal as exc:
    assert str(exc)=="REQUIRED_INPUT", str(exc)
else: raise AssertionError("incomplete descriptor admitted")
result={"state":"EXPECTED_REFUSAL","reason":"REQUIRED_INPUT","missing_roles":["receipt","licence"],"descriptor_sha256":f.sha(f.canonical(d)),"source_sha256":f.sha(source.read_bytes()),"factory_commit":"050aa53d553eff6a7990fc0ed5f00623788babdd","family_admitted":False}
out.write_bytes(f.canonical(result))
print(json.dumps(result,sort_keys=True))
