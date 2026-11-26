import copy
import json
import unittest
from pathlib import Path
from validate_graph import validate
G = json.loads((Path(__file__).resolve().parents[1] / "data/nearest-spider.json").read_text())
class GraphTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(G), (4, 3))
    def test_bad_endpoint(self):
        g = copy.deepcopy(G)
        g["edges"][0]["to"] = "invented"
        with self.assertRaises(ValueError): validate(g)
    def test_live_promotion(self):
        g = copy.deepcopy(G)
        g["nodes"][0]["rag"] = "green"
        with self.assertRaises(ValueError): validate(g)
    def test_no_caveat(self):
        g = copy.deepcopy(G)
        g["scope"] = "Active"
        with self.assertRaises(ValueError): validate(g)
    def test_bad_evidence(self):
        g = copy.deepcopy(G)
        g["edges"][0]["evidence"]["contains"] = ""
        with self.assertRaises(ValueError): validate(g)
