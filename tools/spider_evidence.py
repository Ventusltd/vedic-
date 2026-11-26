#!/usr/bin/env python3
"""Read pinned Spider artifacts, without inferring executable dependencies."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

SPIDER_HEAD = "9801c73e8fd290d621bcf980fcc3fd6851229bf0"
BASE = "species/genome-spider/"
PINS = {
    "genome": (BASE + "data/genome.json", "e32e00174fa6d3bd2565fa60dbf246b4dbe75ecb"),
    "nodes": (BASE + "data/nodes.json", "6fb7867bf6bf3abce14930f72dbfe5f8a323d86c"),
    "edges": (BASE + "data/edges.json", "55c31d741c2472c64552647f63a4c2744d3956d9"),
    "receipt": (BASE + "receipts/LATEST.json", "a92448e75a6a0832291a0ec32450b776034ce439"),
    "lineage": (BASE + "data/gridatlas-lineage.json", "dcf7c1362750fb4114145f3b1e3b460e69f5c1e7"),
    "printer": ("spider_printer_v1/data/topology.json", "71e098e5095c444196095080efe74c37df4add25"),
}


def read_pinned(root, path, expected):
    raw = (root / path).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if blob != expected:
        raise ValueError("Git blob mismatch: " + path)
    return json.loads(raw)


def ids(rows):
    result = {r["id"] for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate graph node")
    return result


def validate_named(nodes, edges):
    known = ids(nodes)
    for edge in edges:
        if edge["from"] not in known or edge["to"] not in known:
            raise ValueError("Dangling graph edge")
    return known


def validate_index(nodes, edges):
    ids(nodes)
    out = []
    for f, t, kind in edges:
        if type(f) is not int or type(t) is not int or not (0 <= f < len(nodes) and 0 <= t < len(nodes)):
            raise ValueError("Invalid graph index")
        out.append((nodes[f]["id"], nodes[t]["id"], kind))
    return out


def graph_summary(data, repo):
    g, n, e, r, l, p = (data[k] for k in ("genome", "nodes", "edges", "receipt", "lineage", "printer"))
    if g["schema"] != "genome-spider.genome.v1" or e["edge_format"] != "index-array-v1":
        raise ValueError("Unknown genome schema")
    gn = validate_named(g["nodes"], g["edges"])
    if gn != ids(n["features"]):
        raise ValueError("Genome vs render node IDs differ")
    indexed = Counter(validate_index(n["features"], e["edges"]))
    evidenced = Counter((x["from"], x["to"], x["type"]) for x in g["edges"])
    if indexed != evidenced:
        raise ValueError("Genome vs render edge multiset differs")
    if (len(gn), sum(indexed.values())) != (r["counts"]["nodes"], r["counts"]["edges"]):
        raise ValueError("Receipt counts differ")
    for edge in g["edges"]:
        ev = edge.get("evidence", {})
        if not ev.get("file") or not ev.get("pattern") or not ev.get("snippet"):
            raise ValueError("Missing dependency evidence")
    validate_named(l["nodes"], l["edges"])
    pn = validate_named(p["nodes"], p["edges"])
    if any(edge["type"] != "reference" for edge in p["edges"]):
        raise ValueError("Unexpected printer edge kind")
    # Exact node IDs, never fuzzy names or producer identity allocation.
    target = "Ventusltd/" + repo
    related = {x["id"] for x in g["nodes"] if x.get("repo") in (repo, target)}
    if target in gn:
        related.add(target)
    neighborhood = [x for x in g["edges"] if x["from"] in related or x["to"] in related]
    references = [x for x in p["edges"] if repo in (x["from"], x["to"])]
    return {
        "schema": "vedic.spider-evidence.v1",
        "snapshot_commit": SPIDER_HEAD,
        "artifact_pins": {k: {"path": v[0], "git_blob": v[1]} for k, v in PINS.items()},
        "focus_repo": target,
        "state": "HISTORICAL_CONTEXT_ONLY",
        "genome": {
            "generated_at": g["generated_at"], "repository_count": len(g["repos_walked"]),
            "node_count": len(gn), "edge_count": sum(indexed.values()),
            "focus_present": bool(related), "focus_node_ids": sorted(related),
            "edge_types": dict(sorted(Counter(x["type"] for x in neighborhood).items())),
            "evidence_edges": neighborhood,
        },
        "spider": {"format": e["edge_format"], "node_count": len(n["features"]),
                   "edge_count": len(e["edges"]), "projection_verified": True},
        "gridatlas_lineage": {"generated_at": l["generated_at"], "node_count": len(l["nodes"]),
                             "edge_count": len(l["edges"]), "current_runtime": "UNVERIFIED"},
        "printer": {"generated_at": p["generated"]["utc"], "node_count": len(pn),
                    "edge_count": len(p["edges"]), "focus_present": repo in pn,
                    "relationship": "URL_REFERENCE_ONLY", "references": references},
        "execution_edges": [],
        "source_identity_matches": [],
        "limitations": ["September graph snapshots do not establish November dependency coverage.",
                        "Repository and file-level observations are not function-level call proof.",
                        "Printer reference edges are not executable dependencies.",
                        "Current source identity and typed composition must come from their owners."],
    }


def selftest():
    nodes = [{"id": "a"}, {"id": "b"}]
    assert validate_index(nodes, [[0, 1, "imports"]]) == [("a", "b", "imports")]
    for invalid in [[-1, 0, "x"], [0, 2, "x"], [True, 1, "x"]]:
        try:
            validate_index(nodes, [invalid])
        except ValueError:
            pass
        else:
            raise AssertionError("invalid index accepted")
    for bad_nodes, bad_edges in [
        (nodes, [{"from": "a", "to": "c"}]),
        ([{"id": "a"}, {"id": "a"}], []),
    ]:
        try:
            validate_named(bad_nodes, bad_edges)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid named graph accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spiders", type=Path, required=True)
    parser.add_argument("--repo", default="gridatlas")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    selftest()
    data = {k: read_pinned(args.spiders, *pin) for k, pin in PINS.items()}
    result = graph_summary(data, args.repo)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "focus": result["focus_repo"], "state": result["state"],
        "genome_nodes": result["genome"]["node_count"], "genome_edges": result["genome"]["edge_count"],
        "focus_edges": len(result["genome"]["evidence_edges"]),
        "printer_nodes": result["printer"]["node_count"], "printer_edges": result["printer"]["edge_count"],
        "printer_refs": len(result["printer"]["references"]), "execution_edges": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
