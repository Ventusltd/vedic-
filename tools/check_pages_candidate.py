"""Exercise the deployable Pages bundle and a private pagination fixture."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from browser_smoke import main as browser_smoke
from stage_pages import stage, V1_ROUTE, V2_ROUTE
import argparse


def exercise_pagination(site):
    dictionary = site / "data" / "dictionary.json"
    data = json.loads(dictionary.read_bytes())
    entries = data["entries"]
    if len(entries) < 101:
        number = max(entry["number"] for entry in entries)
        template = next(entry for entry in entries if entry.get("source"))
        for index in range(101 - len(entries)):
            entries.append({
                **template,
                "gg_id": f"UI-FIXTURE-{index + 1}",
                "number": number + index + 1,
                "word": f"Pagination fixture {index + 1}",
                "priority": number + index + 1,
            })
        dictionary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"Browser pagination fixture: {len(entries)} rows", flush=True)
    browser_smoke(site, run_demos=False, offline=True)


def exercise_public(public):
    browser_smoke(public, run_demos=False, offline=True)
    for route in (V1_ROUTE,V2_ROUTE):
        browser_smoke(public, run_demos=False, offline=True, base_path=route)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('staged',nargs='?',type=Path)
    args=p.parse_args()
    with TemporaryDirectory(prefix="vedic-pages-") as directory:
        root = Path(directory)
        public = args.staged or root / "public"
        if args.staged is None:
            stage(public)
        print("Browser smoke: exact staged Pages payload", flush=True)
        exercise_public(public)
        fixture = root / "fixture"
        shutil.copytree(public, fixture)
        exercise_pagination(fixture)


if __name__ == "__main__":
    main()
