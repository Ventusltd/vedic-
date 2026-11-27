# vedic-
Language designed for non coders where over 477k + lines of unique code is translated into functions in plain English

## Mandatory source-link regression guard

<!-- CVAA:VEDIC-DIRECT-SOURCE -->
See [CVAA vaccine: VEDIC direct source links](https://github.com/Ventusltd/cvaa/blob/97f4c37450c4359d56a1ae53137a7014678f662c/vaccines/202611271054-vedic-direct-source-links.md) and [verified repair](https://github.com/Ventusltd/vedic-/actions/runs/45985502826).

- Every reviewed command's Code cell must render its exact commit-pinned source anchor(s) directly from the initial search index, including composite components. Never require a detail request, a second click or execution of the code to expose source links. Lazy-load explanatory prose only.
- Preserve permanent command IDs, pinned source identity, line ranges, search and pagination. Daily discovery remains read-only: no UI changes, promotion or publication.
- Before publication run the full existing unit, provenance and staged Pages checks, plus `tools/browser_smoke.py`: every row and composite source, Chromium/WebKit, desktop and mobile portrait/landscape, unavailable and stale detail shards, and pagination beyond 100 rows. No sample-only PASS. Missing coverage is failure.
- After deployment, require exact served-file byte verification with `tools/verify_published.py` and a fresh live browser audit tied to the exact deployed Git commit; do not describe a release as working without the receipt. Headless WebKit is not physical iPhone acceptance.
- If any guard fails, stop promotion/success claims, record the defect and recover to a separately verified release. Do not bypass failed CI.

The 27 November 2026 fix restored direct anchors after the 26 November on-demand detail change. The original handset failure was reported but not independently reproduced; the scheduled daily workflow was not shown to be responsible.
