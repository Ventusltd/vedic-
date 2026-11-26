"""Exercise the deployable Pages bundle and a private pagination fixture."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from browser_smoke import main as browser_smoke
from dictionary_shards import build as build_command_shards, write_bundle as write_command_shards
from stage_pages import stage, validate_publication, CATALOGUE, PUBLICATION, FIRST_PROSE_ROUTE, TELEPRINTER_PROSE_ROUTE, V1_ROUTE, V2_ROUTE, V3_ROUTE
import argparse


def exercise_pagination(site):
    dictionary = site / "data" / "dictionary.json"
    data = json.loads(dictionary.read_bytes())
    entries = data["entries"]
    if len(entries) < 101:
        number = max(entry["number"] for entry in entries)
        template = next(entry for entry in entries if entry.get("source"))
        missing = 101 - len(entries)
        for index in range(missing):
            entries.append({
                **template,
                "gg_id": f"UI-FIXTURE-{index + 1}",
                "number": number + index + 1,
                "word": ("<img src=/fixture-should-never-request>" if index == missing - 1 else f"Pagination fixture {index + 1}"),
                "priority": number + index + 1,
            })
        dictionary.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    write_command_shards(site)
    print(f"Browser pagination fixture: {len(entries)} rows", flush=True)
    browser_smoke(site, run_demos=False, offline=True)


def exercise_public(public):
    manifest = json.loads((public / "release.json").read_bytes())
    assert "prose_count" not in manifest
    for name, raw in build_command_shards(json.loads((public/"data/dictionary.json").read_bytes()), json.loads((public/"data/translation-geodesy.json").read_bytes())).items():
        assert (public/name).read_bytes()==raw
    assert manifest["row_count"] == len(json.loads((public / "data/dictionary.json").read_bytes())["entries"])
    for base in (public, *(public / r for r in (V1_ROUTE, V2_ROUTE, V3_ROUTE))):
        assert not (base / CATALOGUE).exists()
        assert not (base / PUBLICATION).exists()
    prior, latest = (public / route for route in (FIRST_PROSE_ROUTE, TELEPRINTER_PROSE_ROUTE))
    for archive, count in ((prior, 6), (latest, 8)):
        assert validate_publication({name: (archive / name).read_bytes() for name in (CATALOGUE, PUBLICATION)}) == count
    prior_rows = json.loads((prior / CATALOGUE).read_bytes())["records"]
    archived_rows = json.loads((latest / CATALOGUE).read_bytes())["records"]
    assert archived_rows[:len(prior_rows)] == prior_rows
    for base in (public, public / V3_ROUTE):
        html = (base / 'index.html').read_text(encoding='utf-8')
        assert 'id="package-evidence"' in html and 'Package download unavailable' in html
    for route in (V1_ROUTE, V2_ROUTE):
        assert 'id="package-evidence"' not in (public / route / 'index.html').read_text(encoding='utf-8')
    baseline = json.loads((latest / "data/dictionary.json").read_bytes())["entries"]
    current = json.loads((public / "data/dictionary.json").read_bytes())["entries"]
    assert current[:len(baseline)] == baseline
    browser_smoke(public, run_demos=False, offline=True)
    for route in (V1_ROUTE,V2_ROUTE,V3_ROUTE,FIRST_PROSE_ROUTE,TELEPRINTER_PROSE_ROUTE):
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
