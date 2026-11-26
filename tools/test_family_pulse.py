import copy
import tempfile
import unittest
from pathlib import Path
from family_pulse import allocate, checkpoint_cursor, family_identities, family_rows, key, export_pulse, verify_extension, proposal_files, verify_proposal, write

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
        self.assertEqual(len(allocate(self.d,queue(c))[1]),1)
        self.assertEqual(self.d["next_number"],1)
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
        self.assertIn("command not compact",allocate(self.d,queue(row("ONE TWO THREE FOUR FIVE SIX")))[1][0]["reason"])
    def test_parquet(self):
        import duckdb
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
    def test_bounded_queue_drains_without_id_gaps(self):
        records = [row("lowercase","bad"), row("FIRST","first"), row("SECOND","second")]
        records[2]["family_refs"] = [8]
        q = queue(*records)
        chosen = []
        added, held = allocate(self.d,q,limit=1,admitted=chosen)
        self.assertEqual((chosen,len(held),len(added)),([1],1,1))
        pending, archive = proposal_files(q,queue(),chosen)
        chosen = []
        added, held = allocate(self.d,pending,limit=1,admitted=chosen)
        pending, archive = proposal_files(pending,archive,chosen)
        self.assertEqual(pending,queue(records[0]))
        self.assertEqual([r["number"] for r in self.d["entries"]],[1,2])
        verify_extension({"entries":[],"next_number":1},self.d,archive)

    def test_retired_family_does_not_block_later_command(self):
        a,b = row("OLD","old"),row("NEW","new")
        b["family_refs"] = [8]
        added,held=allocate(self.d,queue(a,b),family_ids={8})
        self.assertEqual((len(added),len(held)),(1,1))
        self.assertEqual(self.d["entries"][0]["number"],1)

    def test_reviewed_family_overlap(self):
        allocate(self.d,queue(row()))
        other=row("OTHER","other")
        other["family_overlap_reason"]="Distinct reviewed sub-command"
        self.assertEqual(len(allocate(self.d,queue(other))[0]),1)

    def test_candidate_validation_before_number_allocation(self):
        a,b=row("FIRST","first"),row("SECOND","second")
        b["family_refs"]=[8]
        def check(candidate):
            if candidate["word"]=="FIRST":
                raise ValueError("bad source")
        added,held=allocate(self.d,queue(a,b),check_candidate=check)
        self.assertEqual((len(added),len(held)),(1,1))
        self.assertEqual(self.d["entries"][0]["number"],1)

    def test_archive_replay_rejects_extra_record(self):
        c=row()
        allocate(self.d,queue(c))
        with self.assertRaises(ValueError):
            verify_extension({"entries":[],"next_number":1},self.d,queue(c,c))

    def test_proposal_partition_and_replay(self):
        prior=copy.deepcopy(self.d)
        q=queue(row("FIRST","first"),row("SECOND","second"))
        q["records"][1]["family_refs"]=[8]
        indices=[]
        allocate(self.d,q,limit=1,admitted=indices)
        pending,archive=proposal_files(q,queue(),indices)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            write(out/"dictionary.json",self.d)
            write(out/"daily-command-queue.json",pending)
            write(out/"admitted-queue-archive.json",archive)
            write(out/"admitted-indices.json",indices)
            verify_proposal(prior,q,queue(),out)
            write(out/"daily-command-queue.json",queue())
            with self.assertRaisesRegex(ValueError,"queue partition changed"):
                verify_proposal(prior,q,queue(),out)
