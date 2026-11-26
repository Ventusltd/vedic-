"""Bounded, append-only admission of source-reviewed VEDIC contracts.

No source execution, model API, or renumbering. The source manifest is a
durable input queue; its entries are not automatically semantic proof.
"""
import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from family_pulse import key, read, write, require
from source_evidence import POLICY, POLICY_SCHEMA, POLICY_STATE, source_link, verify_exact_span
from validate_dictionary import validate
from validate_translation import fetch

ROOT = Path(__file__).resolve().parents[1]
BASE = "bfc4924495dfe14ab9c074bc7a2af36c32281680"
LEGACY = "a888ef8f20da773d4056cc64a0821495f9dd7631"
DICT = "data/dictionary.json"
QUEUE = "data/source-command-candidates.json"
ARCHIVE = "data/admitted-queue-archive.json"
SCHEMA = "vedic.source-admission-archive.v1"
LIMIT = 20
DEFAULT_OUTPUT = ROOT / "receipts" / "source-admissions"

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, timeout=30)

def pinned(commit, path):
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "invalid manifest commit")
    return json.loads(git("show", f"{commit}:{path}"))

def stamp(commit):
    epoch = int(git("show", "-s", "--format=%ct", commit).strip())
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def contract(c):
    return hashlib.sha256(json.dumps([key(c["purpose"]), [key(x) for x in c["inputs"]],
        key(c["output"]), key(c["limits"])], separators=(",", ":")).encode()).hexdigest()

