"""Replay reviewed append-only dictionary admissions against the frozen baseline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from validate_dictionary import require, validate, verify_source_entries
from validate_v2_allocation import git_blob, git_bytes

ROOT = Path(__file__).resolve().parents[1]
DICTIONARY = "data/dictionary.json"
DECISIONS = "data/command-distillation-review.json"
BASE = "205bbd8f9be2f38d1b6f514022a494474fac79a6"


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def labels(entry):
    return {normalized(text) for text in (entry["word"], *entry.get("aliases", []))}


def allocate(base, batches, commit, timestamp):
    result = json.loads(json.dumps(base))
    known = set().union(*(labels(row) for row in result["entries"]))
    for batch in batches:
        require(batch["schema_version"] == 1 and batch["baseline_count"] == len(base["entries"]),
                "Wrong reviewed-batch version or baseline")
        for c in batch["records"]:
            require(c["review_status"] == "STATIC_SOURCE_REVIEW" and c["verified_executable_package"] is False,
                    "Unsupported command admission status")
            require(normalized(c["word"]) and c["word"] == c["word"].upper(), "Invalid canonical label")
            aliases = c.get("aliases", [])
            require(isinstance(aliases, list) and all(isinstance(alias, str) and normalized(alias) for alias in aliases),
                    "Invalid alias")
            names = labels(c)
            require(len(names) == len(aliases)+1 and not known.intersection(names), "Duplicate command or alias")
            known.update(names)
            app_url = urlsplit(c["application"]["url"])
            require(app_url.scheme == "https" and app_url.hostname and not app_url.username, "Invalid application URL")
            s = c["source"]
            for old in result["entries"]:
                t = old.get("source") or {}
                same_origin = all(s[key] == t.get(key) for key in ("repo", "commit", "path", "blob"))
                require(not same_origin or s["first"] > t["last"] or t["first"] > s["last"],
                        "Overlapping command evidence")
            number = result["next_number"]
            result["next_number"] += 1
            reference = f"msi-command:{s['repo']}:{c['symbol']}"
            row = {key: c[key] for key in ("word", "purpose", "limits", "inputs", "output", "estate_group",
                                           "discipline", "periodic_category", "vedic_class_candidate",
                                           "application", "source", "receipt")}
            row.update(number=number, gg_id=f"GG2050-VEDIC-{number:06d}", kind="FUNCTION",
                       translation_ref=reference, sense_key="function:" + reference,
                       aliases=aliases, fixture_status=c["fixture_status"], demo=None,
                       demo_unavailable_reason="No independently admitted executable package for this command.",
                       state="STATIC_SOURCE_REVIEW", classification_state="CURATED_CANDIDATE",
                       periodic_block_candidate="Unresolved", created_utc=timestamp,
                       creation_evidence=f"https://github.com/Ventusltd/vedic-/commit/{commit}",
                       priority=2, family_id=None, element_id=None, tablet_id=None, line_ids=None, proof=None)
            result["entries"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allocate-from")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    if bool(args.allocate_from) == args.check:
        parser.error("Provide --allocate-from or --check")
    import subprocess

    base = json.loads(git_bytes(BASE, DICTIONARY))
    manifest_path = ROOT / "data/command-distillation-allocation.json"
    if args.allocate_from:
        commit = args.allocate_from
    else:
        commit = json.loads(manifest_path.read_bytes())["review_commit"]
    epoch = subprocess.check_output(["git", "show", "-s", "--format=%ct", commit], cwd=ROOT, text=True)
    timestamp = datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = git_bytes(commit, DECISIONS)
    working_blob = subprocess.check_output(
        ["git", "hash-object", "--path", DECISIONS, DECISIONS], cwd=ROOT, text=True
    ).strip()
    require(git_blob(receipt) == working_blob, "Review receipt differs from committed bytes")
    current = allocate(base, json.loads(receipt)["batches"], commit, timestamp)
    translations = json.loads((ROOT / "data/translation-geodesy.json").read_bytes())
    validate(current, translations, base)
    if args.online:
        verify_source_entries(current)
    target = ROOT / DICTIONARY
    if args.allocate_from:
        target.write_bytes((json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode())
        manifest_path.write_bytes((json.dumps({"review_commit": commit, "baseline_commit": BASE,
                                              "new_commands": len(current["entries"])-len(base["entries"])}, indent=2)+"\n").encode())
    else:
        from family_pulse import verify_extension
        queue = json.loads((ROOT / "data/daily-command-queue.json").read_bytes())
        published = json.loads(target.read_bytes())
        from source_admissions import ARCHIVE, BASE as SOURCE_BASE, pinned, replay_published
        historical = pinned(SOURCE_BASE, DICTIONARY)
        verify_extension(current, historical, queue)
        archive = json.loads((ROOT / ARCHIVE).read_bytes())
        require(replay_published(historical, archive) == published, "exact source-admission replay mismatch")
        validate(published, translations, current)
        current = published
    print("Reviewed dictionary entries:", len(current["entries"]))


if __name__ == "__main__":
    main()
