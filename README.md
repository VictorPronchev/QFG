Turn Blender scenes into interactive field-driven simulations.

QFG Dynamics is an experimental physics and scientific-visualization extension for Blender 5.2 that combines 3D fields, 6-DoF dynamics, collisions, thermal effects, topology, structural constraints, and procedural scientific geometry inside one workflow.

It is designed for artists, technical directors, researchers, and anyone who wants to explore motion and structure beyond conventional rigid-body simulation.

### Highlights

- Field-coupled 6-DoF body dynamics with forces, torques, contacts, drag, gravity, and collision response.
- Interactive 3D scalar and reduced spinor field simulation.
- Gaussian nodes, vortices, Hopf-ring structures, plane waves, boundaries, and custom field actors.
- Thermal feedback, collision heating, HRM dual-frequency driving, and noise robustness tools.
- Reduced topology, gauge, gravity, RF, plasma, cavity, MEMS, and quantum-control research modules.
- BSM-SG / Atlas structural workflow with interaction graphs, orbital planes, field coupling, feedback, constraints, and blind relaxation.
- Molecular scene creation and reduced geometry/energy proxy tools.
- Timeline baking, visualization point clouds, density slices, debug overlays, telemetry, diagnostics, and export.
- Deterministic simulation options for reproducible experiments.
- Built-in showcase scenes for quickly exploring the engine.

### Built for visual experimentation

QFG Dynamics is especially useful for creating unusual motion, energetic structures, procedural scientific scenes, field-driven animation, abstract visual effects, technical visualization, and cinematic simulation concepts that are difficult to achieve with standard rigid-body tools alone.

The extension can be used interactively inside Blender or through its Python SDK for scripted simulations and custom pipelines.

QFG Dynamics 1.0.0 is an experimental research workbench. Some modules are reduced-order, proxy, or conditional models and should not be interpreted as experimentally validated physical laws without independent verification.
## QFG Dynamics 1.0.0 — Initial Release

The first public release of QFG Dynamics introduces a complete field-driven simulation and scientific-visualization environment for Blender 5.2.

### Core simulation

- 3D scalar and reduced spinor QFG field engine.
- NumPy CPU backend with optional PyTorch CPU/CUDA support.
- Configurable numerical grid, domain size, timestep, damping, cohesion, stability, and anisotropy.
- Gaussian, vortex, Hopf-ring, plane-wave, boundary, detector, and custom scene actors.

### 6-DoF dynamics

- Field-coupled rigid-body translation and rotation.
- Body-body and floor contacts.
- Force and torque feedback.
- Gravity, drag, restitution, friction, velocity limits, and deterministic replay.
- Collision, force, torque, and runtime telemetry.

### Visualization and animation

- Density point-cloud visualization.
- Density slices.
- Force and torque debug overlays.
- Timeline baking and cached playback.
- Built-in showcase scenes and cinematic workflows.

### Research modules

- Thermal simulation and collision heating.
- HRM dual-frequency drive and scan tools.
- Reduced topology and Skyrme-style diagnostics.
- Reduced gauge and weak-field gravity sectors.
- RF resonator, plasma, cavity, and MEMS proxy models.
- Yb quantum-control tools.
- Molecular Creator and reduced optimization tools.

### Atlas / BSM-SG workflow

- Source geometry tagging and provenance tracking.
- Interaction graph generation.
- Orbital-plane analysis and structural envelopes.
- Atlas-to-field coupling.
- Field-to-geometry feedback.
- Structural and angular constraints.
- Blind relaxation workflow with reproducible protocol fingerprints.

### Export and reproducibility

- Session and diagnostic export.
- Atlas reports.
- Deterministic seeds.
- Numerical convergence workflow.
- Python SDK access for custom simulation pipelines.

This is the first public release and the API and interface may continue to evolve.
# QFG Lab 5.2 for Blender

## 1.0.0-alpha B6 — Blind Group-15 relaxation harness

B6 turns the Atlas/QFG stack into an end-to-end blind experiment protocol. It captures a reproducible source/configuration fingerprint, runs B3 field coupling + B4 feedback + B5 admissibility projection, samples only the predicted Group-15 valence geometry, and stops only when prediction-side convergence gates are satisfied. The convergence detector does **not** read the experimental holdout registry. A converged result may be frozen automatically; the experimental H-X-H reference remains hidden until the separate Reveal action. See `B6_BLIND_PROTOCOL.md`.


## 0.9.0-alpha B5 — Constraint-aware Atlas / molecular relaxation

B5 projects B4 force/torque proposals into a captured geometric admissible set: reviewed pair connectivity, radial shell distance, per-node angular freedom cones, and symmetry groups. For a C3 valence group the captured azimuth pattern is preserved while the **collective polar tilt remains free**, so the molecular pair angle can genuinely relax instead of being hidden in the constraint. The projection law and stiffnesses remain explicitly **CONDITIONAL**. See `B5_ATLAS_CONSTRAINTS.md`.


## 0.8.0-alpha B4 — Bidirectional Atlas ↔ QFG feedback

