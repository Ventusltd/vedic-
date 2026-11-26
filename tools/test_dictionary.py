import copy,json,unittest
from pathlib import Path
from validate_dictionary import validate
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"data/dictionary.json").read_text())
T=json.loads((ROOT/"data/translation-geodesy.json").read_text())
class DictionaryTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(D,T),len(D["entries"]))
    def test_identity(self):
        d=copy.deepcopy(D); d["entries"][0]["word"]="OTHER"
        with self.assertRaises(ValueError): validate(d,T,D)
    def test_missing_demo(self):
        d=copy.deepcopy(D); d["entries"][0]["demo"]="unknown"
        with self.assertRaises(ValueError): validate(d,T)
    def test_incompatible_inputs(self):
        d=copy.deepcopy(D); d["entries"][5]["inputs"]=["kilovolt_list"]
        with self.assertRaises(ValueError): validate(d,T)
    def test_cycle(self):
        d=copy.deepcopy(D); d["entries"][5]["components"][0]=d["entries"][5]["gg_id"]
        with self.assertRaises(ValueError): validate(d,T)
    def test_duplicate(self):
        d=copy.deepcopy(D); d["entries"].append(d["entries"][0])
        with self.assertRaises(ValueError): validate(d,T)
    def test_same_word_distinct_meaning(self):
        d=copy.deepcopy(D); t=copy.deepcopy(T)
        e=copy.deepcopy(d["entries"][0])
        e.update(number=d["next_number"],gg_id=f'GG2050-VEDIC-{d["next_number"]:06d}',translation_ref="fixture:distinct_meaning",sense_key="function:fixture:distinct_meaning")
        t["records"].append({"id":"fixture:distinct_meaning"})
        d["entries"].append(e); d["next_number"]+=1
        self.assertEqual(validate(d,t,D),len(D["entries"])+1)
    def test_duplicate_meaning(self):
        d=copy.deepcopy(D)
        e=copy.deepcopy(d["entries"][0]); e.update(number=d["next_number"],gg_id=f'GG2050-VEDIC-{d["next_number"]:06d}',word="OTHER")
        d["entries"].append(e); d["next_number"]+=1
        with self.assertRaises(ValueError): validate(d,T,D)
    def test_creation_time_immutable(self):
        d=copy.deepcopy(D); d["entries"][0]["created_utc"]="2026-11-26T02:00:00Z"
        with self.assertRaises(ValueError): validate(d,T,D)

    def test_source_only_cannot_claim_demo(self):
        d=copy.deepcopy(D); d["entries"][6]["demo"]="distance"
        with self.assertRaises(ValueError): validate(d,T)
    def test_source_only_requires_reason(self):
        d=copy.deepcopy(D); d["entries"][6].pop("demo_unavailable_reason")
        with self.assertRaises(ValueError): validate(d,T)
    def test_source_only_requires_source_pin(self):
        d=copy.deepcopy(D); d["entries"][6]["source"]["blob"]="invalid"
        with self.assertRaises(ValueError): validate(d,T)
