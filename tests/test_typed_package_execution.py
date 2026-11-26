import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import package_factory as f
import typed_package_execution as t

args={}
for k in ("archive","receipt"):
    i=sys.argv.index("--"+k); args[k]=Path(sys.argv[i+1]);del sys.argv[i:i+2]

class Typed(unittest.TestCase):
    def setUp(self):
        self.q=f.strict((f.ROOT/"packages/factory/orient-execution.json").read_bytes())
        self.raw=args["archive"].read_bytes()
        self.receipt=f.strict(args["receipt"].read_bytes())
    def runq(self):return t.execute(self.q,self.raw,self.receipt)
    def refuse(self,code):
        with self.assertRaisesRegex(f.Refusal,code):self.runq()
    def test_real(self):
        a=self.runq()
        self.assertEqual(a,self.runq())
        self.assertAlmostEqual(a["pattern"]["output"]["distance_km"],111.31949079327356)
        self.assertEqual(a["pattern"]["output"]["initial_bearing_deg"],90)
    def test_changed(self):
        a=self.runq();self.q["input"]["point_b"]["longitude"]=2;b=self.runq()
        self.assertNotEqual(a["pattern_sha256"],b["pattern_sha256"])
        self.assertAlmostEqual(b["pattern"]["output"]["distance_km"],222.63898158654712)
    def test_nearest(self):self.q["family"]="nearest-substation";self.refuse("NEAREST_NOT_ADMITTED")
    def test_export(self):self.q["export"]="exec";self.refuse("EXPORT_NOT_ADMITTED")
    def test_units(self):self.q["ports"]["distance"]="m";self.refuse("PORT_MISMATCH")
    def test_input_units(self):self.q["input"]["unit"]="radians";self.refuse("INPUT_UNITS")
    def test_bool_coordinate(self):self.q["input"]["point_a"]["latitude"]=True;self.refuse("COORDINATE")
    def test_archive_tamper(self):self.raw+=b"x";self.refuse("ARCHIVE_PIN")
    def test_descriptor(self):self.q["descriptor_sha256"]="a"*64;self.refuse("PATTERN_PIN")
    def test_receipt(self):self.receipt["state"]="PENDING";self.refuse("BUILD_RECEIPT")
    def test_graph(self):self.q["graph"]=[];self.refuse("FIELDS")
    def test_upstream(self):self.q["input"]["point_b"]=self.q["input"]["point_a"];self.refuse("UPSTREAM_RESULT_REFUSED")
    def test_unreviewed_receipt(self):
        with self.assertRaisesRegex(f.Refusal,"REVIEWED_RECEIPT_NOT_PINNED"):
            f.review_receipt("electrical",b'{"schema":"synthetic"}',{},b"{}")
    def test_nearest_handler(self):
        with self.assertRaisesRegex(f.Refusal,"NEAREST_RECEIPTS_PENDING"):
            f.nearest_adapter({},{})

if __name__=="__main__":unittest.main()
