"""Verify source-index totals and audit selected cosine leads in the original sparse feature space."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq


LEXICAL = {"pair", "op", "id", "literal", "symbol"}
STRUCTURAL = {"ast", "kind", "lang", "need", "needs", "dep", "signature", "param", "refusal"}
STAMP = re.compile(r"(^|[^0-9])\d{8}(\d{4})?(?=[^0-9]|$)")


def audit_index(database, library, repeat_output):
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        counts = {table: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                  for table in ("line", "scan", "commit_info", "element", "family", "tablet", "occurrence")}
        counts["repos_with_occurrence_rows"] = db.execute(
            "SELECT count(DISTINCT repo) FROM occurrence").fetchone()[0]
        counts["families_with_elements"] = db.execute(
            "SELECT count(DISTINCT family) FROM element").fetchone()[0]
        lineages = defaultdict(set)
        elements = defaultdict(set)
        occurrences = Counter()
        places = db.execute("""
          SELECT e.family,e.n,te.first,o.repo,o.path FROM tablet_element te
          JOIN element e ON e.n=te.element JOIN occurrence o ON o.tablet=te.tablet
          JOIN scan s ON s.repo=o.repo AND s.commit_sha=o.commit_sha
        """)
        element_counts = Counter()
        for family, element, _, repo, path in places:
            lineage = (repo, STAMP.sub(r"\1{stamp}", path))
            lineages[family].add(lineage)
            elements[family, element].add(lineage)
            occurrences[family] += 1
            element_counts[family, element] += 1
        counts["current_head_families_with_places"] = len(lineages)
        counts["families_across_multiple_current_file_lineages"] = sum(
            len(paths) >= 2 for paths in lineages.values())
        counts["only_same_lineage_multiple_current_places"] = sum(
            occurrences[family] >= 2 and len(paths) == 1 for family, paths in lineages.items())
        rows = [{"family_id": family, "element_id": element, "current_file_lineages": len(paths),
                 "current_places": element_counts[family,element]}
                for (family,element),paths in sorted(elements.items()) if len(paths) >= 2]
        counts["exact_producer_element_ids_across_multiple_current_file_lineages"] = len(rows)
        pq.write_table(pa.Table.from_pylist(rows), repeat_output, compression="zstd")
    text = library.read_text(encoding="utf-8")
    counts["compiled_function_candidates_in_library"] = len(re.findall(r"(?m)^// Family #\d+ · element #\d+", text))
    counts["compiled_js_exports_behind_family_comments"] = len(re.findall(r"(?m)^export const f\d+_", text))
    return counts


def sparse_reviews(feature_file, neighbors, witness):
    families = defaultdict(Counter)
    for batch in pq.ParquetFile(feature_file).iter_batches(columns=["family_id", "tokens"]):
        for row in batch.to_pylist():
            families[row["family_id"]] |= Counter(row["tokens"])
    source = json.loads(witness.read_bytes())
    pairs = {(x["families"][0], x["families"][1]) for x in source["pairs"]}
    ids = sorted({item for pair in pairs for item in pair})
    df = Counter(term for doc in families.values() for term in doc)
    presence = defaultdict(lambda: None)
    edge = pq.read_table(neighbors, filters=[("family_id", "in", ids)],
                         columns=["family_id", "neighbor_family_id", "cosine", "rank"])
    for row in edge.to_pylist():
        presence[row["family_id"],row["neighbor_family_id"]] = (
            row["cosine"], row["rank"])

    def scores(left, right, prefixes=None):
        def weighted(doc):
            return {term: (1 + math.log(count)) * (1 + math.log((1+len(families))/(1+df[term])))
                    for term,count in doc.items()
                    if prefixes is None or term.split(":",1)[0] in prefixes}
        a, b = weighted(families[left]), weighted(families[right])
        denominator = math.sqrt(sum(x*x for x in a.values()) * sum(x*x for x in b.values()))
        return sum(a[k]*b[k] for k in a.keys() & b.keys()) / denominator if denominator else None

    return [{**row,
             "projected_retained_forward_score_rank": presence[*row["families"]],
             "projected_retained_reverse_score_rank": presence[*reversed(row["families"])],
             "exact_sparse_all_terms_tfidf": scores(*row["families"]),
             "exact_sparse_lexical_tfidf": scores(*row["families"], LEXICAL),
             "exact_sparse_structural_tfidf": scores(*row["families"], STRUCTURAL)}
            for row in source["pairs"]]


def drift_leads(feature_file, neighbors, output):
    labels = defaultdict(set)
    broad = {"default", "constructor", "anonymous", "render", "update", "start", "main", "init",
             "getvalue", "callback", "cleanup", "normalize", "normalise", "validate"}
    for batch in pq.ParquetFile(feature_file).iter_batches(columns=["family_id", "symbol"]):
        for row in batch.to_pylist():
            name = (row["symbol"] or "").casefold()
            if name not in broad and re.fullmatch(r"[a-z_$][a-z0-9_$]{3,}", name):
                labels[row["family_id"]].add(name)
    candidates = {}
    for row in pq.read_table(neighbors, filters=[("cosine", ">=", 0.92)],
                             columns=["family_id", "neighbor_family_id", "cosine"]).to_pylist():
        left, right = sorted((row["family_id"], row["neighbor_family_id"]))
        matching = labels[left] & labels[right]
        if matching:
            candidates[left, right] = max(candidates.get((left, right), 0), row["cosine"])
    rows = [{"family_a": left, "family_b": right, "shared_symbol": sorted(labels[left] & labels[right]),
             "cosine": score} for (left, right), score in sorted(candidates.items())]
    schema = pa.schema([("family_a", pa.int64()), ("family_b", pa.int64()),
                        ("shared_symbol", pa.list_(pa.string())), ("cosine", pa.float32())])
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), output, compression="zstd")
    return len(rows)


def cpu_threshold_replay(features, dimension=1024, tile=256):
    import os
    from time import perf_counter
    import numpy as np
    from family_similarity import THRESHOLDS, read_features, representations

    start = perf_counter()
    groups, _ = read_features(features)
    ids, matrix, active, _, _ = representations(groups, dimension)
    prep = perf_counter() - start
    counts = np.zeros(len(THRESHOLDS), dtype=np.int64)
    labels = np.arange(len(ids))
    seconds = 0.0
    outer = perf_counter()
    for begin in range(0, len(ids), tile):
        stop = min(begin + tile, len(ids))
        started = perf_counter()
        scores = matrix[begin:stop] @ matrix.T
        seconds += perf_counter() - started
        eligible = active[begin:stop, None] & active[None, :] & (labels[begin:stop, None] < labels)
        for index, limit in enumerate(THRESHOLDS):
            counts[index] += np.count_nonzero((scores >= limit) & eligible)
    return {
        "families": len(ids), "dimension": dimension, "row_tile": tile, "score_cells": len(ids)**2,
        "observed_openblas_threads_setting": os.environ.get("OPENBLAS_NUM_THREADS"),
        "feature_prep_seconds": prep, "score_only_seconds": seconds,
        "scoring_and_threshold_reduction_seconds": perf_counter() - outer,
        "threshold_totals_unique_unordered": {str(t): int(c) for t,c in zip(THRESHOLDS, counts, strict=True)},
        "scope": "Same float32 feature representation and threshold reduction. CPU replay omits top-k sorting.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--neighbors", type=Path, required=True)
    parser.add_argument("--witness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpu-replay", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    repeat_output = args.output / "repeat-elements.parquet"
    values = audit_index(args.database, args.library, repeat_output)
    pairs = sparse_reviews(args.features, args.neighbors, args.witness)
    drift_output = args.output / "drift-leads.parquet"
    drift_count = drift_leads(args.features, args.neighbors, drift_output)
    with repeat_output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {
        "inventory": values, "canonical_relationships_checked": len(pairs), "relationships": pairs,
        "repeat_elements_sha256": digest, "repeat_elements_bytes": repeat_output.stat().st_size,
        "same_symbol_different_family_drift_leads_at_0_92": drift_count,
        "drift_leads_bytes": drift_output.stat().st_size,
        "drift_leads_sha256": hashlib.sha256(drift_output.read_bytes()).hexdigest(),
        "cpu_replay": cpu_threshold_replay(args.features) if args.cpu_replay else None,
        "notes": [
            "Repeated elements represent the same existing producer element identity across separately normalised current file lineages.",
            "The compiled-library count is source availability and parse admission, separate from verified executions.",
            "Sparse exact here means no hash projection in the selected feature vectors. Tokenisation can still omit or truncate context.",
            "Null projected score means the pair was outside the retained directed top-k; it does not imply a zero score.",
        ],
    }
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
