"""Project deterministic CPU features from the existing immutable Modular Star inventory."""

import argparse
import ast
from collections import Counter, defaultdict
from contextlib import closing
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
import textwrap
from time import perf_counter, process_time

import pyarrow as pa
import pyarrow.parquet as pq

from extract import atomic_write

VERSION = "modular-feature-v1"
TOKEN = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|'
    r'[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|===|!==|=>|==|!=|<=|>=|&&|\|\||\?\?|'
    r'\?\.|\*\*|[-+*/%&|^!<>?:=.,;{}()\[\]]'
)
NON_PRODUCTION = re.compile(r"(?:^|/)(?:vendor|node_modules|fixtures|tests?|generated|attic|archive)(?:/|$)")
GENERATED = re.compile(r"(?:\.min\.|/generated/|(?:^|/)bundle\.)")
WORD_SPLIT = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[_\W]+")
STRINGS = ("repository", "commit", "blob", "path", "symbol", "kind", "lang", "element_sha256",
           "family_sha256", "path_role", "signature", "docstring", "feature_status", "lexer")
NUMBERS = ("element_id", "family_id", "tablet_id", "first_line", "last_line", "col0", "col1")
SCHEMA = pa.schema([(name, pa.int64()) for name in NUMBERS]
                   + [(name, pa.string()) for name in STRINGS]
                   + [("tokens", pa.list_(pa.string())), ("needs", pa.list_(pa.string())),
                      ("refusal_markers", pa.list_(pa.string())), ("constants", pa.list_(pa.string())),
                      ("standalone_candidate", pa.bool_()), ("tokens_truncated", pa.bool_())])
DB = None


def connect(db):
    return sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def init_worker(db):
    global DB
    DB = connect(db)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def path_rank(repo, path, is_current):
    lower = path.lower()
    if GENERATED.search(lower):
        return (8, "generated_path_hint")
    if NON_PRODUCTION.search(lower):
        return (7, "vendor_test_archive_path_hint")
    if "/releases/" in lower or lower.startswith(("editions/", "history/")):
        return (6, "historical_path_hint")
    if repo.lower().endswith("ventus-grid-engine") and is_current and lower.startswith("engine/"):
        return (0, "canonical_engine_path_candidate")
    if is_current:
        return (1, "current_snapshot_path_candidate")
    return (3, "indexed_snapshot_path_candidate")


def plan(conn, limit):
    eligible = conn.execute(
        """SELECT e.n, e.family, hex(e.sha), hex(f.sha), e.kind, e.needs, e.standalone, f.lang
           FROM element e JOIN family f ON e.family=f.n ORDER BY e.n LIMIT ?""",
        (limit or -1,),
    )
    elements = {row[0]: row for row in eligible}
    locations = {}
    # One representative path per unchanged file version; all other occurrences
    # remain addressable by tablet_id in the original Modular Star database.
    for tablet, repo, revision, path, is_current in conn.execute(
        """SELECT o.tablet,o.repo,o.commit_sha,o.path,o.commit_sha=s.commit_sha
           FROM occurrence o LEFT JOIN scan s ON o.repo=s.repo"""
    ):
        priority, role = path_rank(repo, path, is_current)
        choice = (priority, repo, path, revision, role)
        if tablet not in locations or choice < locations[tablet]:
            locations[tablet] = choice
    choices = {}
    for tablet, element, first, last, col0, col1, name in conn.execute(
        """SELECT tablet,element,first,last,col0,col1,name FROM tablet_element"""
    ):
        if element not in elements or tablet not in locations:
            continue
        rank = (locations[tablet], tablet, first, last, -1 if col0 is None else col0, name or "")
        if element not in choices or rank < choices[element][0]:
            choices[element] = (rank, tablet, first, last, col0, col1, name)
    if choices.keys() != elements.keys():
        raise ValueError("Some existing elements have no indexed source occurrence")
    groups = defaultdict(list)
    for element, (rank, tablet, first, last, col0, col1, name) in choices.items():
        _, repo, path, revision, role = rank[0]
        _, family, element_hash, family_hash, kind, needs, standalone, lang = elements[element]
        groups[tablet].append({
            "element_id": element, "family_id": family, "tablet_id": tablet,
            "first_line": first, "last_line": last, "col0": col0, "col1": col1,
            "repository": repo, "commit": revision, "path": path, "symbol": name,
            "path_role": role, "element_sha256": element_hash.lower(),
            "family_sha256": family_hash.lower(), "kind": kind, "lang": lang,
            "needs": json.loads(needs) if needs else None, "standalone_candidate": bool(standalone),
        })
    return groups


