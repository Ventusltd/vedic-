import copy,json,unittest
from pathlib import Path
from validate_dictionary import validate
ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/"data/dictionary.json").read_text())
T=json.loads((ROOT/"data/translation-geodesy.json").read_text())
class DictionaryTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(D,T),6)
    def test_identity(self):
        d=copy.deepcopy(D); d["entries"][0]["word"]="OTHER"
        with self.assertRaises(ValueError): validate(d,T,D)
    def test_missing_demo(self):
        d=copy.deepcopy(D); d["entries"][0]["demo"]="unknown"
        with self.assertRaises(ValueError): validate(d,T)
    def test_incompatible_inputs(self):
        d=copy.deepcopy(D); d["entries"][-1]["inputs"]=["kilovolt_list"]
        with self.assertRaises(ValueError): validate(d,T)
    def test_cycle(self):
        d=copy.deepcopy(D); d["entries"][-1]["components"][0]=d["entries"][-1]["gg_id"]
        with self.assertRaises(ValueError): validate(d,T)
    def test_duplicate(self):
        d=copy.deepcopy(D); d["entries"].append(d["entries"][0])
        with self.assertRaises(ValueError): validate(d,T)
    def test_same_word_distinct_meaning(self):
        d=copy.deepcopy(D); t=copy.deepcopy(T)
        e=copy.deepcopy(d["entries"][0])
        e.update(number=7,gg_id="GG2050-VEDIC-000007",translation_ref="fixture:distinct_meaning",sense_key="function:fixture:distinct_meaning")
        t["records"].append({"id":"fixture:distinct_meaning"})
        d["entries"].append(e); d["next_number"]=8
        self.assertEqual(validate(d,t,D),7)
    def test_duplicate_meaning(self):
        d=copy.deepcopy(D)
        e=copy.deepcopy(d["entries"][0]); e.update(number=7,gg_id="GG2050-VEDIC-000007",word="OTHER")
        d["entries"].append(e); d["next_number"]=8
        with self.assertRaises(ValueError): validate(d,T,D)
    def test_creation_time_immutable(self):
        d=copy.deepcopy(D); d["entries"][0]["created_utc"]="2026-11-26T02:00:00Z"
        with self.assertRaises(ValueError): validate(d,T,D)
