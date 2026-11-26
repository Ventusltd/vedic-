"""Compile the domain crib library and scan all unique indexed lines in ID order."""

import argparse
from contextlib import closing
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import random
import re
import sqlite3
from time import perf_counter

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from dictionary_shards import tokens
from estate_crib_search import DOT_CUDA


BATCH = 8192
MAX_LINE_BYTES = 4096
ROTATION_STEP = 0x9E3779B97F4A7C15


def compile_library(path):
    document = json.loads(path.read_bytes())
    groups = document["groups"]
    if document["schema"] != "vedic.estate-crib-library.v1" or not 1 <= len(groups) <= 64:
        raise ValueError("Unsupported domain library")
    titles = [group["title"] for group in groups]
    if len(set(titles)) != len(titles) or any(not re.fullmatch(r"[A-Z]+(?: [A-Z]+){0,4}", title) for title in titles):
        raise ValueError("Expected distinct compact domain groups")
    vocabulary = sorted({word for group in groups for role in ("actions", "objects") for word in group[role]})
    columns = {word: index for index, word in enumerate(vocabulary)}
    cues = np.zeros((len(vocabulary), 2 * len(groups)), dtype=np.float32)
    for index, group in enumerate(groups):
        for role_index, role in enumerate(("actions", "objects")):
            if not group[role]:
                raise ValueError(f"Group needs both action and object clues: {group['title']}")
            for word in group[role]:
                cues[columns[word], 2 * index + role_index] = 1
    return groups, columns, cues


def source_contexts(database, groups, maximum_id):
    by_tablet = Counter()
    origins = database.execute("SELECT DISTINCT repo, path, tablet FROM occurrence")
    for repo, path, tablet in origins:
        repository = repo.rsplit("/", 1)[-1].casefold()
        path = path.casefold()
        for index, group in enumerate(groups):
            if repository in group["repositories"] or any(hint in path for hint in group["path_contains"]):
                by_tablet[tablet] |= 1 << index
    masks = np.zeros(maximum_id + 1, dtype=np.uint64)
    for tablet, raw in database.execute("SELECT n, lines FROM tablet"):
        mask = by_tablet[tablet]
        if mask:
            masks[np.frombuffer(raw, dtype="<u4")] |= np.uint64(mask)
    return masks


