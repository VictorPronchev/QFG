# QFG Dynamics 0.5.0-alpha — B1 Build Report

## Scope

This build starts the BSM-SG/QFG Blender integration as an auditable geometry layer rather than extending the molecular proxy with unverified energy closures.

## Added

- `atlas_geometry.py`: Blender-independent valence-vector geometry engine.
- `ATLAS_NUCLEON` Blender actor type.
- Nucleon metadata: proton / neutron / deuteron / tritium / helium / other.
- Atlas roles: core / free valence / bound / equatorial / other.
- Direction modes: center-to-object or signed local X/Y/Z axes.
- Provenance labels: SOURCE / DERIVED / CONDITIONAL / CALIBRATED / EXPERIMENTAL / REJECTED.
- Atlas Direct sidebar panel.
- 3-D extraction of pair angles, mean/spread/range, symmetry axis and C3v h/r descriptor.
- Blind prediction freeze and post-freeze N/P/As/Sb holdout reveal.
- Atlas JSON/CSV report export and integration with the full session exporter.
- Viewport valence-vector visualization.
- Regression coverage for the pure geometry module.

## Scientific boundary

No rejected 4F 24-channel multiplicity, 3/24 isotope rule, nE=1 closure, or g-factor rescue term is used by Atlas Direct. Molecular-energy and tunnelling models remain separate conditional/proxy layers.

## Compatibility

- Blender target: 5.2+
- Existing field, dynamics, HRM/RF, thermal, Yb and Molecular Creator code paths preserved.
- Existing public `QFGWorld` runtime API unchanged.
