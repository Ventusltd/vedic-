# VEDIC semantic compiler

The compiler resolves a one-to-five-word command against the existing dictionary. Case and whitespace are normalised. Exact names and aliases resolve to existing permanent IDs. A homonym calls for an explicit existing sense ID. An admitted execution binding supplies the component order, units, canonical source, Kuiper keys, package digest and refusal conditions.

```text
python tools/semantic_compiler.py ORIENT
python tools/semantic_compiler.py AREA --sense-id GG2050-VEDIC-000019
```

`ORIENT` and `MEASURE DISTANCE AND BEARING` resolve to `GG2050-VEDIC-000006`, which combines existing elements for distance and initial bearing. Both take named longitude and latitude in WGS84 degrees. The producer package uses the existing Ventus Grid Engine with sphere radius 6378.137 km. The adapter refuses undefined headings at coincident and antipodal points and at polar origins. Approximate radius drawing, engineering routes and network access lie outside this composition.

The package's pinned source revision `487ec7bd` has no exact indexed Stars occurrence. The byte-identical module at `7c2a7b42` supplies same-blob Stars witnesses for families 511 and 8770, elements 80346 and 32757. The two Kuiper keys are producer-receipt addresses. The execution record retains both revisions and the evidence state of each.

## Private replay

The existing [identity producer](https://github.com/Ventusltd/vedic-/actions/runs/45839291608) and [Package Factory build](https://github.com/Ventusltd/vedic-/actions/runs/45857210164) supply the exact source and build evidence, artifacts `15126683549` and `15135998372`. The archived package was reassembled through the pinned Factory from the producer artifact and local Git objects. The result matches the original manifest, all input digests and the archived package hash.

```text
python tools/replay_orient_archive.py --vedic VEDIC_REPO --engine ENGINE_REPO --source-artifact SOURCE_ZIP --build-artifact FACTORY_ZIP --out PRIVATE_PACKAGE
python tools/semantic_compiler.py ORIENT --input COORDINATES_JSON --archive PRIVATE_PACKAGE/orient.zip --build-receipt PRIVATE_PACKAGE/build-receipt.json
python tools/replay_faraday_orient.py --faraday FARADAY_REPO --factory-repo VEDIC_REPO --private-package PRIVATE_PACKAGE --out NEW_EVIDENCE_DIR
```

Use the exact Factory revision already present in the VEDIC object store, or fetch that reviewed branch into the local object store. The command accepts this input shape.

```json
{"crs":"WGS84","unit":"degrees","point_a":{"longitude":0,"latitude":0},"point_b":{"longitude":1,"latitude":0}}
```

The private caller uses the existing typed execution contract. Windows adds only `SYSTEMROOT` to the pinned runner's child environment for Node's RNG. The execution receipt records the exact staged runner hash. The prior hosted Factory run used Linux network isolation. Local replay validates exact code and package bytes in a private temporary directory.

The staged Faraday candidate uses the published numbered runner at `e439b450` with candidate row 101 after its current 100 rows. It tests equator, date-line crossing and meridian against independently calculated spherical answers, and seven refusal cases. The official Faraday ledger awaits candidate admission. The package retains its private distribution and independent package-acceptance restrictions.

## Source and compiled reuse

```text
node tools/verify_semantic_reuse.mjs STARS_REPO ENGINE_REPO
python -m unittest discover -s tools
```

Three exports were inspected from the 766-entry compiled library. Six fixtures agreed for `REPRESENT` and `VOLTAGE` across compiled exports and canonical engine functions. The approximate circle export for Stars family 5197 produced an initial vertex 495.887553 km away for an intended 500 km at latitude 80°. An alias to a geodesic circle would change meaning.

`CHECK FIRM CAPACITY` is submitted for dictionary review with two pinned engineering family witnesses and an explicit MVA contract. The source's single-transformer utilisation is infinite. A typed portable wrapper and package acceptance remain open.
