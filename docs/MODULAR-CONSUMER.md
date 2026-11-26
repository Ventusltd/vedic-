# VEDIC / Modular Star consumer — recovery and operating contract

## Resume without conversation context

Read this file, [VEDIC language](VEDIC-LANGUAGE.md), and [Neural Link #87](https://github.com/Ventusltd/neural-link-between-agents/issues/87). Read Neural AGENTS.md, PROTOCOL.md, OPERATIONS.md and latest receipts. Confirm current head, ownership and release state. The authoritative producer is Ventusltd/stars; do not change its existing hourly workflow, permanent IDs or source database. Do not create another scanner or ID allocator.

Run Python 3.12+ tests:

    python -m unittest discover -s tools -p 'test_*.py' -v

Run the separate consumer manually using GitHub CLI and public read access:

    python tools/modular_snapshot.py --output receipts/modular-snapshot.json

Use a new filename; receipts are never overwritten. The independent GitHub Actions workflow runs every six hours once merged to the default branch and on demand, without an AI session. PR changes to the consumer exercise it as well. Successful receipts are Actions artifacts retained 30 days; source and tests remain in Git. The raw database is temporary and never published or modified. This first consumer inventories the producer; it does not yet translate the whole estate.

## Input and output

Producer: https://github.com/Ventusltd/stars/releases/tag/modular-star . The tag is mutable. Capture asset ID, size, timestamp and available digest before and after download, refuse inconsistent metadata or hashes. Record compressed and decompressed SHA-256. SQLite opens read-only/query-only, checks integrity and required schema. Unknown translation coverage stays null. Existing unpack(), rebuildTablet(), elementSource() are reference implementations; any new Python occurrence adapter needs parity tests. Keep source occurrences separate from permanent numbered line identities; use distinct-ID unions rather than summing nested ranges.

## Next evolution: the VEDIC dictionary

A dictionary entry is a human-readable capability mapped to existing code, with verb, meaning, input/output contracts and units, source provenance, permanent IDs when resolved, constraints, dependencies and evidence state. Distinguish descriptive entries from executable compositions. A future composition checker must reject mismatched units/types, missing dependencies and unknown or unsupported execution claims. The dictionary must not create a new identity allocator or claim arbitrary combinations are valid. Illustrative words LOCATE, MEASURE, GRID, RANK, VICINITY, DRAW, PROVE, PRINT are proposed vocabulary, not verified executable commands. Reuse existing Periodic Table and Spider Maths Genome; preserve prior agent decisions.

## Maintenance

Do not mutate source apps, the Stars producer or public pointers from this consumer. No new schedule slots in ChatGPT. On failure read exact Actions logs, preserve prior good receipts, report blocker and retry only after diagnosis. Future agents should post a compact receipt on Neural Link: head, snapshot hash, tests, scope, limitations and next action. Publication of the dashboard has its own gate.
