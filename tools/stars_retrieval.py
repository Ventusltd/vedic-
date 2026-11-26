"""Experimental read-only retrieval over the existing Stars compiled family library.

No code execution, source estate crawl, ID allocation, or probability claims.
The producer's headers identify candidates, not independently verified source joins.
"""
import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path

PRODUCER_COMMIT = "ed657689ca187d8cd237f8f4bd3307a020a5eb8a"
PRODUCER_BLOB = "59f2d5e5e2a9a88108908af4e851f56f3913700e"
EXPECTED_COUNT = 766
HEADER = re.compile(
    r"^// Family #(\d+) · element #(\d+) · (\d+) places in (\d+) repositories · "
    r"(https://github\.com/Ventusltd/[A-Za-z0-9_.-]+/blob/[a-f0-9]{40}/[^\s]+)"
    r"\nexport const f(\d+)_([A-Za-z0-9_$]+) = ", re.M)
STOP = frozenset("a an and as at by for from how i in is it of on or the to with want "
                 "please show me calculate function const let var return if else true false null "
                 "undefined new this typeof".split())
WEIGHTS = {"symbol": 3.0, "context": 1.0, "body": 0.5}


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def tokens(s):
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    return [t for t in re.findall(r"[a-z]+[0-9]*", s.lower()) if t not in STOP and len(t) > 1]


def load_library(raw, expected_blob, expected_count):
    require(git_blob(raw) == expected_blob, "producer blob mismatch")
    text = raw.decode("utf-8")
    matches = list(HEADER.finditer(text))
    require(len(matches) == expected_count and
            len(re.findall(r"^// Family #", text, re.M)) == expected_count,
            "producer header count mismatch")
    seen, out = set(), []
    for i, m in enumerate(matches):
        family, element, places, repos, url, export_family, symbol = m.groups()
        require(family == export_family and family not in seen, "family mismatch or duplicate")
        require(int(places) >= int(repos) >= 1, "invalid occurrence counts")
        require(re.search(r"#L\d+(?:-L\d+)?$", url), "missing source span")
        seen.add(family)
        body = text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)]
        require(body.strip().endswith(";"), "compiled export boundary not found")
        # Lexical features, not AST nodes or proven dependencies.
        context = url.split("/blob/", 1)[0].split("/")[-1] + " " + url.split("/blob/", 1)[1].split("/", 1)[1].split("#")[0]
        out.append({"family_id": int(family), "element_id": int(element),
                    "producer_occurrences": int(places), "producer_repositories": int(repos),
                    "source_url": url, "symbol": symbol,
                    "features": {"symbol": collections.Counter(tokens(symbol)),
                                 "context": collections.Counter(tokens(context)),
                                 "body": collections.Counter(tokens(body))}})
    return out


class Index:
    def __init__(self, records):
        require(bool(records), "empty corpus")
        self.records = records
        self.postings = {v: collections.defaultdict(dict) for v in WEIGHTS}
        self.lengths, self.averages = {}, {}
        for v in WEIGHTS:
            lengths = [sum(r["features"][v].values()) for r in records]
            self.lengths[v] = lengths
            self.averages[v] = max(1.0, sum(lengths) / len(records))
            for i, r in enumerate(records):
                for term, count in r["features"][v].items():
                    self.postings[v][term][i] = count

    def query(self, query, limit=10):
        require(type(limit) is int and 1 <= limit <= 100, "invalid limit")
        terms = sorted(set(tokens(query)))
        n = len(self.records)
        scores = collections.defaultdict(lambda: collections.defaultdict(float))
        matched = collections.defaultdict(set)
        known = set()
        for v, weight in WEIGHTS.items():
            for t in terms:
                hits = self.postings[v].get(t, {})
                if not hits:
                    continue
                known.add(t)
                idf = math.log1p((n-len(hits)+0.5)/(len(hits)+0.5))
                for i, tf in hits.items():
                    norm = 1.2*(0.25+0.75*self.lengths[v][i]/self.averages[v])
                    scores[i][v] += weight * idf * tf * 2.2 / (tf+norm)
                    matched[i].add(t)
        ranked = sorted(scores, key=lambda i: (-sum(scores[i].values()), self.records[i].get("gg_id", self.records[i].get("family_id"))))
        rows = []
        for i in ranked[:limit]:
            r = self.records[i]
            rows.append({k: v for k,v in r.items() if k != "features"} |
                        {"score": sum(scores[i].values()), "score_by_view": dict(scores[i]),
                         "matched_terms": sorted(matched[i]),
                         "source_state": r.get("source_state", "PRODUCER_DECLARED_ORIGINAL_SOURCE_NOT_REPLAYED")})
        # Deliberately conservative: discovery may rank a candidate, never auto-select or execute.
        margin = (sum(scores[ranked[0]].values()) - sum(scores[ranked[1]].values())
                  if len(ranked) > 1 else None)
        state = "NO_MATCH" if not rows else "REVIEW_REQUIRED_UNCALIBRATED"
        return {"query": query, "state": state, "unknown_terms": sorted(set(terms)-known),
                "top_score_margin": margin, "auto_selection": None, "results": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--query", action="append", default=[])
    a = p.parse_args()
    raw = a.library.read_bytes()
    records = load_library(raw, PRODUCER_BLOB, EXPECTED_COUNT)
    idx = Index(records)
    queries = a.query or ["voltage consistent site", "winter summer ratings",
                         "distance bearing coordinates", "financial discount rate",
                         "zzqvunknownnonexistent"]
    report = {"schema": "vedic.stars-retrieval-experiment.v1",
              "producer_commit": PRODUCER_COMMIT, "producer_blob": PRODUCER_BLOB,
              "library_sha256": hashlib.sha256(raw).hexdigest(),
              "candidate_count": len(records), "score_state": "UNCALIBRATED_BM25",
              "feature_weights": WEIGHTS, "probabilities_estimated": False,
              "accepted_new_meanings": 0, "independent_source_joins": 0,
              "results": [idx.query(q) for q in queries]}
    with a.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"candidate_count": len(records), "states": [r["state"] for r in report["results"]]}))


if __name__ == "__main__":
    main()
