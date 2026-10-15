# Changelog

## 1.0.0-alpha — B6 blind Group-15 experiment harness

- Added Blender-independent `atlas_blind.py` convergence logic with no dependency on experimental references.
- Added end-to-end B6 run operator: prepare source geometry, optional anchor reset/B5 recapture, initialize QFG, iterate B3/B4/B5, sample valence geometry, stop on prediction-only convergence.
- Added strict blind guards: B6 refuses runs after an experimental reference has been revealed or while an old prediction is frozen.
- Added deterministic SHA-256 protocol fingerprints over source transforms plus B3/B4/B5/QFG/B6 numerical settings.
- Added automatic freeze-on-convergence with `CONDITIONAL` prediction provenance; reveal remains a separate action.
- Added B6 trajectory/status diagnostics and JSON/CSV export.
- Added regression tests for convergent and oscillatory trajectories, deterministic protocol hashing, and conditional frozen-prediction provenance.

## 0.9.0-alpha — B5 constraint-aware Atlas/molecular relaxation

- Added Blender-independent `atlas_constraints.py` with bounded iterative geometry projection.
- Added captured pair connectivity, radial shell preservation and per-node angular freedom cones.
- Added symmetry groups that preserve captured azimuth while leaving collective polar tilt free; C3 molecular pair angles can therefore relax rather than being frozen.
- Added manual-neighbour, parent-child, B2 source-star and no-pair connectivity capture modes.
- Added B5 capture/clear/project operators, per-object constraint declarations and panel diagnostics.
- Integrated B5 after B4 proposals and before optional B3 re-rasterization, closing a topology-aware Atlas↔QFG loop.
- Added B5 JSON export and object-level correction audit properties.
- `REJECTED` geometry is excluded by construction; projection stiffness/tolerances remain CONDITIONAL.
- Added regression tests for connectivity, shell, cone, C3 collective-tilt freedom and provenance exclusion.

## 0.8.0-alpha — B4 bidirectional Atlas/QFG feedback

- Added Blender-independent `atlas_feedback.py` for deterministic QFG→Atlas sampling and bounded relaxation.
- Added periodic central-difference density gradients, matching the periodic FFT field domain.
- Added density-gradient, spin-texture and hybrid torque targets.
- Added per-source force/torque coupling, linear/angular mobility and position/rotation locks.
- Added captured anchor transforms plus position/orientation restoring terms and reset-to-anchor workflow.
- Added hard per-cycle translation/rotation clamps and a maximum anchor-displacement safety radius.
- Added optional automatic B3 re-rasterization after each B4 geometry update, closing the Atlas→QFG→Atlas loop.
- Added force/torque/work-proxy telemetry, object audit properties and full JSON session export.
- Added B4 support in manual stepping and explicit timeline baking; playback remains cache-only.
- `REJECTED` provenance is excluded from feedback by construction.
- B4 force/torque normalization, mobilities and work are **CONDITIONAL dimensionless relaxation proxies**, not first-principles or SI-calibrated BSM-SG dynamics.

## 0.7.0-alpha — B3 Atlas-to-QFG field coupling

- Added Blender-independent `atlas_field.py` and conditional source-field rasterization.
- Added Gaussian and softened inverse-cube source kernels.
- Added director/orbital-plane anisotropy tensors and optional local vector/dipole proxies.
- Added explicit Atlas scalar and vector fields to `QFGEngine3D`.
- Atlas scalar potential now participates in reduced field evolution; spinor mode can also use the local vector projection.
- Added provenance/role filtering so `REJECTED` assumptions cannot drive B3.
- Added per-Atlas-object B3 source strength, radius, anisotropy and enable controls.
- Added auto-apply on initialization and optional refresh before manual solver steps.
- Added B3 field diagnostics, scalar-energy proxy, heatmap slice and JSON/NPZ export paths.
- Absolute BSM-SG/QFG field normalization remains explicitly open and is not hidden in the implementation.

## 0.6.0-alpha — B2 Atlas interaction/orbital/Bohr integration

