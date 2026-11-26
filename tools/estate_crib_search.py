"""VEDIC Virtualised Particle Accelerator command-group search."""

import argparse
from collections import Counter, defaultdict
import functools
import hashlib
import itertools
import json
from pathlib import Path
import random
import sqlite3
from time import perf_counter

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from dictionary_shards import tokens


# Each group needs an object clue and evidence of the operation or two object clues.
GROUPS = (
    ("MEASURE GEODESIC DISTANCE", "measure calculate compute distance haversine", "haversine geodesic spherical distance radius earth"),
    ("FIND INITIAL BEARING", "find calculate compute bearing", "bearing azimuth heading geodesic"),
    ("CHECK GRID CAPACITY", "check assess calculate estimate capacity", "capacity firm transformer substation mva contingency"),
    ("SIZE ENERGY STORAGE", "size sizing model estimate calculate simulate optimise", "battery bess storage charge discharge peak shaving"),
    ("CALCULATE ELECTRICAL POWER", "calculate compute measure convert solve", "power watts megawatt apparent reactive factor current mva"),
    ("ESTIMATE ELECTRICAL LOSSES", "estimate calculate compute measure", "resistance impedance voltage drop losses thermal cable"),
    ("CONVERT MAP COORDINATES", "convert transform project resolve", "latitude longitude coordinates easting northing mercator tile bbox"),
    ("DRAW MAP FEATURES", "draw build render create add", "geojson polygon circle marker layer geometry feature map"),
    ("FIND PROJECT LOCATIONS", "find nearest locate resolve select", "project repd substation vicinity postcode nearby"),
    ("FILTER PROJECT REGISTER", "filter search select rank match", "project repd register application source status capacity"),
    ("BUILD PROJECT MAP LINKS", "build encode link parse resolve", "deeplink permalink href project arrival navigation selection"),
    ("LOAD COLUMNAR DATA", "load read fetch import query scan", "parquet arrow duckdb dataset table schema"),
    ("VALIDATE SECTOR DATA", "audit validate verify check describe", "sector ledger parquet compression schema dataset integrity"),
    ("VERIFY SOURCE IDENTITY", "verify validate compare check hash", "blob digest sha256 sha1 hash commit checksum source identity"),
    ("BUILD RELEASE MANIFESTS", "build emit stage publish package compose", "manifest release generation artifact receipt package archive"),
    ("TRACK SOURCE PROVENANCE", "record track link resolve audit", "provenance evidence source occurrence licence citation lineage"),
    ("SCHEDULE RETRY REQUESTS", "schedule retry backoff wait throttle fetch", "retry backoff timeout request delay queue budget"),
    ("FILTER AND RANK RECORDS", "filter rank sort match select search", "records rows results items score index candidates feature"),
    ("AGGREGATE DATA RECORDS", "aggregate group count sum average merge combine", "records rows values totals count dataset collection"),
    ("PARSE STRUCTURED DOCUMENTS", "parse decode extract normalize normalise", "json yaml csv ast token html markdown schema input"),
    ("CONTROL MAP VIEW", "move pan zoom rotate center centre fit", "map bounds viewport camera layer zoom bearing scale"),
    ("RENDER USER INTERFACE", "render update draw display build", "panel view button canvas tooltip popup element label html"),
    ("UPDATE APPLICATION STATE", "update set save restore reset apply", "state config preferences session settings storage cache"),
    ("CHECK SOFTWARE BEHAVIOUR", "test assert expect compare check", "fixture test mock expected assertion regression behaviour"),
    ("START APPLICATION", "start boot initialize initialise init launch setup install", "application app module component settings container document window runtime map"),
    ("BUILD INTERFACE LAYOUT", "layout arrange fit position measure resize update", "width height bounds rect screen viewport panel grid flex scale"),
    ("WRITE RESEARCH REPORTS", "write export save summarise summarize format report", "report summary output markdown evidence results receipt csv"),
    ("READ REMOTE DATA", "read fetch request download load get", "response endpoint url headers timeout payload network data"),
    ("RENDER MAP OVERLAYS", "draw render update attach add show", "overlay canvas layer labels opacity markers feature map"),
    ("CREATE ELECTRICAL CIRCUITS", "create build draw connect solve calculate", "circuit string wiring inverter feeder segment breaker busbar"),
    ("MANAGE LOCAL FILES", "open write save read remove replace load", "file files path directory folder cache stream temporary"),
    ("MATCH DATA IDENTIFIERS", "match resolve normalize normalise find parse canonical", "identifier id ref reference key slug alias name"),

)



