import copy
import json
import unittest
from pathlib import Path
from validate_graph import validate, validate_aliases
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

    def test_shared_occurrence_alias(self):
        catalogue = json.loads((Path(__file__).resolve().parents[1] / "data/translation-geodesy.json").read_text())
        self.assertEqual(validate_aliases(G, catalogue), 8)
        g = copy.deepcopy(G)
        next(n for n in g["nodes"] if n["id"] == "vedic:distanceKm").pop("catalogue_ref")
        with self.assertRaises(ValueError): validate_aliases(g, catalogue)
    def test_alias_cannot_change_identity(self):
        catalogue = json.loads((Path(__file__).resolve().parents[1] / "data/translation-geodesy.json").read_text())
        g = copy.deepcopy(G)
        next(n for n in g["nodes"] if n["id"] == "vedic:distanceKm")["catalogue_ref"] = "geodesy:initialBearingDeg"
        with self.assertRaises(ValueError): validate_aliases(g, catalogue)
