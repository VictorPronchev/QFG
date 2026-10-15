# Test report — 0.7.0-alpha / B3

Pure numerical regression suite: **PASS**.

Coverage added in B3:

- Gaussian Atlas scalar/vector rasterization shape and finiteness.
- Conditional provenance and source-count summaries.
- `REJECTED` sources are guaranteed to contribute zero field.
- Core engine accepts and exports a B3 field bundle.
- B3 scalar potential produces a measurable evolution difference against an otherwise identical control engine.
- Clear operation restores zero scalar/vector field.
- Spinor vector-projection path remains finite.

Existing B1/B2, dynamics, contact, topology, RF/HRM, Yb and molecular numerical regressions continue to pass.

Blender 5.2 `bpy` UI/operator registration cannot be executed in this container and remains an in-Blender smoke test for the alpha build.