DOT_CUDA = r"""
extern "C" __global__ void cross_dot(
    const float* rows, const float* weights, float* output, int n, int d, int k
) {
    const int tx = threadIdx.x, ty = threadIdx.y;
    const int row = blockIdx.y * 16 + ty, column = blockIdx.x * 16 + tx;
    __shared__ float a[16][16], b[16][16];
    float sum = 0;
    for (int offset = 0; offset < d; offset += 16) {
        a[ty][tx] = row < n && offset + tx < d ? rows[row*d + offset + tx] : 0;
        b[ty][tx] = column < k && offset + ty < d ? weights[(offset+ty)*k + column] : 0;
        __syncthreads();
        #pragma unroll
        for (int i = 0; i < 16; ++i) sum += a[ty][i] * b[i][tx];
        __syncthreads();
    }
    if (row < n && column < k) output[row*k + column] = sum;
}
"""


@functools.lru_cache(maxsize=200_000)
def split_words(text):
    return frozenset(tokens(text).split())


def feature_matrix(rows, vocabulary):
    matrix = np.zeros((len(rows), len(vocabulary)), dtype=np.float32)
    for index, row in enumerate(rows):
        body = set()
        for term in row["tokens"]:
            if term.startswith("id:"):
                body.update(split_words(term[3:]))
        # Signature and symbol carry more weight than dependencies or body text.
        parts = (
            (body, 1),
            (set().union(*(split_words(name) for name in (row["needs"] or []))), 2),
            (split_words(row["docstring"] or ""), 3),
            (split_words(row["signature"] or ""), 4),
            (split_words(row["symbol"] or ""), 6),
        )
        for words, weight in parts:
            columns = [vocabulary[word] for word in words if word in vocabulary]
            matrix[index, columns] = weight
    return matrix


def build_cribs(vocabulary, variants, seed, frequencies):
    rng = random.Random(seed)
    base_weights = np.zeros((len(vocabulary), len(GROUPS) * 2), dtype=np.float32)
    probe_weights = np.zeros((len(vocabulary), len(GROUPS) * variants), dtype=np.float32)
    menus = {}
    for group, (name, action_text, object_text) in enumerate(GROUPS):
        actions = sorted(set(action_text.split()))
        objects = sorted(set(object_text.split()))
        for role, words in enumerate((actions, objects)):
            for word in words:
                base_weights[vocabulary[word], group * 2 + role] = 1
        # One action and two distinct domain terms per hypothesis.
        choices = list(itertools.product(actions, itertools.combinations(objects, 2)))
        chosen = rng.sample(choices, variants)
        menus[name] = [[verb, *nouns] for verb, nouns in chosen]
        for offset, words in enumerate(menus[name]):
            for word in set(words):
                rarity = frequencies[vocabulary[word]]
                probe_weights[vocabulary[word], group * variants + offset] = (
                    2 if rarity < 100 else 1
                )
    return base_weights, probe_weights, menus


def evaluate(xp, matrix, scores, roles, variants, multiply):
    trials = multiply(matrix, scores).reshape(len(matrix), len(GROUPS), variants)
    role_support = multiply(matrix, roles).reshape(len(matrix), len(GROUPS), 2)
    # Score an eligible group by its strongest crib and independent object support.
    grounded = (role_support[:, :, 1] >= 4) & (role_support[:, :, 0] >= 1)
    strength = trials.max(axis=2) + xp.minimum(role_support[:, :, 1], 15)
    strength = xp.where(grounded, strength, 0)
    winner = xp.argmax(strength, axis=1)
    row = xp.arange(len(matrix))
    best = strength[row, winner]
    ties = xp.count_nonzero(strength == best.reshape(-1, 1), axis=1) > 1
    code = xp.where((best >= 12) & ~ties, winner, -1)
    return xp.stack((code, best, xp.argmax(trials, axis=2)[row, winner]), axis=1)


