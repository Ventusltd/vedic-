import json
from pathlib import Path
import unittest
from dictionary_shards import build, INDEX, PREFIX, SIZE
ROOT=Path(__file__).resolve().parents[1]
class ShardsTests(unittest.TestCase):
    def test_full_catalogue(self):
        d=json.loads((ROOT/"data/dictionary.json").read_bytes())
        t=json.loads((ROOT/"data/translation-geodesy.json").read_bytes())
        files=build(d,t);idx=json.loads(files[INDEX])
        self.assertEqual(idx["count"],len(d["entries"]))
        self.assertEqual(idx["entries"],sorted(idx["entries"],key=lambda e:(e["word"].casefold(),e["number"])))
        rows=[]
        for name,raw in files.items():
            if name.startswith(PREFIX):
                page=json.loads(raw)["entries"]
                self.assertLessEqual(len(page),SIZE)
                rows.extend(page)
        self.assertEqual({e["gg_id"] for e in rows},{e["gg_id"] for e in d["entries"]})
        self.assertTrue(all("source" not in e and "application" not in e for e in idx["entries"]))
        self.assertTrue(any("Measure and calculate" in e["patterns"] for e in idx["entries"]))
        self.assertTrue(all(e["code_sources"] for e in idx["entries"]))
        self.assertEqual(len(next(e for e in idx["entries"] if e["word"]=="ORIENT")["code_sources"]),2)
        for entry in idx["entries"]:
            for record in entry["code_sources"]:
                self.assertEqual(set(record["source"]),{"repo","commit","path","first","last"})
    def test_101_rows(self):
        d=json.loads((ROOT/"data/dictionary.json").read_bytes())
        t=json.loads((ROOT/"data/translation-geodesy.json").read_bytes())
        d["entries"]=[dict(d["entries"][0],number=i+1,gg_id=f"fixture-{i+1}",word=f"COMMAND {i+1:03d}") for i in range(101)]
        files=build(d,t)
        self.assertEqual(len(json.loads(files[PREFIX+"000001.json"])["entries"]),100)
        self.assertEqual(len(json.loads(files[PREFIX+"000002.json"])["entries"]),1)
        self.assertEqual(json.loads(files[INDEX])["entries"][-1]["gg_id"],"fixture-101")
