"""Bounded daily family discovery and reviewed dictionary allocation. Never execute source."""
import argparse
import copy
from dictionary_shards import PATTERNS, tokens
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

def allocate(dictionary, queue, limit=MAX_ADDITIONS):
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
        if limit is not None and len(added) >= limit:
            break
        require(e["word"] == e["word"].upper(), "canonical command must be uppercase")
        aliases=e.get("aliases", [])
        require(isinstance(aliases,list) and all(isinstance(a,str) and key(a) for a in aliases), "invalid aliases")
        require(len({key(e["word"]), *map(key,aliases)}) == len(aliases)+1, "duplicate aliases")
        require(e["kind"] == "FUNCTION" and e["state"] == "STATIC_SOURCE_REVIEW" and e["demo"] is None, "unsupported admission")
        require(1 <= len(tokens(e["word"]).split()) <= 5 and
                len(e["word"]) <= 64 and len(e["purpose"]) <= 240, "command not compact")
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

def verify_extension(historic, current, queue):
    """Replay reviewed appended rows without changing any historic allocation."""
    expected=copy.deepcopy(historic)
    allocate(expected,queue,limit=None)
    n=len(current["entries"])
    require(len(historic["entries"])<=n<=len(expected["entries"]),"unreviewed extension length")
    expected["entries"]=expected["entries"][:n]
    expected["next_number"]=historic["next_number"]+n-len(historic["entries"])
    require(expected==current,"dictionary differs from reviewed daily replay")

def asset_metadata():
    release = json.loads(subprocess.check_output(["gh","api",f"repos/{PRODUCER}/releases/tags/{TAG}"], timeout=30))
    a = [a for a in release["assets"] if a["name"] == ASSET and a["state"] == "uploaded"]
    require(len(a) == 1, "missing producer catalogue")
    a = a[0]
    require(0 < a["size"] <= MAX_COMPRESSED and str(a.get("digest","")).startswith("sha256:"), "producer size/digest")
    return {k:a[k] for k in ("id","size","digest","updated_at")}

def acquire(directory):
    before = asset_metadata()
    asset_path = directory / ASSET
    with asset_path.open("wb") as output:
        subprocess.run(["gh", "api", f"repos/{PRODUCER}/releases/assets/{before['id']}",
                        "-H", "Accept: application/octet-stream"], stdout=output, check=True, timeout=90)
    with asset_path.open("rb") as stream:
        raw = stream.read(MAX_COMPRESSED + 1)
    require(len(raw) == before["size"] and
            "sha256:" + hashlib.sha256(raw).hexdigest() == before["digest"], "producer asset changed or corrupt")
    with gzip.open(directory / ASSET,"rb") as stream:
        payload = stream.read(MAX_UNCOMPRESSED + 1)
    require(len(payload) <= MAX_UNCOMPRESSED, "uncompressed catalogue too large")
    d = json.loads(payload)
    require(isinstance(d["families"],dict) and isinstance(d["family_by_hash"],dict), "producer schema")
    return d, before

def family_identities(catalogue):
    identities = {}
    for digest, number in catalogue["family_by_hash"].items():
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{40,64}", digest) and
                type(number) is int and number > 0 and number not in identities,
                "invalid or duplicate permanent family identity")
        identities[number] = digest
    require(identities and all(int(n) in identities for n in catalogue["families"]),
            "invalid producer placement identities")
    return identities


def checkpoint_cursor(checkpoint, identities):
    if checkpoint is None:
        return 0
    require(checkpoint.get("schema") == "vedic.daily-family-pulse.v2", "unsupported checkpoint schema")
    cursor = checkpoint.get("next_cursor")
    require(type(cursor) is int and cursor >= 0, "invalid checkpoint cursor")
    require((cursor == 0 or cursor in identities) and
            identities.get(cursor) == checkpoint.get("cursor_family_hash"),
            "checkpoint family identity changed")
    return cursor


def family_rows(catalogue, identities, entries, cursor):
    words, symbols, mapped, _ = indexes(entries)
    selected = sorted(n for n in identities if n > cursor)[:BATCH]
    rows = []
    for n in selected:
        placement = catalogue["families"].get(str(n))
        v = placement or {}
        names = [x for x in v.get("names",[]) if isinstance(x,str) and x != "(anonymous)"]
        possible = sorted({x for x in names if key(x) in words or key(x) in symbols})
        if n in mapped:
            status = "MAPPED_FAMILY"
        elif placement is None:
            status = "NO_CURRENT_PLACEMENT"
        elif possible:
            status = "POSSIBLE_EXISTING_COMMAND"
        else:
            status = "REVIEW_REQUIRED"
        terms=set(tokens(" ".join(names)).split())
        groups=sorted(p for p,words in PATTERNS.items() if terms.intersection(words))
        labels=sorted({tokens(name).upper() for name in names if tokens(name)})
        rows.append((n,json.dumps(names),int(v.get("repos",0)),json.dumps(v.get("places",[])),status,json.dumps(possible),json.dumps(groups),json.dumps(labels)))
    return rows, selected[-1] if selected else cursor

def export_pulse(rows, out):
    import duckdb
    db = duckdb.connect()
    try:
        db.execute("CREATE TABLE pulse(family_id BIGINT, names_json VARCHAR, repository_count INTEGER, occurrences_json VARCHAR, status VARCHAR, possible_matches_json VARCHAR, pattern_groups_json VARCHAR, candidate_labels_json VARCHAR)")
        if rows:
            db.executemany("INSERT INTO pulse VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        # Parameterised destination; never copy code or the whole producer database.
        db.execute("COPY (SELECT * FROM pulse ORDER BY family_id) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(out)])
        require(db.execute("SELECT count(*) FROM read_parquet(?)",[str(out)]).fetchone()[0] == len(rows), "Parquet round trip")
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT/"receipts")
    args = parser.parse_args()
    d, queue = read(DICT), read(QUEUE)
    prior = json.loads(json.dumps(d))
    with tempfile.TemporaryDirectory(prefix="vedic-family-") as temp:
        catalogue, asset = acquire(Path(temp))
        identities = family_identities(catalogue)
        prior_checkpoint = read(args.checkpoint) if args.checkpoint else None
        cursor = checkpoint_cursor(prior_checkpoint, identities)
        for c in queue["records"]:
            require(set(c["family_refs"]) <= identities.keys(),"unknown Modular Star family")
        added, held = allocate(d,queue)
        out = args.output
        if added:
            validate(d,read(ROOT/"data/translation-geodesy.json"),prior)
            verify_source_entries({"entries":[e for e in d["entries"] if e["gg_id"] in added]})
            write(out/"admission/dictionary.json",d)
        rows, next_cursor = family_rows(catalogue,identities,d["entries"],cursor)
        out.mkdir(parents=True,exist_ok=True)
        export_pulse(rows,out/"family-pulse.parquet")
        write(out/"family-research.json",{"schema":"vedic.daily-family-pulse.v2","producer_asset":asset,
              "producer_family_count":len(identities),"current_placement_family_count":len(catalogue["families"]),
              "scanned_families":len(rows),"previous_cursor":cursor,"next_cursor":next_cursor,
              "cursor_family_hash":identities.get(next_cursor),"status":"research_candidates" if rows else "no_change",
              "dictionary_count":len(prior["entries"]),"proposed_dictionary_count":len(d["entries"]),
              "proposed_additions":added,"held":held,"execution_claim":False,
              "coverage":"permanent family IDs; placement metadata where present"})
if __name__ == "__main__":
    main()
