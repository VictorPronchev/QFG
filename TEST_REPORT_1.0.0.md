# QFG Dynamics 1.0.0-alpha — test report

Pure numerical regression suite: **PASS**.

B6-specific tests cover:

- a smooth asymptotically stable angle trajectory converges;
- a persistent oscillatory trajectory does not converge;
- protocol fingerprints are deterministic under key ordering;
- changing a protocol setting changes the fingerprint;
- frozen comparison preserves `CONDITIONAL` provenance for B6 predictions;
- all B3/B4/B5 regression tests remain active.

Blender `bpy` UI/runtime smoke testing still requires Blender 5.2 itself and is not available in this container.
