# B6 — Blind Group-15 Atlas/QFG relaxation protocol

Version: **QFG Dynamics 1.0.0-alpha**

B6 is the first end-to-end blind experiment harness in the Blender extension. It does not add a new force law. It orchestrates the already-labelled **CONDITIONAL** B3/B4/B5 stack and prevents the experimental Group-15 H-X-H angle from entering the numerical stopping rule.

## Workflow

1. Review/tag the Atlas source objects and choose N, P, As or Sb.
2. Configure B3 field, B4 feedback and B5 geometry constraints.
3. Keep the experimental holdout hidden and reset any previous frozen result.
4. Run **B6 Blind Relaxation**.
5. B6 optionally resets to captured B4 anchors, recaptures B5 admissibility, initializes QFG, and fingerprints the protocol.
6. Each B6 iteration advances QFG, applies B4 feedback, applies B5 constraints, and measures the three VALENCE vectors.
7. Convergence is judged only from the recent prediction trajectory.
8. If converged, B6 can freeze the predicted angle with `CONDITIONAL` provenance.
9. Only then use **Reveal Experimental Holdout**.

## Convergence gates

A run may stop only after the minimum sample count and convergence window are available. The recent window must satisfy:

- small peak-to-peak mean-angle range;
- small linear angle drift per iteration;
- small pair-angle standard deviation (C3-equivalence check);
- optionally, small B5 correction magnitude.

The experimental reference angle is not an input to these gates.

## Reproducibility

Before evolution B6 serializes the current source transforms plus B3/B4/B5/QFG/B6 settings and computes a SHA-256 protocol fingerprint. The full trajectory and fingerprint are included in Atlas/session exports.

## Scientific status

The protocol discipline is strict, but the relaxed geometry is still **CONDITIONAL** because B3 kernel normalization, B4 force/torque relaxation and B5 projection stiffness are not first-principles absolute BSM-SG laws. A successful holdout comparison is evidence about this declared model configuration, not proof of BSM-SG as a fundamental theory.
