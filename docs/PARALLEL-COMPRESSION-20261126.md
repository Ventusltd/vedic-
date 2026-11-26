# Parallel command compression, 26 November 2026

The public baseline contained 69 command meanings. The reviewed append adds CHECK FIRM CAPACITY and keeps the first 69 records unchanged. It describes the arithmetic for caller-supplied transformer ratings and demand in MVA. Its result is outside network availability and security compliance. The source reports zero firm capacity and an infinite firm utilisation quotient for a single transformer. No execution package was admitted for this command.

## Reproduced evidence

- Modular Star inventory at commit 1cf9c7530c7d287ccf9b3cffd70f693fb83c8402 contains 478,800 line IDs, 94 scanned repositories, 34,370 elements, 33,221 permanent families, 7,560 families repeated across current file lineages, 766 compiled library functions, 8,905 file versions and 9,345 indexed commits. The compact producer catalogue has 27,141 current-placement family rows.
- CPU extraction projected 34,370 elements through 4,073 selected source paths and 5,325 file versions. The six-worker run took 7.645 s wall, including 2.738 s of planning, and logged 10.984 aggregate worker CPU seconds. It reused 1,024 elements. A targeted Acorn pass read 29 pinned files, inventoried 2,055 symbols and identified 121 export bindings in 1.663 s. The role and refusal labels are source cues.
- The GPU used 32,769 element-linked families. Another 452 permanent families had no linked element in this snapshot. It evaluated 536,887,296 unique unordered pairs. Cosine thresholds 0.85, 0.90, 0.92, 0.95 and 0.99 yielded 22,806, 17,691, 15,952, 12,313 and 7,710 pairs respectively. The retained graph contains 393,228 directed neighbours. Six canonical relationship checks found bounded parity, a context-dependent variant, numerical drift, inverse contracts and complementary operations. The output includes 6,119 same-symbol cross-family leads at 0.92 or higher among retained neighbours and 725 equal token/count buckets. These are leads. Separately, 7,991 exact producer element IDs appear in multiple current file lineages.
- The full GPU scan took 3.976 s after 17.972 s of CPU feature preparation. Device scoring took 0.833 s and the observed CuPy pool used 402,898,432 bytes, including cached blocks. The full NumPy score-only replay took 5.418 s across six threads and matched GPU aggregate counts at all five thresholds. The 2,048-family transfer-inclusive comparison was 15.46 ms NumPy and 9.43 ms GPU, with maximum score error 1.61e-6 and no threshold-mask disagreements in that comparison.
- ORIENT retained existing ID 6. The compiler resolves two existing operations for distance and initial bearing, retaining their source, Kuiper and Modular Star witness evidence. T4 independently replayed staged Faraday candidate 101 through the digest-matched private package. Three analytic cases and seven refusals passed. A further analytic case from 0?/30? to 90?/30? matched 8407.12488690349 km and 63.43494882292201? within 1e-9. This is one private command verified on bounded fixtures. The Faraday candidate remains staged locally and package redistribution remains blocked.
- Independent CHECK FIRM CAPACITY review used the pinned engine source at 7c2a7b42905674fdcd3aa4bb50af14bc352a7747. Four arithmetic cases and four invalid-input cases passed. The primary source is assessAgainstFirm, lines 171?198, with firmCapacityMva as a dependency. Intake evidence records permanent family IDs 80294 and 80292. Existing UTILISE and CHECK POWER CAP compare different inputs and contracts. [Independent acceptance](https://github.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-7202707297)

## Local artifact identities

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| CPU element features ZSTD Parquet | 31,762,880 | `d7fbf1c9d0c8d4f1a7e6f74b2f0e757af2cdc2915d420e32b5201feee3ffa371` |
| CPU standalone intelligence DuckDB | 69,742,592 | `3a3758791a87c78906e427d1840337e5d27fdb770abf938d069c2c0fae9f7882` |
| GPU neighbour Parquet | 2,649,124 | `635a539f25ff7785f4eaf780f093476c5075e813903419f7e4ba810f504cc72f` |
| GPU family Parquet | 1,337,765 | `9c0baf0c8a2b799c4ee3e8d9b7a105b3cbab9123d5c3c35c0117e21ae29e8283` |
| GPU cluster Parquet | 194,501 | `837ba8e4bb041171d455d219e4fb6742eb358df133adb0366783855a5d75b271` |

Reproduce against the producer SQLite snapshot recorded in the [Modular Star release](https://github.com/Ventusltd/stars/releases/tag/modular-star). Its compressed SHA-256 was `2379a68bd54096b94efcb13fb557aa8eaad68c756b5b3fdf09a64a51da5414c1`. Use the integrated extraction and comparison tools locally with PyArrow, NumPy, SciPy and the existing CUDA/CuPy installation.

```text
python tools/modular_features.py modular.sqlite element-features.parquet --workers 6
python tools/family_similarity.py element-features.parquet similarity-output --dimensions 1024 --tile 256 --top-k 12
```

The measured extraction reused a 1,024-element pilot with `--reuse`. The 766 compiled exports describe producer source availability. The released dictionary counts reviewed meanings. Private execution counts only the package and fixtures actually run. Corpus-wide behavioral equivalence remains unmeasured.