B4 closes the numerical loop between the reviewed Atlas geometry and the live reduced QFG field. B3 still maps Atlas sources into scalar/vector fields; B4 now samples the evolved QFG density/spin texture back at Atlas source locations and applies **bounded translation/rotation relaxation** with anchor restoring terms, hard per-cycle clamps and optional B3 re-rasterization. All force, torque, mobility and work values remain explicitly **CONDITIONAL dimensionless proxies**, not SI-calibrated BSM-SG dynamics. See `B4_ATLAS_FEEDBACK.md`.

### 0.7.0-alpha B3 — Atlas-to-field coupling

B3 connects tagged BSM-SG/Atlas geometry to the live reduced QFG field. It rasterizes explicit Atlas sources into a scalar potential and an optional local vector/orientation field, with SOURCE/DERIVED filtering and CONDITIONAL provenance for all kernel/strength normalization choices. See `B3_ATLAS_FIELD.md`.

**Version 1.0.0-alpha — QFG Dynamics research runtime for Blender 5.2 LTS**

QFG Lab 5.2 combines the numerical, visualization, and experiment-planning prototypes developed around Q‑Field Geometry (QFG) in one Blender extension: a three-dimensional complex field, a reduced spinor/topological sector, HRM and RF tools, thermal feedback, reduced gauge/gravity fields, Yb control models, and a Molecular Creator bridge.

The extension is a **research workbench**, not a claim that a complete or experimentally validated fundamental theory has been implemented. Every module is identified as a numerical core, reduced model, proxy, or interface for a future external solver.

## Requirements

- Blender **5.2.0 LTS or a later 5.2 maintenance release**.
- Blender's bundled NumPy is enough for CPU operation.
- PyTorch is optional for Torch CPU/CUDA acceleration and is not installed automatically.

## Installation

1. Do not extract `qfg_dynamics_blender_5_2_v1.0.0-alpha.zip`.
2. In Blender, open **Edit → Preferences → Extensions**.
3. Open the menu in the upper-right corner and select **Install from Disk**.
4. Select the ZIP archive and enable **QFG Lab 5.2**.
5. In the 3D Viewport, press `N` and open the **QFG 5.2** tab.

The archive follows the Blender 5.2 extension layout: `blender_manifest.toml` and `__init__.py` are at the ZIP root.

## Safest first run

1. Select **Numerical Core → Backend: NumPy**.
2. Select **Grid: 32³**.
3. Click **Starting Scenes → Two-node collision**.
4. Click **Initialize QFG Engine**.
5. Use **Run QFG Steps** or **Bake QFG Timeline**.
6. Inspect `QFG_Field_Points`, `QFG_Density_Slice`, and the diagnostics panel.

## Included modules

### Three-dimensional field engine

- Complex scalar or reduced two-component spinor field.
- Periodic 3-D FFT grid and Strang split-step evolution.
- Gaussian nodes, Hopf-ring ansatz, vortices, and plane waves.
- Phase kicks and static potential/damping boundaries.
- `Z(rho) = 1 + alpha (rho-rho0)`, lambda cohesion, kappa stabilization, and Delta anisotropy.
- NumPy CPU and optional Torch CPU/CUDA backends.

### Topological sector

- Orientation texture `n = Psi† sigma Psi / rho`.
- Reduced Skyrme/Faddeev energy density and optional backreaction.
- Hopf/helicity and texture-gradient proxy diagnostics.
- Winding controls for ring and vortex initial conditions.

These topology values are comparative numerical diagnostics, not automatically established integer invariants without convergence and boundary studies.

### Thermal feedback

- Spectral temperature diffusion.
- Collision-heating proxy.
- Temperature-dependent cohesion.
- Temperature cap and diagnostics.

### HRM, RF, and resonator tools

- Dual-frequency HRM drive with uniform, Gaussian, standing-wave, or radial profiles.
- `(f1,f2)` scan and `modeVar` heatmap.
- FFT, sidebands, sum/difference, and candidate IMD products `2f1-f2` and `2f2-f1`.
- Phase-noise and Allan-deviation proxies.
- Nonlinear RF/Duffing/Kerr reduced-order model with forward/reverse sweeps.
- Cavity QFG-vs-thermal shift, glow-plasma envelope, dielectric-boundary, and MEMS geometry/Q proxies.

### Reduced U(1)-like gauge sector

- Dynamic vector fields `A` and `E`.
- Spectral curl/curl evolution and damping.
- Current estimated from the Q-field phase.
- Gauge-energy diagnostics and optional backreaction.

This is not a complete covariant Maxwell–QFG or SU(2) gauge solver.

### Weak-field gravity proxy

- Poisson solve sourced by local density/energy structure.
- Gravitational potential and energy proxy.
- Optional weak backreaction.

This is not a dynamical metric or Einstein-equation solver.

### Yb research module

- Rabi and Ramsey traces.
- ODMR-like detuning sweep.
- Cavity-Q sweep and two-ion phase proxy.
- Separate conventional baseline and candidate QFG corrections through `Z(rho)` and texture terms.

This is an experiment-planning model, not a complete Yb:YAG, trapped-ion, crystal-field, optical-pumping, or open-system simulation.

