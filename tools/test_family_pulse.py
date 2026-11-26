import copy
import tempfile
import unittest
from pathlib import Path
from family_pulse import allocate, checkpoint_cursor, family_identities, family_rows, key, export_pulse, verify_extension

def row(word="FILTER ASSETS", sym="filterAssets"):
    return {"decision":"REVIEWED_FOR_ADMISSION","family_refs":[7],"entry":{
        "word":word,"translation_ref":"daily:"+sym,"sense_key":"function:daily:"+sym,
        "kind":"FUNCTION","state":"STATIC_SOURCE_REVIEW","demo":None,"purpose":"Filter assets",
        "application":{"url":"https://github.com/Ventusltd/gridatlas"} }}
def queue(*records):
    return {"schema":"vedic.daily-command-queue.v1","records":list(records)}
class DailyTests(unittest.TestCase):
    def setUp(self):
        self.d={"entries":[],"next_number":1}
    def test_normalisation(self):
        self.assertEqual(key("Filter Assets"),key("filter_assets"))
    def test_append_and_replay(self):
        c=row()
        self.assertEqual(len(allocate(self.d,queue(c))[0]),1)
        before=copy.deepcopy(self.d)
        self.assertEqual(allocate(self.d,queue(c))[0],[])
        self.assertEqual(self.d,before)
    def test_family_collision(self):
        allocate(self.d,queue(row()))
        self.assertEqual(allocate(self.d,queue(row("OTHER","other")))[0],[])
    def test_existing_symbol(self):
        self.d["entries"]=[{"word":"FILTER","translation_ref":"old:filterAssets","sense_key":"old"}]
        self.assertEqual(allocate(self.d,queue(row()))[0],[])
    def test_unreviewed(self):
        c=row();c["decision"]="CANDIDATE"
        with self.assertRaises(ValueError): allocate(self.d,queue(c))
    def test_cursor_and_family(self):
        catalogue={"family_by_hash":{"a"*64:7,"b"*64:8,"c"*64:9},
                   "families":{"7":{"names":["filterAssets"],"repos":2},"8":{"names":["other"],"repos":1}}}
        identities=family_identities(catalogue)
        allocate(self.d,queue(row()))
        rows,cursor=family_rows(catalogue,identities,self.d["entries"],0)
        self.assertEqual((rows[0][4],rows[-1][4],cursor),("MAPPED_FAMILY","NO_CURRENT_PLACEMENT",9))
        self.assertEqual(family_rows(catalogue,identities,[],9),([],9))
        checkpoint={"schema":"vedic.daily-family-pulse.v2","next_cursor":9,"cursor_family_hash":"c"*64}
        self.assertEqual(checkpoint_cursor(checkpoint,identities),9)
        checkpoint["cursor_family_hash"]="e"*64
        with self.assertRaises(ValueError): checkpoint_cursor(checkpoint,identities)

    def test_bounded_labels(self):
        with self.assertRaisesRegex(ValueError, "command not compact"):
            allocate(self.d,queue(row("ONE TWO THREE FOUR FIVE SIX")))
    def test_parquet(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("DuckDB installed in daily workflow")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"pulse.parquet"
            export_pulse([(1,"[]",1,"[]","REVIEW_REQUIRED","[]","[]","[]")],p)
            self.assertGreater(p.stat().st_size,0)
            export_pulse([],p)
            self.assertGreater(p.stat().st_size,0)

    def test_review_replay(self):
        historic=copy.deepcopy(self.d)
        c=row()
        allocate(self.d,queue(c))
        verify_extension(historic,self.d,queue(c))
        self.d["entries"][0]["word"]="ALTERED"
        with self.assertRaises(ValueError):
            verify_extension(historic,self.d,queue(c))
