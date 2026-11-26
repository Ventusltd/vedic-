import copy
import shutil
import subprocess
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import package_factory as f

class Contracts(unittest.TestCase):
    def setUp(self):
        self.d=f.strict(f.ADMISSIONS["orient"].read_bytes())
    def reject(self, fn, code):
        with self.assertRaisesRegex(f.Refusal,code):
            fn()
    def mutate(self, key, value, code):
        d=copy.deepcopy(self.d)
        d[key]=value
        self.reject(lambda:f.admit(d),code)
    def test_admission(self):
        self.assertEqual(f.admit(self.d),self.d)
    def test_duplicate_json(self):
        self.reject(lambda:f.strict(b'{"a":1,"a":2}'),"DUPLICATE_KEY")
    def test_nonfinite(self):
        self.reject(lambda:f.strict(b'{"a":NaN}'),"NONFINITE_JSON")
    def test_malformed(self):
        self.reject(lambda:f.strict(b"{"),"INVALID_JSON")
    def test_oversized(self):
        self.reject(lambda:f.strict(b"x"*(f.LIMIT+1)),"INPUT_SIZE")
    def test_unknown_revision(self):
        self.mutate("schema","vedic.package-descriptor.v9","SCHEMA")
    def test_unknown_runtime(self):
        self.mutate("runtime","python","RUNTIME")
    def test_wrong_edition(self):
        self.mutate("edition","a"*40,"ADMISSION_MISMATCH")
    def test_unsupported_export(self):
        self.mutate("exports",["other"],"ADMISSION_MISMATCH")
    def test_missing_licence(self):
        self.mutate("inputs",[i for i in self.d["inputs"] if i["role"]!="licence"],"REQUIRED_INPUT")
    def test_missing_field(self):
        d=copy.deepcopy(self.d); del d["ports"]
        self.reject(lambda:f.validate(d),"FIELDS")
    def test_extra_command(self):
        d=copy.deepcopy(self.d); d["command"]="echo bad"
        self.reject(lambda:f.validate(d),"FIELDS")
    def test_bad_digest(self):
        d=copy.deepcopy(self.d); d["inputs"][0]["digest"]="bad"
        self.reject(lambda:f.validate(d),"DIGEST")
    def test_case_collision(self):
        d=copy.deepcopy(self.d); d["inputs"][1]["filename"]="MODULE.MJS"
        self.reject(lambda:f.validate(d),"PATH_COLLISION")
    def test_traversal(self):
        self.reject(lambda:f.archive({"../escape":b"x"}),"UNSAFE_PATH")
    def test_synthetic_not_admitted(self):
        d=copy.deepcopy(self.d); d["family"]="synthetic"; d["candidate"]="local:synthetic:fixture"
        d["identity_tier"]="SYNTHETIC_TEST_ONLY"
        self.assertEqual(f.validate(d),d)
        self.reject(lambda:f.admit(d),"FAMILY_NOT_ADMITTED")
    def test_missing_input(self):
        with tempfile.TemporaryDirectory() as t:
            self.reject(lambda:f.verified_inputs(self.d,Path(t)),"MISSING_OR_SYMLINK")
    def test_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/"target").write_bytes(b"x"); (p/"module.mjs").symlink_to(p/"target")
            self.reject(lambda:f.read_file(p,"module.mjs"),"MISSING_OR_SYMLINK")
    def test_source_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/"module.mjs").write_bytes(b"changed")
            self.reject(lambda:f.verified_inputs(self.d,p),"INPUT_DIGEST:module")
    def test_oversized_file(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t); (p/"module.mjs").write_bytes(b"x"*(f.LIMIT+1))
            self.reject(lambda:f.read_file(p,"module.mjs"),"INPUT_SIZE")
    def fixture(self):
        p={"x.mjs":b"export const x=1;"}
        p["manifest.json"]=f.canonical({"file_count":2,"files":[{"path":"x.mjs","sha256":f.sha(p["x.mjs"]),"bytes":len(p["x.mjs"])}]})
        return p
    def test_archive_repeat(self):
        p=self.fixture(); a=f.archive(p)
        self.assertEqual(a,f.archive(dict(reversed(list(p.items())))))
        f.verify(a,p)
    def test_manifest_count(self):
        p=self.fixture(); m=f.strict(p["manifest.json"]);m["file_count"]=3;p["manifest.json"]=f.canonical(m)
        self.reject(lambda:f.verify(f.archive(p),p),"MANIFEST_COUNT")
    def test_duplicate_manifest_entry(self):
        p=self.fixture(); m=f.strict(p["manifest.json"]);m["files"]*=2;p["manifest.json"]=f.canonical(m)
        self.reject(lambda:f.verify(f.archive(p),p),"MANIFEST_DUPLICATE")
    def test_archive_duplicate(self):
        p=self.fixture(); buf=io.BytesIO(f.archive(p))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with zipfile.ZipFile(buf,"a") as z:z.writestr("x.mjs",b"x")
        self.reject(lambda:f.verify(buf.getvalue(),p),"ARCHIVE_DUPLICATE")
    def test_archive_symlink(self):
        p=self.fixture(); buf=io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            i=zipfile.ZipInfo("x.mjs");i.create_system=3;i.external_attr=0o120777<<16;z.writestr(i,b"link")
        self.reject(lambda:f.verify(buf.getvalue(),p),"ARCHIVE_METADATA")
    def test_archive_missing_dependency(self):
        p=self.fixture();self.reject(lambda:f.verify(f.archive({"manifest.json":p["manifest.json"]}),p),"ARCHIVE_FILE_SET")
    def test_archive_changed_bytes(self):
        p=self.fixture();q={**p,"x.mjs":b"changed"}
        self.reject(lambda:f.verify(f.archive(q),p),"ARCHIVE_BYTES")
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"candidate.zip";f.publish_local(p,b"first")
            with self.assertRaises(FileExistsError):f.publish_local(p,b"second")
            self.assertEqual(p.read_bytes(),b"first")

