"""Run the nightly NumPy accelerator and retain a compact research checkpoint."""

import hashlib
import json
from pathlib import Path
import re
import tempfile

from modular_snapshot import download_snapshot, inventory

SCHEMA = "vedic.daily-accelerator.v1"
PROBES_PER_GROUP = 16
FIRST_ELEMENT_SEED = 193908
FIRST_DOMAIN_SEED = 20261131
RECEIPT = "accelerator-research.json"
METHOD_FILES = (
    "tools/estate_crib_search.py",
    "tools/estate_domain_scan.py",
    "tools/modular_features.py",
    "tools/dictionary_shards.py",
    "tools/daily_accelerator.py",
    "data/estate-crib-library.json",
)


def validate(state):
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        raise ValueError("Invalid accelerator checkpoint schema")
    for key in ("database_sha256", "method_sha256"):
        if not isinstance(state.get(key), str) or not re.fullmatch(r"[a-f0-9]{64}", state[key]):
            raise ValueError("Invalid accelerator checkpoint digest")
    rounds = state.get("completed_rounds")
    if type(rounds) is not int or rounds < 1:
        raise ValueError("Invalid accelerator round")
    coverage = state.get("probe_coverage")
    if not isinstance(coverage, dict) or not coverage:
        raise ValueError("Missing accelerator probe coverage")
    for group, row in coverage.items():
        if not group or not isinstance(row, dict):
            raise ValueError("Invalid accelerator probe group")
        total = row.get("total")
        if (type(total) is not int or total < PROBES_PER_GROUP or type(row.get("tested")) is not int or
                row["tested"] != min(total, rounds * PROBES_PER_GROUP)):
            raise ValueError("Invalid accelerator probe coverage")
    return state


def same_campaign(previous, method_sha256):
    return previous is not None and previous["method_sha256"] == method_sha256


def verify_advance(previous, current):
    if current == previous:
        return
    if current is None:
        raise ValueError("Missing existing accelerator progress")
    if same_campaign(previous, current["method_sha256"]):
        before = {group: row["total"] for group, row in previous["probe_coverage"].items()}
        after = {group: row["total"] for group, row in current["probe_coverage"].items()}
        if current["completed_rounds"] != previous["completed_rounds"] + 1 or before != after:
            raise ValueError("Accelerator checkpoint skipped a round or changed its probe universe")
    elif current["completed_rounds"] != 1:
        raise ValueError("A new accelerator campaign must start at its first round")


def method_digest(root):
    digest = hashlib.sha256()
    for name in METHOD_FILES:
        payload = (root / name).read_bytes().replace(b"\r\n", b"\n")
        digest.update(name.encode() + b"\0" + hashlib.sha256(payload).digest())
    return digest.hexdigest()


def research(root, output, previous):
    import numpy as np
    import pyarrow.parquet as pq

    from estate_crib_search import GROUPS, search
    from estate_domain_scan import scan_estate
    from modular_features import extract

    if previous is not None:
        validate(previous)
    method = method_digest(root)
    library = root / "data/estate-crib-library.json"
    with tempfile.TemporaryDirectory(prefix="vedic-accelerator-") as directory:
        scratch = Path(directory)
        database, producer, hashes = download_snapshot(scratch, require_digest=True)
        snapshot = inventory(database)["producer_inventory"]
        db_digest = hashes["database_sha256"]
        same = same_campaign(previous, method)
        round_index = previous["completed_rounds"] if same else 0
        campaign_seed = int(method, 16)

        features = scratch / "features.parquet"
        extracted = extract(database, features, workers=2, limit=None)
        elements_dir, domains_dir = scratch / "elements", scratch / "domains"
        element_seed, domain_seed = FIRST_ELEMENT_SEED + round_index, FIRST_DOMAIN_SEED + round_index
        elements = search(features, database, elements_dir, element_seed, backend="numpy",
                          campaign=(campaign_seed, round_index))
        domains = scan_estate(database, library, domains_dir, domain_seed, backend="numpy")
        if extracted["elements"] != snapshot["element"] or domains["lines"] != snapshot["line"]:
            raise ValueError("Accelerator did not cover the source snapshot")
        element_lines = pq.read_table(elements_dir / "lines.parquet")
        domain_lines = pq.read_table(domains_dir / "domain-lines.parquet")
        if not np.array_equal(element_lines["line_id"].to_numpy(), domain_lines["line_id"].to_numpy()):
            raise ValueError("Accelerator passes used different source-line identities")
        single_group = np.isin(element_lines["command_group"].to_numpy(), [group[0] for group in GROUPS])
        domain_mask = domain_lines["lexical_domain_mask"].to_numpy() | domain_lines["source_context_mask"].to_numpy()
        sample = json.loads((elements_dir / "vogel-shots.json").read_bytes())
        shot_fields = ("element_id", "family_id", "command_group")
        shots = {kind: [{key: row[key] for key in shot_fields} for row in sample[kind]]
                 for kind in ("survivors", "unresolved")}
        domain_shots = json.loads((domains_dir / "vogel-shots.json").read_bytes())
        checkpoint = validate({"schema": SCHEMA, "database_sha256": db_digest, "method_sha256": method,
                               "completed_rounds": round_index + 1, "probe_coverage": elements["probe_coverage"]})
        verify_advance(previous, checkpoint)
        coverage = checkpoint["probe_coverage"]
        tested = sum(row["tested"] for row in coverage.values())
        previously_tested = sum(row["tested"] for row in previous["probe_coverage"].values()) if same else 0
        receipt = {
            "checkpoint": checkpoint,
            "backend": "numpy",
            "cpu_gpu_parity": None,
            "producer_asset": producer,
            "source_inventory": {key: snapshot[key] for key in ("line", "element", "family")},
            "seeds": {"elements": element_seed, "domain_sampling": domain_seed},
            "counts": {
                "distinct_hypotheses_tested": tested,
                "new_hypotheses_tested": tested - previously_tested,
                "distinct_hypotheses_available": sum(row["total"] for row in coverage.values()),
                "element_hypothesis_pairs": elements["element_hypothesis_pairs"],
                "line_domain_pairs": domains["line_group_pairs"],
                "line_ids_with_one_group_or_domain_context": int(np.count_nonzero(single_group | domain_mask)),
                "line_ids_with_domain_association": domains["any_domain_lines"],
                "elements_with_one_group": snapshot["element"] - elements["tables"]["elements"]["counts"].get("REVIEW REQUIRED", 0),
                "lines_truncated_for_lexical_scan": domains["bounded_long_lines"],
                "elements_with_truncated_features": extracted["lexically_truncated_elements"],
            },
            "vogel_samples": {"elements": shots, "domains": domain_shots},
            "sha256": {"features": extracted["parquet_sha256"], "elements": elements["tables"]["elements"]["sha256"],
                       "domain_lines": domains["parquet_sha256"]},
            "scope": "All indexed elements and lines in this snapshot. Cumulative coverage counts configured "
                     "crib hypotheses across successful snapshots. Results are leads for review.",
        }
    with (output / RECEIPT).open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    counts = receipt["counts"]
    print(f"Nightly accelerator round {checkpoint['completed_rounds']}: "
          f"{counts['distinct_hypotheses_tested']}/{counts['distinct_hypotheses_available']} "
          f"crib hypotheses covered, {snapshot['element']} elements and {snapshot['line']} line IDs scanned.")
    return checkpoint