- Added conservative name-based nucleon/role auto-detection with DERIVED provenance.
- Added source-star / valence-only / all-tagged interaction graphs and explicit `J_ij` proxy matrices.
- Added orbital-plane normal extraction, axial dihedral diagnostics and ring visualization.
- Added oriented integrated-Bohr-envelope geometric proxy with explicit CONDITIONAL provenance.
- Extended Atlas/full-session exports with B2 graph, plane and envelope JSON/CSV outputs.
- Preserved the 5E freeze: rejected multiplicity/normalization shortcuts are not reintroduced.


## 0.5.0-alpha — B1 Atlas Direct / BSM-SG geometry integration

- Added Blender-independent `atlas_geometry.py` for valence-vector extraction, pair angles, symmetry axis, polar tilt and C3v height-ratio descriptors.
- Added `ATLAS_NUCLEON` actors with nucleon type, Atlas role, direction rule, provenance and source note.
- Added an **Atlas Direct / BSM-SG Geometry** sidebar panel.
- Added selection tagging for core, free-valence, bound and equatorial source structures.
- Added core-centroid, explicit-center-object and world-origin center modes.
- Added 3-D valence-vector visualization generated from the actual Blender transforms.
- Added a blind workflow: **Extract → Freeze Blind Prediction → Reveal Experimental Holdout** for N/P/As/Sb.
- Added JSON/CSV Atlas report export and inclusion in full QFG session exports.
- Added explicit provenance vocabulary: SOURCE / DERIVED / CONDITIONAL / CALIBRATED / EXPERIMENTAL / REJECTED.
- Added pure-Python regression tests for C3v geometry and holdout comparison.
- No molecular energy normalization or rejected 4F/4N multiplicity assumptions are promoted into Atlas Direct.

## 0.4.1-alpha — playback hardening and 6-DoF debug overlay

- Added explicit HOLD/CLAMP/STATUS_ONLY behavior outside the baked timeline cache.
- Status messages now distinguish requested frames from displayed cached frames.
- Added cache bounds/nearest-frame resolution helpers with pure regression tests.
- Cached `QFGWorld.telemetry()` alongside each baked body state.
- Added contact debug telemetry with point, normal, penetration and impulse vectors.
- Added viewport contact, force, torque and angular-velocity vector rendering.
- Added a compact 6-DoF diagnostics HUD for contacts, energy, momentum, angular momentum, force and torque.
- Kept frame-change playback display-only; no numerical solver steps are run by the overlay or handler.
- Preserved all 0.4.0 shape-aware 6-DoF behavior and regression coverage.

## 0.4.0-alpha — 6-DoF rigid bodies and shape-aware contacts

- Added quaternion orientation and angular velocity to `BodySpec` / `BodyState`.
- Added sphere/OBB inertia tensors and world-space inverse inertia.
- Added Sphere/Sphere, Sphere/Box and rotated Box/Box SAT collision detection.
- Contact-point impulses now produce angular response through `r × J`.
- Coulomb friction can generate physical spin; floor contact is shape-aware.
- Added external torque, field-alignment torque and angular drag.
- Added force + torque channels, rotational kinetic energy and angular momentum telemetry.
- Blender bake/cache now stores and reapplies rigid-body quaternion orientation.
- Native Collision showcase shards now use OBB collision shapes and seeded spin.
- Deterministic state hashes now include rotational state.
- Added 0.4 regression checks for inertia, momentum conservation, OBB SAT, friction spin and torque coupling.

## 0.3.3-alpha — Collision Solver v2, force telemetry, native showcase

- Reworked reduced sphere contacts into a stateful contact solver for body/body and floor contacts.
- Added impulse-based Coulomb friction for body/body and floor contacts.
- Added configurable penetration slop and positional correction.
- Added persistent floor-contact state so `contact_begin` is not emitted on every resting step.
- Extended contact events with normal, normal impulse, friction impulse and relative-normal-speed details.
- Added per-body force channels: gravity, QFG field, thermal, drag, contact and total force.
- Added per-body contact impulse telemetry and Blender custom properties for baked/runtime inspection.
- Added kinetic-energy, mean-force and maximum-force profiler metrics.
- Added deterministic translational runtime `snapshot_hash()` for replay regression checks.
- Added a native Blender Hero Showcase with COLLISION, HOPF, VORTEX, HRM_CAVITY, THERMAL, GAUGE_GRAVITY and PLASMA_BOUNDARY modes.
- Moved the camera safety rules into the add-on: unparented world-space camera, DOF off, procedural materials, Eevee selection and compositor disabled for generated showcase scenes.
- Extended session NPZ exports with all force/impulse channels.
- Expanded pure numerical regression tests with contact momentum conservation, tangential-friction reduction, contact begin/end state, floor persistence, force-channel consistency, coupling ON/OFF and deterministic replay hashes.
- Angular dynamics, shape-aware collision and CCD remain planned for the 0.4 line.

