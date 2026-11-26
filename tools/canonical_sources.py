"""Join pinned engine and GridAtlas architecture to existing Modular Star addresses."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess

import pyarrow as pa
import pyarrow.parquet as pq

from modular_features import atomic_write


def git(repo, *arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments])


def blob(repo, commit, path):
    ref = f"{commit}:{path}"
    data = git(repo, "cat-file", "blob", ref)
    return git(repo, "rev-parse", "--verify", ref).decode().strip(), data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_counts(db, library):
    counts = {name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
              for name in ("line", "scan", "element", "family", "tablet", "commit_info", "occurrence")}
    stamp = re.compile(r"(^|[^0-9])\d{8}(\d{4})?(?=[^0-9]|$)")
    places = defaultdict(set)
    for family, repo, path in db.execute(
        """SELECT DISTINCT e.family,o.repo,o.path FROM tablet_element te
           JOIN element e ON te.element=e.n JOIN occurrence o ON o.tablet=te.tablet
           JOIN scan s ON s.repo=o.repo AND s.commit_sha=o.commit_sha"""
    ):
        lineage = stamp.sub(r"\1{stamp}", path)
        places[family].add((repo, lineage))
    counts["repeated_current_families"] = sum(len(paths) >= 2 for paths in places.values())
    counts["compiled_function_exports"] = len(re.findall(
        rb"(?m)^export const f\d+_", library))
    return counts


def by_blob(db, repository, commit, path, oid, prefix_scope):
    return [
        {"repository": repository, "commit": commit, "path": path, "blob": oid,
         "element_id": element, "family_id": family, "symbol": name, "first_line": first,
         "last_line": last, "kind": kind, "needs": json.loads(needs) if needs else None,
         "standalone_candidate": bool(standalone), "source_role": prefix_scope}
        for element, family, name, first, last, kind, needs, standalone in db.execute(
            """SELECT e.n,e.family,te.name,te.first,te.last,e.kind,e.needs,e.standalone
               FROM tablet t JOIN tablet_element te ON te.tablet=t.n
               JOIN element e ON e.n=te.element WHERE t.git_blob=? ORDER BY te.first,e.n""", (oid,))
    ]


def git_line_bases(repo, commit):
    tree = git(repo, "ls-tree", "-r", "-z", commit)
    entries = []
    for line in tree.split(b"\0"):
        if not line:
            continue
        header, path = line.split(b"\t", 1)
        _, kind, oid = header.split()
        if kind == b"blob":
            entries.append((path.decode(), oid))
    received = subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        input=b"\n".join(oid for _, oid in entries) + b"\n",
    )
    pos, running = 0, 0
    offsets = {}
    for path, expected_oid in entries:
        stop = received.index(b"\n", pos)
        oid, kind, length = received[pos:stop].split()
        if oid != expected_oid or kind != b"blob":
            raise ValueError("Unexpected Git batch frame")
        start = stop + 1
        size = int(length)
        pos = start + size + 1
        raw = received[start:pos-1]
        if received[pos-1:pos] != b"\n" or len(raw) != size:
            raise ValueError("Unexpected Git blob length")
        if b"\0" not in raw[:8000]:
            lines = raw.count(b"\n") + int(bool(raw) and not raw.endswith(b"\n"))
            offsets[path] = (running, lines)
            running += lines
    return offsets, running


def kuiper_engine_keys(kuiper, engine, engine_commit, rows):
    wafer = "f7a4cb9e3a764a72b7133bb275bb5387ea083be2"
    _, register = blob(kuiper, wafer, "cosmos/repos.tsv")
    _, ledger = blob(kuiper, wafer, "cosmos/wafer.tsv")
    names = {}
    for line in register.decode().splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            names[int(fields[0])] = fields[1]
    offset = 0
    for line in ledger.decode().splitlines():
        if not line or line.startswith("#"):
            continue
        _, total, repo_id, prefix, gap, *_ = line.split("\t")
        offset += int(gap)
        if names[int(repo_id)] == "ventus-grid-engine" and engine_commit.startswith(prefix):
            break
        offset += int(total)
    else:
        return 0
    bases, count = git_line_bases(engine, engine_commit)
    if count != int(total):
        raise ValueError("Pinned engine tree and Kuiper wafer line counts disagree")
    assigned = 0
    for row in rows:
        if row["repository"] != "Ventusltd/ventus-grid-engine":
            continue
        base, file_count = bases[row["path"]]
        if not 1 <= row["first_line"] <= row["last_line"] <= file_count:
            raise ValueError("Element extends beyond its file")
        row.update(kuiper_first_key=offset + base + row["first_line"] - 1,
                   kuiper_last_key=offset + base + row["last_line"] - 1, kuiper_wafer=wafer)
        assigned += 1
    return assigned


def output_table(path, rows):
    if path.exists():
        raise ValueError(f"Refusing to replace frozen output {path.name}")
    records = pa.Table.from_pylist(rows)
    atomic_write(path, lambda target: pq.write_table(records, target, compression="zstd"))
    return {"name": path.name, "rows": len(rows), "size_bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes())}


def build(db, engine, grid, kuiper, stars, out):
    engine_commit = "7c2a7b42905674fdcd3aa4bb50af14bc352a7747"
    grid_commit = "afffa9781f6130529ae93052604cd3d98d172a35"
    stars_commit = "1cf9c7530c7d287ccf9b3cffd70f693fb83c8402"
    graph_oid, graph_bytes = blob(engine, engine_commit, "genome/engine-graph.json")
    atlas_oid, atlas_bytes = blob(grid, grid_commit, "atlas/current.json")
    _, library = blob(stars, stars_commit, "library/standalone.mjs")
    graph, atlas = json.loads(graph_bytes), json.loads(atlas_bytes)
    if atlas["architecture"] != "IMMUTABLE_SHELL_PLUS_HASHED_CARTRIDGES":
        raise ValueError("Unsupported GridAtlas composition architecture")
    nodes, edges, bindings, architecture = [], [], [], []
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as cx:
        counts = source_counts(cx, library)
        for index, node in enumerate(graph["nodes"]):
            path = node["label"]
            source_oid = None
            if node["type"] == "canonical" and path.startswith("engine/"):
                source_oid, _ = blob(engine, engine_commit, path)
                bindings.extend(by_blob(cx, "Ventusltd/ventus-grid-engine", engine_commit, path,
                                        source_oid, "engine_graph_canonical_module"))
            nodes.append({"graph_index": index, "label": path, "kind": node["type"],
                          "recorded_reason": node.get("reason"), "recorded_url": node.get("gh"),
                          "engine_blob": source_oid, "graph_blob": graph_oid, "graph_commit": engine_commit})
        for item in graph["edges"]:
            source, target = item["from"], item["to"]
            if not 0 <= source < len(nodes) or not 0 <= target < len(nodes):
                raise ValueError("Engine graph edge endpoint missing")
            edges.append({"source_graph_index": source, "target_graph_index": target,
                          "relationship": item["type"], "evidence_json": json.dumps(item.get("evidence")),
                          "graph_blob": graph_oid})
        shell = "atlas/" + atlas["shell"]["index"].removeprefix("./")
        entries = [(item, "runtime_cartridge", "atlas/" + item["path"].removeprefix("./"))
                   for item in atlas["cartridges"]]
        entries.extend([({}, "runtime_router", "atlas/index.html"), ({}, "immutable_shell", shell)])
        positions = {key: idx for idx, key in enumerate(atlas["cartridge_order"])}
        for item, role, path in entries:
            if ".." in PurePosixPath(path).parts:
                raise ValueError("Composition path escapes the atlas")
            source_oid, raw = blob(grid, grid_commit, path)
            if item and item["sha256"] != digest(raw):
                raise ValueError(f"GridAtlas cartridge hash mismatch: {path}")
            architecture.append({"generation": atlas["generation"], "role": role, "path": path, "blob": source_oid,
                                 "commit": grid_commit, "composition_blob": atlas_oid, "sha256": digest(raw),
                                 "cartridge_id": item.get("id"), "load_ordinal": positions.get(item.get("id")),
                                 "slot": item.get("slot"), "anchor": item.get("after") or item.get("replace_script")})
            bindings.extend(by_blob(cx, "Ventusltd/gridatlas", grid_commit, path, source_oid, role))
    for row in bindings:
        row.update(kuiper_first_key=None, kuiper_last_key=None, kuiper_wafer=None)
    assigned = kuiper_engine_keys(kuiper, engine, engine_commit, bindings)
    tables = [output_table(out / f"{name}.parquet", rows)
              for name, rows in (("canonical-bindings", bindings), ("engine-nodes", nodes),
                                 ("engine-edges", edges), ("gridatlas-composition", architecture))]
    report = {"inventory_counts": counts, "gridatlas_generation": atlas["generation"],
              "matched_engine_kuiper_ranges": assigned, "engine_graph_relations": dict(Counter(e["relationship"] for e in edges)),
              "tables": tables, "notes": "Graph edges are registered evidence claims, not proof of interchangeability or package admission."}
    atomic_write(out/"canonical-manifest.json", lambda p: p.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("db", "engine", "grid", "kuiper", "stars", "out"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.db, args.engine, args.grid, args.kuiper, args.stars, args.out), indent=2))


if __name__ == "__main__":
    main()
