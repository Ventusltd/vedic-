# TACIT 3b nearest substation — source selection and recovery

Scope 646c3d324ca07e400ea3d4127e6f63cd8abecbf7; operating directive NL-087 #7195886180. Consumer base 0ee52af60036f32358759a67836578dce6d7da51.

Selected nearest-search because the pinned producer export index().nearest is a useful standalone point search and imports only the pinned v9-geodesy.js module. Reuses VEDIC 000015/000016 and the existing static Spider map; no new identity. Source itself says the historical extraction was not loaded by live Atlas; this candidate makes no live-parity claim. AREA has a separate geometry/core closure and polygon edge limitations; network-topology has a larger published-data schema and is a later candidate. ORIENT is not repeated: distance is a dependency, not a second family.

Run `python packages/nearest-candidate/probe.py` via hosted Ubuntu Actions. Acquires only four pinned files, verifies Git blobs, calculates SHA256, installs the two original modules into a temporary consumer package and invokes the public adapter without network access. Only JSON evidence is uploaded. Synthetic data, exact tie ordering, explicit named coordinates/kV and rejection of malformed records are adapter choices. Numeric range checks cannot detect all swapped coordinates or physically mislabelled voltage units. The producer metric is spherical, not ellipsoidal, and not routing or availability. No external data.

Shared factory descriptor and source receipt are pending TACIT 1b/10; this provisional descriptor is not a factory contract. TACIT 13 dependency confirmation and TACIT 9 independent numerical/package acceptance remain open. Root Apache-2.0 versus producer private/UNLICENSED requires owner rights resolution before redistribution. No upstream source bytes in this branch or artifacts.

Successor: inspect PR exact-head Actions run and evidence JSON; do not claim green until observed. If green, send descriptor and measured hashes to TACIT 1b/10/13/9 and integrate the shared factory only when its interface is available. If red, fix only this branch; retain prior logs. No main/homepage changes or new permanent IDs.
