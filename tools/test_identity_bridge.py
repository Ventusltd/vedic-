"""Synthetic resolver tests: no claims about live producer coverage."""
import hashlib
import sqlite3
import struct
import unittest
from identity_bridge import stars_join, kuiper_join, git_blob

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript("""
        CREATE TABLE line(n INTEGER,sha BLOB,text BLOB);
        CREATE TABLE tablet(n INTEGER,git_blob TEXT,lines BLOB,issue TEXT);
        CREATE TABLE occurrence(repo TEXT,commit_sha TEXT,path TEXT,tablet INTEGER);
        CREATE TABLE family(n INTEGER);
        CREATE TABLE element(n INTEGER,family INTEGER,sha BLOB);
        CREATE TABLE tablet_element(tablet INTEGER,element INTEGER,first INTEGER,last INTEGER,col0 INTEGER,col1 INTEGER,name TEXT);
        """)
        self.lines=[b"function f() {\r\n",b" return 1;\n",b"}"]
        self.s={"repo":"Ventusltd/gridatlas","commit":"a"*40,"path":"test.js",
                "blob":git_blob(b"".join(self.lines)),"first":1,"last":3}
        for i,b in enumerate(self.lines,1):
            self.db.execute("INSERT INTO line VALUES(?,?,?)",(i,hashlib.sha256(b).digest(),b))
        self.db.execute("INSERT INTO tablet VALUES(?,?,?,NULL)",(12,self.s["blob"],struct.pack("<III",1,2,3)))
        self.db.execute("INSERT INTO occurrence VALUES(?,?,?,12)",(self.s["repo"],self.s["commit"],self.s["path"]))
        self.db.execute("INSERT INTO family VALUES(9)")
        self.db.execute("INSERT INTO element VALUES(7,9,?)",(hashlib.sha256(b"".join(self.lines)).digest(),))
        self.db.execute("INSERT INTO tablet_element VALUES(12,7,1,3,0,1,'f')")
        self.r={"summary":{"wafer_address_space":1000},"bodies":[{"repo":"gridatlas","commit":self.s["commit"],
            "path":self.s["path"],"blob":self.s["blob"],"line":1,"verified":True,"on_wafer":True,
            "blob_matches_body":True,"blob_at_path":self.s["blob"],"repo_on_wafer":"gridatlas","key":103,
            "k0":100,"lines_before":3,"commit_lines_measured":20,"commit_lines_wafer":20,
            "blob_lines":3,"wafer_row":0}]}
    def tearDown(self):
        self.db.close()
    def test_exact(self):
        r=stars_join(self.db,self.s)
        self.assertEqual((r["tablet_id"],r["element_id"],r["family_id"],r["line_ids"]),(12,7,9,[1,2,3]))
    def test_historical_occurrence_not_inferred(self):
        r=stars_join(self.db,dict(self.s,commit="b"*40))
        self.assertIsNone(r["tablet_id"])
    def test_blob_mismatch(self):
        with self.assertRaises(ValueError):
            stars_join(self.db,dict(self.s,blob="b"*40))
    def test_corrupt_line(self):
        self.db.execute("UPDATE line SET text=? WHERE n=2",(b"x",))
        with self.assertRaises(ValueError):
            stars_join(self.db,self.s)
    def test_subspan_no_element(self):
        r=stars_join(self.db,dict(self.s,first=2,last=2))
        self.assertEqual(r["line_ids"],[2])
        self.assertIsNone(r["element_id"])
    def test_column_mismatch(self):
        self.assertIsNone(stars_join(self.db,dict(self.s,col0=2,col1=1))["element_id"])
    def test_ambiguous_element(self):
        self.db.execute("INSERT INTO element SELECT 8,family,sha FROM element WHERE n=7")
        self.db.execute("INSERT INTO tablet_element VALUES(12,8,1,3,1,1,'g')")
        self.assertEqual(stars_join(self.db,self.s)["state"],"AMBIGUOUS_ELEMENT_SPAN")
        self.assertEqual(stars_join(self.db,dict(self.s,col0=0,col1=1))["element_id"],7)
    def test_parse_issue(self):
        self.db.execute("UPDATE tablet SET issue='parse problem'")
        self.assertIsNone(stars_join(self.db,self.s)["element_id"])
    def test_kuiper_receipt(self):
        self.assertEqual(kuiper_join(self.s,self.r)["key"],103)
    def test_kuiper_wrong_address(self):
        self.r["bodies"][0]["key"]=104
        self.assertIsNone(kuiper_join(self.s,self.r)["key"])
    def test_kuiper_duplicate(self):
        self.r["bodies"]*=2
        self.assertIsNone(kuiper_join(self.s,self.r)["key"])
    def test_kuiper_wrong_repo_or_quote(self):
        r=self.r["bodies"][0]
        r["repo_on_wafer"]="other"
        self.assertIsNone(kuiper_join(self.s,self.r)["key"])
        r.update(repo_on_wafer="gridatlas",quote_matches=False)
        self.assertIsNone(kuiper_join(self.s,self.r)["key"])
    def test_kuiper_canonical_case_alias(self):
        self.r["bodies"][0]["repo_on_wafer"]="GridAtlas"
        self.assertEqual(kuiper_join(self.s,self.r)["key"],103)
        self.r["bodies"][0]["blob_at_path"]="b"*40
        self.assertIsNone(kuiper_join(self.s,self.r)["key"])
    def test_kuiper_zero_is_valid(self):
        self.r["bodies"][0].update(key=0,k0=0,lines_before=0)
        self.assertEqual(kuiper_join(self.s,self.r)["key"],0)

if __name__=="__main__":
    unittest.main()
