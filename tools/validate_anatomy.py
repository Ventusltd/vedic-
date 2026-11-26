"""Validate VEDIC's read-only anatomy against the pinned producer manifest.
Run python tools/validate_anatomy.py [--online]. No source or release writes.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def require(ok, message):
    if not ok:
        raise ValueError(message)

def validate(d):
    require(d["schema"] == "vedic.anatomy.v1", "schema")
    s = d["source"]
    require(re.fullmatch(r"[0-9a-f]{40}", s["commit"]), "source commit")
    require(re.fullmatch(r"[0-9a-f]{40}", s["git_blob"]), "source blob")
    require(s["repo"] == "Ventusltd/gridatlas" and s["manifest"] == "atlas/current.json", "source identity")
    bodies = {b["id"]: b for b in d["bodies"]}
    require(len(bodies) == len(d["bodies"]) and bodies, "body identity")
    for b in bodies.values():
        require(re.fullmatch(r"[0-9a-f]{64}", b["sha256"]), "body hash")
        require(b["path"].startswith("atlas/") and ".." not in Path(b["path"]).parts, "path")
        require(b["unique_lines"] is None and b["proof"] is None, "unmeasured body")
        require(b["block_ids"] == [] and b["family_ids"] == [], "unverified IDs")
    apps = {a["id"]: a for a in d["apps"]}
    require(len(apps) == len(d["apps"]), "app identity")
    count = 0
    for a in apps.values():
        require(a["status"] in {"MANIFEST_DECLARED", "NOT_MAPPED"}, "app state")
        require(bool(a["capabilities"]) == (a["status"] == "MANIFEST_DECLARED"), "app coverage")
        seen = set()
        for c in a["capabilities"]:
            require(c["id"] not in seen, "duplicate capability")
            seen.add(c["id"])
            require(c["body_ids"] and len(set(c["body_ids"])) == len(c["body_ids"]), "membership")
            require(set(c["body_ids"]) <= bodies.keys(), "dangling body")
            require(c["unique_lines"] is None and c["proof"] is None and c["limit"], "unmeasured capability")
            count += 1
    return len(apps), count, len(bodies)

def online(d):
    s = d["source"]
    base = "https://raw.githubusercontent.com/" + s["repo"] + "/" + s["commit"] + "/"
    def get(path):
        with urlopen(base + path, timeout=30) as r:
            return r.read(5_000_001)
    raw = get(s["manifest"])
    require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == s["git_blob"], "manifest blob differs")
    m = json.loads(raw)
    require(m["generation"] == s["generation"], "generation differs")
    expected = {x["id"]: x for x in m["cartridges"]}
    require(set(expected) == {x["id"] for x in d["bodies"]}, "manifest coverage")
    for b in d["bodies"]:
        e = expected[b["id"]]
        require(b["path"] == "atlas/" + e["path"].removeprefix("./"), "path mismatch")
        require(b["sha256"] == e["sha256"] and b["declared"] == e.get("capabilities", []), "manifest metadata mismatch")
        require(hashlib.sha256(get(b["path"])).hexdigest() == b["sha256"], "source SHA256 mismatch: " + b["id"])

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--online", action="store_true")
    args = p.parse_args()
    d = json.loads((ROOT / "data/anatomy.json").read_text())
    print("apps / capabilities / bodies:", validate(d))
    if args.online:
        online(d)
        print("Pinned manifest and cartridge byte hashes verified.")
