"""Stage Git-exact current and historical VEDIC Pages payloads with file digests."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from dictionary_shards import build as build_command_shards

ROOT = Path(__file__).resolve().parents[1]
LEGACY_PUBLIC_FILES = (
    "index.html",
    "data/anatomy.json",
    "data/translation-geodesy.json",
    "data/nearest-spider.json",
    "data/dictionary.json",
)
CATALOGUE = "data/prose-catalogue.json"
PUBLICATION = "data/prose-publication.json"
CURRENT_PUBLIC_FILES = LEGACY_PUBLIC_FILES
PROSE_ARCHIVE_FILES = (*LEGACY_PUBLIC_FILES, CATALOGUE, PUBLICATION)
V1_COMMIT = "b17a153a6c0698902bfa89516a34ec8a956c11e7"
V1_ROUTE = "releases/202611260135-v1"
V2_ROUTE = "releases/202611261351"
V2_COMMIT = "55ff568b378acff4adae02fb5c758b4f4f8c6bcd"
V3_ROUTE = "releases/20261126-v3"
V3_COMMIT = "9d6a3a35b12fc4709f4b65965ca1f17a87277a2d"
FIRST_PROSE_ROUTE = "releases/20261126-prose-reader"
FIRST_PROSE_COMMIT = "7ca32d66e96ce8f453a99363ffaf04de265f2f6a"
TELEPRINTER_PROSE_ROUTE = "releases/20261126-prose-teleprinter"
TELEPRINTER_PROSE_COMMIT = "205bbd8f9be2f38d1b6f514022a494474fac79a6"

def git_bytes(ref, name):
    return subprocess.check_output(["git","show",f"{ref}:{name}"],cwd=ROOT)
def digest(data):
    return hashlib.sha256(data).hexdigest()

def validate_publication(payload):
    raw = payload[CATALOGUE]
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("Public prose requires a bounded catalogue")
    catalogue = json.loads(raw)
    publication = json.loads(payload[PUBLICATION])
    records = catalogue["records"]
    if catalogue["schema"] != "vedic.prose.catalogue.v1" or not isinstance(records, list) or not records:
        raise ValueError("Missing published prose")
    if publication["schema"] != "vedic.prose.publication-batch.v1" or publication["catalogue"] != {
        "path": "prose-catalogue.json", "rows": len(records), "sha256": digest(raw)
    }:
        raise ValueError("Prose catalogue differs from approved batch")
    ids = set()
    hashes = []
    for row in records:
        for field in ("id", "software", "prose", "status", "provenance", "evidence"):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError("Invalid public prose field: " + field)
        if row["id"] in ids:
            raise ValueError("Duplicate public prose reference: " + row["id"])
        ids.add(row["id"])
        hashes.append({"id": row["id"], "sha256": digest(row["prose"].encode("utf-8"))})
    if hashes != publication["records"]:
        raise ValueError("Public prose text or reading order differs from approved batch")
    return len(records)

def write_bundle(destination, payload, version, ref):
    prose_count = validate_publication(payload) if CATALOGUE in payload else None
    for name, data in payload.items():
        target=destination/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        if target.read_bytes()!=data:
            raise ValueError("staged mismatch: "+name)
    manifest={"schema":"vedic.pages.release.v1","version":version,"source_commit":ref,
        "row_count":len(json.loads(payload["data/dictionary.json"])["entries"]),
        "files":{name:digest(data) for name,data in payload.items()}}
    if prose_count is not None:
        manifest["prose_count"] = prose_count
    (destination/"release.json").write_bytes((json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    for name,h in manifest["files"].items():
        if digest((destination/name).read_bytes())!=h:
            raise ValueError("digest mismatch "+name)
        print(f"{h}  {destination/name}",flush=True)
def stage(destination):
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    current={name:git_bytes(head,name) for name in CURRENT_PUBLIC_FILES}
    v3={name:git_bytes(V3_COMMIT,name) for name in LEGACY_PUBLIC_FILES}
    v2={name:git_bytes(V2_COMMIT,name) for name in LEGACY_PUBLIC_FILES}
    for name,data in current.items():
        if (ROOT/name).read_bytes()!=data:
            raise ValueError("working tree differs from committed bytes: "+name)
    prior={name:git_bytes(V1_COMMIT,name) for name in LEGACY_PUBLIC_FILES}
    destination.mkdir(parents=True,exist_ok=False)
    first_prose = {name:git_bytes(FIRST_PROSE_COMMIT,name) for name in PROSE_ARCHIVE_FILES}
    teleprinter_prose = {name:git_bytes(TELEPRINTER_PROSE_COMMIT,name) for name in PROSE_ARCHIVE_FILES}
    generated = build_command_shards(json.loads(current["data/dictionary.json"]), json.loads(current["data/translation-geodesy.json"]))
    current.update(generated)
    write_bundle(destination,current,"20261126-commands",head)
    write_bundle(destination/TELEPRINTER_PROSE_ROUTE,teleprinter_prose,"20261126-prose-teleprinter",TELEPRINTER_PROSE_COMMIT)
    write_bundle(destination/FIRST_PROSE_ROUTE,first_prose,"20261126-prose-reader",FIRST_PROSE_COMMIT)
    write_bundle(destination/V1_ROUTE,prior,"202611260135-v1",V1_COMMIT)
    write_bundle(destination/V2_ROUTE,v2,"202611261351",V2_COMMIT)
    write_bundle(destination/V3_ROUTE,v3,"20261126-v3",V3_COMMIT)
    (destination/".nojekyll").touch()
    expected = {".nojekyll", "release.json", *CURRENT_PUBLIC_FILES, *generated}
    expected.update(f"{route}/{name}" for route in (V1_ROUTE, V2_ROUTE, V3_ROUTE)
                    for name in (*LEGACY_PUBLIC_FILES, "release.json"))
    actual={p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    expected.update(f"{route}/{name}" for route in (FIRST_PROSE_ROUTE, TELEPRINTER_PROSE_ROUTE)
                    for name in (*PROSE_ARCHIVE_FILES, "release.json"))
    if actual!=expected:
        raise ValueError("public file-set mismatch")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("destination",type=Path)
    stage(p.parse_args().destination)
