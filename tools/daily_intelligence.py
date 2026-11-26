"""Bounded daily family discovery and reviewed dictionary allocation. Never execute source."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from validate_dictionary import validate, verify_source_entries

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = "Ventusltd/stars"
TAG = "modular-star"
ASSET = "catalog.json.gz"
MAX_COMPRESSED = 16 * 1024**2
MAX_UNCOMPRESSED = 96 * 1024**2
BATCH = 100
MAX_ADDITIONS = 20
QUEUE = ROOT / "data/daily-command-queue.json"
DICT = ROOT / "data/dictionary.json"

def require(ok, message):
    if not ok:
        raise ValueError(message)

def key(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def indexes(entries):
    words, symbols, families, senses = set(), set(), set(), set()
    for e in entries:
        words.add(key(e["word"]))
        words.update(key(a) for a in e.get("aliases", []))
        if e.get("translation_ref"):
            symbols.add(key(e["translation_ref"].rsplit(":", 1)[-1]))
        families.update(e.get("modular_family_refs", []))
        if type(e.get("family_id")) is int:
            families.add(e["family_id"])
        senses.add(e["sense_key"])
    return words, symbols, families, senses

def allocate(dictionary, queue):
    """Allocate only explicitly reviewed, pinned functions; no inferred semantics."""
    require(queue["schema"] == "vedic.daily-command-queue.v1", "queue schema")
    words, symbols, families, senses = indexes(dictionary["entries"])
    added, held = [], []
    for c in queue["records"]:
        require(c["decision"] == "REVIEWED_FOR_ADMISSION", "unreviewed command")
        require(isinstance(c["family_refs"], list) and c["family_refs"] and
                all(type(f) is int and f > 0 for f in c["family_refs"]), "family refs")
        e = c["entry"]
        name = key(e["word"])
        sym = key(e["translation_ref"].rsplit(":", 1)[-1])
        if not name or name in words or name in symbols or sym in words or sym in symbols or e["sense_key"] in senses or families.intersection(c["family_refs"]):
            held.append({"word": e["word"], "reason": "existing word, symbol, sense or family; reconcile, do not duplicate"})
            continue
        if len(added) >= MAX_ADDITIONS:
            break
        require(e["kind"] == "FUNCTION" and e["state"] == "STATIC_SOURCE_REVIEW" and e["demo"] is None, "unsupported admission")
        require(len(e["word"]) <= 64 and len(e["purpose"]) <= 240, "command not compact")
        require(e.get("application") and e["application"]["url"].startswith("https://"), "application/source reference")
        require(not any(key(a) in words or key(a) in symbols for a in e.get("aliases", [])), "alias collision")
        n = dictionary["next_number"]
        row = dict(e, number=n, gg_id=f"GG2050-VEDIC-{n:06d}", modular_family_refs=sorted(set(c["family_refs"])))
        dictionary["entries"].append(row)
        dictionary["next_number"] += 1
        added.append(row["gg_id"])
        words.add(name); words.update(key(a) for a in e.get("aliases", []))
        symbols.add(sym); families.update(c["family_refs"]); senses.add(e["sense_key"])
    return added, held

def asset_metadata():
    release = json.loads(subprocess.check_output(["gh","api",f"repos/{PRODUCER}/releases/tags/{TAG}"], timeout=30))
    a = [a for a in release["assets"] if a["name"] == ASSET and a["state"] == "uploaded"]
    require(len(a) == 1, "missing producer catalogue")
    a = a[0]
    require(0 < a["size"] <= MAX_COMPRESSED and str(a.get("digest","")).startswith("sha256:"), "producer size/digest")
    return {k:a[k] for k in ("id","size","digest","updated_at")}

def acquire(directory):
    before = asset_metadata()
    subprocess.run(["gh","release","download",TAG,"--repo",PRODUCER,"--pattern",ASSET,"--dir",str(directory)],check=True,timeout=90)
    raw = (directory / ASSET).read_bytes()
    require(before == asset_metadata() and len(raw) == before["size"] and
            "sha256:" + hashlib.sha256(raw).hexdigest() == before["digest"], "producer asset changed or corrupt")
    with gzip.open(directory / ASSET,"rb") as stream:
        payload = stream.read(MAX_UNCOMPRESSED + 1)
    require(len(payload) <= MAX_UNCOMPRESSED, "uncompressed catalogue too large")
    d = json.loads(payload)
    require(isinstance(d["families"],dict) and isinstance(d["family_by_hash"],dict), "producer schema")
    return d, before

def family_rows(catalogue, entries, cursor):
    words, symbols, mapped, _ = indexes(entries)
    families = sorted((int(n), v) for n,v in catalogue["families"].items())
    require(families, "empty producer catalogue")
    unseen = [(n,v) for n,v in families if n > cursor]
    selected = (unseen or families)[:BATCH]
    rows = []
    for n,v in selected:
        names = [x for x in v.get("names",[]) if isinstance(x,str) and x != "(anonymous)"]
        possible = sorted({x for x in names if key(x) in words or key(x) in symbols})
        status = "MAPPED_FAMILY" if n in mapped else "POSSIBLE_EXISTING_COMMAND" if possible else "REVIEW_REQUIRED"
        rows.append((n,json.dumps(names),int(v["repos"]),json.dumps(v.get("places",[])),status,json.dumps(possible)))
    return rows, selected[-1][0], len(families)

def export_pulse(rows, out):
    import duckdb
    db = duckdb.connect()
    try:
        db.execute("CREATE TABLE pulse(family_id BIGINT, names_json VARCHAR, repository_count INTEGER, occurrences_json VARCHAR, status VARCHAR, possible_matches_json VARCHAR)")
        db.executemany("INSERT INTO pulse VALUES (?, ?, ?, ?, ?, ?)", rows)
        # Parameterised destination; never copy code or the whole producer database.
        db.execute("COPY (SELECT * FROM pulse ORDER BY family_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(out)])
        require(db.execute("SELECT count(*) FROM read_parquet(?)",[str(out)]).fetchone()[0] == len(rows), "Parquet round trip")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cursor",type=int,default=0)
    args = parser.parse_args()
    d, queue = read(DICT), read(QUEUE)
    prior = json.loads(json.dumps(d))
    with tempfile.TemporaryDirectory(prefix="vedic-family-") as temp:
        catalogue, asset = acquire(Path(temp))
        family_ids = {int(n) for n in catalogue["families"]}
        for c in queue["records"]:
            require(set(c["family_refs"]) <= family_ids,"unknown Modular Star family")
        added, held = allocate(d,queue)
        if added:
            validate(d,read(ROOT/"data/translation-geodesy.json"),prior)
            verify_source_entries({"entries":[e for e in d["entries"] if e["gg_id"] in added]})
            write(DICT,d)
        rows, cursor, total = family_rows(catalogue,d["entries"],args.cursor)
        out = ROOT/"receipts"
        out.mkdir(exist_ok=True)
        export_pulse(rows,out/"family-pulse.parquet")
        write(out/"daily-research.json",{"schema":"vedic.daily-family-pulse.v1","producer_asset":asset,
              "producer_family_count":total,"scanned_families":len(rows),"next_cursor":cursor,
              "dictionary_count":len(d["entries"]),"added":added,"held":held,
              "execution_claim":False,"coverage":"family candidates, not semantic or executable coverage"})
        print(json.dumps({"added":added,"next_cursor":cursor,"family_count":total}))
if __name__ == "__main__":
    main()
