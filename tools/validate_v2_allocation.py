"""Deterministic V2 allocation and source/licence replay; never writes permanent IDs outside this recipe."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from validate_translation import fetch
from validate_dictionary import validate, verify_source_entries, require

ROOT = Path(__file__).resolve().parents[1]
def read(path):
    return json.loads((ROOT / path).read_bytes())
def git_bytes(ref, path):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)
def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
def allocate(previous, receipt, allocation):
    result = json.loads(json.dumps(previous))
    for c in receipt["selected"]:
        n = result["next_number"]
        result["next_number"] += 1
        scope = "kuiper" if c["agent"] == 2 else ("gridatlas-search" if "cartridges/" in c["source"]["path"] else "gridatlas-vicinity")
        tr = f'tacit15:{scope}:{c["symbol"]}'
        entry = dict(number=n, gg_id=f"GG2050-VEDIC-{n:06d}", word=c["word"], kind="FUNCTION",
            translation_ref=tr, inputs=c["inputs"], output=c["output"], demo=None,
            demo_unavailable_reason="Existing application; exact runtime mapping unverified.",
            state="STATIC_SOURCE_REVIEW", estate_group=c["estate_group"], discipline=c["discipline"],
            classification_state="CURATED_CANDIDATE", periodic_category=c["periodic_category"],
            periodic_block_candidate="Unresolved", vedic_class_candidate=c["vedic_class_candidate"],
            created_utc=allocation["created_utc"], sense_key="function:"+tr,
            creation_evidence="https://github.com/Ventusltd/vedic-/commit/"+allocation["candidate_receipt_commit"],
            priority=2, purpose=c["purpose"], limits=c["limits"], source=c["source"], receipt=c["receipt"],
            application=c["application"], family_id=None, element_id=None, tablet_id=None, line_ids=None, proof=None)
        for old in result["entries"]:
            s, t = old.get("source", {}), entry["source"]
            same = all(s.get(k) == t[k] for k in ("repo","commit","path","blob"))
            require(not same or s["last"] < t["first"] or t["last"] < s["first"], "overlapping source meaning")
        result["entries"].append(entry)
    return result
def verify_receipt(receipt, allocation, current, old, online=False, reader=fetch):
    require(receipt["proposed"] == len(receipt["selected"])+len(receipt["held"]) == 40, "candidate accounting")
    require(len({(c["agent"], c["word"]) for c in receipt["selected"]+receipt["held"]}) == 40, "duplicate candidate")
    require(all(c["decision"]=="ACCEPT_CANDIDATE_FOR_CI" and c["span_kind"]=="WHOLE_FUNCTION" for c in receipt["selected"]), "unreviewed candidate")
    require(all(c["decision"]=="HELD" and c["reason"] for c in receipt["held"]), "missing hold reason")
    require(allocate(old,receipt,allocation)==current, "non-deterministic allocation or modified old entries")
    require(len(old["entries"])==allocation["previous_count"] and len(current["entries"])==allocation["new_count"], "row count")
    require(current["next_number"]==allocation["next_number"] and len(receipt["held"])==allocation["held"], "identity accounting")
    require([{"gg_id":e["gg_id"],"sense_key":e["sense_key"],"source":e["source"]} for e in current["entries"][len(old["entries"]):]]==allocation["accepted"], "allocation receipt mismatch")
    validate(current,read("data/translation-geodesy.json"),old)
    if online:
        verify_source_entries(current, reader)
        cache = {}
        for c in receipt["selected"]:
            s, licence = c["source"], c["licence"]
            key = (s["repo"],s["commit"],licence["path"])
            if key not in cache:
                cache[key] = reader(*key)
            raw = cache[key]
            require(git_blob(raw)==licence["blob"] and b"Apache License" in raw and b"Version 2.0" in raw, "licence mismatch")
        # Emit source excerpt hashes only; do not publish or execute upstream code.
        for c in receipt["selected"]:
            s=c["source"]
            key=(s["repo"],s["commit"],s["path"])
            if key not in cache:
                cache[key]=reader(*key)
            raw=cache[key]
            require(git_blob(raw)==s["blob"],"source blob mismatch")
            span=b"".join(raw.splitlines(keepends=True)[s["first"]-1:s["last"]])
            print(c["word"],hashlib.sha256(span).hexdigest(),flush=True)
    return len(current["entries"])
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--online",action="store_true")
    args=p.parse_args()
    receipt=read("data/tacit15-v2-candidate-decisions.json")
    allocation=read("data/tacit15-v2-allocation.json")
    prior=git_bytes(allocation["baseline_commit"],"data/dictionary.json")
    source=git_bytes(allocation["candidate_receipt_commit"],"data/tacit15-v2-candidate-decisions.json")
    require(git_blob(prior)==allocation["prior_dictionary_blob"],"prior blob mismatch")
    require(git_blob(source)==allocation["candidate_receipt_blob"] and source==(ROOT/"data/tacit15-v2-candidate-decisions.json").read_bytes(),"candidate receipt changed")
    print("Validated deterministic dictionary allocation:",verify_receipt(receipt,allocation,read("data/dictionary.json"),json.loads(prior),args.online))
if __name__=="__main__":
    main()
