# FIND CAPABILITY review

The proposed dictionary row uses the existing static source-admission policy. The allocator appends one provisional row, GG2050-VEDIC-000095, to the 94 prior entries. Its source is the top-level SEED lookup adapter at the pinned revision. It accepts a non-blank objective, the curated SQLite catalogue and an optional integer limit from one to five. The output gives a lookup status, a bounded shortlist and evidence locators. A shortlist is discovery evidence; selecting and running an instrument is a separate operation. [Exact adapter](https://github.com/Ventusltd/seed-data/blob/153c1159ff58edcb8be5f598c2c78d13c85b6afd/experiments/economical-seeds/vedic_candidate.py#L12-L31) · [SEED candidate and input contract](https://github.com/Ventusltd/seed-data/blob/153c1159ff58edcb8be5f598c2c78d13c85b6afd/experiments/economical-seeds/VEDIC_CANDIDATE.md)

## Review the proposed admission

From the VEDIC draft branch, reproduce the dictionary and its immutable source pins.

```text
python tools/source_admissions.py --check --online
python tools/validate_dictionary.py --online
python -m unittest discover -s tools -p 'test_find_capability_admission.py' -v
python tools/semantic_compiler.py "FIND CAPABILITY"
```

The compiler resolves the proposed row as `STATIC_POLICY_REPRODUCED` with readiness `NO_REVIEWED_PACKAGE_BINDING`. Execution refuses `PACKAGE_NOT_ADMITTED`. The draft needs independent exact-head review and the usual release approval. Preserve the queue commit as an ancestor as required by the [review process](DAILY-OPERATIONS.md).

## Reproduce the distinct SEED shadow evidence

Use a clean checkout of [the pinned kit](https://github.com/Ventusltd/seed-data/tree/153c1159ff58edcb8be5f598c2c78d13c85b6afd/experiments/economical-seeds). Run its three candidate tests and build the original 28-record catalogue or include the two separately verified additions described in the kit. An example request is `{"objective":"verify a captured component against exact historical source","limit":1}`.

```text
python -m unittest -v test_vedic_candidate.py
python seed_discover.py build --record next-rail/rail-record.json --record next-compose/instrument.json
python vedic_candidate.py "FIND CAPABILITY" --input request.json
```

The known request returns `audit-captured-source`; the unsupported volcanic-eruption fixture returns an empty result. SEED reports zero inference calls and zero underlying source and evidence-payload bytes read for these invocations. The shadow output retains its candidate status. The separate executable admission requires a reviewed binding, package and licence judgment through the existing VEDIC process.
