"""Compute bounded, source-ID-preserving similarity leads for existing Stars families."""

import argparse
from collections import Counter, defaultdict
import functools
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


THRESHOLDS = (0.85, 0.90, 0.92, 0.95, 0.99)
POLICY = "vedic-family-signed-hash-tfidf-v1"
COSINE_CUDA = r"""
extern "C" __global__ void cosine(
    const float* features, float* result, int n, int d, int begin, int rows
) {
    const int tx = threadIdx.x, ty = threadIdx.y;
    const int local_row = blockIdx.y * 16 + ty;
    const int row = begin + local_row, col = blockIdx.x * 16 + tx;
    const int load_col = blockIdx.x * 16 + ty;
    __shared__ float a[16][17], b[16][17];
    float acc = 0.0f;
    for (int offset = 0; offset < d; offset += 16) {
        a[ty][tx] = local_row < rows ? features[row*d + offset + tx] : 0.0f;
        b[ty][tx] = load_col < n ? features[load_col*d + offset + tx] : 0.0f;
        __syncthreads();
        #pragma unroll
        for (int i = 0; i < 16; ++i) acc = fmaf(a[ty][i], b[tx][i], acc);
        __syncthreads();
    }
    if (local_row < rows && col < n) result[local_row*n+col] = acc;
}
"""


