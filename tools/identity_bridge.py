"""TACIT 10: exact read-only joins to Modular Star and Kuiper producer receipts.

No scanner, allocator, semantic inference, runtime execution or publication.
Producer element IDs describe indexed physical spans, not semantic equivalence.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import struct
from contextlib import closing
from pathlib import Path

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def pinned(s):
    require(re.fullmatch(r"Ventusltd/[A-Za-z0-9_.-]+", s["repo"]), "bad repo")
    require(all(re.fullmatch(r"[0-9a-f]{40}", s[k]) for k in ("commit", "blob")), "bad Git pin")
    require(s["path"] and all(p not in ("", ".", "..") for p in s["path"].split("/")), "bad path")
    require(type(s["first"]) is int and type(s["last"]) is int and 1 <= s["first"] <= s["last"], "bad span")
    return s

def stars_join(db, s):
    s = pinned(s)
    result = {"state": "OCCURRENCE_NOT_INDEXED", "tablet_id": None, "line_ids": None,
              "element_id": None, "family_id": None, "element_candidates": [], "span_sha256": None}
    row = db.execute("""SELECT t.n,t.git_blob,t.lines,t.issue FROM occurrence o
        JOIN tablet t ON t.n=o.tablet WHERE o.repo=? AND o.commit_sha=? AND o.path=?""",
        (s["repo"], s["commit"], s["path"])).fetchone()
    if row is None:
        return result
    tablet, blob, packed, issue = row
    require(blob == s["blob"], "indexed occurrence blob differs from pin")
    require(isinstance(packed, bytes) and len(packed) % 4 == 0, "bad packed tablet")
    ids = [x[0] for x in struct.iter_unpack("<I", packed)]
    require(all(ids) and s["last"] <= len(ids), "invalid tablet/span")
    texts = []
    for i in ids:
        line = db.execute("SELECT sha,text FROM line WHERE n=?", (i,)).fetchone()
        require(line is not None and hashlib.sha256(line[1]).digest() == line[0], "invalid permanent line")
        texts.append(line[1])
    require(git_blob(b"".join(texts)) == blob, "tablet reconstruction differs from Git blob")
    selected = ids[s["first"]-1:s["last"]]
    chunk = b"".join(texts[s["first"]-1:s["last"]])
    result.update(state="EXACT_OCCURRENCE_LINES", tablet_id=tablet, line_ids=selected,
                  span_sha256=sha(chunk), parse_issue=issue)
    matches = db.execute("""SELECT te.element,e.family,te.col0,te.col1,te.name,e.sha,f.n
        FROM tablet_element te JOIN element e ON e.n=te.element
        LEFT JOIN family f ON f.n=e.family
        WHERE te.tablet=? AND te.first=? AND te.last=? ORDER BY te.element""",
        (tablet,s["first"],s["last"])).fetchall()
    for eid, fid, c0, c1, name, esha, family in matches:
        require(family is not None and esha == hashlib.sha256(chunk).digest(), "invalid element identity")
        result["element_candidates"].append({"element_id":eid,"family_id":fid,"col0":c0,"col1":c1,"name":name})
    # An exact physical span is not necessarily an exact AST node. Multiple candidates abstain.
    # If columns are supplied by a separately verified contract, require both to match.
    eligible = result["element_candidates"]
    if "col0" in s or "col1" in s:
        require(type(s.get("col0")) is int and type(s.get("col1")) is int, "partial column pin")
        eligible = [e for e in eligible if (e["col0"],e["col1"]) == (s["col0"],s["col1"])]
    if len(eligible) == 1 and not issue:
        result.update(state="EXACT_INDEXED_PHYSICAL_SPAN", element_id=eligible[0]["element_id"],
                      family_id=eligible[0]["family_id"])
    elif len(eligible) > 1:
        result["state"] = "AMBIGUOUS_ELEMENT_SPAN"
    return result

def request(s, meaning):
    return {"id":meaning, "repo":s["repo"].split("/",1)[1], "commit":s["commit"],
            "path":s["path"], "blob":s["blob"], "line":s["first"]}

def kuiper_join(s, receipt):
    # Existing edition_keys.py output; a successful arithmetic check is not an independent wafer replay.
    q = request(s, "")
    candidates = [r for r in receipt.get("bodies", []) if all(r.get(k)==q[k] for k in ("repo","commit","path","blob","line"))]
    if len(candidates) != 1:
        return {"state":"NO_UNIQUE_PRODUCER_RECEIPT","key":None}
    r = candidates[0]
    space = receipt.get("summary",{}).get("wafer_address_space")
    ints = ("key","k0","lines_before","commit_lines_measured","commit_lines_wafer","blob_lines","wafer_row")
    valid = (r.get("verified") is True and r.get("on_wafer") is True and r.get("blob_matches_body") is True
             and r.get("blob_at_path")==s["blob"] and r.get("repo_on_wafer")==q["repo"]
             and not r.get("wafer_rows_same_sha12") and r.get("quote_matches") is not False
             and all(type(r.get(k)) is int and r[k]>=0 for k in ints)
             and type(space) is int and 0<=r["key"]<space
             and r["commit_lines_measured"]==r["commit_lines_wafer"]
             and r["blob_lines"]>=s["first"]
             and r["lines_before"]+r["blob_lines"]<=r["commit_lines_measured"]
             and r["key"]==r["k0"]+r["lines_before"]+s["first"]-1)
    if not valid:
        return {"state":"PRODUCER_RECEIPT_REFUSED","key":None}
    return {"state":"PINNED_PRODUCER_RECEIPT_MATCH_NOT_WAFER_REPLAY","key":r["key"],
            "wafer_row":r["wafer_row"],"wafer_address_space":space}

def resolve(dictionary, translations, database, expected_sha, receipt=None):
    require(digest(database)==expected_sha, "snapshot digest mismatch")
    require(not any(Path(str(database)+suffix).exists() for suffix in ("-wal","-journal")), "snapshot has sidecar")
    tr = {e["id"]:e for e in translations["records"]}
    require(len(tr)==len(translations["records"]), "duplicate translation")
    output, requests = [], []
    seen = set()
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        require(db.execute("PRAGMA quick_check").fetchall()==[("ok",)], "database integrity")
        require(db.execute("SELECT count(*) FROM occurrence").fetchone()[0]>0,"empty producer")
        for e in dictionary["entries"]:
            mid=e["gg_id"]
            require(mid not in seen,"duplicate meaning")
            seen.add(mid)
            s=e.get("source") or tr.get(e.get("translation_ref"),{}).get("source")
            if s is None:
                require(e["kind"]=="COMPOSITION","function without pin")
                output.append({"gg_id":mid,"state":"COMPOSITION_COMPONENTS_ONLY","components":e.get("components",[])})
                continue
            s=pinned(s)
            requests.append(request(s,mid))
            output.append({"gg_id":mid,"source":s,"stars":stars_join(db,s),
                           "kuiper":kuiper_join(s,receipt) if receipt is not None else {"state":"NOT_REPLAYED","key":None}})
    require(digest(database)==expected_sha,"snapshot changed during read")
    require(requests,"no source pins examined")
    return {"schema":"vedic.identity-bridge.v1","snapshot_sha256":expected_sha,
            "entries":output,"kuiper_requests":requests,
            "exact_occurrences":sum(e.get("stars",{}).get("tablet_id") is not None for e in output),
            "exact_physical_elements":sum(e.get("stars",{}).get("element_id") is not None for e in output),
            "receipt_matches":sum(e.get("kuiper",{}).get("key") is not None for e in output),
            "indexed_unique_line_ids":len({i for e in output for i in (e.get("stars",{}).get("line_ids") or [])}),
            "runtime_verified":False,"translated_unique_lines":None}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database",type=Path,required=True)
    p.add_argument("--snapshot-sha",required=True)
    p.add_argument("--dictionary",type=Path,default=Path("data/dictionary.json"))
    p.add_argument("--translations",type=Path,default=Path("data/translation-geodesy.json"))
    p.add_argument("--kuiper-receipt",type=Path)
    p.add_argument("--kuiper-sha")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--requests",type=Path,required=True)
    a=p.parse_args()
    receipt=None
    if a.kuiper_receipt:
        raw=a.kuiper_receipt.read_bytes()
        require(a.kuiper_sha==sha(raw),"Kuiper receipt digest mismatch")
        receipt=json.loads(raw)
    result=resolve(json.loads(a.dictionary.read_text()),json.loads(a.translations.read_text()),
                   a.database,a.snapshot_sha,receipt)
    result["kuiper_receipt_sha256"]=a.kuiper_sha if receipt is not None else None
    for path,data in ((a.output,result),(a.requests,result["kuiper_requests"])):
        with path.open("x",encoding="utf-8") as f:
            json.dump(data,f,indent=2,sort_keys=True); f.write("\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("entries","kuiper_requests")},indent=2))

if __name__=="__main__":
    main()
