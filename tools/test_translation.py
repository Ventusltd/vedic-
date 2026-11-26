import copy
import json
import hashlib
import unittest
from pathlib import Path
from validate_translation import validate, verify_source

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "data/translation-geodesy.json").read_text())
A = json.loads((ROOT / "data/anatomy.json").read_text())

class TranslationTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(D, A), 5)
    def test_unknown_target(self):
        d = copy.deepcopy(D)
        d["capability"] = "missing"
        with self.assertRaises(ValueError): validate(d, A)
    def test_false_identity(self):
        d = copy.deepcopy(D)
        d["records"][0]["family_id"] = 511
        with self.assertRaises(ValueError): validate(d, A)
    def test_false_proof(self):
        d = copy.deepcopy(D)
        d["records"][0]["state"] = "TESTED"
        with self.assertRaises(ValueError): validate(d, A)
    def test_duplicate(self):
        d = copy.deepcopy(D)
        d["records"].append(d["records"][0])
        with self.assertRaises(ValueError): validate(d, A)
    def test_source(self):
        d = copy.deepcopy(D)
        d["records"] = d["records"][:1]
        r = d["records"][0]
        raw = ("export function " + r["name"] + "(a) {\n  return a;\n}\n").encode()
        r["source"].update(first=1,last=3,blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest())
        self.assertEqual(verify_source(d, lambda *args: raw), 1)
        with self.assertRaises(ValueError): verify_source(d, lambda *args: raw+b" ")
        r["source"]["first"] = 2
        with self.assertRaises(ValueError): verify_source(d, lambda *args: raw)
