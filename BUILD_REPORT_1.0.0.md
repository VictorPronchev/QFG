# QFG Dynamics 1.0.0-alpha — B6 build report

B6 adds an end-to-end blind Group-15 relaxation harness on top of B3 field coupling, B4 bidirectional feedback and B5 topology-aware constraints.

Implemented:

- Blender-independent `atlas_blind.py` convergence and protocol hashing.
- Prediction-only convergence gates with no holdout lookup.
- Strict blind-state guards before a run.
- Optional source-anchor reset and B5 recapture.
- Iterative QFG/B4/B5 relaxation with geometry trajectory capture.
- Automatic conditional freeze on convergence; experimental reveal remains separate.
- SHA-256 protocol fingerprint, JSON/CSV trajectory export and session export.
- Version bump to 1.0.0-alpha.

The physical status remains explicit: B6 predictions are CONDITIONAL because the dynamical bridge remains conditionally normalized.