def candidate_id(c):
    return hashlib.sha256(json.dumps(c["source"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def contract_payload(candidate):
    return {key: value for key, value in candidate.items() if key != "policy_receipt"}


def policy_contract_digest(candidate):
    body = json.dumps(contract_payload(candidate), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def make_policy_receipt(candidate, raw):
    return {
        "schema": POLICY_SCHEMA,
        "policy": POLICY,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "contract_sha256": policy_contract_digest(candidate),
    }


def verify_policy_receipt(candidate):
    receipt = candidate.get("policy_receipt")
    require(isinstance(receipt, dict) and set(receipt) == {
        "schema", "policy", "source_sha256", "contract_sha256"
    }, "missing strict policy receipt")
    require(receipt["schema"] == POLICY_SCHEMA and receipt["policy"] == POLICY,
            "unsupported source policy")
    require(isinstance(receipt["source_sha256"], str) and
            re.fullmatch(r"[0-9a-f]{64}", receipt["source_sha256"]),
            "invalid policy source digest")
    require(receipt["contract_sha256"] == policy_contract_digest(candidate),
            "policy receipt does not bind candidate contract")
    source = candidate.get("source")
    require(isinstance(source, dict) and set(source) == {
        "repo", "commit", "blob", "path", "first", "last"
    }, "invalid policy source fields")
    require(candidate.get("receipt") == source_link(source),
            "policy evidence must link to the exact pinned source")


def read_policy_source(repo, commit, path):
    return fetch(repo, commit, quote(path, safe="/"))


def verify_policy_candidate(candidate, raw):
    verify_policy_receipt(candidate)
    from daily_source_policy import POLICY as REPRODUCER_POLICY, reproduce_candidate

    require(REPRODUCER_POLICY == POLICY, "unexpected source policy implementation")
    verify_exact_span(candidate["source"], candidate["symbol"], raw)
    require(candidate["policy_receipt"] == make_policy_receipt(candidate, raw),
            "policy receipt does not bind pinned source bytes")
    require(reproduce_candidate(candidate["source"], raw) == contract_payload(candidate),
            "candidate differs from exact policy reproduction")


def allocate_one(d, c, manifest, timestamp):
    require(isinstance(c, dict), "invalid candidate")
    w, sym = c["word"], c["symbol"]
    require(bool(re.fullmatch(r"[A-Z][A-Z0-9]*(?: [A-Z0-9]+){0,4}", w)) and len(w)<=64, "invalid canonical label")
    require(bool(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", sym)), "invalid symbol")
    require(isinstance(c["purpose"],str) and 0<len(c["purpose"])<=240, "purpose")
    require(isinstance(c["limits"],str) and 0<len(c["limits"])<=600, "limits")
    require(isinstance(c["output"],str) and 0<len(c["output"])<=300, "output")
    require(isinstance(c["inputs"],list) and all(isinstance(x,str) and x for x in c["inputs"]), "inputs")
    aliases=c.get("aliases",[])
    require(isinstance(aliases,list) and all(isinstance(x,str) and key(x) for x in aliases), "aliases")
    labels={key(w),*map(key,aliases)}
    require(len(labels)==1+len(aliases), "duplicate aliases")
    s=c["source"]
    require(bool(re.fullmatch(r"Ventusltd/[A-Za-z0-9][A-Za-z0-9_.-]*",s["repo"])), "source repository")
    require(all(re.fullmatch(r"[0-9a-f]{40}",s[k]) for k in ("commit","blob")), "source pin")
    require(bool(re.fullmatch(r"[A-Za-z0-9_. /-]+",s["path"])) and
            not {"", ".", ".."}.intersection(s["path"].split("/")), "source path")
    require(type(s["first"]) is int and type(s["last"]) is int and 1<=s["first"]<=s["last"], "source span")
    ref=f"source-command:{s['repo']}:{sym}"
    fingerprint = contract(c)
    for old in d["entries"]:
        old_labels={key(old["word"]),*map(key,old.get("aliases",[]))}
        old_sym=key((old.get("translation_ref") or "").rsplit(":",1)[-1])
        require(not labels.intersection(old_labels|{old_sym}) and key(sym) not in old_labels|{old_sym}, "duplicate label or symbol")
        require(old["sense_key"]!="function:"+ref, "duplicate sense")
        t=old.get("source") or {}
        if all(s[k]==t.get(k) for k in ("repo","path","blob")):
            require(s["last"]<t["first"] or s["first"]>t["last"], "overlapping source occurrence")
        if old.get("contract_fingerprint"):
            require(old["contract_fingerprint"]!=fingerprint, "duplicate contract")
    n=d["next_number"]
    row={k:copy.deepcopy(c[k]) for k in ("word","purpose","limits","inputs","output",
        "estate_group","discipline","periodic_category","vedic_class_candidate","source","receipt")}
    row.update(number=n,gg_id=f"GG2050-VEDIC-{n:06d}",kind="FUNCTION",
        translation_ref=ref,sense_key="function:"+ref,aliases=aliases,
        fixture_status="Static source reviewed; runtime not verified",
        demo=None,demo_unavailable_reason="No independently admitted executable package.",
        state="STATIC_SOURCE_REVIEW",classification_state="CURATED_CANDIDATE",
        periodic_block_candidate="Unresolved",created_utc=timestamp,
        creation_evidence=f"https://github.com/Ventusltd/vedic-/commit/{manifest}",
        priority=2,family_id=None,element_id=None,tablet_id=None,line_ids=None,proof=None,
        contract_fingerprint=fingerprint,admission_policy="source-reviewed-v1",
        application={"name":c["estate_group"],"url":f"https://github.com/{s['repo']}/blob/{s['commit']}/{quote(s['path'])}#L{s['first']}-L{s['last']}",
            "instructions":"Inspect the pinned source and input contract.","state":"RELATED_APPLICATION_RUNTIME_UNVERIFIED"})
    if "policy_receipt" in c:
        row["admission_policy"] = POLICY
        row["state"] = POLICY_STATE
        row["policy_receipt"] = copy.deepcopy(c["policy_receipt"])
        row["fixture_status"] = "Static source contract reproduced by policy; runtime not verified"
    d["entries"].append(row)
    d["next_number"]+=1
    return row

def replay(base, archive, load=pinned, date=stamp, *, legacy_records=(), checker=None):
    require(archive["schema"]==SCHEMA and archive["baseline_commit"]==BASE,"archive schema")
    d=copy.deepcopy(base)
    records = archive["records"]
    require(isinstance(records, list) and records[:len(legacy_records)] == list(legacy_records),
            "immutable legacy source-admission archive prefix changed")
    cache={}
    seen=set()
    for position, a in enumerate(records):
        m=a["manifest_commit"]
        if m not in cache:
            q=load(m,QUEUE)
            require(q["schema"]=="vedic.source-candidates.v1","manifest schema")
            cache[m]=(q["records"],date(m))
        manifest_records,timestamp=cache[m]
        i=a["index"]
        require(type(i) is int and 0<=i<len(manifest_records),"manifest index")
        c=manifest_records[i]
        require(a["candidate"]==c and a["candidate_id"]==candidate_id(c),"archive evidence mismatch")
        require(a["candidate_id"] not in seen,"duplicate archived source")
        seen.add(a["candidate_id"])
        strict = position >= len(legacy_records)
        if strict:
            verify_policy_receipt(c)
        allocate_one(d,c,m,timestamp)
        if strict and checker is not None:
            checker(c)
    return d

def replay_published(base, archive, *, checker=None):
    legacy = pinned(LEGACY, ARCHIVE)
    return replay(base, archive, legacy_records=legacy["records"], checker=checker)


def prepare(d, archive, queue, manifest, timestamp, checker, limit=LIMIT):
    require(queue["schema"]=="vedic.source-candidates.v1","queue schema")
    require(type(limit) is int and 0<=limit<=LIMIT,"admission budget")
    known={a["candidate_id"] for a in archive["records"]}
    held=[];added=[]
    for i,c in enumerate(queue["records"]):
        if len(added)>=limit: break
        before=len(d["entries"])
        try:
            cid=candidate_id(c)
            if cid in known: continue
            verify_policy_receipt(c)
            row=allocate_one(d,c,manifest,timestamp)
            checker(c)
        except (ValueError,KeyError,TypeError,AttributeError,IndexError) as exc:
            if len(d["entries"])>before:
                d["entries"].pop();d["next_number"]-=1
            held.append({"index":i,"reason":str(exc)[:240]})
            continue
        archive["records"].append({"manifest_commit":manifest,"index":i,"candidate_id":cid,"candidate":c})
        known.add(cid);added.append(row["gg_id"])
    return added,held

def stage_proposal(destination, dictionary, archive):
    destination = destination.resolve()
    require(not destination.exists(), "proposal destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".admission-", dir=destination.parent) as temporary:
        snapshot = Path(temporary) / "snapshot"
        write(snapshot / DICT, dictionary)
        write(snapshot / ARCHIVE, archive)
        snapshot.rename(destination)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--check",action="store_true")
    p.add_argument("--prepare",action="store_true")
    p.add_argument("--limit",type=int,default=LIMIT)
    p.add_argument("--online", action="store_true", help="independently reproduce archived policy contracts")
    p.add_argument("--output-dir", type=Path, help="stage proposed dictionary and archive together")
    args=p.parse_args()
    require(args.check!=args.prepare,"choose exactly one mode")
    require(not args.check or args.output_dir is None, "--output-dir requires --prepare")

    source_cache = {}

    def check_policy(candidate):
        source = candidate["source"]
        key = source["repo"], source["commit"], source["path"]
        if key not in source_cache:
            source_cache[key] = read_policy_source(*key)
        verify_policy_candidate(candidate, source_cache[key])

    base=pinned(BASE,DICT)
    current=read(ROOT/DICT)
    archive=read(ROOT/ARCHIVE)
    require(replay_published(base, archive, checker=check_policy if args.online else None) == current,
            "dictionary differs from exact source-admission replay")
    if args.check:
        print("Exact source-admission replay:",len(current["entries"]))
        return
    manifest=git("log","-1","--format=%H","--",QUEUE).decode().strip()
    queue=pinned(manifest,QUEUE)
    require(queue==read(ROOT/QUEUE),"uncommitted candidate manifest")
    translations=read(ROOT/"data/translation-geodesy.json")
    def check(candidate):
        validate(current,translations,base)
        check_policy(candidate)
    added,held=prepare(current,archive,queue,manifest,stamp(manifest),check,args.limit)
    require(replay_published(base, archive) == current,"proposal replay mismatch")
    destination = args.output_dir or DEFAULT_OUTPUT
    if added:
        stage_proposal(destination, current, archive)
    print(json.dumps({"added":added,"held":held,"count":len(current["entries"]),
                      "output_dir": str(destination.resolve()) if added else None}))

if __name__=="__main__":
    main()