def sha256_file(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def read_features(path):
    """Aggregate supplied existing element occurrences by their permanent family."""

    table = pq.read_table(path)
    required = {"family_id", "element_id", "tokens"}
    if not required.issubset(table.column_names):
        raise ValueError(f"Feature file must contain {sorted(required)}")
    allowed = required | {"counts", "lang", "language", "repo", "path", "symbol"}
    groups = defaultdict(list)
    seen_elements = set()
    for row in table.select([col for col in table.column_names if col in allowed]).to_pylist():
        family, element, tokens = (row[k] for k in ("family_id", "element_id", "tokens"))
        if type(family) is not int or type(element) is not int or family <= 0 or element <= 0:
            raise ValueError("Expected existing positive integer family and element IDs")
        if element in seen_elements:
            raise ValueError(f"Repeated element ID in feature input: {element}")
        seen_elements.add(element)
        if not isinstance(tokens, list) or any(not isinstance(value, str) or not value for value in tokens):
            raise ValueError(f"Invalid token array for element {element}")
        counts = row.get("counts")
        if counts is None:
            features = Counter(tokens)
        else:
            if len(tokens) != len(counts) or any(type(count) is not int or count <= 0 for count in counts):
                raise ValueError(f"Invalid positive token counts for element {element}")
            features = Counter()
            for token, count in zip(tokens, counts, strict=True):
                features[token] += count
        groups[family].append((element, features))
    if not groups:
        raise ValueError("No computational families were supplied")
    return groups, len(seen_elements)


@functools.lru_cache(maxsize=200_000)
def projection(token):
    raw = hashlib.blake2b(token.encode(), digest_size=8, person=b"VEDIC-v1").digest()
    return int.from_bytes(raw[:4], "little"), (1 if raw[4] & 1 else -1)


def representations(groups, dimension):
    ids = np.asarray(sorted(groups), dtype=np.int64)
    docs = []
    document_frequency = Counter()
    for family in ids:
        # Same-logic element variants keep their shared family identity.
        document = Counter()
        for _, features in sorted(groups[family]):
            document |= features
        docs.append(document)
        document_frequency.update(document.keys())
    idf = {k: np.log((1 + len(ids)) / (1 + frequency)) + 1
           for k, frequency in document_frequency.items()}
    matrix = np.zeros((len(ids), dimension), dtype=np.float32)
    metadata = []
    for index, (family, document) in enumerate(zip(ids, docs, strict=True)):
        terms = sorted(document.items())
        fingerprint = hashlib.sha256(json.dumps(terms, separators=(",", ":"), ensure_ascii=False)
                                      .encode()).hexdigest() if terms else None
        for term, count in terms:
            bucket, sign = projection(term)
            matrix[index, bucket % dimension] += sign * (1 + np.log(count)) * idf[term]
        metadata.append({
            "family_id": int(family),
            "representative_element_id": min(element for element, _ in groups[family]),
            "element_count": len(groups[family]),
            "term_count": len(terms),
            "unprojected_feature_sha256": fingerprint,
        })
    norms = np.linalg.norm(matrix, axis=1)
    active = norms > 0
    matrix[active] /= norms[active, None]
    return ids, matrix, active, metadata, len(document_frequency)


def device_score(cp, kernel, data, begin, rows):
    n, dimension = data.shape
    scores = cp.empty((rows, n), dtype=cp.float32)
    kernel(((n + 15) // 16, (rows + 15) // 16), (16, 16),
           (data, scores, np.int32(n), np.int32(dimension), np.int32(begin), np.int32(rows)))
    return scores


def ranked_neighbors(cp, scores, index, active, top_k):
    count = scores.shape[1]
    scores[~active[index], :] = -cp.inf
    scores[:, ~active] = -cp.inf
    rows = cp.arange(len(index), dtype=cp.int32)
    scores[rows, index] = -cp.inf
    # Preserve score order, then resolve exact float32 ties by existing ascending ID order.
    bits = scores.view(cp.uint32)
    ordered = bits ^ cp.where(bits & cp.uint32(0x80000000),
                              cp.uint32(0xFFFFFFFF), cp.uint32(0x80000000))
    priority = (ordered.astype(cp.uint64) << 32) | (np.uint64(count) - cp.arange(count, dtype=cp.uint64))
    indices = cp.empty((len(index), top_k), dtype=cp.int32)
    values = cp.empty((len(index), top_k), dtype=cp.float32)
    for rank in range(top_k):
        chosen = cp.argmax(priority, axis=1)
        indices[:, rank] = chosen
        values[:, rank] = scores[rows, chosen]
        priority[rows, chosen] = 0
    return indices.get(), values.get()


def benchmark(cp, kernel, matrix):
    rows = min(2048, len(matrix))
    sample = np.ascontiguousarray(matrix[np.linspace(0, len(matrix) - 1, rows, dtype=int)])
    cp.cuda.Stream.null.synchronize()
    bench_started = perf_counter()
    device = cp.asarray(sample)
    start, finish = cp.cuda.Event(), cp.cuda.Event()
    start.record()
    values = device_score(cp, kernel, device, 0, rows)
    finish.record()
    finish.synchronize()
    gpu_ms = cp.cuda.get_elapsed_time(start, finish)
    observed = values.get()
    gpu_total = perf_counter() - bench_started
    cpu_started = perf_counter()
    expected = sample @ sample.T
    cpu_seconds = perf_counter() - cpu_started
    error = np.abs(expected - observed)
    close = bool(np.allclose(expected, observed, atol=2e-5, rtol=2e-5))
    if not close:
        raise RuntimeError("GPU cosine failed NumPy parity")
    return {
        "families": rows, "score_cells": rows**2, "numpy_score_seconds": cpu_seconds,
        "gpu_kernel_seconds": gpu_ms / 1000, "gpu_transfer_inclusive_seconds": gpu_total,
        "numpy_over_transfer_inclusive_ratio": cpu_seconds / gpu_total,
        "max_absolute_score_difference": float(error.max()), "numpy_parity": close,
        "threshold_mask_disagreements": {
            str(t): int(np.count_nonzero((expected >= t) != (observed >= t))) for t in THRESHOLDS
        },
    }


def matrix_scan(cp, kernel, matrix, active, tile_rows, top_k):
    n = len(matrix)
    memory = cp.get_default_memory_pool()
    uploaded = cp.asarray(matrix)
    gpu_active = cp.asarray(active)
    live_columns = cp.arange(n, dtype=cp.int32)
    ranks = np.empty((n, top_k), dtype=np.int32)
    values = np.empty((n, top_k), dtype=np.float32)
    totals = np.zeros(len(THRESHOLDS), dtype=np.int64)
    score_seconds = 0.0
    peak_pool = memory.total_bytes()
    for begin in range(0, n, tile_rows):
        step = min(tile_rows, n - begin)
        index = cp.arange(begin, begin + step, dtype=cp.int32)
        start, finish = cp.cuda.Event(), cp.cuda.Event()
        start.record()
        scores = device_score(cp, kernel, uploaded, begin, step)
        finish.record()
        cp.clip(scores, -1, 1, out=scores)
        upper = gpu_active[index, None] & gpu_active[None, :] & (index[:, None] < live_columns)
        counts = cp.stack([cp.count_nonzero((scores >= threshold) & upper) for threshold in THRESHOLDS])
        totals += counts.get()
        ranks[begin:begin+step], values[begin:begin+step] = ranked_neighbors(
            cp, scores, index, gpu_active, top_k)
        score_seconds += cp.cuda.get_elapsed_time(start, finish) / 1000
        peak_pool = max(peak_pool, memory.total_bytes())
        del scores, upper, counts
    return ranks, values, totals, score_seconds, peak_pool


def sparse_components(ids, target, values, limit):
    count, top_k = target.shape
    start = np.repeat(np.arange(count), top_k)
    end = target.ravel()
    good = np.isfinite(values.ravel()) & (values.ravel() >= limit)
    graph = coo_matrix((np.ones(np.count_nonzero(good), dtype=np.uint8),
                       (start[good], end[good])), shape=(count, count)).tocsr()
    _, components = connected_components(graph, directed=False)
    size = np.bincount(components)
    rep = np.full(len(size), np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(rep, components, ids)
    return (pa.table({
        "family_id": ids, "component_representative_family_id": rep[components],
        "component_size": size[components],
    }), {"threshold": limit, "non_singleton_components": int((size > 1).sum()),
         "families_in_non_singleton_components": int(size[size > 1].sum()),
         "retained_directed_edges": int(good.sum())})


def neighbor_table(ids, target, values):
    count, top_k = target.shape
    row = np.repeat(ids, top_k)
    cols = ids[target.ravel()]
    scores = values.ravel()
    order = np.tile(np.arange(1, top_k + 1, dtype=np.int16), count)
    enabled = np.isfinite(scores)
    return pa.table({"family_id": row[enabled], "neighbor_family_id": cols[enabled],
                     "cosine": scores[enabled], "rank": order[enabled]})


def analyse(input_path, output, dimension, tile_rows, requested_top):
    import cupy as cp

    if output.exists():
        raise ValueError("Choose a new immutable output directory")
    if not (dimension % 16 == 0 and 16 <= dimension <= 4096
            and 16 <= tile_rows <= 512 and 1 <= requested_top <= 64):
        raise ValueError("Invalid feature dimension, tile size or neighbor count")
    digest = sha256_file(input_path)
    started = perf_counter()
    groups, elements = read_features(input_path)
    ids, matrix, active, metadata, unique_terms = representations(groups, dimension)
    if len(ids) < 2 or np.count_nonzero(active) < 2:
        raise ValueError("At least two nonempty families are required")
    encode_seconds = perf_counter() - started
    if digest != sha256_file(input_path):
        raise ValueError("Feature input changed during processing")
    memory_free, memory_total = cp.cuda.runtime.memGetInfo()
    estimated_memory = matrix.nbytes + tile_rows * len(ids) * 40
    if estimated_memory > memory_free // 2:
        raise MemoryError("Tile and feature estimate exceeds half available VRAM")
    kernel = cp.RawKernel(COSINE_CUDA, "cosine")
    warm = cp.asarray(matrix[:16])
    device_score(cp, kernel, warm, 0, len(warm))
    cp.cuda.Stream.null.synchronize()
    bench = benchmark(cp, kernel, matrix)
    cp.get_default_memory_pool().free_all_blocks()
    top_k = min(requested_top, len(ids) - 1)
    start = perf_counter()
    ranks, values, totals, score_seconds, pool_peak = matrix_scan(
        cp, kernel, matrix, active, tile_rows, top_k)
    wall_scan = perf_counter() - start
    clusters, cluster_counts = sparse_components(ids, ranks, values, 0.92)
    neighbors = neighbor_table(ids, ranks, values)
    counts = Counter(row["unprojected_feature_sha256"] for row in metadata
                     if row["unprojected_feature_sha256"] is not None)
    n = len(ids)
    evaluated = int(np.count_nonzero(active))
    summary = {
        "schema": "vedic.family-similarity.v1", "feature_method": POLICY,
        "feature_sha256": digest, "families": n, "nonempty_families": evaluated, "elements": elements,
        "unique_input_terms": unique_terms, "dimensions": dimension, "tile_rows": tile_rows,
        "neighbors_per_family_cap": top_k, "neighbor_rows": neighbors.num_rows,
        "computed_gpu_score_cells_including_diagonal_and_empty": n * n,
        "ordered_nonself_nonempty_comparisons": evaluated * (evaluated - 1),
        "unique_nonself_nonempty_pairs": evaluated * (evaluated - 1) // 2,
        "threshold_totals_unique_unordered": {str(k): int(v) for k, v in zip(THRESHOLDS, totals, strict=True)},
        "families_with_multiple_producer_elements": sum(len(rows) > 1 for rows in groups.values()),
        "equal_unprojected_feature_buckets": sum(count > 1 for count in counts.values()),
        "families_in_equal_unprojected_feature_buckets": sum(count for count in counts.values() if count > 1),
        "feature_and_normalization_seconds": encode_seconds, "gpu_score_kernel_seconds": score_seconds,
        "scan_wall_seconds": wall_scan,
        "ordered_valid_comparisons_per_scan_second": evaluated * (evaluated - 1) / wall_scan,
        "observed_cupy_pool_bytes_including_cached_blocks": pool_peak,
        "gpu_vram_free_before_bytes": memory_free, "gpu_vram_total_bytes": memory_total,
        "benchmark": bench, "graph": cluster_counts,
        "limits": [
            "Family IDs come from input. Equal token/count fingerprints are not equal source bytes.",
            "All dot products are exhaustive at the chosen projected float32 representation.",
            "Projection collisions and recorded runtime context can change relationships.",
            "Sparse connected components use retained neighbors, and transitive membership is not equivalence.",
            "Benchmarked fixed feature scoring, not source extraction, English, or program execution.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".family-sim-", dir=output.parent) as temp:
        staged = Path(temp) / "release"
        staged.mkdir()
        tables = {"families": pa.Table.from_pylist(metadata),
                  "neighbors": neighbors, "clusters": clusters}
        for name, table in tables.items():
            pq.write_table(table, staged / f"{name}.parquet", compression="zstd")
        summary["artifacts"] = {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sorted(staged.glob("*.parquet"))
        }
        (staged / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        os.rename(staged, output)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--tile", type=int, default=192)
    parser.add_argument("--top-k", type=int, default=12)
    args = parser.parse_args()
    print(json.dumps(analyse(args.input, args.output, args.dimensions, args.tile, args.top_k), indent=2))


if __name__ == "__main__":
    main()
