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
