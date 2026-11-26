"""Validate the append-only VEDIC dictionary and its initial composition."""
import json
import hashlib
from source_evidence import POLICY, POLICY_SCHEMA, POLICY_STATE, source_link, verify_exact_span
from validate_translation import fetch
import re
from urllib.parse import quote
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
# Frozen allocation: do not replace or renumber these entries.
GENESIS = ("MEASURE", "REPRESENT", "VOLTAGE", "DESTINATION", "BEARING", "ORIENT")
DEMO_KEYS = {"distance","point","voltage","destination","bearing","orient"}
def require(ok, message):
    if not ok:
        raise ValueError(message)
def validate(d, translations, prior=None):
    require(d["schema"] == "vedic.dictionary.v1", "wrong schema")
    entries = d["entries"]
    by_id = {e["gg_id"]: e for e in entries}
    by_number = {e["number"]: e for e in entries}
    require(len(entries) == len(by_id) == len(by_number), "duplicate identity")
    require(len({e["sense_key"] for e in entries}) == len(entries), "duplicate meaning")
    require(d["next_number"] == max(by_number, default=0)+1, "wrong next ID")
    require(set(by_number) == set(range(1, d["next_number"])), "missing permanent number")
    for i, word in enumerate(GENESIS, 1):
        require(by_number[i]["word"] == word, "genesis identity changed")
        require(by_number[i]["created_utc"] == "2026-11-26T01:35:15Z", "genesis timestamp changed")
        require(by_number[i]["creation_evidence"] == "https://github.com/Ventusltd/vedic-/commit/5ddc2e611dbcccb68cc4f7342637fddb912e5ef1", "genesis creation evidence changed")
    source = {r["id"]: r for r in translations["records"]}
    for e in entries:
        require(e["gg_id"] == f'GG2050-VEDIC-{e["number"]:06d}', "invalid GlobalGrid ID")
        require(e["demo"] in DEMO_KEYS or (e["demo"] is None and e["kind"] == "FUNCTION" and e["number"] > len(GENESIS) and bool(e.get("demo_unavailable_reason"))), "unregistered demo")
        require(isinstance(e["word"], str) and bool(e["word"].strip()), "empty word")
        require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e["created_utc"])), "timestamp must be UTC")
        datetime.fromisoformat(e["created_utc"].replace("Z", "+00:00"))
        require(bool(re.fullmatch(r"https://github\.com/Ventusltd/vedic-/commit/[0-9a-f]{40}", e["creation_evidence"])), "missing creation evidence")
        for key in ("estate_group","discipline","periodic_category","vedic_class_candidate"):
            require(bool(e[key]), "missing classification")
        require(e["vedic_class_candidate"] in {"Structure","Movement","Computation","Flow","Data"}, "unknown class")
        require(e["classification_state"] == "CURATED_CANDIDATE", "unproven classification")
        if e["kind"] == "FUNCTION":
            policy = e.get("admission_policy") == POLICY
            if e["translation_ref"] not in source:
                require(e["demo"] is None, "source-only function cannot claim a demo")
                require(all(e.get(k) is None for k in ("family_id","element_id","tablet_id","line_ids","proof")), "unverified identity or proof")
                require(all(isinstance(e.get(k), str) and e[k].strip() for k in ("purpose","limits","receipt")), "missing source description")
                s = e["source"]
                require(bool(re.fullmatch(r"Ventusltd/[A-Za-z0-9_.-]+", s["repo"])), "bad source repo")
                require(all(re.fullmatch(r"[0-9a-f]{40}", s[k]) for k in ("commit","blob")), "bad source pin")
                require(not s["path"].startswith("/") and ".." not in s["path"].split("/") and bool(s["path"]), "bad source path")
                require(type(s["first"]) is int and type(s["last"]) is int and 1 <= s["first"] <= s["last"], "bad source span")
                if policy:
                    receipt = e.get("policy_receipt")
                    require(isinstance(receipt, dict) and receipt.get("schema") == POLICY_SCHEMA
                            and receipt.get("policy") == POLICY, "invalid policy receipt")
                    require(all(isinstance(receipt.get(k), str) and re.fullmatch(r"[0-9a-f]{64}", receipt[k])
                                for k in ("source_sha256", "contract_sha256")), "invalid policy receipt digest")
                    require(e["receipt"] == source_link(s), "invalid policy evidence link")
                else:
                    require(re.fullmatch(r"https://github\.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-[1-9][0-9]*",
                                         e["receipt"]), "missing receipt")
            require(e["sense_key"] == "function:" + e["translation_ref"], "invalid function sense key")
            require(e["state"] == (POLICY_STATE if policy else "STATIC_SOURCE_REVIEW"), "unsupported proof state")
        elif e["kind"] == "COMPOSITION":
            require(e["state"] == "DEMO_CANDIDATE", "unsupported composition status")
            require(e["composition_mode"] == "shared_inputs", "unsupported composition")
            require(e["sense_key"] == "composition:" + e["composition_mode"] + ":" + ",".join(e["components"]), "invalid composition sense key")
            components = [by_id[x] for x in e["components"]]
            require(len(components) >= 2 and len({x["gg_id"] for x in components}) == len(components), "duplicate or absent components")
            require(all(x["number"] < e["number"] for x in components), "forward reference or cycle")
            require(all(x["inputs"] == e["inputs"] for x in components), "incompatible component inputs")
        else:
            raise ValueError("unknown kind")
    if prior:
        for old in prior["entries"]:
            require(old["gg_id"] in by_id, "deleted permanent ID")
            for key in ("number","word","kind","translation_ref","components","sense_key","created_utc","creation_evidence","composition_mode"):
                require(old.get(key) == by_id[old["gg_id"]].get(key), "changed permanent identity")
    return len(entries)
def verify_source_entries(d, reader=None):
    raw_cache = {}
    legacy_cache = {}
    if reader is None:
        def reader(repo, commit, path):
            return fetch(repo, commit, quote(path, safe="/"))

    for e in d["entries"]:
        if e["demo"] is not None or "source" not in e:
            continue
        s = e["source"]
        key = (s["repo"],s["commit"],s["path"])
        if key not in raw_cache:
            raw_cache[key] = reader(*key)
        raw = raw_cache[key]
        require(len(raw) <= 1_000_000, "source too large")
        name = e["translation_ref"].rsplit(":",1)[-1]
        if e.get("admission_policy") == POLICY:
            verify_exact_span(s, name, raw)
            continue
        if key not in legacy_cache:
            blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
            legacy_cache[key] = (blob, raw.decode("utf-8").splitlines())
        blob, lines = legacy_cache[key]
        require(blob == s["blob"], f"source blob mismatch {key}: expected {s['blob']}, got {blob}")
        require(s["last"] <= len(lines), "source span outside file")
        require(re.search(r"\b(?:function\s+"+re.escape(name)+r"\s*\(|"+re.escape(name)+r"\s*:)",lines[s["first"]-1]), f"source start mismatch {e['gg_id']} {name}")
        require(lines[s["last"]-1].strip() == "}", f"source end mismatch {e['gg_id']} {name}")
    return len(raw_cache)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--prior", type=Path)
    p.add_argument("--online", action="store_true")
    args = p.parse_args()
    d = json.loads((ROOT/"data/dictionary.json").read_text(encoding="utf-8"))
    t = json.loads((ROOT/"data/translation-geodesy.json").read_text(encoding="utf-8"))
    prior = json.loads(args.prior.read_text(encoding="utf-8")) if args.prior else None
    print("Dictionary entries:", validate(d,t,prior))
    if args.online:
        print("Additional pinned source files:", verify_source_entries(d))
