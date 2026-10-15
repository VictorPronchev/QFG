# B2 — Atlas interaction, orbital planes and integrated Bohr-envelope proxies

QFG Dynamics 0.6.0-alpha extends **Atlas Direct** without promoting unresolved molecular-normalization assumptions into source physics.

## Pipeline

`Blender Atlas objects → reviewed tags → valence geometry → interaction topology → orbital-plane normals → integrated-envelope proxy → export`

### 1. Conservative auto-detection

**Auto-detect Selected** reads object names only. Names such as `Deuteron_valence_01`, `Proton_core`, or `He_core` can be tagged automatically. These tags are always marked **DERIVED**, never SOURCE, and carry a confidence/evidence note. Existing SOURCE tags are preserved unless an operator explicitly allows overwrite.

Mesh shape is deliberately **not** interpreted as particle identity.

### 2. Interaction graph `J_ij`

Three topology modes are available:

- **Source star** — tagged `VALENCE ↔ EQUATORIAL` edges only. This is the preferred minimal topology for the current NH3/Group-15 work.
- **Valence pairs** — diagnostic valence–valence graph.
- **All tagged** — diagnostic complete graph.

The default kernel is **Topology only**, which creates unit edges and is marked **DERIVED**. Optional kernels `|cos χ|`, `cos²χ`, `1/r³`, and `cos²χ/r³` are explicitly **CONDITIONAL** geometry proxies. They are not interaction energies and inverse-distance values depend on Blender scene units.

### 3. Orbital planes

Each Atlas object can define its orbital-plane normal from local ±X/±Y/±Z. This is the cleanest workflow when the Blender object is oriented from Atlas/source geometry. A `Valence vector` convenience mode also exists, but is marked **CONDITIONAL**.

The B2 analyzer reports pairwise axial dihedral angles; `n` and `-n` are treated as the same plane normal.

### 4. Integrated Bohr envelope

B2 can build an oriented ellipsoidal envelope around tagged Atlas structures using object bounds, a fixed radius, or object centers only. The result is marked **CONDITIONAL** and is explicitly a geometric envelope proxy, not a solved BSM-SG electromagnetic/SG Bohr surface.

The proxy is useful for reproducible visualization, overlap bookkeeping, and later field-solver integration.

## Provenance rule

- `SOURCE` — explicit source/user-reviewed geometry
- `DERIVED` — deterministic geometry from SOURCE inputs
- `CONDITIONAL` — model bridge/proxy
- `CALIBRATED` — uses a fitted or measured scale
- `EXPERIMENTAL` — external reference
- `REJECTED` — audit/history only

B2 intentionally does **not** restore the rejected 24-channel counting, `3/24` isotope rule, `n_E=1` shortcut, or a fitted factor-of-two normalization.
