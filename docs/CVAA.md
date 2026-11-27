# CVAA — mandatory independent audit

Central registry: [Ventusltd/cvaa](https://github.com/Ventusltd/cvaa/tree/b124c39e5343b24dd5b546a0c279a1c06360bdad).

The registry is the single source of antibody definitions. This consumer pins the reviewed registry Git SHA, checks out complete histories, verifies the registry identity, proves its antibodies on diseased and healthy fixtures, and runs the complete locked registry against this repository using a data-only snapshot. No consumer code is executed by an antibody. CI emits its exact identities, logs, structured results and SARIF evidence. It does not automatically alter either repository, add exemptions, or publish software.

## Operation and release authority

- Every PR, push to main and explicit dispatch triggers the same bounded audit. Existing application tests and release workflows remain intact.
- A finding is a finding. A skipped, superseded, inapplicable, unmeasured or unavailable rule is not evidence of immunity. Consult the JSON and logs, not merely the green tick; the registry may consider a no-finding run with skipped rules incomplete.
- Do not use `--no-lock`, `--baseline-write`, `continue-on-error` or a mutable registry branch to manufacture acceptance. Never broaden or renew exceptions automatically. Record and repair findings against the exact source revision.
- Registry updates require a reviewed immutable SHA, a passing lock/selftest receipt and an explicit change to this consumer's pin. CVAA's own registry compliance and self-audit remain separate requirements; the initial deployment is an audit, not certification of estate-wide immunity.
- A CVAA PASS does not confer owner approval, prove a live deployment, grant cross-repository write permission, or substitute for target-specific runtime tests.
- Before any release, review the CVAA evidence with the destination repository's established tests and approval rules. Do not merge a failed audit; do not disable other checks to achieve a green result.
- Keep evidence in the linked Actions run; do not paste secrets, private paths or raw private memory into public reports.

## Coverage of the initial registry

All 47 definitions at the pinned revision are loaded, with supersession and applicability governed by the registry itself. The corpus includes registry integrity, sandbox safety, pinned actions, least permissions, full history, bounded operations, provenance, generation integrity, context conservation, rollback, publication authority, observer isolation, runtime contracts, memory completeness, computational evidence, leak detection, and Kuiper/Neural Link-specific checks. A named rule is not a claim that every target has the necessary contract or that its result is PASS.

Pending reviewed registry proposals: [VEDIC context conservation #3](https://github.com/Ventusltd/cvaa/pull/3) and [direct source links #4](https://github.com/Ventusltd/cvaa/pull/4). These are not part of the pinned registry and must not be represented as active until their own CI and integration pass.

## VEDIC-specific rules

- A command is a reviewed stable identity, not a dynamically inferred permission to execute. Preserve permanent IDs, exact pinned sources and line ranges; distinguish dictionary presence, source navigation and authenticated execution.
- Never put Code anchors behind a command-detail fetch; all source links and composite components must be rendered from the initial index. Keep explanatory prose lazy only. The existing regression suite and [VEDIC guard PR #37](https://github.com/Ventusltd/vedic-/pull/37) are the runtime layer; the latter is pending and must not be claimed as deployed.
- Daily discovery remains bounded and read-only. No UI rewrite or publication authority comes from candidate discovery.
- Distinguish tested candidate, byte-identical public readback and physical handset acceptance.
