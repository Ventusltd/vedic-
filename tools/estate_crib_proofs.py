"""Check exact source strings and whole-block identities in a Modular Star snapshot."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import struct

import pyarrow.parquet as pq


def string_matches(database, phrases):
    results = {phrase: [] for phrase in phrases}
    keys = [(phrase, phrase.encode()) for phrase in results]
    for number, raw in database.execute("SELECT n, text FROM line ORDER BY n"):
        for phrase, encoded in keys:
            if encoded in raw:
                results[phrase].append(number)
    return results


def source_block(database, tablet, first, last):
    packed, = database.execute("SELECT lines FROM tablet WHERE n=?", (tablet,)).fetchone()
    ids = [line[0] for line in struct.iter_unpack("<I", packed)][first - 1:last]
    if len(ids) != last - first + 1:
        raise ValueError("Source block is outside the tablet")
    text = {}
    unique = sorted(set(ids))
    for start in range(0, len(unique), 500):
        batch = unique[start:start + 500]
        placeholders = ",".join("?" for _ in batch)
        text.update(database.execute(f"SELECT n, text FROM line WHERE n IN ({placeholders})", batch))
    return ids, hashlib.sha256(b"".join(text[number] for number in ids)).hexdigest()


def block_matches(database, number, phrases):
    digest, family = database.execute("SELECT lower(hex(sha)), family FROM element WHERE n=?", (number,)).fetchone()
    placements = []
    locations = set()
    for tablet, first, last, name in database.execute(
        "SELECT tablet, first, last, name FROM tablet_element WHERE element=? ORDER BY tablet, first", (number,)
    ):
        line_ids, actual = source_block(database, tablet, first, last)
        if actual != digest:
            raise ValueError(f"Whole block digest mismatch for element {number} in tablet {tablet}")
        origins = []
        for repo, commit, path, blob in database.execute(
            """SELECT o.repo, o.commit_sha, o.path, lower(hex(t.git_blob))
               FROM occurrence AS o JOIN tablet AS t ON t.n=o.tablet
               WHERE o.tablet=? ORDER BY o.repo, o.path, o.commit_sha""", (tablet,)
        ):
            locations.add((repo, path))
            origins.append({"repository": repo, "commit": commit, "path": path, "blob": blob})
        phrase_hits = [phrase for phrase, hits in phrases.items() if not set(line_ids).isdisjoint(hits)]
        placements.append({"tablet_id": tablet, "first": first, "last": last, "symbol": name,
                           "exact_strings": phrase_hits, "origins": origins})
    if not placements:
        raise ValueError(f"No whole-block placement for {number}")
    return {"element_id": number, "family_id": family, "physical_block_sha256": digest,
            "tablet_placements": len(placements), "repository_paths": len(locations), "matches": placements}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("groups", type=Path, help="elements.parquet from the accelerator")
    parser.add_argument("output", type=Path)
    parser.add_argument("--phrase", required=True, action="append", help="exact UTF-8 substring of one indexed line")
    parser.add_argument("--block", required=True, type=int, action="append", help="existing Modular Star element ID")
    args = parser.parse_args()
    groups = pq.read_table(args.groups, columns=["element_id", "command_group", "score", "crib"]).to_pylist()
    by_element = {row["element_id"]: row for row in groups}
    with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as database:
        phrases = string_matches(database, args.phrase)
        blocks = [block_matches(database, number, phrases) for number in dict.fromkeys(args.block)]
        lines, = database.execute("SELECT count(*) FROM line").fetchone()
    for block in blocks:
        block["word_and_pattern_result"] = by_element[block["element_id"]]
    result = {"schema": "vedic.estate-crib-proof.v1", "unique_lines_examined": lines,
              "exact_strings": phrases, "whole_block_witnesses": blocks}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({"unique_lines_examined": lines,
                      "string_counts": {key: len(value) for key, value in phrases.items()},
                      "verified_block_placements": {item["element_id"]: item["tablet_placements"] for item in blocks}}))


if __name__ == "__main__":
    main()
