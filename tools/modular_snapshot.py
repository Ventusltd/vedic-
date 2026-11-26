"""Read-only Modular Star consumer. No producer writes and no ID allocation."""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import sqlite3
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path

PRODUCER = "Ventusltd/stars"
TAG = "modular-star"
ASSET = "modular.sqlite.gz"
MAX_BYTES = 4 * 1024**3
TABLES = ("line", "tablet", "family", "element", "tablet_element", "occurrence", "scan")

def require(ok, message):
    if not ok:
        raise ValueError(message)

def gh(*args):
    return subprocess.check_output(["gh", *args], timeout=300)

def metadata():
    release = json.loads(gh("api", f"repos/{PRODUCER}/releases/tags/{TAG}"))
    assets = [a for a in release["assets"] if a["name"] == ASSET and a["state"] == "uploaded"]
    require(len(assets) == 1, "expected exactly one completed database asset")
    a = assets[0]
    return {"release_id": release["id"], "asset_id": a["id"], "size": a["size"],
            "updated_at": a["updated_at"], "digest": a.get("digest")}

def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def unpack_snapshot(compressed, database, before, after):
    require(before == after, "producer asset changed during download; retry later")
    require(compressed.stat().st_size == before["size"], "asset size mismatch")
    require(0 < before["size"] <= MAX_BYTES, "compressed size outside bound")
    compressed_hash = sha256(compressed)
    if before["digest"] is not None:
        require(before["digest"] == "sha256:" + compressed_hash, "asset digest mismatch")
    written = 0
    with gzip.open(compressed, "rb") as src, database.open("xb") as dst:
        while chunk := src.read(1024 * 1024):
            written += len(chunk)
            require(written <= MAX_BYTES, "uncompressed database exceeds bound")
            dst.write(chunk)
    return {"compressed_sha256": compressed_hash, "database_sha256": sha256(database),
            "database_bytes": written, "asset_digest_verified": before["digest"] is not None}

def inventory(database):
    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        require(db.execute("PRAGMA quick_check").fetchall() == [("ok",)], "SQLite integrity check failed")
        names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require(set(TABLES) <= names, "producer schema incompatible")
        counts = {table: db.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in TABLES}
        require(counts["line"] > 0 and counts["tablet"] > 0, "empty producer inventory")
        repos = db.execute("SELECT count(DISTINCT repo) FROM occurrence").fetchone()[0]
        return {"producer_inventory": counts, "repositories_with_occurrences": repos,
                "translated_unique_lines": None, "active_application_unique_lines": None,
                "scope": "Producer database inventory, including historical occurrences; not VEDIC translation coverage."}

def acquire(output):
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), "refuse to overwrite existing receipt")
    with tempfile.TemporaryDirectory(prefix="vedic-stars-") as directory:
        temp = Path(directory)
        before = metadata()
        require(0 < before["size"] <= MAX_BYTES, "asset size outside bound")
        gh("release", "download", TAG, "--repo", PRODUCER, "--pattern", ASSET, "--dir", str(temp))
        after = metadata()
        database = temp / "modular.sqlite"
        hashes = unpack_snapshot(temp / ASSET, database, before, after)
        report = {"schema": "vedic.modular-snapshot.v1", "producer": PRODUCER, "release_tag": TAG,
                  "asset": ASSET, "metadata": before, "snapshot": hashes,
                  "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(), **inventory(database)}
        with output.open("x", encoding="utf-8") as f:
            json.dump(report, f, sort_keys=True, indent=2)
            f.write("\n")
        return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(acquire(args.output), indent=2))