def gpu_scorer(cp, cues, powers):
    kernel = cp.RawKernel(DOT_CUDA, "cross_dot")
    weights = cp.asarray(cues)
    device_powers = cp.asarray(powers)

    def score(matrix):
        device = cp.asarray(matrix)
        n, width = matrix.shape
        k = cues.shape[1]
        scores = cp.empty((n, k), dtype=cp.float32)
        kernel(((k + 15) // 16, (n + 15) // 16), (16, 16),
               (device, weights, scores, np.int32(n), np.int32(width), np.int32(k)))
        hits = (scores[:, 0::2] >= 1) & (scores[:, 1::2] >= 2)
        return cp.sum(hits * device_powers, axis=1, dtype=cp.uint64).get()

    score(np.zeros((1, cues.shape[0]), dtype=np.float32))
    return score


def scan(database, columns, cues, backend="cupy"):
    powers = 2 ** np.arange(cues.shape[1] // 2, dtype=np.uint64)
    gpu_score = None
    if backend == "cupy":
        import cupy as cp

        gpu_score = gpu_scorer(cp, cues, powers)
    lookup = lru_cache(maxsize=16384)(tokens)
    started = perf_counter()
    elapsed = cpu_seconds = preparation = 0.0
    line_ids, winners = [], []
    truncated = 0

    cursor = database.execute("SELECT n, text FROM line ORDER BY n")
    while rows := cursor.fetchmany(BATCH):
        initial = perf_counter()
        matrix = np.zeros((len(rows), len(columns)), dtype=np.float32)
        for row, (number, raw) in enumerate(rows):
            truncated += len(raw) > MAX_LINE_BYTES
            terms = lookup(raw[:MAX_LINE_BYTES].decode("utf-8", errors="replace")).split()
            matrix[row, [columns[word] for word in terms if word in columns]] = 1
            line_ids.append(number)
        preparation += perf_counter() - initial
        initial = perf_counter()
        cpu = matrix @ cues
        expected = np.sum(((cpu[:, 0::2] >= 1) & (cpu[:, 1::2] >= 2)) *
                          powers, axis=1, dtype=np.uint64)
        cpu_seconds += perf_counter() - initial
        if gpu_score is not None:
            initial = perf_counter()
            actual = gpu_score(matrix)
            elapsed += perf_counter() - initial
            if not np.array_equal(actual, expected):
                raise ValueError("CPU and GPU disagree on line domain clues")
        winners.append(expected)
    benchmarks = {"cupy_seconds_including_transfers": elapsed if gpu_score is not None else None,
                  "numpy_seconds": cpu_seconds, "line_preparation_seconds": preparation,
                  "peak_cached_gpu_bytes": cp.get_default_memory_pool().total_bytes() if gpu_score is not None else None,
                  "seconds_including_database_iteration": perf_counter() - started}
    return np.asarray(line_ids), np.concatenate(winners), truncated, benchmarks


def source_shots(line_ids, lexical, contexts, groups, seed):
    rng = random.Random(seed)
    result = {}
    for index, group in enumerate(groups):
        bit = 1 << index
        eligible = np.flatnonzero((lexical & bit) != 0)
        if not len(eligible):
            continue
        rotation = rng.getrandbits(64)
        positions = {}
        for shot in range(len(eligible) * 4):
            if len(positions) == min(4, len(eligible)):
                break
            selected = ((rotation + shot * ROTATION_STEP) & ((1 << 64) - 1)) * len(eligible) >> 64
            positions[selected] = None
        result[group["title"]] = [
            {"line_id": int(line_ids[eligible[position]]),
             "same_group_in_source_context": bool(contexts[eligible[position]] & bit)}
            for position in positions
        ]
    return result


def sha256(path):
    with path.open("rb") as data:
        return hashlib.file_digest(data, "sha256").hexdigest()


def spider_evidence(path, groups):
    genome = json.loads(path.read_bytes())
    ids = {node["id"] for node in genome["nodes"]}
    wanted = {"Ventusltd/" + repository for group in groups for repository in group["repositories"]}
    edges = []
    for edge in genome["edges"]:
        start, target = edge["from"], edge["to"]
        start_repo, target_repo = start.split("::", 1)[0], target.split("::", 1)[0]
        if target_repo != start_repo and target_repo in wanted and start in ids and target in ids:
            evidence = edge["evidence"]
            edges.append({"from": start, "to": target, "type": edge["type"],
                          "file": evidence["file"], "line": evidence["line"], "pin": edge.get("pin")})
    return {"sha256": sha256(path), "graph_nodes": len(ids), "graph_edges": len(genome["edges"]),
            "named_group_repositories_present": sorted(ids & wanted), "matching_feed_edges": len(edges),
            "source_references": edges}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("library", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=20261126)
    parser.add_argument("--spider", type=Path, help="existing Spiders genome.json for local provenance references")
    parser.add_argument("--backend", choices=("numpy", "cupy"), default="cupy")
    args = parser.parse_args()
    scan_estate(args.database, args.library, args.output, args.seed, args.spider, args.backend)


def scan_estate(database_path, library, output, seed, spider_path=None, backend="cupy"):
    groups, columns, cues = compile_library(library)
    with closing(sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)) as database:
        maximum_id, = database.execute("SELECT max(n) FROM line").fetchone()
        context_index = source_contexts(database, groups, maximum_id)
        ids, lexical, truncated, benchmark = scan(database, columns, cues, backend)
    contexts = context_index[ids]
    shots = source_shots(ids, lexical, contexts, groups, seed)
    output.mkdir(parents=True, exist_ok=False)
    spider = spider_evidence(spider_path, groups) if spider_path else None
    if spider:
        (output / "spider-references.json").write_text(json.dumps(spider, indent=2) + "\n", encoding="utf-8")
    parquet = output / "domain-lines.parquet"
    pq.write_table(pa.table({"line_id": ids, "lexical_domain_mask": lexical,
                             "source_context_mask": contexts}), parquet, compression="zstd")
    (output / "vogel-shots.json").write_text(json.dumps(shots, indent=2) + "\n", encoding="utf-8")
    receipt = {"schema": "vedic.estate-domain-scan.v1", "seed": seed,
               "library_sha256": sha256(library), "database_sha256": sha256(database_path),
               "lines": len(ids), "line_group_pairs": len(ids) * len(groups),
               "source_context_lines": int(np.count_nonzero(contexts)),
               "lexical_group_lines": int(np.count_nonzero(lexical)),
               "same_domain_agreement_lines": int(np.count_nonzero(contexts & lexical)),
               "any_domain_lines": int(np.count_nonzero(contexts | lexical)),
               "bounded_long_lines": truncated, "backend": backend,
               "exact_cpu_gpu_mask_parity": True if backend == "cupy" else None,
               "groups_in_bit_order": [group["title"] for group in groups],
               "spider_evidence_sha256": spider["sha256"] if spider else None,
               "spider_cross_repository_references": spider["matching_feed_edges"] if spider else None,
               "counts": {group["title"]: {
                   "lexical": int(np.count_nonzero(lexical & (1 << index))),
                   "context": int(np.count_nonzero(contexts & (1 << index))),
               } for index, group in enumerate(groups)},
               "benchmark": benchmark, "parquet_sha256": sha256(parquet), "parquet_bytes": parquet.stat().st_size}
    (output / "manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key not in {"groups_in_bit_order", "counts"}}, indent=2))
    return receipt


if __name__ == "__main__":
    main()
