"""Fail closed on unsupported VEDIC translation claims; read-only source check."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def require(condition, message):
    if not condition:
        raise ValueError(message)

def validate(data, anatomy):
    require(data["schema"] == "vedic.translation.v1", "translation schema")
    require(data["receipt"].startswith("https://github.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-"), "receipt")
    apps = [a for a in anatomy["apps"] if a["id"] == data["app"]]
    require(len(apps) == 1 and data["capability"] in {c["id"] for c in apps[0]["capabilities"]}, "translation target missing")
    require(bool(data["relationship"]), "relationship not explained")
    require(bool(data["records"]), "empty translation batch")
    ids = set()
    for r in data["records"]:
        require(r["id"] not in ids, "duplicate translation ID")
        ids.add(r["id"])
        for key in ("name", "purpose", "inputs", "outputs", "limits", "block_candidate"):
            require(isinstance(r[key], str) and bool(r[key].strip()), "missing " + key)
        require(r["state"] == "STATIC_SOURCE_REVIEW", "unproven state promotion")
        require(r["proof"] is None and r["family_id"] is None and r["line_ids"] is None, "unverified identity or proof")
        s = r["source"]
        require(s["repo"] == "Ventusltd/ventus-grid-engine" and s["path"] == "engine/v9-geodesy.js", "unexpected producer")
        for k in ("commit", "blob"):
            require(bool(re.fullmatch(r"[0-9a-f]{40}", s[k])), "bad source " + k)
        require(type(s["first"]) is int and type(s["last"]) is int and 1 <= s["first"] <= s["last"], "source range")
    return len(ids)

def verify_source(data, reader):
    cache = {}
    for r in data["records"]:
        s = r["source"]
        key = (s["repo"], s["commit"], s["path"])
        if key not in cache:
            cache[key] = reader(*key)
        raw = cache[key]
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(blob == s["blob"], "source blob mismatch")
        lines = raw.decode("utf-8").splitlines()
        require(s["last"] <= len(lines), "range outside source")
        excerpt = lines[s["first"]-1:s["last"]]
        require(excerpt[0].startswith("export function " + r["name"] + "(") and excerpt[-1] == "}", "function boundary mismatch")
    return len(data["records"])

def fetch(repo, commit, path):
    with urlopen("https://raw.githubusercontent.com/" + repo + "/" + commit + "/" + path, timeout=30) as response:
        return response.read(1_000_001)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--online", action="store_true")
    args = p.parse_args()
    d = json.loads((ROOT / "data/translation-geodesy.json").read_text())
    a = json.loads((ROOT / "data/anatomy.json").read_text())
    print("Translation records:", validate(d, a))
    if args.online:
        print("Pinned source boundaries verified:", verify_source(d, fetch))
