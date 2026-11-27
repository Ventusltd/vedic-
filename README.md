# vedic-
Language designed for non coders where over 477k + lines of unique code is translated into functions in plain English

## Mandatory source-link regression guard

<!-- CVAA:VEDIC-DIRECT-SOURCE -->
See [CVAA vaccine: VEDIC direct source links](https://github.com/Ventusltd/cvaa/blob/97f4c37450c4359d56a1ae53137a7014678f662c/vaccines/202611271054-vedic-direct-source-links.md) and [verified repair](https://github.com/Ventusltd/vedic-/actions/runs/45985502826).

- Every reviewed command's Code cell must render its exact commit-pinned source anchor(s) directly from the initial search index, including composite components. Never require a detail request, a second click or execution of the code to expose source links. Lazy-load explanatory prose only.
- Preserve permanent command IDs, pinned source identity, line ranges, search and pagination. Daily discovery remains read-only: no UI changes, promotion or publication.
- A cached command index that lacks complete direct source anchors, contains mutable refs, or is structurally invalid must be retried once with cache reload, then explicitly refused. Do not restore the former two-click fallback. The browser fixture must exercise successful bounded recovery, persistent stale-index refusal and invalid source-pin refusal. This protects against the observed old-index shape; a structurally valid stale index is not cryptographically bound to the release by this check.
- Before publication run the full existing unit, provenance and staged Pages checks, plus `tools/browser_smoke.py`: every row and composite source, Chromium/WebKit, desktop and mobile portrait/landscape, unavailable and stale detail shards, and pagination beyond 100 rows. No sample-only PASS. Missing coverage is failure.
- Candidate checks must verify every direct anchor's browser actionability and real click/tap navigation for representative first, last and composite entries, using an intercepted destination fixture. External source availability is verified separately by online source checks. The fixture does not prove rendering of the external GitHub site.
- Serialize main validation and publication. Immediately before deployment, confirm that the checkout, staged release identity and current main SHA agree; refuse a stale run. This reduces ordering races but does not make the remote check and deployment atomic.
- After deployment, require exact served-file byte verification with `tools/verify_published.py` and a fresh live browser audit tied to the exact deployed Git commit; do not describe a release as working without the receipt. Headless WebKit is not physical iPhone acceptance.
- If any guard fails, stop promotion/success claims, record the defect and recover to a separately verified release. Do not bypass failed CI.

The 27 November 2026 fix restored direct anchors after the 26 November on-demand detail change. The original handset failure was reported but not independently reproduced; the scheduled daily workflow was not shown to be responsible.
