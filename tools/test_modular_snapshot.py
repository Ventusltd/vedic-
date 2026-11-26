import gzip
import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from modular_snapshot import inventory, unpack_snapshot, TABLES

class SnapshotTests(unittest.TestCase):
    def test_read_only_inventory(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.sqlite"
            with closing(sqlite3.connect(p)) as db, db:
                for t in TABLES:
                    db.execute(f'CREATE TABLE "{t}" (repo TEXT)')
                db.execute("INSERT INTO line VALUES ('x')")
                db.execute("INSERT INTO tablet VALUES ('x')")
                db.execute("INSERT INTO occurrence VALUES ('test')")
            before = p.read_bytes()
            result = inventory(p)
            self.assertEqual(result["producer_inventory"]["line"], 1)
            self.assertIsNone(result["translated_unique_lines"])
            self.assertEqual(p.read_bytes(), before)
    def test_missing_schema(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.sqlite"
            with closing(sqlite3.connect(p)) as db, db:
                db.execute("CREATE TABLE other (n INT)")
            with self.assertRaises(ValueError):
                inventory(p)
    def test_snapshot_pin_and_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "snapshot.gz"
            payload = b"test bytes"
            p.write_bytes(gzip.compress(payload, mtime=0))
            meta = {"size": p.stat().st_size, "digest": "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest(), "asset_id": 1}
            result = unpack_snapshot(p, Path(d) / "out", meta, dict(meta))
            self.assertEqual(result["database_sha256"], hashlib.sha256(payload).hexdigest())
            with self.assertRaises(ValueError):
                unpack_snapshot(p, Path(d) / "race", meta, dict(meta, asset_id=2))
            with self.assertRaises(ValueError):
                wrong = dict(meta, digest="sha256:" + "0"*64)
                unpack_snapshot(p, Path(d) / "bad", wrong, wrong)
            self.assertFalse((Path(d) / "race").exists())
