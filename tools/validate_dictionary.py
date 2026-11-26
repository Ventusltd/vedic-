"""Validate the append-only VEDIC dictionary and its initial composition."""
import json
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
    require(len({e["word"] for e in entries}) == len(entries), "duplicate word")
    require(d["next_number"] == max(by_number, default=0)+1, "wrong next ID")
    require(set(by_number) == set(range(1, d["next_number"])), "missing permanent number")
    for i, word in enumerate(GENESIS, 1):
        require(by_number[i]["word"] == word, "genesis identity changed")
    source = {r["id"]: r for r in translations["records"]}
    for e in entries:
        require(e["gg_id"] == f'GG2050-VEDIC-{e["number"]:06d}', "invalid GlobalGrid ID")
        require(e["demo"] in DEMO_KEYS, "unregistered demo")
        for key in ("estate_group","discipline","periodic_category","vedic_class_candidate"):
            require(bool(e[key]), "missing classification")
        require(e["vedic_class_candidate"] in {"Structure","Movement","Computation","Flow","Data"}, "unknown class")
        require(e["classification_state"] == "CURATED_CANDIDATE", "unproven classification")
        if e["kind"] == "FUNCTION":
            require(e["translation_ref"] in source, "missing source translation")
            require(e["state"] == "STATIC_SOURCE_REVIEW", "unsupported proof state")
        elif e["kind"] == "COMPOSITION":
            require(e["state"] == "DEMO_CANDIDATE", "unsupported composition status")
            require(e["composition_mode"] == "shared_inputs", "unsupported composition")
            components = [by_id[x] for x in e["components"]]
            require(len(components) >= 2 and len({x["gg_id"] for x in components}) == len(components), "duplicate or absent components")
            require(all(x["number"] < e["number"] for x in components), "forward reference or cycle")
            require(all(x["inputs"] == e["inputs"] for x in components), "incompatible component inputs")
        else:
            raise ValueError("unknown kind")
    if prior:
        for old in prior["entries"]:
            require(old["gg_id"] in by_id, "deleted permanent ID")
            for key in ("number","word","kind","translation_ref","components"):
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
