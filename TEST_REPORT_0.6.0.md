# QFG Dynamics 0.6.0-alpha — B2 regression report

Pure numerical test coverage now includes:

- name-only deuteron/valence inference and unresolved-name handling;
- provenance rule that auto inference stays DERIVED;
- `K1,3`-style Source-star graph edge count;
- topology-only graph normalization;
- finite CONDITIONAL `cos²/r³` proxy matrix;
- axial orbital-plane equivalence (`n` and `-n` represent the same plane);
- finite oriented integrated-envelope proxy;
- all pre-existing QFG field, dynamics, 6-DoF, molecular and Atlas Direct regressions.

Result: **PASS**.

Blender-specific UI/operator registration still requires a Blender 5.2 smoke test because `bpy` is unavailable in the build environment.