### Molecular Creator bridge

- Blender atoms, inferred bonds, and bond visualization.
- Transparent Coulomb, overlap/coherence, beta-gradient, gamma-kinetic, and eta-topology proxy terms.
- Property proxies for band gap, wavelength, oscillator strength, coherence, stability, and synthetic complexity.
- Target objective and derivative-free geometry optimizer.
- H2, H2O, and benzene starting systems.

This is not a self-consistent Kohn–Sham/QFG-DFT solver. The module defines a clean bridge to a future validated electronic-structure backend.

### Atlas Direct, B2/B3 and B4 feedback

- SOURCE/DERIVED nucleon and valence geometry extraction from Blender transforms.
- Interaction graph, orbital-plane and integrated-envelope diagnostics.
- Conditional Atlas scalar/vector field rasterization into the live QFG engine.
- **B4:** bounded QFG→Atlas translation/rotation feedback with anchors, safety clamps and optional B3 re-rasterization.
- Force/torque/work-proxy telemetry with explicit CONDITIONAL provenance.
- `REJECTED` assumptions are excluded from field generation and feedback.

See `ATLAS_DIRECT.md`, `B2_ATLAS_INTEGRATION.md`, `B3_ATLAS_FIELD.md`, and `B4_ATLAS_FEEDBACK.md`.

### Blender visualization and export

- Mesh vertices plus Geometry Nodes `Mesh to Points`; no obsolete `PointCloud.points.add()` call.
- Density slices, heatmap planes, and curve plots.
- Explicit timeline baking, keeping heavy FFT work out of playback handlers.
- CSV, JSON, and compressed NPZ export.

## Included scene presets

- Two-node collision
- Hopf-ring prototype
- HRM cavity prototype
- Thermal collision
- Gauge + gravity laboratory
- Plasma boundary laboratory
- Vortex laboratory

## Scientific interpretation

QFG Lab separates five levels:

1. A visual pattern produced by selected equations and initial conditions.
2. A numerically converged feature robust to timestep, grid, domain, and backend changes.
3. A quantitative prediction defined before measurement.
4. An experimental signal surviving control runs and uncertainty analysis.
5. Evidence discriminating QFG from a conventional model.

Only the final two levels can contribute to physical validation. A Blender animation alone is not evidence for a new particle, force, quantum processor, or energy mechanism.

## Deliberately incomplete in 1.0.0-alpha

The extension does not yet include:

- the complete covariant Euler–Lagrange system of the proposed action;
- self-consistent U(1) and SU(2) gauge dynamics;
- a dynamical metric or Einstein solver;
- calibrated SI mapping of all parameters;
- a converged minimum-energy Hopfion solver;
- quantized charge, mass, or spin extraction;
- a real QFG-DFT/Kohn–Sham SCF implementation;
- Bayesian molecular graph generation;
- direct NI-DAQ, FPGA, laser, RF-generator, or photodiode control;
- convex-hull/triangle-mesh collision, joints, CCD, broad-phase acceleration, sleeping islands, deformables, and engineering-grade contact calibration.

These remain explicit module boundaries rather than being represented by decorative code.

## License

The Blender extension is licensed under **GNU GPL v3.0 or later**. See `LICENSE`.



## New in 0.4.1 Alpha: playback safety and 6-DoF debug overlay

- Explicit out-of-range baked playback modes: **Hold nearest baked frame**, **Clamp timeline**, or **Status only**.
- The status line now distinguishes the requested Blender frame from the cached frame actually displayed.
- Cached frames now preserve world telemetry, including linear/angular momentum and active contact counts.
- Viewport contact debug: contact points, normals, and impulse vectors.
- Optional total-force, total-torque, and angular-velocity vectors for dynamic bodies.
- Lightweight 2-D 6-DoF HUD with body/floor contacts, kinetic-energy split, momentum, angular momentum, force, and torque metrics.
- Debug visualization is display-only; frame handlers never advance the numerical solver.

## New in 0.4.0 Alpha: 6-DoF QFG Dynamics

The `QFGWorld` body layer now tracks quaternion orientation and angular velocity, derives inertia from Sphere/Box shapes, applies impulses at contact points, and exports force **and torque** channels. Dynamic bodies can use spheres or oriented boxes; OBB contacts use SAT and the native Collision showcase now creates box-shaped shards with physical spin. Deterministic hashes include rotational state. See `DYNAMICS_SDK.md`.

## 0.5.0-alpha: Atlas Direct

The **Atlas Direct / BSM-SG Geometry** panel adds an auditable source-geometry path for BSM-SG/ANS Blender models. Tag source objects as core, free valence, bound or equatorial structures, choose how each valence direction is represented, and extract world-space pair angles directly from Blender transforms.

Atlas Direct is intentionally separated from the Molecular Creator energy proxy. Its blind holdout workflow is **Extract → Freeze → Reveal**, with explicit provenance labels (`SOURCE`, `DERIVED`, `CONDITIONAL`, `CALIBRATED`, `EXPERIMENTAL`, `REJECTED`). See `ATLAS_DIRECT.md`.
