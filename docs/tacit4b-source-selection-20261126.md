# TACIT 4b — first source-selection checkpoint (2026-11-26)
Status: SOURCE_SELECTED; not built, admitted, independently accepted or released.
Scope: Neural Link 646c3d324ca07e400ea3d4127e6f63cd8abecbf7, issue 87.
VEDIC base: 0ee52af60036f32358759a67836578dce6d7da51.
## Selected first family
Use the original `tableShape(p,mps,layout)` export from Solar Design Studio's deployed edition 202609282123. Homepage index points to this edition's overlay.html, whose plant.js adapter imports plant-layout.mjs, which in turn imports tableShape from structures.mjs. The latter has no imports and declares no DOM dependence. Do not copy/reimplement the formula. Pin the complete existing structures.mjs bytes, and expose only tableShape through a validated adapter.
Producer snapshot: Ventusltd/globalgrid2050 @ 2f4b7cb82ee154fa3c684cba634d45f2183c6e7d.
Source path: energy-transition-simulator/202609282123/mod/engine/structures.mjs
Reported Git blob: 52619f60fea35e05d7634d760b7c19b6712f9b97.
Plant-layout caller blob: 80279238551c6326c40e600cb6a0bffa528431f9.
Plant adapter blob: 6e0557ffdfe07193c6e88455ac53f31a56f77cee.
The copied-file header asserts v12 3adcee9 and file-last-change f52e11f; attempted v12 commit retrieval returned 404, so upstream equivalence remains unverified. The header's Modular Star family #148673 refers to parseFormat, not tableShape; no permanent identity inferred.
## Proposed narrow contract
Explicit moduleLongM, moduleShortM, moduleGapM, tiers, orient, tableCols, modulesPerString and layout. Initially support only south-facing fixed-tilt 2P portrait with explicit positive integer columns and modulesPerString; reject other formats until verified, and reject nonfinite/invalid dimensions. Output original tiers, orient, along, up, slope (metres), cols and module count. No energy yield, structural approval, real terrain, electrical string compatibility, or financial forecast. Geometry means slant dimensions, not projected ground footprint.
Synthetic known-answer candidate: 2.384 m long, 1.134 m short, 0.02 m gap, 2 tiers, 30 columns, 30 modules/string -> along 1.134 m, up 2.384 m, slope 4.788 m, 60 modules. Expected arithmetic only; not yet executed.
## Next gate
TACIT 10 exact full-byte source receipt and identity evidence; TACIT 13 dependency closure; TACIT 1b common descriptor/factory contract; TACIT 9 independent acceptance after candidate CI. Rights and original-source provenance remain unresolved; no distribution or homepage changes. Financial sandbox candidate gis-sld-v5-finance.js appears DOM-bound and is deferred until first family proven. Repository-local AGENTS.md retrieval returned 404; do not infer that all rules are absent. No implementation or test result claimed.
