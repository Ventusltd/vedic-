import datetime as dt
import hashlib
import unittest

from daily_intelligence import MAX_BYTES, discover

SOURCE = b"def count_sites(rows) -> int:\n    return len(rows)\n"
PIN = {"repo": "Ventusltd/fixture", "commit": "a" * 40, "path": "unit.py",
       "blob": hashlib.sha1(f"blob {len(SOURCE)}\0".encode() + SOURCE).hexdigest()}
DAY = dt.date(2026, 11, 26)


class DailyCommandTests(unittest.TestCase):
    def run_case(self, rows=(), raw=SOURCE, pin=PIN):
        return discover(raw, {"schema": "vedic.dictionary.v1", "entries": list(rows)},
                        DAY, pin, ("count_sites",))

    def test_replays_and_reports_function_range(self):
        result = self.run_case()
        self.assertEqual(result, self.run_case())
        self.assertEqual(result["candidate"]["parameters"], ["rows"])
        self.assertEqual(result["candidate"]["output_annotation"], "int")
        self.assertEqual((result["source"]["first"], result["source"]["last"]), (1, 2))

    def test_existing_alias_and_span_produce_no_change(self):
        for row in (
            {"word": "SITE TOTAL", "aliases": ["Count Sites"], "gg_id": "ID"},
            {"word": "ROW TOTAL", "source": {**PIN,"first":1,"last":2}, "gg_id": "ID"},
        ):
            result = self.run_case([row])
            self.assertEqual(result["status"], "no_change")
            self.assertIsNone(result["candidate"])
            self.assertEqual(result["existing_matches"], ["ID"])

    def test_rejects_modified_oversized_and_ambiguous_sources(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            self.run_case(raw=SOURCE + b"\n")
        with self.assertRaisesRegex(ValueError, "byte budget"):
            self.run_case(raw=b"x" * (MAX_BYTES + 1))
        raw = SOURCE * 2
        pin = {**PIN, "blob": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()}
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            self.run_case(raw=raw, pin=pin)

    def test_one_pass_plan_does_not_repeat(self):
        future = DAY + dt.timedelta(days=1)
        result = discover(SOURCE, {"schema": "vedic.dictionary.v1", "entries": []},
                          future, PIN, ("count_sites",))
        self.assertEqual(result["status"], "no_change")
        self.assertIsNone(result["candidate"])
        self.assertEqual(result["checkpoint"], "pinned-plan-exhausted")
