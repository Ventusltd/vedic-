"""Stage Git-exact current and historical VEDIC Pages payloads with file digests."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    "index.html",
    "data/anatomy.json",
    "data/translation-geodesy.json",
    "data/nearest-spider.json",
    "data/dictionary.json",
)
V1_COMMIT = "b17a153a6c0698902bfa89516a34ec8a956c11e7"
V1_ROUTE = "releases/202611260135-v1"
V2_ROUTE = "releases/202611261351"
def git_bytes(ref, name):
    return subprocess.check_output(["git","show",f"{ref}:{name}"],cwd=ROOT)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def write_bundle(destination, payload, version, ref):
    for name, data in payload.items():
        target=destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        if target.read_bytes()!=data:
            raise ValueError("staged mismatch: "+name)
    manifest={"schema":"vedic.pages.release.v1","version":version,"source_commit":ref,
        "row_count":len(json.loads(payload["data/dictionary.json"])["entries"]),
        "files":{name:digest(data) for name,data in payload.items()}}
    (destination/"release.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    for name,h in manifest["files"].items():
        if digest((destination/name).read_bytes())!=h:
            raise ValueError("digest mismatch "+name)
        print(f"{h}  {destination/name}",flush=True)
def stage(destination):
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    current={name:git_bytes(head,name) for name in PUBLIC_FILES}
    for name,data in current.items():
        if (ROOT/name).read_bytes()!=data:
            raise ValueError("working tree differs from committed bytes: "+name)
    prior={name:git_bytes(V1_COMMIT,name) for name in PUBLIC_FILES}
    destination.mkdir(parents=True,exist_ok=False)
    write_bundle(destination,current,"202611261351",head)
    write_bundle(destination/V1_ROUTE,prior,"202611260135-v1",V1_COMMIT)
    write_bundle(destination/V2_ROUTE,current,"202611261351",head)
    (destination/".nojekyll").touch()
    expected={".nojekyll"}|{prefix+name for prefix in ("",V1_ROUTE+"/",V2_ROUTE+"/") for name in (*PUBLIC_FILES,"release.json")}
    actual={p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if actual!=expected:
        raise ValueError("public file-set mismatch")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("destination",type=Path)
    stage(p.parse_args().destination)
