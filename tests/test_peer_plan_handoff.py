import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import package_factory as f
import typed_package_execution as t

args={}
for k in ("peer","archive","receipt"):
    i=sys.argv.index("--"+k);args[k]=Path(sys.argv[i+1]);del sys.argv[i:i+2]

class Peer(unittest.TestCase):
    def setUp(self):
        self.peer=f.strict(args["peer"].read_bytes())
        self.raw=args["archive"].read_bytes()
        self.receipt=f.strict(args["receipt"].read_bytes())
    def runq(self):
        return t.execute_peer(f.canonical(self.peer),self.raw,self.receipt)
    def refuse(self,code):
        with self.assertRaisesRegex(f.Refusal,code):self.runq()
    def test_actual(self):
        result=t.execute_peer(args["peer"].read_bytes(),self.raw,self.receipt)
        self.assertEqual(result["peer_parity"],"MATCH_WITHIN_1E-9")
        self.assertEqual(result["pattern"]["output"]["initial_bearing_deg"],90)
    def test_wrong_export(self):self.peer["plan"]["nodes"][0]["export"]="other";self.refuse("PEER_DAG_MISMATCH")
    def test_wrong_occurrence(self):self.peer["plan"]["nodes"][0]["source"]["commit"]="a"*40;self.refuse("PEER_DAG_MISMATCH")
    def test_wrong_unit(self):self.peer["plan"]["outputs"]["distance_km"]="m";self.refuse("PEER_DAG_MISMATCH")
    def test_wrong_args(self):self.peer["plan"]["args"][2]=2;self.refuse("PEER_DAG_MISMATCH")
    def test_abstain(self):self.peer["state"]="ABSTAIN";self.refuse("PEER_EXECUTION_STATE")
    def test_wrong_source(self):self.peer["source_sha256"]="a"*64;self.refuse("PEER_SOURCE")
    def test_wrong_prior_result(self):self.peer["outputs"]["distance_km"]=1;self.refuse("PEER_PARITY")
    def test_wrong_graph(self):self.peer["plan"]["nodes"].append(self.peer["plan"]["nodes"][0]);self.refuse("PEER_DAG_MISMATCH")
if __name__=="__main__":unittest.main()
