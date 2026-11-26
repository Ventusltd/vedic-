import json
from pathlib import Path
import unittest
from conversational_execution import coordinates, strict_json, propose, ORIENT, MEASURE, BEARING, plan, source_check
from stars_retrieval import Index, load_library, git_blob
from semantic_retrieval import curated_records

ROOT=Path(__file__).resolve().parents[1]


def example(a=(0,0),b=(1,0)):
    return {"crs":"WGS84","unit":"degrees","point_a":{"longitude":a[0],"latitude":a[1]},
            "point_b":{"longitude":b[0],"latitude":b[1]}}


class TestConversation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=json.loads((ROOT/"data/dictionary.json").read_text())
        t=json.loads((ROOT/"data/translation-geodesy.json").read_text())
        cls.c=Index(curated_records(d,t),prefer_coverage=True)
        raw=(f"// Family #42 · element #43 · 2 places in 1 repositories · "
             f"https://github.com/Ventusltd/testcode/blob/{'a'*40}/math.js#L1-L3\n"
             "export const f42_distance = function distance(a,b){return a-b;};\n").encode()
        cls.p=Index(load_library(raw,git_blob(raw),1))

    def test_v2_census(self):
        self.assertEqual(len(self.c.records),50)
        self.assertEqual(len({r["gg_id"] for r in self.c.records}),50)

    def test_paraphrases(self):
        for q in ["Calculate the distance and initial bearing between two points",
                  "Find the distance and heading between two locations",
                  "How far apart are two points and what is their bearing?"]:
            with self.subTest(q=q):
                r=propose(q,self.c,self.p)
                self.assertEqual(r["candidate_id"],ORIENT)
                self.assertFalse(r["execution_authorized_by_ranking"])

    def test_abstention(self):
        for q in ["road route distance and bearing","connection capacity","financial discount rate",
                  "measure distance between two points","show bearing between two points",
                  "select two assets in GridAtlas and calculate distance and bearing",
                  "do not calculate distance and bearing","distance and bearing in radians"]:
            with self.subTest(q=q):
                self.assertEqual(propose(q,self.c,self.p)["state"],"ABSTAIN")

    def test_named_coordinates(self):
        self.assertEqual(coordinates(example()),[0,0,1,0])
        self.assertEqual(coordinates(example((179,0),(-179,0))),[179,0,-179,0])

    def test_invalid_coordinates(self):
        for a,b in [((181,0),(1,0)),((0,91),(1,0)),((True,0),(1,0)),
                    ((float("nan"),0),(1,0)),((0,0),(0,0)),((180,0),(-180,0)),
                    ((0,0),(180,0)),((0,90),(1,0))]:
            with self.subTest(a=a,b=b):
                with self.assertRaises(ValueError):
                    coordinates(example(a,b))

    def test_schema_refusals(self):
        for data in [dict(example(),unit="radians"),dict(example(),crs="EPSG:27700"),
                     dict(example(),point_a=[0,0]),dict(example(),point_b=None),
                     dict(example(),point_a={"lat":0,"lon":0})]:
            with self.assertRaises(ValueError):
                coordinates(data)

    def test_duplicate_json(self):
        with self.assertRaises(ValueError):
            strict_json('{"x":0,"x":1}')
        with self.assertRaises(ValueError):
            strict_json('{"x":NaN}')

    def test_wrong_receipt_or_source(self):
        from hashlib import sha256
        with self.assertRaisesRegex(ValueError,"receipt digest"):
            source_check(b"bad",b"{}","wrong")
        with self.assertRaisesRegex(ValueError,"source Git blob"):
            source_check(b"bad",b"{}",sha256(b"{}").hexdigest())

    def test_abstention_blocks_plan(self):
        with self.assertRaisesRegex(ValueError,"intent abstained"):
            plan({"state":"ABSTAIN"},example(),[])

    def test_missing_identity_blocks_plan(self):
        with self.assertRaisesRegex(ValueError,"unverified node set"):
            plan({"state":"PLAN_PROPOSED","candidate_id":ORIENT},example(),[])


if __name__=="__main__":
    unittest.main()
