"""Reproduce static command contracts from a bounded set of reviewed source pins."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from daily_intelligence import MAX_BYTES, PIN, ROOT, fetch
from source_evidence import (
    LIGHTNING_LAYER_SOURCE,
    LIGHTNING_LAYER_SYMBOL,
    source_link,
    verify_blob,
    verify_exact_span,
)


POLICY = "vedic.static-source.v1"
# A name or a high similarity score cannot establish these contracts. Each
# descriptor is scoped to the reviewable immutable source file below.
CONTRACTS = {
    "audit_file": {
        "word": "AUDIT SECTOR PARQUET",
        "purpose": "Check a sector intelligence Parquet file against its schema, keys and staged values.",
        "inputs": ["DuckDB connection with the staged dataset", "Parquet file path",
                   "sector dataset definition", "stage label"],
        "output": "Audit record with row counts, key checks, typed value checks, null counts, compression and file digest.",
        "limits": "Requires the matching staged data and sector schema. Refuses schema, key, typed value, required-null or compression mismatches.",
    },
    "build_browser_projection": {
        "word": "BUILD SECTOR BROWSER PROJECTION",
        "purpose": "Build a topic-ranked browser data projection from landed sector intelligence Parquet files.",
        "inputs": ["DuckDB connection", "landed sector items, topic and binding file paths",
                   "sector intelligence contract with browser row limit"],
        "output": "Browser projection with fields, bounded topic rows and counts before the limit.",
        "limits": "Uses the existing sector release ordering and per-topic cap. Refuses selected rows with project bindings or news eligibility. Publication is separate.",
    },
    "validate_contract": {
        "word": "VERIFY SECTOR DATA CONTRACT",
        "purpose": "Check that a Pipeline News sector release contract matches its declared dataset and storage rules.",
        "inputs": ["Pipeline News sector release contract for the pinned generation"],
        "output": "Validated dataset definitions indexed by dataset name.",
        "limits": "Specific to the source generation, provenance, dataset order, keys, physical types, ZSTD layout and federation policy. A mismatch raises an error.",
    },
    "validate_ledger": {
        "word": "CHECK SECTOR DATA LEDGER",
        "purpose": "Check a Pipeline News sector ledger against its generation, schema, keys and source policy.",
        "inputs": ["sector data ledger", "validated sector contract", "dataset definitions indexed by name"],
        "output": "Returns normally when checks pass and raises an error on an invalid ledger.",
        "limits": "Specific to the pinned generation. Checks UTC provenance, row structure, key and reference integrity, and the pinned source policy.",
    },
}

LIGHTNING_CONTRACT = {
    "word": "REGISTER LIGHTNING MAP LAYER",
    "purpose": "Add the archived GridAtlas satellite-flash point layer to the map configuration when it is absent.",
    "inputs": ["GridAtlas map initialization options with a layer-group configuration",
               "original map initializer captured by the cartridge"],
    "output": "The original initializer's result after adding the point-layer configuration if needed.",
    "limits": "Source-only record for the archived cartridge. An existing layer is kept and the feed is registered without preload. The layer describes optical satellite flashes.",
    "symbol": LIGHTNING_LAYER_SYMBOL,
    "source": LIGHTNING_LAYER_SOURCE,
    "estate_group": "GridAtlas",
    "discipline": "Geospatial visualisation",
    "periodic_category": "map layers",
    "vedic_class_candidate": "Computation",
    "aliases": [],
    "receipt": source_link(LIGHTNING_LAYER_SOURCE),
}


SOLAR_LOOP_AREA_SOURCE = {
    "repo": "Ventusltd/solar-electrical-topology-analysis-engine-text-based",
    "commit": "d3b4c497144c2c9b3e8f0e82117e7e9abe4672b9",
    "blob": "e3014bc950722a78e91810e97610b05326e94531",
    "path": "src/solar_topology/geometry_receipts.py",
    "first": 50,
    "last": 122,
}
SOLAR_LOOP_AREA_CONTRACT = {
    "word": "ESTIMATE SOLAR LOOP AREA",
    "purpose": "Estimate weighted DC conductor loop area for one solar string from declared segment geometry.",
    "inputs": ["Solar string segment rows with a single run, topology and string and contiguous segment indexes from one",
               "Conductor length in metres, pole separation in millimetres and a dimensionless participation weight per segment"],
    "output": "Deterministic geometry receipt with loop area in square metres, per-segment contributions, route lengths, paired-route fraction and warnings.",
    "limits": "Engineering screening approximation. Supply finite, nonnegative lengths and separations. The estimate uses declared geometry and weights and warns about missing separation on participating segments and assumed or defaulted geometry.",
    "symbol": "calculate_geometry_receipt",
    "source": SOLAR_LOOP_AREA_SOURCE,
    "estate_group": "Solar Electrical Topology",
    "discipline": "Solar electrical design",
    "periodic_category": "conductor geometry",
    "vedic_class_candidate": "Computation",
    "aliases": [],
    "receipt": source_link(SOLAR_LOOP_AREA_SOURCE),
}

EXPLICIT_CONTRACTS = (LIGHTNING_CONTRACT, SOLAR_LOOP_AREA_CONTRACT)


def pinned_functions(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("Policy source exceeds the byte budget")
    git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if git_blob != PIN["blob"]:
        raise ValueError("Policy source blob differs from the reviewed pin")
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError) as error:
        raise ValueError("Invalid policy Python source") from error
    for name, contract in CONTRACTS.items():
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(functions) != 1 or functions[0].decorator_list:
            raise ValueError(f"Expected one plain top-level policy function: {name}")
        function = functions[0]
        source = {**PIN, "first": function.lineno, "last": function.end_lineno}
        yield source, {
            **contract,
            "symbol": name,
            "source": source,
            "estate_group": "Pipeline News",
            "discipline": "Data engineering",
            "periodic_category": "sector intelligence",
            "vedic_class_candidate": "Computation",
            "aliases": [],
            "receipt": f"https://github.com/{PIN['repo']}/blob/{PIN['commit']}/{quote(PIN['path'])}"
                       f"#L{source['first']}-L{source['last']}",
        }


def reproduce_candidate(source, raw):
    """Reconstruct the exact allowed command for verification from source bytes."""
    for candidate in EXPLICIT_CONTRACTS:
        if source == candidate["source"]:
            verify_blob(source, raw)
            return candidate
    if any(source.get(key) != value for key, value in PIN.items()):
        raise ValueError("Source is outside the reviewed static policy")
    for anchor, candidate in pinned_functions(raw):
        if source == anchor:
            return candidate
    raise ValueError("Source span is outside the reviewed static policy")


def discover_candidates(raw, archive):
    from source_admissions import candidate_id, make_policy_receipt

    admitted = {row["candidate_id"] for row in archive["records"]}
    records = []
    for _, candidate in pinned_functions(raw):
        if candidate_id(candidate) in admitted:
            continue
        records.append({**candidate, "policy_receipt": make_policy_receipt(candidate, raw)})
    return {"schema": "vedic.source-candidates.v1", "records": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    archive = json.loads((ROOT / "data/admitted-queue-archive.json").read_bytes())
    queue = discover_candidates(fetch(PIN), archive)
    from source_admissions import candidate_id, make_policy_receipt, read_policy_source

    admitted = {row["candidate_id"] for row in archive["records"]}
    for candidate in EXPLICIT_CONTRACTS:
        if candidate_id(candidate) in admitted:
            continue
        source = candidate["source"]
        raw = read_policy_source(source["repo"], source["commit"], source["path"])
        verify_exact_span(source, candidate["symbol"], raw)
        queue["records"].append({**candidate, "policy_receipt": make_policy_receipt(candidate, raw)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")
    print(f"Reproduced {len(queue['records'])} pending static source contracts")


if __name__ == "__main__":
    main()
