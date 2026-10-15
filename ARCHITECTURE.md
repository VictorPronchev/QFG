# QFG Lab 5.2 Architecture

## Design principle

Blender is the scene editor, experiment dashboard, geometry visualizer, timeline player, and results notebook. Numerical models are kept in independent modules so that each can be tested outside Blender and replaced by a more complete solver later.

## Module map

- `core.py` — 3-D field, spinor texture, topology, thermal, gauge, gravity, noise, diagnostics.
- `diagnostics.py` — session export, FFT, IMD, Allan and phase-noise proxies, timeline cache.
- `experiments.py` — HRM scan, plasma envelope, cavity shift, MEMS proxy, validation map.
- `rom.py` — nonlinear driven resonator reduced-order model.
- `yb.py` — Rabi, Ramsey, ODMR-like, Q-factor and two-ion phase models.
- `molecular.py` — molecular data model, transparent proxy functional, property targets, optimizer.
- `atlas_geometry.py` — Blender-independent Atlas Direct valence-vector geometry, C3v descriptors, provenance and blind-holdout comparison.
- `atlas_b2.py` — interaction-graph, orbital-plane and integrated-envelope geometry diagnostics.
- `atlas_field.py` — B3 Atlas→QFG conditional scalar/vector field rasterizer.
- `atlas_feedback.py` — B4 QFG→Atlas bounded force/torque relaxation and safety/anchor logic.
- `atlas_constraints.py` — B5 topology/shell/cone/symmetry admissibility projection with free collective C3 polar tilt.
- `atlas_blind.py` — B6 prediction-only convergence detector and reproducible protocol fingerprinting; intentionally independent of experimental holdouts.
- `properties.py` — Blender scene and actor parameters.
- `operators.py` — bridge from UI/scene objects to numerical modules.
- `dynamics.py` — QFGWorld, deterministic 6-DoF rigid-body solver, shape-aware contacts, force/torque telemetry.
- `showcase.py` — native procedural Hero Showcase stage, safe camera and render setup.
- `visualization.py` — field points, slices, curves, heatmaps and molecular bonds.
- `presets.py` — reproducible starting laboratories.
- `handlers.py` — playback of cached frames only.
- `runtime.py` — transient state and result caches.
- `panels.py` — Blender 5.2 user interface.

## Model status levels

- **Core numerical implementation:** explicit equations are evolved numerically.
- **Reduced model:** selected degrees of freedom are represented; the full covariant system is not solved.
- **Proxy:** a transparent measurable or comparative surrogate is calculated.
- **Bridge:** Blender-side data model for a future external validated solver.

## Performance strategy

- NumPy 32³ is the safe default.
- NumPy 64³ is suitable for moderate experiments.
- Torch/CUDA is optional for larger grids.
- Timeline playback reads baked arrays; it does not run the FFT solver in the frame-change handler.
- Point visualization is capped and thresholded to avoid generating a vertex for every voxel.

## Planned replacement boundaries

1. Replace reduced gauge dynamics with a constraint-preserving Maxwell/QFG solver.
2. Replace gravity proxy with a validated weak-field stress-energy mapping, then only if justified with a metric solver.
3. Replace molecular proxy with an external SCF/Kohn–Sham engine and calibrated QFG terms.
4. Replace Yb Bloch proxies with crystal/ion-specific Hamiltonians and measured apparatus transfer functions.
5. Add direct instrument control only through isolated adapters with explicit safety interlocks.


## QFG Dynamics 0.4 runtime layer

```text
Blender actors / Python content
          |
          v
      sdk.py
          |
          v
  QFGWorld (dynamics.py)
    |             |
    v             v
QFGEngine3D   6-DoF body/contact solver
    |             |
    +------ events/profiling/cache -----> Blender timeline adapter
```

`QFGWorld` is the public simulation-scene abstraction. The current body solver
is intentionally replaceable; a future C++/CUDA backend should preserve the
Python SDK and cache format.

## 0.6 B2 Atlas modules

- `atlas_geometry.py`: blind valence geometry and holdout comparison.
- `atlas_b2.py`: Blender-independent nucleon name inference, interaction graph/J proxy, orbital-plane analysis, and integrated-envelope estimation.
- Blender bridge in `operators.py`/`panels.py`: scene tagging, visualization, provenance and export only.

This keeps scientific calculations testable without `bpy` and prevents viewport state from becoming part of the numerical definition.

## B3 Atlas field path (0.7.0-alpha)

`atlas_geometry.py` and `atlas_b2.py` remain geometry/provenance layers. `atlas_field.py` is the first explicit bridge into the live numerical engine. It consumes only filtered Atlas source descriptors and returns dimensionless scalar/vector arrays. `QFGEngine3D` stores those arrays separately from ordinary static boundaries so the B3 contribution can be inspected, cleared, exported and regression-tested independently.

The separation is intentional: no B3 parameter is silently promoted to a source-derived BSM-SG energy constant.

## B4 bidirectional feedback path (0.8.0-alpha)

B4 closes the reduced numerical loop without changing the scientific provenance rules:

```text
reviewed Atlas transforms
        |
        v
 atlas_field.py (B3, CONDITIONAL)
        |
        v
 QFGEngine3D evolution on periodic grid
        |
        +--> density / spin texture
                    |
                    v
          atlas_feedback.py (B4)
          periodic gradient + local target
                    |
          bounded dx / bounded dtheta
                    |
                    v
           Blender Atlas transforms
                    |
                    +---- optional B3 re-rasterize ---->
```

The B4 update is deliberately a **relaxation bridge**, not a hidden Newtonian or SI force law.  Force scale, torque scale, mobilities, anchor strengths and the work proxy are CONDITIONAL.  SOURCE/DERIVED geometry can be audited independently, REJECTED provenance is excluded, and every cycle is limited by translation, rotation and anchor-radius clamps.

Timeline baking may execute B4 numerically, but ordinary playback remains display-only and never advances either solver or feedback.


## 0.9 B5 constrained-relaxation layer

```text
reviewed Atlas geometry
      ↓
B3 field → QFG evolution → B4 proposal
                         ↓
               B5 admissibility projection
                         ↓
                  updated Atlas geometry
                         ↓
               optional B3 re-rasterize
```

B5 is deliberately geometry-only. It does not supply the missing absolute molecular interaction normalization. Symmetry groups preserve captured azimuthal structure but allow a shared polar tilt to evolve, enabling blind Group-15 pyramid-angle tests without fitting the target angle.


## 1.0 B6 blind experiment harness

```text
reviewed Atlas source geometry
      ↓
optional reset to B4 anchors + B5 recapture
      ↓
B3 field → QFG evolution → B4 feedback → B5 projection
      ↓
three-valence geometry sample
      ↓
prediction-only convergence detector
      ↓
CONDITIONAL frozen prediction
      ↓
(separate user action) experimental reveal
```

`atlas_blind.py` does not import `atlas_geometry.GROUP15_REFERENCE_ANGLES` and cannot use the holdout value as a stopping target. B6 fingerprints the source transforms and numerical protocol before evolution, records the full angle trajectory, and only freezes a prediction after convergence gates are satisfied.
