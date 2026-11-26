"""Two retrieval cohorts: curated VEDIC meanings and compiled producer families.

Ranks evidence, never authorizes execution; scores are not comparable across cohorts.
No new VEDIC or producer IDs. Limits are displayed but never positive search features.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from stars_retrieval import Index, load_library, tokens, require, PRODUCER_BLOB, EXPECTED_COUNT


def text(value):
    if isinstance(value, list):
        return " ".join(text(x) for x in value)
    return str(value or "")


def curated_records(dictionary, translations):
    require(dictionary["schema"] == "vedic.dictionary.v1", "wrong dictionary schema")
    refs = {r["id"]: r for r in translations["records"]}
    seen = set()
    result = []
    for e in dictionary["entries"]:
        ident = e["gg_id"]
        require(ident not in seen, "duplicate meaning")
        seen.add(ident)
        t = refs.get(e.get("translation_ref"), {})
        purpose = e.get("purpose") or t.get("purpose")
        require(bool(purpose), "meaning without purpose")
        source = e.get("source") or t.get("source")
        kind = e["kind"]
        require((kind == "FUNCTION" and source) or
                (kind == "COMPOSITION" and e.get("components")), "missing source or components")
        # Positive purpose, declared inputs/outputs, app/domain context. Never
        # index limitations as capabilities: "not a route" is not route planning.
        result.append({
            "gg_id": ident, "word": e["word"], "purpose": purpose, "kind": kind,
            "source": source, "components": e.get("components", []),
            "declared_inputs": e.get("inputs"), "declared_output": e.get("output"),
            "limits": e.get("limits") or t.get("limits"),
            "application": e.get("application"),
            "source_state": e.get("state", "UNVERIFIED"),
            "execution_state": "NOT_AUTHORIZED",
            "features": {
                "symbol": Counter(tokens(text([e["word"], purpose]))),
                "context": Counter(tokens(text([e.get("estate_group"), e.get("discipline")]))),
                "body": Counter(tokens(text([t.get("name"), e.get("inputs"), e.get("output"),
                                             t.get("inputs"), t.get("outputs")]))),
            },
        })
    require(all(x in seen for r in result for x in r["components"]), "missing component")
    return result


def search(curated, producer, query, limit=5):
    return {
        "query": query,
        "curated_meanings": curated.query(query, limit),
        "compiled_candidates": producer.query(query, limit),
        "decision": "REVIEW_REQUIRED_NO_EXECUTION",
        "cross_cohort_scores_comparable": False,
        "identity_join_state": "NOT_PERFORMED",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dictionary", type=Path, required=True)
    p.add_argument("--translations", type=Path, required=True)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--query", action="append", default=[])
    a = p.parse_args()
    d = json.loads(a.dictionary.read_text(encoding="utf-8"))
    t = json.loads(a.translations.read_text(encoding="utf-8"))
    cr = curated_records(d,t)
    pr = load_library(a.library.read_bytes(), PRODUCER_BLOB, EXPECTED_COUNT)
    c,p = Index(cr, prefer_coverage=True),Index(pr)
    queries = a.query or [
        "distance and bearing between two points",
        "render selected Vicinity asset facts",
        "browse ranked asset by swipe",
        "spherical polygon area",
        "spherical cap area",
        "financial discount rate",
        "road route",
        "connection capacity",
        "zzqvunknownnonexistent",
    ]
    report = {"schema": "vedic.two-cohort-retrieval.v1",
              "curated_count": len(cr), "compiled_count": len(pr),
              "unique_combined_count": None,
              "score_state": "UNCALIBRATED_BM25",
              "results": [search(c,p,q) for q in queries]}
    with a.output.open("x",encoding="utf-8") as f:
        json.dump(report,f,indent=2,sort_keys=True)
        f.write("\n")
    for q in report["results"]:
        print(q["query"], [(r["gg_id"],r["word"]) for r in q["curated_meanings"]["results"][:3]],
              [(r["family_id"],r["symbol"]) for r in q["compiled_candidates"]["results"][:3]])


if __name__ == "__main__":
    main()