def utf16_slice(text, start=None, stop=None):
    return text.encode("utf-16-le")[slice(None if start is None else start * 2,
                                             None if stop is None else stop * 2)].decode("utf-16-le")


def selected_text(lines, start, stop):
    parts = [line.decode("utf-8", errors="replace") for line in lines]
    if start is None or stop is None:
        return "".join(parts)
    if len(parts) == 1:
        return utf16_slice(parts[0], start, stop)
    return utf16_slice(parts[0], start) + "".join(parts[1:-1]) + utf16_slice(parts[-1], stop=stop)


def feature_row(row, text):
    kind = row["kind"] or "unknown"
    features = ["kind:" + kind, "lang:" + row["lang"]]
    signature = next((line.strip()[:240] for line in text.splitlines() if line.strip()), "")
    markers = sorted(set(re.findall(r"\b(?:throw|raise|assert)\b|return\s+(?:null|None)\b", text)))
    constants = []
    doc = None
    if row["lang"] == "py":
        try:
            tree = ast.parse(textwrap.dedent(text))
            first = tree.body[0] if tree.body else None
            if isinstance(first, (ast.FunctionDef, ast.AsyncFunctionDef)):
                signature = f"{first.name}({ast.unparse(first.args)})"
            if isinstance(first, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = (ast.get_docstring(first) or "")[:1024] or None
            features.extend("ast:" + type(node).__name__ for node in ast.walk(tree))
        except (SyntaxError, ValueError, RecursionError):
            pass
    for value in (row["symbol"] or "", *(row["needs"] or [])):
        features.extend("symbol:" + word.lower() for word in WORD_SPLIT.split(value) if word)
    sequence = []
    for token in TOKEN.findall(text):
        if token.startswith(("//", "/*")):
            continue
        if token[0] in "\"'":
            sequence.append("literal:string")
        elif token[0].isdigit():
            sequence.append("literal:number")
            if len(constants) < 20 and token not in constants:
                constants.append(token)
        elif token[0].isalpha() or token[0] in "_$":
            sequence.append("id:" + token.lower())
        else:
            sequence.append("op:" + token)
    truncated = len(sequence) > 512 or len(features) > 512
    sequence = sequence[:512]
    features = features[:512] + sequence
    features.extend("pair:" + a + "|" + b for a, b in zip(sequence, sequence[1:]))
    return {**row, "tokens": features, "signature": signature, "docstring": doc,
            "constants": constants, "refusal_markers": markers,
            "tokens_truncated": truncated, "lexer": "bounded_lexical_ngrams_with_indexed_structure",
            "feature_status": "source_span_reconstructed"}


def process_tablet(task):
    tablet, rows = task
    started = process_time()
    blob, packed = DB.execute("SELECT git_blob,lines FROM tablet WHERE n=?", (tablet,)).fetchone()
    numbers = [item[0] for item in struct.iter_unpack("<I", packed)]
    wanted = sorted({number for row in rows for number in numbers[row["first_line"]-1:row["last_line"]]})
    lines = {}
    for offset in range(0, len(wanted), 500):
        batch = wanted[offset:offset + 500]
        placeholders = ",".join("?" for _ in batch)
        lines.update(DB.execute(f"SELECT n,text FROM line WHERE n IN ({placeholders})", batch))
    out = []
    for row in rows:
        raw = [lines[n] for n in numbers[row["first_line"]-1:row["last_line"]]]
        if not raw or digest(b"".join(raw)) != row["element_sha256"]:
            raise ValueError(f"Indexed source hash mismatch for element {row['element_id']}")
        body = selected_text(raw, row["col0"], row["col1"])
        out.append(feature_row({**row, "blob": blob}, body))
    return out, process_time() - started


KEYS = ("element_id", "family_id", "element_sha256", "family_sha256", "repository",
        "commit", "path", "first_line", "last_line", "col0", "col1", "symbol",
        "path_role", "kind", "lang", "needs", "standalone_candidate")


def extract(db, output, workers, limit, prior=None):
    if output.exists():
        raise ValueError("Refusing to replace frozen output")
    start = perf_counter()
    with closing(connect(db)) as conn:
        groups = plan(conn, limit)
    plan_seconds = perf_counter() - start
    cached = {}
    if prior is not None:
        receipt = json.loads(prior.with_suffix(".json").read_text(encoding="utf-8"))
        if receipt.get("parquet_sha256") != digest(prior.read_bytes()):
            raise ValueError("Incremental feature input differs from its frozen manifest")
        table = pq.read_table(prior)
        if (table.schema.metadata or {}).get(b"feature_version", b"").decode() != VERSION:
            raise ValueError("Cannot reuse features from a different schema version")
        cached = {row["element_id"]: row for row in table.to_pylist()}
    result = []
    remaining = []
    cached_count = 0
    for tablet, rows in sorted(groups.items()):
        needs_work = []
        for row in rows:
            hit = cached.get(row["element_id"])
            if hit is not None and all(hit.get(key) == row.get(key) for key in KEYS):
                result.append(hit)
                cached_count += 1
            else:
                needs_work.append(row)
        if needs_work:
            remaining.append((tablet, needs_work))
    cpu = 0
    if remaining:
        if workers == 1:
            init_worker(db)
            try:
                for rows, seconds in map(process_tablet, remaining):
                    result.extend(rows)
                    cpu += seconds
            finally:
                DB.close()
        else:
            with ProcessPoolExecutor(max_workers=workers, initializer=init_worker, initargs=(db,)) as pool:
                for rows, seconds in pool.map(process_tablet, remaining, chunksize=12):
                    result.extend(rows)
                    cpu += seconds
    result.sort(key=lambda row: row["element_id"])
    table = pa.Table.from_pylist(result, schema=SCHEMA).replace_schema_metadata({b"feature_version": VERSION.encode()})
    atomic_write(output, lambda temporary: pq.write_table(table, temporary, compression="zstd"))
    report = {
        "feature_version": VERSION, "workers": workers, "planning_wall_seconds": plan_seconds,
        "cpu_worker_seconds": cpu, "wall_seconds": perf_counter() - start,
        "elements": len(result), "families": len({row["family_id"] for row in result}),
        "selected_tablets": len(groups), "reused_elements": cached_count,
        "lexically_truncated_elements": sum(row["tokens_truncated"] for row in result),
        "roles": dict(Counter(row["path_role"] for row in result)),
        "parquet_sha256": digest(output.read_bytes()), "parquet_bytes": output.stat().st_size,
        "identity_basis": "Existing Modular Star element and family IDs; reconstructed span bytes verified against element SHA-256.",
    }
    atomic_write(output.with_suffix(".json"), lambda t: t.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite", type=Path)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reuse", type=Path)
    args = parser.parse_args()
    if args.workers < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Worker and sample limits must be positive")
    print(json.dumps(extract(args.sqlite, args.parquet, args.workers, args.limit, args.reuse), indent=2))


if __name__ == "__main__":
    main()
