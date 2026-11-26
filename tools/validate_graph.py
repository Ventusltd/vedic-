"""Validate the initial static dependency graph. No live-use inference."""
import argparse
import hashlib
import json
from pathlib import Path
from validate_translation import fetch, require

ROOT = Path(__file__).resolve().parents[1]
def validate(g, reader=None):
    require(g["schema"] == "vedic.static-spider.v1", "schema")
    require("not loaded by the live Atlas" in g["scope"], "historical caveat absent")
    require(g["receipt"].startswith("https://github.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-"), "receipt")
    nodes = {n["id"]: n for n in g["nodes"]}
    require(len(nodes) == len(g["nodes"]) and len(nodes) > 0, "duplicate or empty nodes")
    cache = {}
    def excerpt(s):
        key = (s["repo"], s["commit"], s["path"])
        require(key[0] == "Ventusltd/ventus-grid-engine" and key[2] in ("engine/v9-geodesy.js", "engine/v9-nearest-search.js"), "unapproved source")
        require(type(s["first"]) is int and type(s["last"]) is int and 1 <= s["first"] <= s["last"], "invalid source range")
        if reader is None:
            return None
        if key not in cache:
            cache[key] = reader(*key)
        raw = cache[key]
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == s["blob"], "source blob mismatch")
        lines = raw.decode("utf-8").splitlines()
        require(s["last"] <= len(lines), "range outside source")
        return "\n".join(lines[s["first"]-1:s["last"]])
    scope = excerpt(g["scope_source"])
    if scope is not None:
        require("NOT loaded by the live Atlas" in scope, "historical source caveat not found")
    for n in nodes.values():
        require(n["id"].startswith("vedic:") and n["rag"] == "grey", "false identity or runtime status")
        excerpt(n["source"])
    seen = set()
    for e in g["edges"]:
        key = (e["from"], e["to"], e["type"])
        require(key not in seen, "duplicate edge")
        seen.add(key)
        require(e["from"] in nodes and e["to"] in nodes and e["type"] in {"calls","contains"}, "unknown graph endpoint or relationship")
        ev = e["evidence"]
        require(bool(ev["contains"]), "missing edge evidence")
        text = excerpt(ev)
        if text is not None:
            require(ev["contains"] in text, "edge evidence absent")
    require(bool(seen), "empty graph")
    return len(nodes), len(seen)

def occurrence_key(source):
    # Physical source range, not a permanent Stars identity.
    return tuple(source[k] for k in ("repo", "commit", "path", "blob", "first", "last"))

def validate_aliases(graph, catalogue):
    records = catalogue["records"]
    by_id = {r["id"]: r for r in records}
    by_occurrence = {occurrence_key(r["source"]): r["id"] for r in records}
    require(len(by_id) == len(records) == len(by_occurrence), "duplicate catalogue occurrence")
    standalone = set()
    for n in graph["nodes"]:
        key = occurrence_key(n["source"])
        alias = n.get("catalogue_ref")
        if key in by_occurrence:
            require(alias == by_occurrence[key], "shared occurrence must reference catalogue")
        else:
            require(alias is None, "alias does not match exact source occurrence")
            require(key not in standalone, "duplicate standalone graph occurrence")
            standalone.add(key)
    # Never use this count as global line/family coverage.
    return len(by_occurrence) + len(standalone)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--online", action="store_true")
    args = p.parse_args()
    graph = json.loads((ROOT / "data/nearest-spider.json").read_text())
    print("Static graph nodes / edges:", validate(graph, fetch if args.online else None))
    catalogue = json.loads((ROOT / "data/translation-geodesy.json").read_text())
    print("Distinct source ranges (not permanent line IDs):", validate_aliases(graph, catalogue))
