"""Regression checks for producer coordinates and immutable incremental feature reuse."""

from contextlib import closing
import json
import sqlite3
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pyarrow.parquet as pq

from modular_features import digest, extract, selected_text


class TestModularFeatures(unittest.TestCase):
    def test_acorn_utf16_single_and_multi_line_columns(self):
        first = b"before " + "\U0001f600".encode() + b" body\r\n"
        last = b"finish after\n"
        self.assertEqual(selected_text([first], 7, 9), "\U0001f600")
        self.assertEqual(selected_text([first, last], 10, 6), "body\r\nfinish")

    def test_index_identity_and_incremental_reuse(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "modular.sqlite"
            source = b"function ping(){\n  return 1;\n}\n"
            lines = source.splitlines(keepends=True)
            with closing(sqlite3.connect(db)) as cx:
                cx.executescript("""
                    CREATE TABLE line(n INTEGER, text BLOB);
                    CREATE TABLE tablet(n INTEGER, git_blob TEXT, lines BLOB);
                    CREATE TABLE family(n INTEGER, sha BLOB, lang TEXT);
                    CREATE TABLE element(n INTEGER, family INTEGER, sha BLOB, kind TEXT,
                                         needs TEXT, standalone INTEGER);
                    CREATE TABLE tablet_element(tablet INTEGER, element INTEGER, first INTEGER,
                                                 last INTEGER, col0 INTEGER, col1 INTEGER, name TEXT);
                    CREATE TABLE occurrence(tablet INTEGER, repo TEXT, commit_sha TEXT, path TEXT);
                    CREATE TABLE scan(repo TEXT, commit_sha TEXT);
                """)
                cx.executemany("INSERT INTO line VALUES (?,?)", enumerate(lines, start=1))
                cx.execute("INSERT INTO tablet VALUES (?,?,?)", (123, "a"*40, struct.pack("<III", 1, 2, 3)))
                cx.execute("INSERT INTO family VALUES (?,?,?)", (81, bytes.fromhex("1"*64), "js"))
                cx.execute("INSERT INTO element VALUES (?,?,?,?,?,?)",
                           (321, 81, bytes.fromhex(digest(source)), "function", "[]", 1))
                cx.execute("INSERT INTO tablet_element VALUES (?,?,?,?,?,?,?)",
                           (123, 321, 1, 3, 0, 1, "ping"))
                cx.execute("INSERT INTO occurrence VALUES (?,?,?,?)",
                           (123, "Ventusltd/test", "b"*40, "src/utils.js"))
                cx.execute("INSERT INTO scan VALUES (?,?)", ("Ventusltd/test", "b"*40))
                cx.commit()
            first, second = root/"first.parquet", root/"second.parquet"
            extract(db, first, 1, None)
            report = extract(db, second, 1, None, first)
            self.assertEqual(report["reused_elements"], 1)
            entry = pq.read_table(second).to_pylist()[0]
            self.assertEqual((entry["family_id"], entry["element_id"]), (81, 321))
            self.assertIn("literal:number", entry["tokens"])
            first.with_suffix(".json").write_text(json.dumps({"parquet_sha256": "0"*64}))
            with self.assertRaises(ValueError):
                extract(db, root/"rejected.parquet", 1, None, first)
