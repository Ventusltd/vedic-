import copy
import unittest
from source_admissions import BASE, SCHEMA, allocate_one, candidate_id, prepare, replay

MANIFEST = "a"*40
TIME = "2026-11-26T00:00:00Z"

def candidate(word="FIRST COMMAND",symbol="firstCommand",first=10):
    return {"word":word,"symbol":symbol,"purpose":"Purpose of "+word,
      "limits":"Source contract only","inputs":["x"],"output":"result",
      "estate_group":"Test","discipline":"Test","periodic_category":"Test",
      "vedic_class_candidate":"Computation","aliases":[],
      "source":{"repo":"Ventusltd/test","commit":"b"*40,"blob":"c"*40,
          "path":"engine/test.js","first":first,"last":first+2},
      "receipt":"https://github.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-1"}

def dictionary():
    return {"entries":[],"next_number":1}

def archive():
    return {"schema":SCHEMA,"baseline_commit":BASE,"records":[]}

def queue(*c):
    return {"schema":"vedic.source-candidates.v1","records":list(c)}

class AdmissionTests(unittest.TestCase):
    def test_bad_record_does_not_consume_id(self):
        d,a=dictionary(),archive()
        good=candidate()
        bad=candidate("lowercase","bad",20)
        added,held=prepare(d,a,queue(bad,good),MANIFEST,TIME,lambda row:None)
        self.assertEqual((added,len(held),d["next_number"]),(["GG2050-VEDIC-000001"],1,2))
    def test_bounded_drain_and_exact_replay(self):
        d,a=dictionary(),archive()
        q=queue(*(candidate(f"COMMAND {i}",f"cmd{i}",10+i*4) for i in range(21)))
        self.assertEqual(len(prepare(d,a,q,MANIFEST,TIME,lambda row:None)[0]),20)
        self.assertEqual(len(prepare(d,a,q,MANIFEST,TIME,lambda row:None)[0]),1)
        self.assertEqual(prepare(d,a,q,MANIFEST,TIME,lambda row:None)[0],[])
        expected=replay(dictionary(),a,lambda m,p:q,lambda m:TIME)
        self.assertEqual(expected,d)
        self.assertEqual([e["number"] for e in d["entries"]],list(range(1,22)))
    def test_duplicate_symbol_and_source(self):
        d,a=dictionary(),archive()
        q=queue(candidate(),candidate("SECOND","firstCommand",20),candidate("THIRD","third",11))
        added,held=prepare(d,a,q,MANIFEST,TIME,lambda row:None)
        self.assertEqual((len(added),len(held)),(1,2))
    def test_check_failure_rolls_back(self):
        d,a=dictionary(),archive()
        q=queue(candidate(),candidate("SECOND","second",20))
        def check(row):
            if row["word"]=="FIRST COMMAND":
                raise ValueError("source mismatch")
        added,held=prepare(d,a,q,MANIFEST,TIME,check)
        self.assertEqual((len(added),len(held),d["entries"][0]["number"]),(1,1,1))
    def test_archive_tamper(self):
        d,a=dictionary(),archive()
        q=queue(candidate())
        prepare(d,a,q,MANIFEST,TIME,lambda row:None)
        a["records"][0]["candidate"]=copy.deepcopy(a["records"][0]["candidate"])
        a["records"][0]["candidate"]["purpose"]="tampered"
        with self.assertRaisesRegex(ValueError,"archive evidence mismatch"):
            replay(dictionary(),a,lambda m,p:q,lambda m:TIME)
