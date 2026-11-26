"""Exercise the deployable Pages bundle and a private pagination fixture."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from browser_smoke import main as browser_smoke
from stage_pages import stage


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


def main():
    with TemporaryDirectory(prefix="vedic-pages-") as directory:
        root = Path(directory)
        public = root / "public"
        stage(public)
        print("Browser smoke: exact staged Pages payload", flush=True)
        browser_smoke(public, run_demos=False, offline=True)
        fixture = root / "fixture"
        shutil.copytree(public, fixture)
        exercise_pagination(fixture)


if __name__ == "__main__":
    main()