## 0.3.2-alpha — Cinematic camera and field-render hotfix

- Replaced the parented camera rig in the showcase with a safe world-space
  cinematic camera path outside the reactor chamber.
- Disabled depth of field for the technical hero render.
- Removed the central optical-axis field gate from the generated stage.
- Reduced containment-ring thickness and emission.
- Added a non-zero field-emission fallback when `qfg_density` is unavailable.
- Improved default QFG field display visibility for final renders.
- Added a no-rebake camera/stage repair script for existing scenes.


## 0.3.1-alpha — Render proxy and showcase hotfix

- QFG Gaussian, Hopf, vortex and boundary authoring meshes are now
  viewport-only proxies and excluded from final renders.
- Fixed the broad `QFG_Dynamics_Core` sphere covering the active camera.
- Showcase v2 selects Eevee explicitly instead of silently retaining Cycles.
- Added camera and visible-object render preflight diagnostics.
- Added a one-click repair script for existing baked `.blend` files.


## 0.3.0-alpha — QFG Dynamics runtime foundation

- Added a public `QFGWorld`/`BodySpec`/`WorldConfig` Python SDK layer.
- Added deterministic fixed-order field/body stepping and timeline caching.
- Added trilinear density, temperature, and field-gradient queries.
- Added reduced field-coupled sphere bodies with drag, gravity, floor and body contacts.
- Added runtime events for contact, field entry/exit, and temperature phase transitions.
- Added per-step profiling for spectral field, field queries, body integration, contacts and total runtime.
- Added `DYNAMIC_BODY` Blender actors and editable coupling/material parameters.
- Added a QFG Dynamics reactor-showcase preset with deterministic orbiting debris.
- Extended timeline cache, playback handler, session export, CSV events and profiler output.
- Added `sdk.py` so content scripts no longer need to depend directly on private runtime globals.
- Added pure-Python determinism and field-query regression tests.
- This remains an alpha research runtime; collision bodies are spherical proxies and are not a PhysX/Chaos replacement.

## 0.2.0 — Blender 5.2 LTS full-workbench rebuild

- Rebuilt the package as a Blender 5.2 extension with a root-level manifest and `__init__.py`.
- Raised the Blender target to 5.2.0 and reorganized the sidebar into focused QFG 5.2 panels.
- Expanded the 3-D FFT core with scalar and reduced spinor modes, Hopf-ring, vortex, plane-wave, and boundary actors.
- Added orientation texture, reduced Skyrme/Faddeev density, topology backreaction, and Hopf/helicity proxies.
- Added thermal diffusion, collision heating, and temperature-dependent cohesion.
- Added HRM spatial drive profiles, `(f1,f2)` scans, `modeVar` heatmaps, FFT/IMD, phase-noise, and Allan-deviation proxies.
- Added a reduced dynamic U(1)-like `A/E` field sector and gauge-energy diagnostics.
- Added a weak-field Poisson gravity proxy and optional backreaction.
- Added RF/Duffing hysteresis, cavity-shift, glow-plasma boundary, and MEMS geometry/Q models.
- Expanded the Yb module with Rabi, Ramsey, ODMR-like, cavity-Q, and two-ion phase comparison runs.
- Expanded Molecular Creator with transparent QFG-inspired proxy terms, target properties, and derivative-free geometry optimization.
- Added Blender heatmap planes, curve plots, timeline cache, and extended CSV/JSON/NPZ export.
- Kept mesh-vertex + Geometry Nodes point visualization to avoid the old `PointCloud.points.add()` error.
- Changed the Blender extension license to GPL-3.0-or-later and valid extension tags.
- Added pure-Python regression tests for the numerical modules.

## 0.1.3

- Fixed Blender 4.1 error `bpy_prop_collection: attribute "add" not found`.
- Replaced direct PointCloud allocation with mesh vertices plus Geometry Nodes `Mesh to Points`.

## 0.1.0

- Initial modular QFG Blender research prototype.
