"""Discover one pinned computational function for review. No source is executed."""
import argparse
import ast
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PIN = {
    "repo": "Ventusltd/pipelinenews",
    "commit": "d71672c221e0b4121e415204f91ccf642bc9894f",
    "path": "build/python/202609010719-build-sector-intelligence-parquet.py",
    "blob": "a0431a7383a2fd0166f667a19c922de4919cf3c8",
}
SYMBOLS = ("audit_file", "build_browser_projection", "validate_contract", "validate_ledger")
MAX_BYTES = 256 * 1024
MAX_FUNCTION_LINES = 180
PLAN_START = dt.date(2026, 11, 26)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normalized(value):
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def fetch(pin):
    url = f"https://raw.githubusercontent.com/{pin['repo']}/{pin['commit']}/{pin['path']}"
    with urlopen(Request(url, headers={"User-Agent": "VEDIC-daily-commands"}), timeout=20) as response:
        return response.read(MAX_BYTES + 1)


def discover(raw, dictionary, day, pin=PIN, symbols=SYMBOLS):
    if len(raw) > MAX_BYTES:
        raise ValueError("Source exceeds daily byte budget")
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if blob != pin["blob"]:
        raise ValueError("Source blob differs from pinned evidence")
    if dictionary.get("schema") != "vedic.dictionary.v1" or not isinstance(dictionary.get("entries"), list):
        raise ValueError("Invalid dictionary evidence")
    offset = (day - PLAN_START).days
    if not 0 <= offset < len(symbols):
        return exhausted(dictionary, day)
    symbol = symbols[offset]
    matches = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef)
               and node.name == symbol]
    if len(matches) != 1:
        raise ValueError("Pinned computational function is absent or ambiguous")
    function = matches[0]
    first = min([function.lineno, *(node.lineno for node in function.decorator_list)])
    last = function.end_lineno
    if not 1 <= first <= last or last - first + 1 > MAX_FUNCTION_LINES:
        raise ValueError("Function exceeds daily line budget")
    source = {**pin, "first": first, "last": last}
    label = normalized(symbol).upper()
    duplicates = []
    potential_homonyms = []
    for entry in dictionary["entries"]:
        existing = entry.get("source") or {}
        same_origin = all(existing.get(key) == pin[key] for key in pin)
        known = [entry["word"], *entry.get("aliases", []), entry.get("translation_ref", "").rsplit(":", 1)[-1]]
        same_span = same_origin and existing["first"] <= last and first <= existing["last"]
        if same_span:
            duplicates.append(entry["gg_id"])
        elif any(isinstance(text, str) and normalized(text) == normalized(symbol) for text in known):
            duplicates.append(entry["gg_id"])
            potential_homonyms.append(entry["gg_id"])
    key = sha256(json.dumps(source, sort_keys=True).encode())
    result = {
        "schema": "vedic.daily-command-discovery.v1", "utc_date": day.isoformat(),
        "checkpoint": key, "source": source, "source_sha256": sha256(raw),
        "dictionary_sha256": sha256(json.dumps(dictionary, sort_keys=True).encode()),
        "existing_matches": sorted(set(duplicates)), "status": "no_change" if duplicates else "review_required",
        "candidate": None, "exceptions": [{"reason": "label_collision_requires_semantic_review", "gg_id": value}
                                            for value in sorted(set(potential_homonyms))],
    }
    if not duplicates:
        args = function.args
        result["candidate"] = {
            "id": "candidate:" + key, "label_hint": label, "symbol": symbol,
            "parameters": [node.arg for node in (*args.posonlyargs, *args.args, *args.kwonlyargs)],
            "output_annotation": ast.unparse(function.returns) if function.returns else None,
            "evidence": "Pinned function boundary; semantic equivalence and executable behavior require review.",
        }
    return result


def exhausted(dictionary, day):
    return {
        "schema": "vedic.daily-command-discovery.v1", "utc_date": day.isoformat(),
        "status": "no_change", "candidate": None, "existing_matches": [],
        "checkpoint": "pinned-plan-exhausted", "exceptions": [],
        "dictionary_sha256": sha256(json.dumps(dictionary, sort_keys=True).encode()),
        "reason": "No unvisited scheduled scope in this pinned plan. Renew the plan through reviewed changes.",
    }


def write_receipt(path, result):
    body = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != body:
        raise ValueError("Existing receipt differs; choose a new receipt path")
    path.write_bytes(body)
    print(body.decode(), end="")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=dt.date.fromisoformat)
    parser.add_argument("--output", type=Path, default=ROOT / "receipts" / "daily-research.json")
    args = parser.parse_args()
    day = args.date or dt.datetime.now(dt.timezone.utc).date()
    try:
        dictionary = json.loads((ROOT / "data/dictionary.json").read_bytes())
        if not 0 <= (day - PLAN_START).days < len(SYMBOLS):
            result = exhausted(dictionary, day)
        else:
            result = discover(fetch(PIN), dictionary, day)
    except (ValueError, OSError, SyntaxError, KeyError, TypeError) as error:
        write_receipt(args.output, {"schema": "vedic.daily-command-discovery.v1",
                                    "utc_date": day.isoformat(), "source": PIN,
                                    "status": "error", "candidate": None, "exceptions": [type(error).__name__]})
        raise
    write_receipt(args.output, result)


if __name__ == "__main__":
    main()
