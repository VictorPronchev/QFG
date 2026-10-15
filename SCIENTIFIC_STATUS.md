# Scientific status and interpretation

QFG Lab implements equations and hypotheses from the working QFG documents as testable computational prototypes. It does not establish that the proposed ontology or corrections describe nature.

## Implemented directly

- Complex field density and phase evolution on a 3-D periodic grid.
- Density anchoring, gradient stabilization, damping, HRM forcing, and thermal feedback.
- Reduced spinor orientation texture and topology-related energy diagnostics.
- Numerical scans and exportable observables.

## Implemented as reduced sectors

- U(1)-like gauge field.
- Weak-field gravitational potential.
- Yb Bloch/control dynamics.
- Nonlinear RF resonator and plasma envelope.

## B2 provenance extensions

- Name-based nucleon/role inference is **DERIVED heuristic**, never SOURCE by itself.
- Source-star connectivity is a reproducible topology descriptor.
- `J_ij` overlap/inverse-cube values are **CONDITIONAL geometry proxies**, not calibrated energies.
- Orbital-plane local-axis extraction can preserve SOURCE orientation; the valence-vector normal bridge is CONDITIONAL.
- The integrated Bohr envelope is a CONDITIONAL oriented geometric envelope, not a solved electromagnetic/SG field surface.

## Implemented as source/derived geometry bridges

- Atlas Direct: user-tagged BSM-SG/ANS source objects → deterministic 3-D valence vectors, pair angles, symmetry descriptors and blind freeze/reveal holdouts.
- Provenance is explicit: SOURCE, DERIVED, CONDITIONAL, CALIBRATED, EXPERIMENTAL, REJECTED.
- Atlas Direct does **not** establish the physical correctness of the BSM-SG nuclear ontology; it makes geometry claims reproducible and falsifiable.

## Implemented as proxies/bridges

- Hopf/helicity estimator.
- QFG-inspired molecular functional and target optimizer.
- Cavity, MEMS, phase-noise, Allan and IMD signatures.

## Required before a physical claim

- Grid, timestep, domain and backend convergence.
- Conservation checks with damping/drives disabled.
- Conventional-model baseline.
- Blind or preregistered parameter scans.
- Instrument calibration and uncertainty budget.
- Replication and model comparison.

Terms such as “candidate resonance”, “proxy”, and “reduced model” are deliberate and should be preserved in publications and project descriptions.


## QFG Dynamics body runtime

The 0.4 dynamic-body layer is an engine-architecture and visualization
prototype with a deterministic reduced 6-DoF solver. Bodies may use spheres or
oriented boxes; contact response includes inertia, contact-point impulses and
Coulomb friction. Field force/torque coupling is derived from sampled gradients
of the reduced QFG fields. These mechanics are not experimentally calibrated
and must not be described as a validated replacement for PhysX, Chaos, Bullet,
finite-element analysis, or certified structural software.

## B3 Atlas-to-field bridge

- SOURCE/DERIVED Atlas transforms may now drive a reduced numerical field.
- The source kernel, source strengths, radii, anisotropy tensor law and vector coupling are **CONDITIONAL**.
- `REJECTED` Atlas objects are excluded from field generation by construction.
- The scalar field is a reduced QFG potential term; the vector field is an optional reduced spin/orientation term.
- B3 does **not** supply the missing absolute BSM-SG molecular interaction normalization identified by the 5E freeze.
- A visually stable Blender field is not experimental evidence; convergence, conventional baselines and blind measurement comparisons remain required.

## B4 bidirectional Atlas/QFG feedback

- B4 samples reduced QFG density gradients and, in spinor mode, local spin texture at Atlas source positions.
- Translation and orientation updates are **bounded relaxation proxies** with explicit per-source couplings/mobilities and anchor restoring terms.
- The gradient uses periodic central differences to match the FFT field topology.
- Optional re-rasterization closes the numerical loop: Atlas geometry → B3 field → QFG evolution → B4 geometry update → refreshed B3 field.
- Force, torque and `W*` work bookkeeping are dimensionless CONDITIONAL diagnostics; they are not SI force, torque or energy.
- `REJECTED` provenance is excluded from B4 by construction.
- B4 does not resolve the 5E missing absolute interaction normalization and must not be described as a first-principles BSM-SG molecular dynamics engine.


## B5 constraint-aware Atlas/molecular relaxation

- B5 constrains B4 motion to a captured geometric admissible set rather than adding a new absolute force law.
- Pair connectivity can be explicit SOURCE-reviewed data or DERIVED topology; complete-graph assumptions are not inserted automatically.
- Radial shell and angular-cone constraints encode declared geometric freedom only.
- C3 symmetry groups preserve captured azimuth while allowing the common polar tilt — and therefore the pair angle — to change.
- Iterative stiffnesses, tolerances and safety clamps are **CONDITIONAL numerical parameters**, not BSM-SG constants.
- `REJECTED` geometry is excluded by construction.
- B5 does not resolve the 5E missing absolute energy normalization or the failed one-coordinate tunnelling dynamics.


## B6 blind Group-15 relaxation protocol

- B6 is an experiment-control layer, not a new physical law.
- B3/B4/B5 dynamics remain **CONDITIONAL**, therefore a B6 relaxed angle is also CONDITIONAL even when the input Atlas geometry is SOURCE.
- Convergence uses only predicted angle stability, drift, C3 spread and optional B5 correction size; no experimental target enters the convergence detector.
- A SHA-256 protocol fingerprint records source transforms and numerical settings for reproducibility.
- A converged B6 result may be frozen while the experimental reference remains hidden; reveal/comparison is a separate action.
- Failure to converge is a valid outcome and must not be converted into a fitted angle.
