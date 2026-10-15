# Build report — QFG Dynamics 0.7.0-alpha / B3

B3 was built on top of 0.6.0-alpha without removing the B1/B2 Atlas provenance workflow or the existing dynamics, molecular, Yb, RF/HRM, thermal, gauge and gravity modules.

Implemented:

- Blender-independent `atlas_field.py`.
- Finite Gaussian and softened inverse-cube Atlas source kernels.
- Director/orbital-normal anisotropy tensor bridge.
- Scalar potential and local vector-field rasterization on the QFG grid.
- Explicit `QFGEngine3D.set_atlas_field()` / `clear_atlas_field()` API.
- Scalar B3 potential included in field evolution for scalar and spinor modes.
- Local B3 vector projection included in reduced spinor evolution.
- SOURCE/role filtering and per-object strength/radius/anisotropy controls.
- Auto-apply on engine initialization/reset and optional refresh before manual steps.
- B3 field heatmap slice, runtime diagnostics and Atlas/full-session export metadata.
- Scalar Atlas energy proxy and field arrays in numerical snapshots.

No absolute physical energy normalization is introduced. The B3 bridge is labeled `CONDITIONAL` throughout.
