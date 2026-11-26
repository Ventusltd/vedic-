import copy
import json
import unittest
from pathlib import Path
from validate_anatomy import validate

DATA = json.loads((Path(__file__).resolve().parents[1] / "data/anatomy.json").read_text())
class AnatomyTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(DATA), (3, 4, 9))
    def test_dangling(self):
        d = copy.deepcopy(DATA)
        d["apps"][0]["capabilities"][0]["body_ids"] = ["missing"]
        with self.assertRaises(ValueError): validate(d)
    def test_invented_count(self):
        d = copy.deepcopy(DATA)
        d["bodies"][0]["unique_lines"] = 42
        with self.assertRaises(ValueError): validate(d)
    def test_duplicate(self):
        d = copy.deepcopy(DATA)
        d["bodies"].append(d["bodies"][0])
        with self.assertRaises(ValueError): validate(d)
    def test_unverified_proof(self):
        d = copy.deepcopy(DATA)
        d["apps"][0]["capabilities"][0]["proof"] = "PASS"
        with self.assertRaises(ValueError): validate(d)
if __name__ == "__main__":
    unittest.main()
