# VEDIC / Modular Star consumer — recovery and operating contract

## Resume without conversation context

Read this file, [VEDIC language](VEDIC-LANGUAGE.md), and [Neural Link #87](https://github.com/Ventusltd/neural-link-between-agents/issues/87). Read Neural AGENTS.md, PROTOCOL.md, OPERATIONS.md and latest receipts. Confirm current head, ownership and release state. The authoritative producer is Ventusltd/stars; do not change its existing hourly workflow, permanent IDs or source database. Do not create another scanner or ID allocator.

Run Python 3.12+ tests:

    python -m unittest discover -s tools -p 'test_*.py' -v

Run the separate consumer manually using GitHub CLI and public read access:

    python tools/modular_snapshot.py --output receipts/modular-snapshot.json

Choose a new filename for each snapshot receipt. The database stays in runner scratch.

## Nightly discovery

The [Modular Star consumer](https://github.com/Ventusltd/vedic-/actions/workflows/modular-consumer.yml) runs once daily at 03:37 UTC. Python and NumPy score every indexed element and scan every unique line in the verified Stars snapshot for configured domain cues. The workflow shuffles each set of crib hypotheses deterministically, then takes the next slice. The current 4,683 hypotheses span 23 successful rounds. After that, the job keeps taking seeded samples against the latest snapshot.

The existing `automation/vedic-daily-state` branch keeps the family cursor and probe-coverage checkpoint together. A Stars refresh records a new snapshot digest and continues the same hypothesis sweep. Changes to the scoring method or library start a fresh sweep. Cumulative counts track hypotheses tested across snapshots. Individual receipts identify the exact snapshot examined and preserve a small sample of leads by permanent ID. Dictionary admission still requires reviewed evidence.

To rehearse the CPU run without advancing scheduled state, choose **Rehearse the nightly CPU accelerator** when dispatching the workflow. The run uploads `vedic-accelerator-<run>-<attempt>` for 14 days. SQLite, features and intermediate Parquet stay in runner scratch.

## Input and output

Producer: https://github.com/Ventusltd/stars/releases/tag/modular-star . The tag is mutable. Capture asset ID, size, timestamp and available digest before and after download, refuse inconsistent metadata or hashes. Record compressed and decompressed SHA-256. SQLite opens read-only/query-only, checks integrity and required schema. Unknown translation coverage stays null. Existing unpack(), rebuildTablet(), elementSource() are reference implementations; any new Python occurrence adapter needs parity tests. Keep source occurrences separate from permanent numbered line identities; use distinct-ID unions rather than summing nested ranges.

## Next evolution: the VEDIC dictionary

A dictionary entry is a human-readable capability mapped to existing code, with verb, meaning, input/output contracts and units, source provenance, permanent IDs when resolved, constraints, dependencies and evidence state. Distinguish descriptive entries from executable compositions. A future composition checker must reject mismatched units/types, missing dependencies and unknown or unsupported execution claims. The dictionary must not create a new identity allocator or claim arbitrary combinations are valid. Illustrative words LOCATE, MEASURE, GRID, RANK, VICINITY, DRAW, PROVE, PRINT are proposed vocabulary, not verified executable commands. Reuse existing Periodic Table and Spider Maths Genome; preserve prior agent decisions.

## Maintenance

Do not mutate source apps, the Stars producer or public pointers from this consumer. No new schedule slots in ChatGPT. On failure read exact Actions logs, preserve prior good receipts, report blocker and retry only after diagnosis. Future agents should post a compact receipt on Neural Link: head, snapshot hash, tests, scope, limitations and next action. Publication of the dashboard has its own gate.
