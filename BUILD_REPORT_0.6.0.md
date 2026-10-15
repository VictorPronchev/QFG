# QFG Dynamics 0.6.0-alpha — B2 build report

## Added

- Blender-independent `atlas_b2.py` numerical module.
- Conservative name-based nucleon/role inference with DERIVED provenance and confidence/evidence.
- Interaction graph builder with Source-star, Valence-only and All-tagged topologies.
- Explicit `j_proxy_matrix` with topology-only DERIVED mode and optional CONDITIONAL overlap / inverse-cube kernels.
- Orbital-plane normal extraction and axial dihedral analysis.
- Orbital-plane ring visualization in Blender.
- Oriented integrated-Bohr-envelope geometric proxy with object-bound/fixed/point radius modes.
- B2 runtime state and inclusion in Atlas/full-session JSON/CSV export.
- B2 controls in the Atlas Direct panel and per-object orbital-normal settings.

## Scientific guardrails

- Auto-detection does not create SOURCE provenance.
- Absolute `J_ij` energies are not claimed.
- `1/r^3` kernels are scene-unit-dependent geometry proxies.
- The integrated Bohr envelope is not presented as a solved field surface.
- Rejected 4-series multiplicity/normalization shortcuts remain excluded.

## Validation

- Pure Python numerical regression suite passes.
- Python syntax compilation passes for the full package.
- Blender `bpy` registration/runtime smoke test remains to be executed inside Blender 5.2.