def select_groups(cp, matrix, base, probes, variants):
    kernel = cp.RawKernel(DOT_CUDA, "cross_dot")

    def multiply(rows, weights):
        n, d = rows.shape
        k = weights.shape[1]
        output = cp.empty((n, k), dtype=cp.float32)
        kernel(((k + 15) // 16, (n + 15) // 16), (16, 16),
               (rows, weights, output, np.int32(n), np.int32(d), np.int32(k)))
        return output

    # Compile separately from the transfer-inclusive comparison.
    warmup = cp.asarray(matrix[:16])
    evaluate(cp, warmup, cp.asarray(probes), cp.asarray(base), variants, multiply)
    cp.cuda.Stream.null.synchronize()
    started = perf_counter()
    device = cp.asarray(matrix)
    scores, roles = cp.asarray(probes), cp.asarray(base)
    start, stop = cp.cuda.Event(), cp.cuda.Event()
    start.record()
    classified = cp.concatenate([
        evaluate(cp, device[i:i + 2048], scores, roles, variants, multiply)
        for i in range(0, len(device), 2048)
    ])
    stop.record()
    result = classified.get().astype(np.int32)
    gpu_seconds = perf_counter() - started
    gpu_kernel = cp.cuda.get_elapsed_time(start, stop) / 1000
    gpu_pool = cp.get_default_memory_pool().total_bytes()
    started = perf_counter()
    expected = np.concatenate([
        evaluate(np, matrix[i:i + 2048], probes, base, variants, np.matmul)
        for i in range(0, len(matrix), 2048)
    ]).astype(np.int32)
    cpu_seconds = perf_counter() - started
    if not np.array_equal(result, expected):
        raise RuntimeError("CuPy and NumPy group attribution differ")
    return result, gpu_seconds, gpu_kernel, cpu_seconds, gpu_pool


def label(code):
    return GROUPS[code][0] if code >= 0 else "REVIEW REQUIRED"


def grouped_families(db, rows, results):
    grouped = defaultdict(Counter)
    present = Counter()
    for row, (code, _, _) in zip(rows, results, strict=True):
        family = row["family_id"]
        present[family] += 1
        if code >= 0:
            grouped[family][int(code)] += 1
    result = []
    for family, hexdigest in db.execute("SELECT n, lower(hex(sha)) FROM family ORDER BY n"):
        groups = grouped[family]
        disposition = "NO LINKED ELEMENT"
        if present[family]:
            disposition = label(next(iter(groups))) if len(groups) == 1 else (
                "MULTIPLE COMMAND GROUPS" if groups else "REVIEW REQUIRED"
            )
        result.append({"family_id": family, "family_sha256": hexdigest,
                       "linked_elements": present[family], "command_group": disposition,
                       "supported_groups": [label(group) for group in sorted(groups)]})
    return result


def grouped_lines(db, codes):
    line_ids = np.fromiter((row[0] for row in db.execute("SELECT n FROM line ORDER BY n")), dtype=np.int64)
    flags = np.zeros(int(line_ids.max()) + 1, dtype=np.uint32)
    seen = np.zeros(len(flags), dtype=bool)
    tablets = {n: np.frombuffer(packed, dtype="<u4")
               for n, packed in db.execute("SELECT n, lines FROM tablet")}
    for tablet, element, first, last in db.execute(
        "SELECT tablet, element, first, last FROM tablet_element"
    ):
        indices = tablets[tablet][first - 1:last]
        seen[indices] = True
        group = codes[element]
        if group >= 0:
            flags[indices] |= np.uint32(1 << group)
    chosen = flags[line_ids]
    labels = np.full(len(line_ids), "UNMAPPED SOURCE LINE", dtype="<U32")
    labels[seen[line_ids]] = "REVIEW REQUIRED"
    labels[(chosen & (chosen - np.uint32(1))) != 0] = "MULTIPLE COMMAND GROUPS"
    for group, (name, _, _) in enumerate(GROUPS):
        labels[chosen == (1 << group)] = name
    return pa.table({"line_id": line_ids, "command_group": labels.tolist()})


def disagreement_rows(prior_path, matches):
    prior_rows = pq.read_table(prior_path, columns=["element_id", "element_sha256", "command_group"]).to_pylist()
    prior = {row["element_id"]: row for row in prior_rows}
    if len(prior) != len(prior_rows) or len(prior) != len(matches):
        raise ValueError("Comparison must cover the same unique elements")
    changed = []
    for row in matches:
        original = prior[row["element_id"]]
        if original["element_sha256"] != row["element_sha256"]:
            raise ValueError("Comparison element source differs")
        if original["command_group"] != row["command_group"]:
            changed.append({**row, "previous_group": original["command_group"]})
    return changed


def vogel_shots(rows, seed, count=8):
    """Use a random rotation and golden-ratio increments on stable-ID order."""
    rows = sorted(rows, key=lambda row: row["element_id"])
    size = len(rows)
    count = min(count, size)
    rotation = random.Random(seed).getrandbits(64)
    step = 0x9E3779B97F4A7C15
    mask = (1 << 64) - 1
    indices = {}
    for index in range(size * 4):
        if len(indices) == count:
            break
        position = ((((rotation + index * step) & mask) * size) >> 64)
        indices[position] = None
    if len(indices) != count:
        raise RuntimeError("Vogel sample did not reach its distinct shot count")
    fields = ("element_id", "family_id", "repository", "commit", "blob", "path",
              "first_line", "last_line", "symbol", "command_group", "previous_group")
    return [{key: rows[i][key] for key in fields if key in rows[i]} for i in indices]


def digest(path):
    with path.open("rb") as raw:
        return hashlib.file_digest(raw, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("features", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=193904)
    parser.add_argument("--compare", type=Path, help="prior elements Parquet for disagreement evidence")
    args = parser.parse_args()

    import cupy as cp

    source_columns = ("element_id", "family_id", "element_sha256", "repository", "commit", "blob", "path",
                      "symbol", "first_line", "last_line", "path_role", "signature", "docstring",
                      "tokens", "needs", "tokens_truncated")
    started = perf_counter()
    rows = pq.read_table(args.features, columns=list(source_columns)).to_pylist()
    vocabulary = {word: index for index, word in enumerate(
        sorted({word for _, actions, objects in GROUPS for word in (actions + " " + objects).split()})
    )}
    matrix = feature_matrix(rows, vocabulary)
    variants = 16
    base, probes, menus = build_cribs(vocabulary, variants, args.seed,
                                     np.count_nonzero(matrix, axis=0))
    feature_seconds = perf_counter() - started
    result, gpu_seconds, gpu_kernel, cpu_seconds, pool = select_groups(cp, matrix, base, probes, variants)
    matches = []
    codes = {}
    export_fields = tuple(key for key in source_columns if key not in {"tokens", "needs", "docstring"})
    for row, (code, score, menu) in zip(rows, result, strict=True):
        code = int(code)
        codes[row["element_id"]] = code
        group = label(code)
        matches.append({**{key: row[key] for key in export_fields}, "command_group": group,
                        "score": int(score), "crib": menus[group][int(menu)] if code >= 0 else []})
    if len(codes) != len(rows):
        raise ValueError("Duplicate source element IDs")
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if {r[0] for r in db.execute("SELECT n FROM element")} != codes.keys():
            raise ValueError("Element coverage differs from the pinned database")
        families = grouped_families(db, rows, result)
        lines = grouped_lines(db, codes)
    args.output.mkdir(parents=True, exist_ok=False)
    tables = {"elements": pa.Table.from_pylist(matches), "families": pa.Table.from_pylist(families), "lines": lines}
    changed = disagreement_rows(args.compare, matches) if args.compare else []
    if changed:
        tables["disagreements"] = pa.Table.from_pylist(changed)
    named = [row for row in matches if row["symbol"] not in {None, "", "(anonymous)"}]
    shots = {
        "survivors": vogel_shots([row for row in named if row["command_group"] != "REVIEW REQUIRED"], args.seed + 1),
        "unresolved": vogel_shots([row for row in named if row["command_group"] == "REVIEW REQUIRED"], args.seed + 2),
        "disagreements": vogel_shots(changed, args.seed + 3),
    }
    (args.output / "vogel-shots.json").write_text(json.dumps(shots, indent=2) + "\n", encoding="utf-8")
    receipts = {}
    for name, table in tables.items():
        path = args.output / (name + ".parquet")
        pq.write_table(table, path, compression="zstd")
        receipts[name] = {"rows": len(table), "bytes": path.stat().st_size, "sha256": digest(path),
                          "counts": dict(Counter(table["command_group"].to_pylist()))}
    manifest = {"schema": "vedic.estate-crib-search.v1", "seed": args.seed, "menus": menus,
                "name": "Virtualised Particle Accelerator",
                "feature_file_sha256": digest(args.features), "database_sha256": digest(args.database),
                "comparison_sha256": digest(args.compare) if args.compare else None,
                "vogel_shots": {key: len(value) for key, value in shots.items()},
                "truncated_element_features": sum(bool(row["tokens_truncated"]) for row in rows),
                "vocabulary_size": len(vocabulary), "hypotheses": probes.shape[1],
                "element_hypothesis_pairs": len(rows) * probes.shape[1], "tables": receipts,
                "feature_seconds": feature_seconds, "numpy_seconds": cpu_seconds,
                "cupy_seconds_including_transfers": gpu_seconds, "cupy_kernel_batch_seconds": gpu_kernel,
                "cupy_pool_bytes": pool, "cpu_gpu_classification_equal": True,
                "scope": "Lexical and source-span leads. Semantic admission and execution require separate evidence."}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "menus"}, indent=2))


if __name__ == "__main__":
    main()
