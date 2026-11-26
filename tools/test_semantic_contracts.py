import unittest
from semantic_contracts import (UNVERIFIED, compile_manifest, compatibility,
                                git_blob, physical_lines, search, observations)

RAW = b"import math\r\ndef length(x):\r\n    return math.sqrt(x)"
PIN = {"repo":"Ventusltd/example", "commit":"a"*40, "path":"length.py",
       "blob":git_blob(RAW), "first":2, "last":3}
def entry(n=1, **overrides):
    e = {"gg_id":f"GG2050-VEDIC-{n:06d}", "word":"LENGTH", "kind":"FUNCTION",
         "purpose":"Measure cable length", "inputs":["number"], "output":"distance_m",
         "source":dict(PIN)}
    e.update(overrides)
    return e
def build(entries, reader=lambda *args: RAW, parse=True):
    return compile_manifest({"schema":"vedic.dictionary.v1","entries":entries},
                            {"records":[]}, reader, parse)
class SemanticContractsTests(unittest.TestCase):
    def test_physical_lines(self):
        self.assertEqual(physical_lines(b"a\r\nb\n"), [b"a\r\n", b"b\n"])
        self.assertEqual(physical_lines(b""), [])
        self.assertEqual(physical_lines(b"\n"), [b"\n"])
        self.assertEqual(physical_lines(b"a\rb"), [b"a\rb"])
    def test_exact_span(self):
        e = build([entry()])["entries"][0]
        m = e["mechanical"]
        self.assertEqual(m["byte_count"], len(b"def length(x):\r\n    return math.sqrt(x)"))
        self.assertEqual(m["line_count"], 2)
        self.assertEqual(m["syntax"]["symbol"], "length")
        self.assertEqual(m["syntax"]["parameters"], ["x"])
        self.assertEqual(m["syntax"]["file_imports"], ["math"])
        self.assertEqual(e["state_signature"]["inputs"], UNVERIFIED)
        self.assertEqual(e["output_class"], UNVERIFIED)
        self.assertFalse(e["runtime_verified"])
    def test_dedup_no_identity_merge(self):
        calls = []
        def read(*args):
            calls.append(args)
            return RAW
        m = build([entry(),entry(2,word="DISTANCE")],read)
        self.assertEqual(m["unique_verified_spans"],1)
        self.assertEqual(m["dictionary_entries"],2)
        self.assertEqual(len(calls),1)
    def test_bad_blob_rejected(self):
        with self.assertRaisesRegex(ValueError,"blob mismatch"):
            build([entry()],lambda *args: RAW+b"\n")
    def test_invalid_span_rejected(self):
        with self.assertRaisesRegex(ValueError,"span exceeds"):
            build([entry(source=dict(PIN,last=4))])
    def test_traversal_rejected(self):
        with self.assertRaisesRegex(ValueError,"invalid path"):
            build([entry(source=dict(PIN,path="../length.py"))])
    def test_duplicate_id_rejected(self):
        with self.assertRaisesRegex(ValueError,"duplicate"):
            build([entry(),entry()])
    def test_partial_ast_does_not_claim_function(self):
        self.assertEqual(observations("x.py",RAW,3,3)["state"],"SPAN_NOT_EXACT_AST_NODE")
    def test_source_less_composition(self):
        c = entry(2,kind="COMPOSITION",source=None,components=["GG2050-VEDIC-000001"])
        out = build([entry(),c])["entries"][1]
        self.assertIsNone(out["mechanical"])
        self.assertEqual(out["components"],["GG2050-VEDIC-000001"])
    def test_missing_component_rejected(self):
        with self.assertRaisesRegex(ValueError,"unknown composition"):
            build([entry(2,kind="COMPOSITION",source=None,components=["GG2050-VEDIC-000001"])])
    def test_intent_search_and_no_match(self):
        m = build([entry(),entry(2,word="VOLTAGE",purpose="Determine voltage",inputs=[],output="kv")])
        self.assertEqual(search(m,"measure cable length")[0]["word"],"LENGTH")
        self.assertEqual(search(m,"unrelated elephant"),[])
        self.assertEqual(search(m,"the and"),[])
    def test_ties_deterministic(self):
        m = build([entry(2),entry()])
        self.assertEqual([e["gg_id"] for e in search(m,"length")],
                         ["GG2050-VEDIC-000001","GG2050-VEDIC-000002"])
    def test_port_compatibility(self):
        a = {"type":"number","unit":"km","shape":"scalar","schema":"distance.v1","state":"VERIFIED_CONTRACT"}
        self.assertEqual(compatibility(a,a),"DECLARED_PORT_MATCH_NOT_EXECUTION_PROOF")
        self.assertEqual(compatibility(a,dict(a,unit="m")),"ADAPTER_REQUIRED")
        self.assertEqual(compatibility(a,dict(a,state="UNVERIFIED")),"UNVERIFIED_PORTS")
        self.assertEqual(compatibility(a,dict(a,schema=None)),"UNVERIFIED_PORTS")
        self.assertEqual(compatibility("number","number"),"UNVERIFIED_PORTS")
    def test_js_parser_optional(self):
        try:
            import esprima
        except ImportError:
            self.skipTest("optional formal parser not installed")
        result = observations("a.js",b"function f(x) {\n return document.getElementById('map');\n}\n",1,3)
        self.assertEqual(result["state"],"STATIC_SYNTAX_OBSERVATION")
        self.assertEqual(result["literal_dom_id_arguments"],["map"])
    def test_html_parser_optional(self):
        try:
            import bs4
        except ImportError:
            self.skipTest("optional DOM parser not installed")
        result = observations("a.html",b'<div id="map"></div>\n<script src="map.js"></script>\n',1,2)
        self.assertEqual(result["dom_ids"],["map"])
        self.assertEqual(result["script_src"],["map.js"])
        self.assertEqual(observations("a.html",b"<p>1</p>\n<p>2</p>",2,2)["state"],"HTML_SUBSPAN_REQUIRES_PRODUCER_BOUNDARY")
if __name__ == "__main__":
    unittest.main()
