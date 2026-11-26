import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import package_factory as f

class SecondFamily(unittest.TestCase):
    def setUp(self):
        self.d=f.strict(f.PENDING["electrical"].read_bytes())
    def test_missing_receipt(self):
        with self.assertRaisesRegex(f.Refusal,"SOURCE_RECEIPT_PENDING"):
            f.admit(self.d)
    def test_no_forged_receipt(self):
        d=copy.deepcopy(self.d)
        d["inputs"].append({"role":"receipt","filename":"receipt.json","repo":"Ventusltd/vedic-",
           "commit":"a"*40,"path":"receipt.json","algorithm":"sha256","digest":"a"*64,"output":"source-receipt.json"})
        with self.assertRaisesRegex(f.Refusal,"SOURCE_RECEIPT_PENDING"):
            f.admit(d)
    def test_no_archive(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/"bad.zip"
            with self.assertRaisesRegex(f.Refusal,"SOURCE_RECEIPT_PENDING"):
                f.build(self.d,Path(t),out)
            self.assertFalse(out.exists())
    def test_explicit_handler_refuses_unreviewed_receipt(self):
        with self.assertRaisesRegex(f.Refusal,"ELECTRICAL_RECEIPT_REVIEW_REQUIRED"):
            f.electrical_adapter(self.d,{"receipt":b"{}"})
    def test_flat_two_file_esm_closure(self):
        # Synthetic GIS-like relative .js import: do not rewrite extension.
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            files={"package.json":b'{"type":"module"}',
                   "nearest.js":b"import {x} from './geodesy.js'; export const y=x+1;",
                   "geodesy.js":b"export const x=2;"}
            manifest={"file_count":len(files)+1,"files":[{"path":k,"sha256":f.sha(v),"bytes":len(v)} for k,v in sorted(files.items())]}
            files["manifest.json"]=f.canonical(manifest)
            raw=f.archive(files); f.verify(raw,files)
            for k,v in files.items(): (p/k).write_bytes(v)
            script="import {y} from './nearest.js'; if(y!==3)process.exit(1);"
            (p/"consumer.mjs").write_text(script)
            subprocess.check_call(["node","consumer.mjs"],cwd=p)
            (p/"geodesy.js").unlink()
            self.assertNotEqual(subprocess.run(["node","consumer.mjs"],cwd=p,capture_output=True).returncode,0)

if __name__=="__main__":
    unittest.main()
