import unittest
from stars_retrieval import git_blob, load_library, Index, tokens


def row(f, symbol, code):
    return (f"// Family #{f} · element #{f} · 3 places in 2 repositories · "
            f"https://github.com/Ventusltd/testcode/blob/{'a'*40}/math.js#L1-L3\n"
            f"export const f{f}_{symbol} = {code};\n\n")


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.raw = (row(12, "voltageOf", "function(n){return n.voltage_kv}") +
                    row(20, "ratingsOf", "function(n){return n.winter_mva}") +
                    row(10, "voltageOf", "function(n){return n.voltage_kv}")).encode()

    def load(self, raw=None, count=3):
        raw = self.raw if raw is None else raw
        return load_library(raw, git_blob(raw), count)

    def test_camel_case(self):
        self.assertEqual(tokens("DCVoltage_drop"), ["dc", "voltage", "drop"])

    def test_exact_pins_and_census(self):
        records = self.load()
        self.assertEqual([r["family_id"] for r in records], [12,20,10])
        self.assertTrue(records[0]["source_url"].endswith("#L1-L3"))

    def test_tampering(self):
        with self.assertRaisesRegex(ValueError, "blob mismatch"):
            load_library(self.raw+b"x", git_blob(self.raw), 3)

    def test_wrong_count(self):
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            self.load(count=2)

    def test_duplicate_family(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.load(self.raw+row(12,"again","function(){}").encode(), 4)

    def test_export_identity_mismatch(self):
        with self.assertRaisesRegex(ValueError, "family mismatch"):
            self.load(self.raw.replace(b"f12_voltageOf", b"f13_voltageOf"))

    def test_boundary(self):
        with self.assertRaisesRegex(ValueError, "boundary"):
            self.load(self.raw.rstrip().rstrip(b";"))

    def test_retrieval_and_ties(self):
        q = Index(self.load()).query("voltage")
        self.assertEqual([r["family_id"] for r in q["results"][:2]], [10,12])
        self.assertEqual(q["top_score_margin"], 0)
        self.assertIsNone(q["auto_selection"])
        self.assertEqual(q["state"], "REVIEW_REQUIRED_UNCALIBRATED")
        self.assertNotIn("features", q["results"][0])

    def test_unknown(self):
        q = Index(self.load()).query("zzunseenword")
        self.assertEqual(q["state"], "NO_MATCH")
        self.assertEqual(q["results"], [])

    def test_unknown_terms_preserved(self):
        q = Index(self.load()).query("winter zzunseenword")
        self.assertEqual(q["unknown_terms"], ["zzunseenword"])
        self.assertEqual(q["results"][0]["family_id"],20)

    def test_deterministic(self):
        idx = Index(self.load())
        self.assertEqual(idx.query("voltage winter"), idx.query("voltage winter"))

    def test_invalid_limit(self):
        with self.assertRaises(ValueError):
            Index(self.load()).query("voltage",0)


if __name__ == "__main__":
    unittest.main()
