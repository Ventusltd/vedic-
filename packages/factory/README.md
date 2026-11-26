# TACIT 1b — private package factory v1

Owner scope: [immutable mandate](https://github.com/Ventusltd/neural-link-between-agents/blob/646c3d324ca07e400ea3d4127e6f63cd8abecbf7/SESSIONS/2026-11-26-TACIT-1b-TO-5b-PACKAGE-BUILD-SCOPE.md). Additive implementation; PR13 remains untouched. No permanent IDs or public releases.

## Consumer contract

`python tools/package_factory.py validate --descriptor packages/factory/admissions/orient.json`

`python tools/package_factory.py build --descriptor packages/factory/admissions/orient.json --inputs /path/to/pinned-inputs --out /path/to/new.zip`

Run under an actual network namespace without credentials. Acquisition is separate. The descriptor is JSON, with exact keys enforced by the executable validator. All sources have a repository, commit, original path, local filename, digest algorithm and expected digest; inputs are bounded to 2 MiB each. Evidence receipt paths identify artifacts, not necessarily files in Git. The allowlist in code points to reviewed descriptor files; candidate descriptors cannot nominate commands, network endpoints, adapters or hooks. This is an admission mechanism, not arbitrary code execution.

The v1 runtime is Node ESM >=18 with zero declared runtime dependencies, flat portable filenames, deterministic ZIP_STORED, private package and no registry install claim. Both direct path and package name imports are exercised. The source module and prior adapter are unchanged; the pinned PR13 Python is parsed for literal adapter, README and consumer test strings, never executed by the factory. SHA256 or exact Git blob SHA1 is checked independently against the admission and observed SHA256 is recorded for every input. The new candidate version and manifest differ intentionally from PR13; no claim that its archive hash matches PR13.

TACIT 2b/3b/4b: propose another descriptor following the exact key structure in admissions/orient.json, with a family name and local candidate identifier, source and receipt pins, precise ports, runtime dependency closure and licence notice. The factory owner reviews a family-specific adapter and adds its handler and admission in a separate reviewed commit; no source formula changes. Synthetic descriptors may validate structurally but must fail real admission. TACIT 5b consumes only exact manifest and build receipt, not a working directory. TACIT 9 must independently assess the exact archive; TACIT 15 owns publication.

Refusal codes include DUPLICATE_KEY, INVALID_JSON, SCHEMA, FIELDS, CANDIDATE, PACKAGE_NAME, VERSION, FAMILY, RUNTIME, EDITION, TIER, LICENCE, BUILD, EXPORT, PORTS, INPUTS, SOURCE_PIN, SOURCE_PATH, DIGEST, DIGEST_ALGORITHM, UNSAFE_PATH, PATH_COLLISION, REQUIRED_INPUT, REQUIRED_OUTPUT, FAMILY_NOT_ADMITTED, ADMISSION_MISMATCH, MISSING_OR_SYMLINK, INPUT_SIZE, INPUT_DIGEST, RECEIPT, ADAPTER_CONTRACT, ARCHIVE_DUPLICATE, ARCHIVE_METADATA, ARCHIVE_FILE_SET, ARCHIVE_BYTES, MANIFEST_COUNT, MANIFEST_DUPLICATE, MANIFEST_FILES, NONREPRODUCIBLE. CLI refuses nonzero; no archive is emitted until checks pass, and an existing output is never overwritten.

Outstanding: second real family; independent review; Stars occurrence; redistribution rights. No npm or public package distribution. Linux-only O_NOFOLLOW and network namespace in this candidate. The receipt reports development checks, not independent acceptance.

## Second-turn electrical integration (receipt held)

`packages/factory/pending/electrical.json` records exact TACIT2b first-turn source, adapter and test pins. It deliberately lacks a TACIT10 receipt and is not an admission; its identity tier is a proposed target only. The build/validate commands refuse SOURCE_RECEIPT_PENDING even if a caller adds a forged receipt. The separate `probe-pending-electrical` command verifies all pinned bytes, runs original peer tests and direct/package-name import tests in a disposable clean directory, and emits evidence only, no archive. Once TACIT10 supplies an exact independently pinned receipt and TACIT13 confirms closure, review the actual receipt schema, update electrical_adapter, move reviewed descriptor into ADMISSIONS and remove pending entry. Keep old ORIENT bytes unchanged. Synthetic two-file .js ESM test proves flat relative import support, not real GIS admission.

Third turn: pinned peer proposals for nearest and solar remain pending; electrical pre-admission now uses the exact 51-test revision plus peer consumer. `tools/typed_package_execution.py` accepts only the fixed ORIENT request shape and exact previously verified archive/descriptor. CI invokes it under network isolation; no NLP, arbitrary graph, nearest composition or public release. A receipt registry is empty until actual TACIT10/13 reviews are pinned. Example request in `packages/factory/orient-execution.json`.
