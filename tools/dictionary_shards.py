"""Deterministic Pages-only search index and 100-command detail pages."""
import json
import re
from pathlib import Path

INDEX = "data/command-index.json"
PREFIX = "data/command-pages/"
SIZE = 100
PATTERNS = {
    "Find and select": "find search choose pick nearest lookup geocode query locate".split(),
    "Measure and calculate": "measure calculate distance bearing area length loss voltage power energy estimate convert".split(),
    "Check and validate": "validate verify check assert invariant quality".split(),
    "Load and transform data": "load fetch read decode normalize normalise parse index sample import export convert".split(),
    "Filter and rank": "filter rank score sort select".split(),
    "Navigate and display": "navigate render display fly view open present map browse link guidance".split(),
    "Explain and inspect": "explain describe inspect report summarise summarize".split(),
    "Build and combine": "build combine compose aggregate total balance merge".split(),
}
def tokens(value):
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(value))
    return " ".join(re.findall(r"[^\W_]+",value.casefold()))

def encode(value):
    return (json.dumps(value,ensure_ascii=False,separators=(",",":"))+"\n").encode()

def build(d,t):
    meanings={r["id"]:r.get("purpose","") for r in t["records"]}
    rows=sorted(d["entries"],key=lambda e:(e["word"].casefold(),e["number"]))
    result, index = {}, []
    for start in range(0,len(rows),SIZE):
        path=f"{PREFIX}{start//SIZE+1:06d}.json"
        detail=[]
        for e in rows[start:start+SIZE]:
            purpose=meanings.get(e.get("translation_ref"),e.get("purpose","")) or ""
            symbol=(e.get("translation_ref") or "").rsplit(":",1)[-1]
            aliases=e.get("aliases",[])
            tags=e.get("pattern_tags",[])
            if not isinstance(tags,list) or any(not isinstance(x,str) or not x.strip() or len(x)>64 for x in tags):
                raise ValueError("invalid reviewed pattern tags")
            terms=set(tokens(" ".join([e["word"],symbol,purpose,*aliases])).split())
            patterns=sorted(set(tags+[p for p,w in PATTERNS.items() if terms.intersection(w)]),key=str.casefold)
            row={k:e[k] for k in ("gg_id","number","word","estate_group","discipline","vedic_class_candidate","created_utc")}
            app=e.get("application") or {}
            row.update(purpose=purpose, launch=[app["name"],app["url"]] if app else None,
                       priority=e.get("priority",9),page=path,components=e.get("components",[]),patterns=patterns,
                       search=tokens(" ".join([e["word"],e["gg_id"],purpose,e["estate_group"],e["discipline"],
                             e["vedic_class_candidate"],symbol,*aliases,*patterns,
                             *("family "+str(n) for n in e.get("modular_family_refs",[]))])))
            index.append(row)
            detail.append({**e,"patterns":patterns})
        result[path]=encode({"schema":"vedic.command-page.v1","entries":detail})
    result[INDEX]=encode({"schema":"vedic.command-index.v1","count":len(index),"page_size":SIZE,"resources":d["resources"],"entries":index})
    return result

def write_bundle(root):
    root=Path(root)
    files=build(json.loads((root/"data/dictionary.json").read_bytes()),json.loads((root/"data/translation-geodesy.json").read_bytes()))
    for p in (root/PREFIX).glob("*.json"):
        p.unlink()
    for name,raw in files.items():
        p=root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(raw)
    return files
