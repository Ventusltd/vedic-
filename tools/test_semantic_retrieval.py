import json
from pathlib import Path
import unittest
from semantic_retrieval import curated_records, search
from stars_retrieval import Index, load_library, git_blob

ROOT = Path(__file__).resolve().parents[1]


class TestSemanticRetrieval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = json.loads((ROOT/"data/dictionary.json").read_text(encoding="utf-8"))
        t = json.loads((ROOT/"data/translation-geodesy.json").read_text(encoding="utf-8"))
        cls.records = curated_records(d,t)
        cls.curated = Index(cls.records, prefer_coverage=True)
        raw = (f"// Family #42 · element #43 · 2 places in 1 repositories · "
               f"https://github.com/Ventusltd/testcode/blob/{'a'*40}/math.js#L1-L3\n"
               "export const f42_distance = function distance(a,b){return a-b;};\n").encode()
        cls.compiled = Index(load_library(raw,git_blob(raw),1))

    def test_census_and_separate_identifiers(self):
        self.assertGreaterEqual(len(self.records),39)
        self.assertTrue(all("family_id" not in x for x in self.records))

    def test_application_bound_present(self):
        q = search(self.curated,self.compiled,"render selected Vicinity asset facts")
        top = q["curated_meanings"]["results"][0]
        self.assertEqual(top["word"],"PRESENT")
        self.assertEqual((top["source"]["first"],top["source"]["last"]),(55,67))
        self.assertIsNone(q["curated_meanings"]["auto_selection"])

    def test_application_bound_browse(self):
        q = self.curated.query("browse ranked asset by swipe")
        self.assertEqual(q["results"][0]["word"],"BROWSE")

    def test_polysemy(self):
        polygon = self.curated.query("spherical polygon area")["results"][0]
        cap = self.curated.query("spherical cap area")["results"][0]
        self.assertEqual((polygon["word"],cap["word"]),("AREA","AREA"))
        self.assertNotEqual(polygon["gg_id"],cap["gg_id"])

    def test_composition(self):
        r = self.curated.query("distance and bearing between two points")["results"][0]
        self.assertEqual(r["word"],"ORIENT")
        self.assertIn("distance", r["matched_terms"])
        self.assertIn("bearing", r["matched_terms"])
        self.assertEqual(len(r["components"]),2)
        self.assertIsNone(r["source"])

    def test_limits_not_positive(self):
        d={"schema":"vedic.dictionary.v1","entries":[{"gg_id":"test","word":"MEASURE",
            "purpose":"Compute distance","kind":"FUNCTION","source":{"first":1},"limits":"not zzlimitword"}]}
        idx=Index(curated_records(d,{"records":[]}))
        self.assertEqual(idx.query("zzlimitword")["state"],"NO_MATCH")

    def test_separate_cohort_results(self):
        q=search(self.curated,self.compiled,"distance")
        self.assertFalse(q["cross_cohort_scores_comparable"])
        self.assertEqual(q["decision"],"REVIEW_REQUIRED_NO_EXECUTION")
        self.assertEqual(q["identity_join_state"],"NOT_PERFORMED")
        self.assertEqual(q["compiled_candidates"]["results"][0]["family_id"],42)

    def test_unknown(self):
        q=search(self.curated,self.compiled,"zzqvunknownnonexistent")
        self.assertEqual(q["compiled_candidates"]["state"],"NO_MATCH")
        self.assertEqual(q["curated_meanings"]["state"],"NO_MATCH")

    def test_repeat(self):
        self.assertEqual(search(self.curated,self.compiled,"distance"),
                         search(self.curated,self.compiled,"distance"))

if __name__=="__main__":
    unittest.main()
