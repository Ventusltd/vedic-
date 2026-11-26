"""Bounded daily VEDIC research receipt; no automatic authorship or publishing."""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from stage_pages import validate_publication, CATALOGUE, PUBLICATION

ROOT = Path(__file__).resolve().parents[1]
SPAN = re.compile(r"https://github\.com/Ventusltd/(gridatlas)/blob/([0-9a-f]{40})/([A-Za-z0-9_./-]+)#L(\d+)(?:-L(\d+))?")
MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 40

def inventory(records):
    sources = {}
    for record in records:
        for repo, sha, path, first, last in SPAN.findall(record["provenance"]):
            if ".." in path.split("/"):
                raise ValueError("Invalid source path")
            lo, hi = int(first), int(last or first)
            if not 1 <= lo <= hi:
                raise ValueError("Invalid source span")
            sources.setdefault((repo, sha, path), set()).update(range(lo, hi + 1))
    return sources

def next_gap(lines, covered, day):
    # Candidate windows are nearby uncovered lines, not claims of semantic coverage.
    gaps = []
    for anchor in sorted(covered):
        if anchor + 1 not in covered and anchor < lines:
            lo = anchor + 1
            hi = lo
            while hi < min(lines, lo + MAX_LINES - 1) and hi + 1 not in covered:
                hi += 1
            gaps.append((lo, hi))
    return gaps[day % len(gaps)] if gaps else None

def main():
    payload = {name: (ROOT / name).read_bytes() for name in (CATALOGUE, PUBLICATION)}
    count = validate_publication(payload)
    records = json.loads(payload[CATALOGUE])["records"]
    sources = inventory(records)
    if not sources:
        raise ValueError("No pinned GridAtlas source spans found")
    day = dt.datetime.now(dt.timezone.utc).date().toordinal()
    repo, sha, path = sorted(sources)[day % len(sources)]
    url = f"https://raw.githubusercontent.com/Ventusltd/{repo}/{sha}/{path}"
    with urlopen(Request(url, headers={"User-Agent": "VEDIC-daily-research"}), timeout=20) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Source exceeds bounded daily budget")
    line_count = len(data.decode("utf-8").split("\n"))
    covered = sources[(repo, sha, path)]
    if max(covered) > line_count:
        raise ValueError("Published source range outside pinned file")
    gap = next_gap(line_count, covered, day)
    link = f"https://github.com/Ventusltd/{repo}/blob/{sha}/{path}"
    result = {
        "schema": "vedic.daily-research.v1",
        "published_passages": count,
        "distinct_cited_locations": sum(map(len, sources.values())),
        "source": link,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_lines": line_count,
        "candidate": f"{link}#L{gap[0]}-L{gap[1]}" if gap else None,
        "status": "candidate for human/AI review; no new prose or execution claimed",
    }
    print(json.dumps(result, indent=2))
    out = ROOT / "receipts" / "daily-research.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
