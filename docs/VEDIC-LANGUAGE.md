# VEDIC language — draft 0.1

Coordination: [NL-087](https://github.com/Ventusltd/neural-link-between-agents/issues/87). Tacit 1 owns the language and dashboard; Tacit 2 owns independent functional evidence and review.

VEDIC translates a bounded assembly of code into plain English about its observable purpose. It is not yet an executable programming language and must not imply that paraphrases are semantically equivalent to code.

## Statement structure

- **Application:** the named user-facing product and pinned composition.
- **Capability:** a verb and object in everyday English, for example "Find nearby grid infrastructure".
- **When:** the user action or system event, if known.
- **Uses:** stable body IDs and their source provenance; separate actual dependencies from proposed reuse.
- **Produces:** an observable output, including units and boundary conditions where evidenced.
- **Cannot conclude:** what the output does not establish.
- **Evidence:** manifest declaration, static source analysis, or executed test, with pinned commit and exact source path/range or receipt.
- **Identity:** existing block, family and line IDs when independently resolved; otherwise unknown.
- **State:** declared, inferred, tested, historical, or unknown. A passing test only supports its named assertion and input.

## First translation

Application: GridAtlas, generation 202611222343.

Capability: Find nearby grid infrastructure.

When: a project or substation is selected.

Uses: sld-sandbox and substation-intelligence cartridges, as recorded in the pinned composition. This is a manifest-backed candidate grouping, not a runtime call graph.

Produces: nearby infrastructure and measured distances, subject to source-data availability.

Cannot conclude: connection capacity, land access, permission or a constructible cable route.

Evidence: [pinned GridAtlas manifest](https://github.com/Ventusltd/gridatlas/blob/afffa9781f6130529ae93052604cd3d98d172a35/atlas/current.json). Actual function boundaries and runtime observations are pending independent review.

## Invariants

Reuse Modular Star's permanent IDs, existing Periodic Table, Vedic categories, Spider Maths Genome, and existing proof machinery. Do not renumber or infer IDs from names. Distinguish mathematical identity from semantic equivalence and code membership from execution. Count unique numbered lines by set union within any selected scope; overlapping capabilities are non-additive. Keep historical corpus and active composition counts separate. Missing evidence remains null; a manifest-declared feature is not a proven feature. Do not alter producer applications or publish an unreviewed dashboard.

## Dashboard presentation

Use GlobalGrid2050 black/cyan SCADA styling as in SatNav, with concise action labels and progressive disclosure from application to capability, body, block, family and line. Every drill-down must expose its evidence and uncertainty. Integrate existing Spider Printer only after its implementation and interface have been identified; the local print action is not that integration.
