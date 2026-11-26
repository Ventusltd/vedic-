"""Validate the append-only VEDIC dictionary and its initial composition."""
import json
import re
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
        require(e["demo"] in DEMO_KEYS, "unregistered demo")
        require(isinstance(e["word"], str) and bool(e["word"].strip()), "empty word")
        require(bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e["created_utc"])), "timestamp must be UTC")
        datetime.fromisoformat(e["created_utc"].replace("Z", "+00:00"))
        require(bool(re.fullmatch(r"https://github\.com/Ventusltd/vedic-/commit/[0-9a-f]{40}", e["creation_evidence"])), "missing creation evidence")
        for key in ("estate_group","discipline","periodic_category","vedic_class_candidate"):
            require(bool(e[key]), "missing classification")
        require(e["vedic_class_candidate"] in {"Structure","Movement","Computation","Flow","Data"}, "unknown class")
        require(e["classification_state"] == "CURATED_CANDIDATE", "unproven classification")
        if e["kind"] == "FUNCTION":
            require(e["translation_ref"] in source, "missing source translation")
            require(e["sense_key"] == "function:" + e["translation_ref"], "invalid function sense key")
            require(e["state"] == "STATIC_SOURCE_REVIEW", "unsupported proof state")
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
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--prior", type=Path)
    args = p.parse_args()
    d = json.loads((ROOT/"data/dictionary.json").read_text())
    t = json.loads((ROOT/"data/translation-geodesy.json").read_text())
    prior = json.loads(args.prior.read_text()) if args.prior else None
    print("Dictionary entries:", validate(d,t,prior))