REAL_INPUTS = None
if "--real-inputs" in sys.argv:
    i=sys.argv.index("--real-inputs")
    REAL_INPUTS=Path(sys.argv[i+1])
    del sys.argv[i:i+2]

@unittest.skipUnless(REAL_INPUTS is not None,"requires actual pinned inputs")
class RealInputControls(unittest.TestCase):
    def setUp(self):
        self.d=f.strict(f.ADMISSIONS["orient"].read_bytes())
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for item in self.d["inputs"]:
            shutil.copyfile(REAL_INPUTS/item["filename"],self.root/item["filename"])
    def reject_changed(self, filename, role):
        p=self.root/filename
        p.write_bytes(p.read_bytes()+b"\n")
        out=self.root/"bad.zip"
        with self.assertRaisesRegex(f.Refusal,"INPUT_DIGEST:"+role):
            f.build(self.d,self.root,out)
        self.assertFalse(out.exists())
    def test_changed_real_source(self):
        self.reject_changed("module.mjs","module")
    def test_changed_real_receipt(self):
        self.reject_changed("receipt.json","receipt")
    def test_changed_real_licence(self):
        self.reject_changed("LICENSE","licence")
    def test_changed_real_prototype(self):
        self.reject_changed("prototype.py","prototype")
    def test_missing_real_licence(self):
        (self.root/"LICENSE").unlink()
        with self.assertRaisesRegex(f.Refusal,"MISSING_OR_SYMLINK"):
            f.build(self.d,self.root,self.root/"bad.zip")
        self.assertFalse((self.root/"bad.zip").exists())
    def test_missing_runtime_dependency_even_with_matching_manifest(self):
        payload,script=f.assemble(self.d,self.root)
        del payload["v9-geodesy.mjs"]
        m=f.strict(payload["manifest.json"])
        m["files"]=[r for r in m["files"] if r["path"]!="v9-geodesy.mjs"]
        m["file_count"]-=1
        payload["manifest.json"]=f.canonical(m)
        raw=f.archive(payload)
        f.verify(raw,payload)
        with self.assertRaises(subprocess.CalledProcessError):
            f.run_consumer(self.d,raw,payload,script)
    def test_archive_traversal_on_read(self):
        payload,_=f.assemble(self.d,self.root)
        buf=io.BytesIO(f.archive(payload))
        with zipfile.ZipFile(buf,"a") as z:
            z.writestr("../escape",b"bad")
        with self.assertRaisesRegex(f.Refusal,"UNSAFE_PATH"):
            f.verify(buf.getvalue(),payload)

if __name__=="__main__":
    unittest.main()
