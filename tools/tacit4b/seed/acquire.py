"""Read-only bounded acquisition. GitHub token is never persisted."""
import json, subprocess, sys, urllib.request, zipfile, io, hashlib
from pathlib import Path
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
cohort=json.loads(Path(__file__).with_name("cohort.json").read_text())
def api(path,raw=False):
    args=["gh","api"]
    if raw: args+=["-H","Accept: application/vnd.github.raw+json"]
    return subprocess.check_output(args+[path],timeout=60)
for r in cohort:
    f=r["family"];s=r["source"];d=r["descriptor"];t=r["test"]
    with urllib.request.urlopen("https://raw.githubusercontent.com/"+s["repo"]+"/"+s["commit"]+"/"+s["path"],timeout=30) as q: b=q.read(2097153)
    (root/(f+".mjs")).write_bytes(b)
    (root/(f+".json")).write_bytes(api("repos/Ventusltd/vedic-/contents/"+d["path"]+"?ref="+d["commit"],True))
    (root/(f+"-run.json")).write_bytes(api("repos/Ventusltd/vedic-/actions/runs/"+str(t["run"])))
    (root/(f+"-job.json")).write_bytes(api("repos/Ventusltd/vedic-/actions/jobs/"+str(t["job"])))
z=api("repos/Ventusltd/vedic-/actions/artifacts/15126683549/zip")
with zipfile.ZipFile(io.BytesIO(z)) as f: r=f.read("source-receipt/receipt.json")
assert hashlib.sha256(r).hexdigest()=="83147e90c0f0831ee1f82ce5e721a3521dc843421a96ae9cba3425343d0b3c19"
(root/"orient-receipt.json").write_bytes(r)
