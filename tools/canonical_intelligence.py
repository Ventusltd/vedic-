"""Produce private Acorn metadata for canonical bound modules, reusing local Acorn."""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
from time import perf_counter

import pyarrow.parquet as pq

from canonical_sources import blob, output_table
from extract import atomic_write


def build(t1, engine, grid, acorn_root):
    start = perf_counter()
    bindings = pq.read_table(t1/"canonical-bindings.parquet").to_pylist()
    provenance = {}
    indexed_slots = {}
    for row in bindings:
        source_key = tuple(row[key] for key in ("repository", "commit", "path", "blob"))
        if row["path"].endswith((".js", ".mjs", ".html")):
            provenance[source_key] = source_key
            indexed_slots.setdefault(source_key + (row["first_line"], row["last_line"]), []).append(row)
    sources = []
    for repository, commit, path, expected in sorted(provenance):
        repo = engine if repository == "Ventusltd/ventus-grid-engine" else grid
        oid, raw = blob(repo, commit, path)
        if oid != expected:
            raise ValueError(f"Canonical source pin mismatch: {path}")
        sources.append({"repository": repository, "commit": commit, "path": path,
                        "blob": oid, "text": raw.decode("utf-8")})
    runner = Path(__file__).with_name("canonical_acorn.mjs")
    received = subprocess.check_output(["node", str(runner), str(acorn_root)],
                                       input=json.dumps(sources).encode("utf-8"))
    report = json.loads(received)
    metadata, symbols = [], []
    for row in report["files"]:
        identity = {key: row[key] for key in ("repository", "commit", "path", "blob")}
        source_key = tuple(identity.values())
        metadata.append({**identity, **{key + "_json": json.dumps(row[key], ensure_ascii=False)
                                          for key in ("imports", "constants", "refusals", "exports", "issues")}})
        for symbol in row["symbols"]:
            anchors = indexed_slots.get(source_key + (symbol["first_line"], symbol["last_line"]), [])
            # Use the name if possible. With ambiguous/anonymous spans retain all
            # possible anchors explicitly, rather than assigning an identity.
            named = [candidate for candidate in anchors if candidate["symbol"] == symbol["name"]]
            exact = named or anchors
            identifiers = sorted({candidate["element_id"] for candidate in exact})
            families = sorted({candidate["family_id"] for candidate in exact})
            symbols.append({**identity, **symbol, "matched_element_ids": identifiers,
                            "matched_family_ids": families,
                            "match_status": "unambiguous_name_and_lines" if len(named)==1
                            else "line_range_candidates" if exact else "outside_indexed_spans"})
    tables = [output_table(t1/"canonical-file-metadata.parquet", metadata),
              output_table(t1/"canonical-symbols.parquet", symbols)]
    summary = {"acorn_version": report["acorn_version"], "files": len(metadata), "symbols": len(symbols),
               "matches": dict(Counter(row["match_status"] for row in symbols)),
               "static_imports": sum(len(row["imports"]) for row in report["files"]),
               "export_bindings": sum(len(row["exports"]) for row in report["files"]),
               "top_level_constants": sum(len(row["constants"]) for row in report["files"]),
               "refusal_markers": sum(len(row["refusals"]) for row in report["files"]),
               "parse_issues": sum(len(row["issues"]) for row in report["files"]),
               "elapsed_seconds": perf_counter() - start, "tables": tables,
               "notes": "Static imports are source syntax; browser global bindings and dynamic dependencies are not fully resolved. Refusal markers are source cues."}
    atomic_write(t1/"canonical-acorn-manifest.json",
                 lambda p: p.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8"))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("t1", "engine", "grid", "acorn_root"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.t1, args.engine, args.grid, args.acorn_root), indent=2))


if __name__ == "__main__":
    main()
