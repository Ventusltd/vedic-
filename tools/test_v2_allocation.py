"""Mutation checks for deterministic V2 allocation, independent of the online gate."""
import copy
import json
import unittest
from validate_v2_allocation import read, allocate, verify_receipt
from validate_dictionary import verify_source_entries
class V2Tests(unittest.TestCase):
    def setUp(self):
        self.r=read("data/tacit15-v2-candidate-decisions.json")
        self.a=read("data/tacit15-v2-allocation.json")
        self.d=read("data/dictionary.json")
        self.d["entries"]=self.d["entries"][:self.a["new_count"]]
        self.d["next_number"]=self.a["next_number"]
        self.old=copy.deepcopy(self.d)
        self.old["entries"]=self.old["entries"][:39]
        self.old["next_number"]=40
    def test_deterministic_allocation(self):
        self.assertEqual(allocate(self.old,self.r,self.a),self.d)
        self.assertEqual(verify_receipt(self.r,self.a,self.d,self.old),50)
    def test_old_entry_mutation(self):
        self.d["entries"][0]["application"]["instructions"]="mutated"
        with self.assertRaises(ValueError):
            verify_receipt(self.r,self.a,self.d,self.old)
    def test_duplicate_source(self):
        self.r["selected"].append(copy.deepcopy(self.r["selected"][0]))
        with self.assertRaises(ValueError):
            allocate(self.old,self.r,self.a)
    def test_wrong_blob(self):
        e=copy.deepcopy(self.d["entries"][39])
        with self.assertRaisesRegex(ValueError,"blob mismatch"):
            verify_source_entries({"entries":[e]},lambda *args:b"wrong")
    def test_wrong_span(self):
        import hashlib
        e=copy.deepcopy(self.d["entries"][39])
        raw=b"function describe(a){\n}\n"
        e["source"].update(blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest(),first=1,last=3)
        with self.assertRaisesRegex(ValueError,"outside file"):
            verify_source_entries({"entries":[e]},lambda *args:raw)
