"""Package local factor tables without modifying the shared catalogue."""

import argparse
import json
from pathlib import Path
import re
import sqlite3
from time import perf_counter

import duckdb
import pyarrow.parquet as pq

from canonical_sources import blob, digest, output_table
from modular_features import atomic_write

STARS = "1cf9c7530c7d287ccf9b3cffd70f693fb83c8402"


def build(db, t1, stars):
    started = perf_counter()
    library_blob, raw = blob(stars, STARS, "library/standalone.mjs")
    compiled = re.findall(
        rb"(?m)^// Family #(\d+) [^\n]*?element #(\d+) [^\n]*? (https://github\.com/\S+)\n"
        rb"export const (f[0-9]+_[A-Za-z0-9_$]+)\s*=", raw)
    compiled_rows = [
        {"family_id": int(family), "element_id": int(element), "recorded_source": url.decode(),
         "export_name": name.decode(), "producer_commit": STARS, "library_blob": library_blob,
         "status": "compiled_candidate_no_admission"}
        for family, element, url, name in compiled
    ]
    if len(compiled_rows) != 766 or len({row["family_id"] for row in compiled_rows}) != len(compiled_rows):
        raise ValueError("Compiled library exports disagree with this pinned inventory")
    features = pq.read_table(t1/"element-features.parquet", columns=["family_id", "element_id"])
    exported_families = {row["family_id"] for row in compiled_rows}
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as conn:
        coverage = [
            {"family_id": family, "family_sha256": sha.lower(), "language": lang,
             "indexed_element_count": elements, "has_feature_row": elements > 0,
             "compiled_candidate": family in exported_families}
            for family, sha, lang, elements in conn.execute(
                "SELECT f.n,hex(f.sha),f.lang,count(e.n) FROM family f LEFT JOIN element e "
                "ON f.n=e.family GROUP BY f.n ORDER BY f.n")
        ]
    assert sum(row["indexed_element_count"] for row in coverage) == features.num_rows
    tables = [output_table(t1/"compiled-members.parquet", compiled_rows),
              output_table(t1/"family-coverage.parquet", coverage)]
    files = {
        "element_features": "element-features.parquet",
        "family_coverage": "family-coverage.parquet",
        "compiled_members": "compiled-members.parquet",
        "engine_nodes": "engine-nodes.parquet",
        "engine_edges": "engine-edges.parquet",
        "gridatlas_composition": "gridatlas-composition.parquet",
        "canonical_bindings": "canonical-bindings.parquet",
        "canonical_symbols": "canonical-symbols.parquet",
        "canonical_file_metadata": "canonical-file-metadata.parquet",
    }
    target = t1/"canonical-intelligence.duckdb"
    scratch = target.with_suffix(".part")
    if target.exists() or scratch.exists():
        raise ValueError("Refusing to replace existing intelligence file")
    with duckdb.connect(str(scratch)) as local:
        for name, file in files.items():
            local.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet(?)", [str(t1/file)])
        totals = local.execute("SELECT count(*), count(DISTINCT family_id) FROM element_features").fetchone()
        assert totals == (features.num_rows, sum(row["has_feature_row"] for row in coverage))
        local.execute("CHECKPOINT")
    scratch.rename(target)
    manifest = {
        "tables": tables, "compiled_candidates": len(compiled_rows), "duckdb": target.name,
        "duckdb_sha256": digest(target.read_bytes()), "duckdb_size_bytes": target.stat().st_size,
        "database_tables": files, "processing_seconds": perf_counter() - started,
        "families_without_linked_elements": sum(not row["has_feature_row"] for row in coverage),
    }
    atomic_write(t1/"t1-intelligence-manifest.json",
                 lambda p: p.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8"))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("db", "t1", "stars"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.db, args.t1, args.stars), indent=2))


if __name__ == "__main__":
    main()
