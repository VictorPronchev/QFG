# QFG Dynamics 0.9.0-alpha — B5 build report

## Scope

B5 adds constraint-aware Atlas/molecular relaxation on top of B3 field coupling
and B4 bidirectional feedback.

## Added

- Blender-independent `atlas_constraints.py`.
- Captured pair-distance connectivity.
- Radial shell preservation with explicit tolerance.
- Per-node angular freedom cones.
- Symmetry groups that preserve captured azimuth while allowing collective polar
  tilt to evolve.
- B5 capture / clear / manual projection operators.
- Automatic B5 projection inside B4 when enabled.
- Per-object B5 enable/fixed/radius/cone/neighbour/symmetry declarations.
- B5 diagnostics and JSON export.
- Provenance rules excluding REJECTED nodes and edges.

## Verification

- Python compileall: PASS.
- Pure numerical regression suite: PASS.
- Pair-distance recovery: PASS.
- Shell-radius recovery: PASS.
- Angular-cone enforcement: PASS.
- C3 symmetry with non-frozen collective polar tilt: PASS.
- REJECTED exclusion: PASS.

Blender `bpy` runtime is unavailable in the build container, so final UI/operator
smoke testing must be performed in Blender 5.2.
