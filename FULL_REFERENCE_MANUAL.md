**QFG DYNAMICS 1.0.0-alpha**

**Full Reference Manual for Blender 5.2**

Unified QFG field, dynamics and structural simulation

<img src="/mnt/data/qfg_docs_bundle/docs/assets/media/image1.jpg" style="width:7in;height:0.98437in" />

QFG Lab 5.2 research workbench \| BSM-SG / Atlas Direct B1-B6 \| Dynamics \| Topology \| RF / HRM \| Yb \| Molecular proxy tools

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>SCIENTIFIC STATUS</strong></p>
<p>QFG Dynamics 1.0.0-alpha is a research workbench. It includes numerical solvers, reduced models, proxy metrics and conditional bridges. Numerical stability, convergence and attractive visualization are useful engineering evidence, but they are not by themselves experimental validation or proof of a first-principles physical theory.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

Manual revision: 15 October 2026

# About this manual

This manual is the full English reference for the QFG Dynamics 1.0.0-alpha Blender 5.2 extension. It expands the quick-start guide into a section-by-section description of the user interface, numerical workflow, object-level actor system, Atlas Direct / BSM-SG pipeline, research modules, reproducibility controls, export path and practical scene-building workflows.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>VERSION SCOPE</strong></p>
<p>The manual targets qfg_dynamics_blender_5_2_v1.0.0-alpha.zip and Blender 5.2 LTS. The extension is alpha software: labels, defaults and operator locations may change in later builds. When behavior differs, treat the installed UI and exported session metadata as authoritative for that build.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## Documentation conventions

| **Term**     | **Meaning**                                                                  |
|--------------|------------------------------------------------------------------------------|
| SOURCE       | Reviewed source geometry or source metadata used directly by the protocol.   |
| DERIVED      | Deterministic calculation from SOURCE inputs without a new fitted parameter. |
| CONDITIONAL  | A model bridge, proxy or hypothesis not fixed by source geometry alone.      |
| CALIBRATED   | A parameter fixed using reference or measurement data.                       |
| EXPERIMENTAL | An external measured/reference value reserved for comparison.                |
| REJECTED     | Retained for audit/history but excluded from prediction-driving input.       |

UI names are shown in bold in the prose. Paths use arrows, for example: 3D Viewport -\> Sidebar (N) -\> QFG 5.2. Numerical quantities such as Atlas scalar energy, work proxy and topology proxy are named exactly as the plugin presents them; do not reinterpret them as SI quantities unless a separate calibration is explicitly documented.

## Contents

- 1\. Purpose and architecture

- 2\. Requirements, installation and extension package

- 3\. Interface map

- 4\. Safest first test and core workflow

- 5\. Main QFG Dynamics panel

- 6\. Starting Scenes and Native Hero Showcase

- 7\. Numerical Core

- 8\. Dynamics Runtime - 6-DoF field-coupled bodies

- 9\. Field and Topology

- 10\. Thermal and HRM

- 11\. Gauge, Gravity and Noise

- 12\. Visualization and Timeline

- 13\. 6-DoF Debug Overlay

- 14\. Diagnostics and Export

- 15\. RF / HRM / Plasma ROM

- 16\. Cavity and MEMS

- 17\. Yb Quantum-Control Suite

- 18\. Atlas Direct / BSM-SG B1 - source geometry

- 19\. Atlas provenance and audit semantics

- 20\. B2 - interaction graph, orbital planes and Bohr envelope

- 21\. B3 - Atlas to QFG field bridge

- 22\. B4 - QFG to Atlas feedback

- 23\. B5 - topology and angular constraints

- 24\. B6 - blind relaxation and holdout workflow

- 25\. Atlas export and audit trail

- 26\. Molecular Creator

- 27\. QFG Actor 5.2 - object-level reference

- 28\. Practical scene recipes

- 29\. Cinematic and presentation workflow

- 30\. Reproducibility, convergence and numerical controls

- 31\. Troubleshooting

- 32\. Scientific interpretation and limits

- Appendix A. SDK and scripting

- Appendix B. Blender extension package and manifest

- Appendix C. Quick reference

- Glossary

# 1. Purpose and architecture

QFG Lab 5.2 turns Blender into an interactive research workbench in which scene geometry, a numerical QFG field, reduced rigid-body dynamics, topology diagnostics, RF/HRM tools, thermal/gauge/gravity proxies, Yb control models, molecular proxy functions and BSM-SG / Atlas geometry can be explored from one interface.

The core design idea is a bidirectional workflow. Blender objects can define sources for a numerical field; the field is evolved by the numerical engine; diagnostics and visualizations are returned to Blender; and, in the Atlas pipeline, a bounded conditional feedback layer can move or rotate source geometry while preserving a reviewed admissible structure.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th>Blender geometry -&gt; QFG numerical state -&gt; diagnostics / visualization<br />
-&gt; Dynamics Runtime<br />
-&gt; Atlas B3 field bridge -&gt; B4 feedback -&gt; B5 constraints -&gt; B6 orchestration</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## What the extension is good at

- Fast controlled experiments inside a familiar 3D environment.

- Repeatable parameter sweeps and scene presets.

- Field visualization and timeline baking.

- Reduced 6-DoF body motion coupled to field, temperature and contacts.

- Traceable Atlas geometry workflows with explicit provenance.

- Creating presentation-ready scientific visualizations and cinematic demonstrations without separating simulation and scene authoring into different applications.

## What it is not

- It is not an SI-calibrated general first-principles solver.

- The reduced gauge and gravity sectors are not a replacement for full Maxwell or Einstein field solvers.

- The Molecular Creator is not Kohn-Sham DFT or an ab initio quantum-chemistry package.

- The plasma module is not a PIC or full kinetic plasma solver.

- B3/B4/B5 are explicitly conditional bridges; B6 makes the experiment reproducible and blind but does not upgrade a conditional force law into a proven fundamental law.

# 2. Requirements, installation and extension package

## 2.1 Requirements

| **Requirement**       | **Recommendation**                                                                                 |
|-----------------------|----------------------------------------------------------------------------------------------------|
| Blender               | Blender 5.2.0 LTS or a later 5.2-series build.                                                     |
| CPU backend           | NumPy included with Blender is sufficient for initial work.                                        |
| Optional acceleration | PyTorch CPU/CUDA can be used when available; the extension does not install PyTorch automatically. |
| Memory                | For grids of 64^3 and above, plan for substantial RAM/VRAM.                                        |
| First-run profile     | NumPy CPU, Scalar prototype, 32^3 grid, dt = 0.002.                                                |

## 2.2 Installation

**1.** Do not unpack the extension ZIP.

**2.** Open Edit -\> Preferences -\> Extensions.

**3.** Open the menu in the upper-right corner and choose Install from Disk.

**4.** Select qfg_dynamics_blender_5_2_v1.0.0-alpha.zip.

**5.** Enable QFG Lab 5.2 / QFG Dynamics 1.0.0 Alpha.

**6.** Return to the 3D Viewport, press N and open the QFG 5.2 tab.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>IF THE EXTENSION DOES NOT APPEAR</strong></p>
<p>Verify Blender 5.2, confirm that the correct ZIP was installed, and check that the extension contains blender_manifest.toml and __init__.py in the package structure. Also remove or disable older builds using the same package ID before reinstalling.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## 2.3 Recommended repository/package layout

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th>qfg_lab_52/<br />
blender_manifest.toml<br />
__init__.py<br />
sdk.py / sdk/<br />
numerical modules...<br />
UI / operators...<br />
README.md<br />
LICENSE<br />
docs/<br />
QFG_Dynamics_1.0.0-alpha_Quick_Start_and_Showcase_EN.pdf<br />
QFG_Dynamics_1.0.0-alpha_Full_Reference_Manual_EN.pdf</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

A compact README and quick-start PDF are appropriate inside the extension ZIP. The full manual is also ideal for the Git repository, where it can evolve independently of every binary extension update.

# 3. Interface map

UI path: 3D Viewport -\> Sidebar (N) -\> QFG 5.2

| **Panel**                      | **Primary role**                                                                    |
|--------------------------------|-------------------------------------------------------------------------------------|
| QFG Dynamics 1.0.0 Alpha       | Initialize, run steps, reset, clear results, validation suite.                      |
| Starting Scenes                | Presets and Native Hero Showcase.                                                   |
| Numerical Core                 | Backend, field mode, grid, domain, dt and step counts.                              |
| Dynamics Runtime               | 6-DoF dynamic bodies, contacts, field/thermal force and torque.                     |
| Field and Topology             | QFG order-parameter settings, topology sector and orientation diagnostics.          |
| Thermal and HRM                | Temperature diffusion, collision heating and dual-frequency drive.                  |
| Gauge, Gravity and Noise       | Reduced U(1), weak-field gravity proxy and robustness noise.                        |
| Visualization and Timeline     | Point cloud, density slice, bake/cache and playback.                                |
| 6-DoF Debug Overlay            | HUD, contacts and force/torque/angular vectors.                                     |
| Diagnostics and Export         | Numerical metrics, profiler and session export.                                     |
| RF / HRM / Plasma              | Nonlinear resonator, frequency scans and plasma boundary proxy.                     |
| Cavity and MEMS                | Cavity shift and geometry/Q proxy.                                                  |
| Yb Quantum-Control Suite       | Rabi, Ramsey, ODMR, Q sweep and two-ion phase proxy.                                |
| Atlas Direct / BSM-SG Geometry | B1-B6 geometry, graph, field bridge, feedback, constraints and blind orchestration. |
| Molecular Creator              | Starter molecules, inferred bonds, transparent energy proxies and optimizer.        |

UI path: Properties -\> Object -\> QFG Actor 5.2

Object Properties holds all settings that belong to one Blender object: actor type, source geometry, dynamic-body mass and collision shape, Atlas nucleon identity, per-object field strengths, feedback mobility and constraint metadata.

# 4. Safest first test and core workflow

## 4.1 Installation sanity test

**1.** Numerical Core -\> Backend = NumPy CPU.

**2.** Field = Scalar prototype.

**3.** Grid = 32^3 Standard, Domain length = 16, dt = 0.002.

**4.** Starting Scenes -\> Two-node collision.

**5.** Click Initialize QFG Engine.

**6.** Click Run QFG Steps several times.

**7.** Visualization and Timeline -\> Update Visualization.

**8.** Inspect QFG_Field_Points, QFG_Density_Slice and Diagnostics and Export.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>PASS CRITERIA</strong></p>
<p>The engine initializes without exceptions; numerical time advances; field diagnostics remain finite; visualization objects update; and session controls respond. Only after this baseline works should you enable heavier topology, dynamics feedback, B3/B4/B5 or larger grids.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## 4.2 General working pattern

| Configure -\> Initialize -\> Run / Bake -\> Inspect -\> Export -\> Change one variable -\> Repeat |
|---------------------------------------------------------------------------------------------------|

For debugging and science alike, change one subsystem at a time. If you simultaneously increase grid size, alter lambda/kappa, enable topology, add body collisions and change the field bridge, you lose the ability to identify which change caused an observed effect.

# 5. Main panel - QFG Dynamics 1.0.0 Alpha

| **Command**           | **What it does**                                                           | **When to use it**                                                                    |
|-----------------------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Initialize QFG Engine | Creates or rebuilds the numerical runtime from current scene and settings. | After changing core parameters, preset, source geometry or Atlas field configuration. |
| Run QFG Steps         | Executes Steps per action numerical steps.                                 | Interactive inspection and controlled manual evolution.                               |
| Reset                 | Returns the runtime to the configured initial state.                       | Repeat the same protocol without rebuilding the Blender scene.                        |
| Clear Results         | Removes generated result/visualization artifacts.                          | Before a clean new experiment or export.                                              |
| Run Validation Suite  | Runs built-in sanity checks for the numerical configuration.               | Before important experiment series or after a major configuration change.             |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>ATLAS NOTE</strong></p>
<p>When B3 Apply on engine initialize is enabled, Initialize/Reset can automatically rebuild the Atlas-derived field. This is convenient but can hide a geometry change if you are not expecting re-rasterization. Check B3 diagnostics whenever the source geometry changes.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 6. Starting Scenes and Native Hero Showcase

## 6.1 Native Hero Showcase

The Native Hero Showcase builds presentation-ready scenes that combine numerical content with lighting, camera framing and useful defaults. Use Preview quality while iterating. Final quality increases numerical and rendering load. Depending on the selected showcase, Build creates the scene, Build + Bake additionally computes a timeline, and Render Still renders a selected hero frame.

| **Preset**          | **What it demonstrates**                                 | **Good first question**                                         |
|---------------------|----------------------------------------------------------|-----------------------------------------------------------------|
| Two-node collision  | Two field nodes, interaction and baseline visualization. | Does my installation and field core work?                       |
| Hopf-ring prototype | Reduced spinor/topology ansatz and Hopf proxy.           | Can I see topology-sensitive structure and diagnostics?         |
| Vortex prototype    | Phase winding and spinor texture.                        | How does a winding source evolve?                               |
| HRM cavity          | Dual-frequency HRM drive.                                | How do two drive frequencies affect response?                   |
| Thermal collision   | Collision heating and thermal feedback.                  | How do contacts change temperature and dynamics?                |
| Gauge + gravity     | Reduced gauge and weak-field gravity sectors.            | What changes when conditional backreaction sectors are enabled? |
| Plasma boundary     | Driven boundary / glow-plasma proxy.                     | How does the reduced envelope respond to a driven boundary?     |

## 6.2 Preview versus final

- Use 32^3 and modest visualization point counts for preview.

- Use 48^3/64^3 or a justified higher grid for confirmation, not merely because it looks smoother.

- Bake before final animation playback; avoid recomputing heavy FFT evolution on every frame change.

- Keep debug overlays out of final beauty renders unless the purpose is an engineering explainer.

# 7. Numerical Core

| **Control**      | **Meaning**                                                 | **Starting recommendation**                                                                   |
|------------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Backend          | Auto, NumPy CPU, PyTorch CPU or PyTorch CUDA.               | NumPy CPU for first validation; CUDA for expensive runs after baseline parity is established. |
| Field            | Scalar prototype or reduced two-component Spinor prototype. | Scalar unless orientation/spin/topology is specifically required.                             |
| Grid             | Typical range 24^3 to 128^3.                                | 32^3 preview; 48^3/64^3 convergence check.                                                    |
| Domain length    | Size of the periodic numerical box.                         | 16.0 default.                                                                                 |
| dt               | Numerical time step.                                        | 0.002 default; reduce when unstable.                                                          |
| Steps per action | Steps executed by Run QFG Steps.                            | 10 for interactive work.                                                                      |
| Steps per frame  | Numerical steps per baked Blender frame.                    | 5 as a practical starting value.                                                              |

## 7.1 Grid and domain

Grid resolution and domain length jointly determine spatial sampling. A larger grid at fixed domain reduces cell spacing; a larger domain at fixed grid makes each cell coarser. Do not discuss grid convergence using grid number alone - record both grid and domain length.

## 7.2 Time step

dt is a numerical control, not a visual speed slider. If a result changes dramatically when dt is halved, the original run has not demonstrated time-step convergence. For important runs, repeat at dt/2 and compare qualitative structure plus core diagnostics.

## 7.3 Backend parity

NumPy and Torch backends may have small floating-point differences. A robust qualitative result should survive backend changes within reasonable tolerance. Establish a NumPy reference before interpreting a CUDA-only result.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>CONVERGENCE RULE</strong></p>
<p>A physically interesting claim should not depend dramatically on grid, dt or backend. Repeat important runs with smaller dt and a higher grid before interpretation.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 8. Dynamics Runtime - 6-DoF field-coupled bodies

Dynamics Runtime is separate from Atlas B4. It integrates general QFG DYNAMIC_BODY objects with translation, rotation, contacts and coupling to field and temperature sectors.

| **Control**                            | **Purpose**                                                                           |
|----------------------------------------|---------------------------------------------------------------------------------------|
| Dynamics substeps                      | Internal rigid-body updates per QFG step; increase for stiff contacts or fast motion. |
| Deterministic replay / World seed      | Makes ordering and stochastic components repeatable.                                  |
| World gravity / Floor height           | Global acceleration and reduced collision floor.                                      |
| Body collisions                        | Enables reduced body-body contacts.                                                   |
| Maximum body / angular speed           | Safety clamps against runaway dynamics.                                               |
| Global field force                     | Global multiplier for field-driven translation.                                       |
| Global thermal force                   | Global multiplier for temperature-gradient coupling.                                  |
| Field torque                           | Global multiplier for field-driven rotation.                                          |
| Event thresholds                       | Thresholds for field/contact/phase events.                                            |
| Penetration slop / Position correction | Reduced collision stabilization controls.                                             |

## 8.1 Body forces and torques

A dynamic body can combine initial velocity, gravity, drag, contact response, field coupling, thermal coupling and external torque. Use the per-body controls in QFG Actor 5.2 together with global multipliers in Dynamics Runtime. When behavior is surprising, first separate each force contribution rather than compensating with arbitrary damping.

## 8.2 Contacts

Collision primitives are reduced sphere or oriented-box representations, not arbitrary deformable contact meshes. Restitution controls bounce; friction controls tangential resistance; penetration correction stabilizes overlap. Increase substeps before using extreme correction gains.

## 8.3 Runtime profiler and telemetry

The runtime profiler reports body count, contacts, events and timing for field/query/body/total work. 6-DoF telemetry provides kinetic-energy proxy, average/max force and torque, momentum and angular momentum. These are essential for distinguishing a visual artifact from a numerical runaway.

# 9. Field and Topology

| **Parameter**            | **Role / interpretation**                                           |
|--------------------------|---------------------------------------------------------------------|
| Vacuum density rho0      | Reference density of the reduced QFG order parameter.               |
| lambda cohesion          | Cohesive term in the reduced model.                                 |
| kappa stability          | Stabilizing term; default around 0.0019 in this build.              |
| alpha in Z(rho)          | Density-dependent dielectric/response proxy.                        |
| zeta_EM                  | EM-like coupling proxy.                                             |
| Damping                  | Global numerical damping.                                           |
| Delta anisotropy         | Anisotropic reduced term.                                           |
| Topology / Skyrme sector | Enables orientation field and reduced topological diagnostics.      |
| Spin exchange            | Reduced orientation/spin coupling.                                  |
| Skyrme backreaction      | Feeds topological proxy contribution back into effective potential. |
| External B proxy         | External orientation vector / proxy field.                          |

## 9.1 Scalar versus spinor mode

Scalar mode is the simplest and safest field representation. Spinor mode introduces an orientation field and enables topology-sensitive diagnostics. Use spinor mode because the research question requires orientation/topology - not because it looks more complex.

## 9.2 Topology diagnostics

Compute Topology calculates Hopf proxy, Skyrme proxy and orientation variance. These are comparative numerical metrics. A finite Hopf proxy in a finite periodic grid is not automatically a rigorously proven topological invariant; convergence and boundary analysis remain necessary.

## 9.3 Interpreting lambda and kappa

Treat lambda and kappa as model parameters within the reduced QFG formulation. Explore them systematically: establish a baseline, vary one parameter, record diagnostics and repeat. Avoid tuning multiple terms simultaneously to match a desired image.

# 10. Thermal and HRM

## 10.1 Thermal module

| **Control**          | **Meaning**                                             |
|----------------------|---------------------------------------------------------|
| Heat conduction      | Diffusion / equalization rate of the temperature field. |
| Collision heating    | How strongly contacts add a thermal proxy contribution. |
| Critical temperature | Reference threshold for temperature-dependent effects.  |
| Temperature cap      | Numerical safety limit against runaway temperature.     |

Thermal coupling can affect both the field evolution and QFG dynamic bodies. Keep thermal terms disabled for a clean mechanical baseline, then enable them in a controlled A/B comparison.

## 10.2 HRM dual drive

HRM adds two drives A1 and A2 with frequencies f1 and f2. The spatial drive profile can be Uniform, Gaussian, Standing X or Radial ring; width/radius parameters control the driven region. HRM is useful for response maps and comparative resonance studies, not as an automatically validated microscopic Hamiltonian.

# 11. Gauge, Gravity and Noise

| **Sector**         | **Controls**                                         | **Interpretation**                                              |
|--------------------|------------------------------------------------------|-----------------------------------------------------------------|
| Reduced U(1)       | Gauge coupling q, damping, wave speed, backreaction. | Reduced A/E field sector; not a complete Maxwell/QFG solver.    |
| Weak-field gravity | Effective G and backreaction.                        | Poisson-like gravity proxy; not an Einstein metric solver.      |
| Noise robustness   | Noise amplitude and seed.                            | Tests whether an observed pattern survives small perturbations. |

## 11.1 Why noise matters

A visually striking structure that disappears under tiny seeded perturbations is not robust. Use controlled noise sweeps to distinguish persistent behavior from an over-sensitive initial condition.

## 11.2 Backreaction discipline

Enable backreaction only after confirming the corresponding sector without backreaction. This keeps the causal chain interpretable and helps identify when a coupled system becomes numerically stiff.

# 12. Visualization and Timeline

| **Control**          | **What it does**                                          |
|----------------------|-----------------------------------------------------------|
| Density threshold    | Minimum relative density shown in point visualization.    |
| Maximum points       | Caps visualization point count for performance.           |
| Point radius         | Visual point size only.                                   |
| Slice axis           | Chooses X/Y/Z central density slice.                      |
| Update Visualization | Rebuilds point cloud/slice from current numerical state.  |
| Bake start / end     | Timeline range for precomputation.                        |
| Bake QFG Timeline    | Runs solver work and caches results for Blender playback. |
| Clear cache          | Deletes baked timeline cache.                             |
| Outside baked range  | Hold nearest baked frame, Clamp timeline or Status only.  |

## 12.1 Visualization is not the field itself

Threshold, point radius and maximum-point limits change what you see, not the underlying numerical state. When comparing runs, separate visualization changes from model changes.

## 12.2 Why bake

For animation and presentation, bake the timeline. Heavy 3D FFT work should not run from an ordinary frame-change playback handler if you need deterministic, responsive scrubbing. Bake once, then inspect or render cached states.

# 13. 6-DoF Debug Overlay

The debug overlay is an engineering instrument rather than a final-render effect. It can show a HUD, contacts, force vectors, torque vectors and angular velocity. Vector scales are display multipliers only and do not change the solver.

| **Overlay item**                | **Use it to diagnose**                                                     |
|---------------------------------|----------------------------------------------------------------------------|
| HUD                             | Runtime state, body counts, contact/event counts and selected diagnostics. |
| Contact points/normals          | Whether collision geometry is being interpreted correctly.                 |
| Force vectors                   | Unexpected translation or sign errors in coupling.                         |
| Torque vectors                  | Unexpected rotation or orientation coupling.                               |
| Angular velocity                | Runaway spin and damping behavior.                                         |
| Momentum P / angular momentum L | Global sanity checks and drift.                                            |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>DEBUG ORDER</strong></p>
<p>If dynamics becomes unstable, inspect force/torque magnitude, contact count and speed clamps before changing many parameters. A runaway caused by a single extreme force should not be “fixed” by hiding it behind heavy damping.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 14. Diagnostics and Export

| **Metric**                | **Meaning**                                                               |
|---------------------------|---------------------------------------------------------------------------|
| t                         | Current numerical time.                                                   |
| Max density / Norm        | Peak density and field norm.                                              |
| modeVar                   | Mode-variance proxy used in response comparisons.                         |
| Energy proxy              | Reduced QFG energy metric.                                                |
| Max T                     | Maximum temperature.                                                      |
| Gauge E / Gravity E       | Energy proxies for reduced gauge/gravity sectors.                         |
| Atlas scalar E            | B3 scalar proxy integral of density times Atlas potential; not SI energy. |
| Field P / Body P / Body L | Momentum diagnostics for field and dynamic bodies.                        |
| Profiler timings          | Field/query/body/total runtime costs.                                     |

## 14.1 Export Session

Output directory selects the export destination. Export Session writes configuration and available numerical results in formats such as JSON, CSV and NPZ depending on the module. Keep the session export with the .blend file and a short note describing the question being tested.

## 14.2 Audit discipline

- Record plugin version, Blender version, backend, grid, domain and dt.

- Record all enabled conditional sectors.

- Keep the random/world seed for deterministic runs.

- Do not report proxy quantities with SI units unless a separate calibration establishes the conversion.

# 15. RF / HRM / Plasma ROM

## 15.1 Nonlinear RF resonator

The reduced-order resonator supports detuning sweeps, drive amplitude, linear/nonlinear loss, Duffing/Kerr-like nonlinearity, external coupling and second-tone ratio. Run ROM generates frequency/response data for comparative analysis. It is a reduced model intended for exploration and trend studies.

## 15.2 HRM scan

**1.** Set f1 min/max and f2 min/max.

**2.** Choose the number of points, duration, dt and reduced 1D/scan resolution nx.

**3.** Select the response metric.

**4.** Run HRM Scan.

**5.** Inspect the strongest response/modeVar combinations and repeat around promising regions at higher resolution.

## 15.3 Glow-plasma boundary proxy

Boundary factor, ionization and recombination describe a reduced glow-plasma envelope. Run Plasma evaluates the proxy model. Do not present it as a full particle-in-cell or kinetic plasma calculation.

# 16. Cavity and MEMS

| **Tool**              | **Key controls**                                                 | **Purpose**                                                   |
|-----------------------|------------------------------------------------------------------|---------------------------------------------------------------|
| Cavity shift          | Q factor, maximum power, density per power, thermal coefficient. | Compare a QFG-like density shift with a thermal contribution. |
| MEMS geometry/Q proxy | Base Q and geometry scale.                                       | Quick trend proxy for geometry versus Q.                      |

These tools are most useful for parameter exploration and hypothesis generation. Export the sweep data rather than relying on a single plotted peak.

# 17. Yb Quantum-Control Suite

The Yb suite provides research-planning and comparative control tools: Rabi and Ramsey traces, ODMR-like detuning sweep, cavity-Q sweep and a two-ion phase proxy.

| **Control family**    | **Examples**                                       |
|-----------------------|----------------------------------------------------|
| Time/control          | Duration, dt, Rabi frequency, detuning.            |
| Decoherence           | Dephasing, relaxation.                             |
| Cavity                | Q factor, cavity power, density offset.            |
| QFG-related           | QFG correction scale, texture coupling/divergence. |
| Spectroscopic/control | AC Stark scale, Ramsey free time.                  |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>SCOPE</strong></p>
<p>The Yb module is not a complete crystal-field Hamiltonian or open-system master-equation solver. Use it to organize reduced comparisons, sweeps and control hypotheses.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 18. Atlas Direct / BSM-SG B1 - source geometry

Atlas Direct is the most specialized pipeline in the extension. Its purpose is to keep source geometry, deterministic derived quantities, conditional QFG bridges and experimental holdout data separate so that every stage can be reproduced and audited.

## 18.1 Element and nuclear center

| **Control**    | **Options / guidance**                                                                           |
|----------------|--------------------------------------------------------------------------------------------------|
| Atlas element  | N, P, As, Sb in the Group-15 holdout workflow.                                                   |
| Nuclear center | Tagged core centroid (recommended), Center object or World origin.                               |
| Nucleon type   | Proton, Neutron, Deuteron, Tritium, Helium, Other.                                               |
| Direction rule | Per-object local axis or reviewed valence direction; do not infer angles from camera projection. |

## 18.2 Tagging objects

Select one or more Blender objects and use Tag Core, Tag Valence, Tag Bound or Tag Equatorial. Auto-detect Selected uses name heuristics and marks the result as DERIVED; SOURCE tags should be manually reviewed.

| **Atlas role** | **Typical meaning**                                                                  |
|----------------|--------------------------------------------------------------------------------------|
| CORE           | Participates in the reviewed central/source structure.                               |
| VALENCE        | Free or semi-free structural arm used in geometry extraction and Group-15 workflows. |
| BOUND          | Tagged supporting/bound structure.                                                   |
| EQUATORIAL     | Reference/support role used by source-star topology and related constructions.       |

## 18.3 Extract Atlas Geometry

Extract Atlas Geometry computes pair angles between VALENCE vectors, mean angle, standard deviation, min/max and the C3v h/r proxy. Vector display scale affects only drawing. Always compute angles from 3D vectors, not screenshots.

# 19. Atlas provenance and audit semantics

| **Status**   | **Meaning / allowed use**                                              |
|--------------|------------------------------------------------------------------------|
| SOURCE       | Explicitly reviewed BSM-SG/ANS source geometry or source metadata.     |
| DERIVED      | Deterministic calculation from SOURCE inputs; no new fitted parameter. |
| CONDITIONAL  | Model bridge or hypothesis not fixed by source geometry alone.         |
| CALIBRATED   | Reference/measurement used to fix a parameter.                         |
| EXPERIMENTAL | External measured/reference value.                                     |
| REJECTED     | Retained only for audit/history and must not drive prediction.         |

## 19.1 Why provenance is part of the solver protocol

Without provenance, a user can accidentally feed a fitted or experimental quantity back into a stage described as predictive. The Atlas pipeline therefore treats provenance not as a note-taking convenience but as part of protocol control.

## 19.2 Recommended source note

For each important Atlas object, use the source note to record origin, transformation, review decision and any external file/figure identifier. This makes later re-tagging and review much easier.

# 20. B2 - interaction graph, orbital planes and Bohr envelope

## 20.1 Interaction graph Jij

| **Topology**  | **Use**                                                                               |
|---------------|---------------------------------------------------------------------------------------|
| Source star   | VALENCE \<-\> EQUATORIAL edges; preferred minimal topology for current Group-15 work. |
| Valence pairs | Diagnostic graph only among VALENCE nodes.                                            |
| All tagged    | Diagnostic complete graph among all tagged objects.                                   |

| **J proxy kernel**         | **Status / interpretation**                                                                 |
|----------------------------|---------------------------------------------------------------------------------------------|
| Topology only              | Unit edges; DERIVED topology diagnostic.                                                    |
| \|cos chi\| / cos^2 chi    | Orientation-overlap proxies; CONDITIONAL.                                                   |
| 1/r^3 / cos^2 chi \* 1/r^3 | Scene-unit dependent geometry proxies; CONDITIONAL; softening protects against singularity. |

## 20.2 Orbital planes

An orbital-plane normal is defined per object from +/-Local X/Y/Z. Valence-vector mode is a convenience bridge and is CONDITIONAL. The analyzer computes axial dihedral angles while treating n and -n as the same plane. This is a geometric orientation tool; it is not a solved electron orbital.

## 20.3 Integrated Bohr envelope

Radius mode can use Object bounds, Fixed radius or Centers only. Padding expands the envelope. The result is an oriented ellipsoidal geometric proxy for visualization and overlap bookkeeping, not a solved physical Bohr surface.

## 20.4 Graph validation checklist

- Confirm site count and roles before building the graph.

- Inspect unexpected isolated nodes and high-degree nodes.

- Check softening before using inverse-power kernels.

- Record topology choice and J kernel in the exported report.

# 21. B3 - Atlas to QFG field bridge

B3 rasterizes tagged Atlas objects into a scalar potential and optionally a vector/director field. Even when the input geometry is SOURCE, the bridge itself is CONDITIONAL.

| **Control**                 | **Guidance**                                                                              |
|-----------------------------|-------------------------------------------------------------------------------------------|
| Atlas field bridge          | Master enable; default OFF.                                                               |
| Apply on engine initialize  | Automatically builds field during Initialize/Reset; default ON.                           |
| Refresh before manual steps | Re-rasterizes before Run Steps; useful when sources are moved manually.                   |
| Field source scope          | SOURCE only (safest), SOURCE + DERIVED, or All non-rejected.                              |
| Field roles                 | Valence + equatorial, Valence only, or All Atlas roles.                                   |
| Kernel                      | Gaussian recommended finite numerical source; Soft 1/r^3 is a conditional geometry proxy. |
| Atlas -\> QFG length scale  | Maps Blender units into the numerical box.                                                |
| Scalar potential scale      | Global scalar field strength; default around 0.25.                                        |
| Vector/spin scale           | Default 0.0; enable only when an orientation bridge is required.                          |
| Vector field                | Director or Dipole proxy.                                                                 |
| Orbital-normal mix          | Blend between valence director and orbital normal.                                        |
| Field safety clip           | Limits runaway potential values.                                                          |

## 21.1 Apply and clear

Apply Atlas Field builds/rasterizes the field; Clear Atlas Field removes it. Diagnostics show source count, V min/max/RMS and \|B\| max/RMS. A zero field usually indicates disabled bridge, wrong source scope/roles, per-object source disabled or zero scales.

## 21.2 Safe first B3 run

**1.** Use SOURCE only.

**2.** Use Gaussian kernel.

**3.** Keep vector/spin scale at 0 unless specifically required.

**4.** Use a modest scalar scale.

**5.** Apply Atlas Field and inspect diagnostics before enabling any B4 feedback.

# 22. B4 - QFG to Atlas feedback

B4 closes the conditional loop: QFG density/spin texture is sampled at Atlas source positions and converted into bounded translation/rotation updates. It is not an SI-calibrated force law.

| **Control**                   | **Meaning**                                                      |
|-------------------------------|------------------------------------------------------------------|
| B4 bidirectional feedback     | Master enable; default OFF.                                      |
| Auto-capture anchors          | Captures reviewed source transforms on first use.                |
| Rebuild B3 after feedback     | Re-rasterizes field after geometry moves.                        |
| Torque target                 | Density gradient, Spin texture or Hybrid.                        |
| Hybrid spin mix               | Blend in Hybrid target.                                          |
| B4 force / torque scale       | Global conditional feedback gains.                               |
| Position / Orientation anchor | Restoring terms toward captured geometry.                        |
| Torque orbital mix            | Blend between director and orbital-normal torque source.         |
| Max translation / cycle       | Safety clamp; default about 0.02 scene units.                    |
| Max rotation / cycle          | Safety clamp; default about 1 degree.                            |
| Max anchor displacement       | Hard displacement limit from captured anchor; default about 0.5. |

## 22.1 Operational sequence

**1.** Review SOURCE geometry.

**2.** Capture Anchors.

**3.** Apply Feedback Once.

**4.** Inspect displacement, rotation, work proxy and clipping.

**5.** Only then run multiple feedback cycles or B6 orchestration.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>WORK PROXY</strong></p>
<p>B4 force/torque/total work proxy is a dimensionless audit quantity. Do not label it joules or a calibrated physical work without an independent mapping.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 23. B5 - topology and angular constraints

B5 projects the movement proposed by B4 back into an admissible geometric set. Its role is to prevent the feedback bridge from destroying reviewed source topology while leaving explicitly allowed collective degrees of freedom free.

| **Control**               | **Meaning**                                                                        |
|---------------------------|------------------------------------------------------------------------------------|
| Geometry constraints      | Master B5 enable; default OFF.                                                     |
| Auto-capture              | Automatically captures the constraint snapshot.                                    |
| Connectivity capture      | Manual neighbours, Parent-child, B2 Source star or No pair distances.              |
| Pair-distance stiffness   | Strength of restoring captured pair distances.                                     |
| Shell stiffness           | Preserves radial shell distance.                                                   |
| Angular-cone stiffness    | Applies per-object angular freedom cone.                                           |
| Symmetry stiffness        | Restores equivalence within a symmetry group without fixing collective polar tilt. |
| Shell tolerance           | Allowed radial error.                                                              |
| Projection iterations     | Bounded projection iterations; default around 8.                                   |
| Convergence tolerance     | Numerical stop tolerance for projection.                                           |
| Max B5 correction / iter  | Safety clamp; default around 0.025.                                                |
| Preserve movable centroid | Optionally preserves centroid of movable nodes.                                    |

## 23.1 C3 / Group-15 use

Assign the same B5 symmetry group, for example C3_valence, to the three free VALENCE objects. B5 preserves the 120-degree azimuth pattern and arm equivalence while leaving collective polar tilt free. Therefore the H-X-H-like pair angle can relax and is not secretly fixed by the symmetry constraint.

## 23.2 Signs of over-constraint

- Large B5 corrections every iteration.

- B4 repeatedly pushes against the same hard boundary.

- Angle freezes immediately at a value already encoded by the constraint.

- Small tolerance changes cause discontinuous geometry jumps.

# 24. B6 - blind relaxation and holdout workflow

B6 is an orchestration layer for blind experiments. It does not introduce a new force law. Its key function is to freeze the protocol, iterate B3/B4/B5 in a controlled order, detect convergence from model outputs, and keep the experimental holdout out of the stopping rule.

| **Setting**                      | **Default / role**                                    |
|----------------------------------|-------------------------------------------------------|
| Auto-initialize QFG              | ON - reinitialize before run.                         |
| Reset to B4 anchors              | ON - start from captured source geometry.             |
| Recapture B5 constraints         | ON - freeze admissible geometry before the blind run. |
| QFG steps / iteration            | 1\.                                                   |
| Min / max iterations             | About 12 / 160.                                       |
| Convergence window               | Last 8 samples.                                       |
| Angle window tolerance           | About 0.02 degrees peak-to-peak.                      |
| Angle drift tolerance            | About 0.003 degrees per iteration.                    |
| C3 spread tolerance              | About 0.02 degrees.                                   |
| B5 correction tolerance          | 0 disables this optional convergence gate.            |
| Freeze prediction on convergence | ON.                                                   |

## 24.1 Protocol fingerprint

Run Blind Relaxation creates a SHA-256 protocol fingerprint from source transforms and numerical settings. Treat this hash as the identity of the numerical protocol. If settings change, the new run should have a new fingerprint.

## 24.2 Correct blind order

| SOURCE review -\> configure B3/B4/B5 -\> B6 run -\> convergence -\> Freeze Prediction -\> Reveal Experimental Holdout -\> residual report |
|-------------------------------------------------------------------------------------------------------------------------------------------|

## 24.3 Invalid blind-run patterns

- Revealing the experimental target before freezing prediction.

- Using the target angle as a hidden B5 constraint.

- Calling max-iterations termination “convergence”.

- Ignoring persistent clipping or large B5 corrections.

- Changing grid/dt after seeing the target and reporting the tuned run as the original prediction.

# 25. Atlas export and audit trail

Export Atlas Report records the available geometry, provenance, B2 graph/planes/envelope, B3 field configuration, B4 feedback telemetry, B5 constraints and B6 protocol/trajectory. Use it as the audit trail for every serious Atlas series.

## 25.1 Minimum files to keep

- The .blend scene.

- Export Session output.

- Export Atlas Report.

- Protocol SHA-256.

- Plugin and Blender version.

- Backend/grid/domain/dt.

- A short statement of the question being tested and which outputs were considered primary.

## 25.2 Suggested run naming

| PH3_B6_SOURCE_GAUSS_C3_grid48_dt001_hash-1a2b3c4d |
|---------------------------------------------------|

# 26. Molecular Creator

Molecular Creator is a separate reduced proxy module; do not confuse it with Atlas Direct. It can generate starter geometries for H2, H2O and C6H6, infer bonds and evaluate transparent proxy terms.

| **Proxy/control**          | **Role**                                                             |
|----------------------------|----------------------------------------------------------------------|
| Coulomb proxy              | Reduced electrostatic contribution.                                  |
| Coherence overlap          | Overlap/coherence term.                                              |
| beta gradient proxy        | Gradient contribution.                                               |
| gamma kinetic proxy        | Kinetic-like contribution.                                           |
| eta topology proxy         | Topology-like contribution.                                          |
| Bond stiffness / tolerance | Reduced bond penalty and inferred-bond tolerance.                    |
| Target-driven optimizer    | Derivative-free geometry optimization toward selected proxy targets. |

## 26.1 Evaluate Molecule

Evaluate Molecule computes current proxy indicators. The target-driven optimizer can use target energy, band gap, lambda-max, oscillator target, iteration count and step size. This is not Kohn-Sham/QFG-DFT SCF; report it as a transparent reduced proxy optimizer.

# 27. QFG Actor 5.2 - object-level reference

UI path: Properties -\> Object -\> QFG Actor 5.2

| **Actor type**   | **Primary use**                          |
|------------------|------------------------------------------|
| Gaussian node    | Localized complex field node.            |
| Hopf ring ansatz | Ring-like spinor/topological source.     |
| Vortex node      | Phase-winding source.                    |
| Plane wave       | Uniform complex wave source.             |
| Boundary         | Static potential/damping sphere or box.  |
| Molecular atom   | Atom used by Molecular Creator.          |
| Atlas nucleon    | BSM-SG/Atlas source for B1-B6.           |
| Yb probe         | Scene marker for Yb experiments.         |
| Detector         | Measurement marker or region.            |
| QFG dynamic body | Reduced rigid body for Dynamics Runtime. |

## 27.1 Atlas nucleon settings

| **Group**      | **Settings**                                                                                      |
|----------------|---------------------------------------------------------------------------------------------------|
| Identity       | Nucleon type, Atlas role, Provenance, Source note.                                                |
| Geometry       | Valence direction, Orbital plane normal.                                                          |
| B3 source      | Field source on/off, source strength, radius, anisotropy.                                         |
| B4 feedback    | Feedback on/off, force/torque coupling, linear/angular mobility, position/rotation locks.         |
| B5 constraints | Constrained, fixed node, preserve shell radius, angular freedom cone, neighbours, symmetry group. |
| Auto-tag audit | Inference confidence and evidence note for DERIVED auto-detection.                                |

## 27.2 Dynamic body settings

| **Setting**                       | **Explanation**                                                |
|-----------------------------------|----------------------------------------------------------------|
| Linear / angular velocity         | Initial translational and rotational motion.                   |
| Body mass                         | Reduced mass parameter.                                        |
| Collision shape                   | Sphere or oriented box.                                        |
| Collision radius / half extents   | Collision primitive dimensions.                                |
| Field / thermal / torque coupling | Per-body coupling to corresponding sectors.                    |
| External torque                   | Constant external torque vector.                               |
| Linear / angular drag             | Damping.                                                       |
| Restitution / friction            | Contact response.                                              |
| Kinematic                         | Object is driven externally and not integrated as a free body. |
| Softening temperature             | Thermal/phase-transition proxy threshold.                      |

## 27.3 Actor setup hygiene

- Apply Blender scale before relying on collision dimensions.

- Use meaningful object names for Atlas and dynamic bodies.

- Keep decorative meshes, labels, cameras and lights untagged.

- Record per-object overrides; a global setting can appear ineffective if a body coupling is zero.

# 28. Practical scene recipes

## 28.1 Two-node collision

**1.** Start from a clean scene or use Starting Scenes -\> Two-node collision.

**2.** Use NumPy, Scalar, 32^3, domain 16, dt 0.002.

**3.** Initialize and run steps.

**4.** Update Visualization.

**5.** Enable debug overlay only after the baseline field appears.

**6.** Bake a short timeline and scrub through the result.

## 28.2 Hopf-ring / topology scene

**1.** Switch Field to reduced Spinor prototype.

**2.** Use the Hopf-ring preset or set one object to Hopf ring ansatz.

**3.** Enable topology sector.

**4.** Initialize and run a short preview.

**5.** Compute Topology and record Hopf proxy, Skyrme proxy and orientation variance.

**6.** Repeat at higher grid before interpreting persistence.

## 28.3 6-DoF field-coupled body scene

**1.** Create two simple spheres.

**2.** Enable QFG Actor on each and choose QFG dynamic body.

**3.** Set mass, sphere collision radius and opposite initial velocities.

**4.** Set nonzero field coupling; leave thermal coupling zero for the baseline.

**5.** Enable body collisions and deterministic replay.

**6.** Run/bake and inspect contacts, force vectors and momentum.

**7.** Repeat with field coupling = 0 for an A/B control.

## 28.4 Thermal collision

**1.** Build the Thermal collision preset.

**2.** Run a mechanical baseline with collision heating disabled.

**3.** Enable collision heating and choose a conservative temperature cap.

**4.** Bake both runs.

**5.** Compare Max T, body motion and event timing.

## 28.5 Atlas graph to field

**1.** Tag reviewed Atlas objects and confirm provenance.

**2.** Extract Atlas Geometry.

**3.** B2: build Source star interaction graph.

**4.** Generate planes/envelope only if required by the question.

**5.** B3: SOURCE only + Gaussian kernel + scalar bridge.

**6.** Apply Atlas Field and inspect V min/max/RMS before enabling feedback.

## 28.6 B4/B5/B6 blind relaxation

**1.** Capture B4 Anchors.

**2.** Apply Feedback Once and inspect clipping.

**3.** Enable B5 and capture constraints.

**4.** Verify that symmetry does not encode the target angle.

**5.** Run B6 with the experimental holdout hidden.

**6.** If converged, Freeze Prediction.

**7.** Reveal holdout only after freeze and export the residual report.

# 29. Cinematic and presentation workflow

The extension can support technical demonstrations and cinematic presentations in the same Blender project. A useful showcase tells a causal story rather than only rotating a camera around a mesh.

## 29.1 Recommended story arc

| Field awakening -\> localized structure -\> QFG dynamics -\> Atlas / Jij -\> multi-body field coupling -\> integrated hero shot |
|---------------------------------------------------------------------------------------------------------------------------------|

## 29.2 What may be cinematic

- Lighting, bloom/glow, volumetric haze and camera motion.

- Trails and graphical labels derived from computed trajectories.

- Atlas graph lines and orientation guides used as explanatory visualization.

- Title cards and HUD text describing grid, dt, seed and active stage.

## 29.3 What should remain traceable

- Body trajectories used in a physics claim should come from the runtime or baked cache.

- Field visualizations should state which quantity and threshold they display.

- Atlas/Jij lines should be described as interaction/model visualization, not direct experimental imaging.

- Keep a technical export beside the beauty render so the demo can be reproduced.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><p><strong>PRESENTATION LANGUAGE</strong></p>
<p>Prefer “visualization of the model/runtime” over “this is what the nucleus/electron really looks like” unless an independent measurement supports that specific interpretation.</p></th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 30. Reproducibility, convergence and numerical controls

## 30.1 Stable numerical experiment

**1.** Run a preview at 32^3.

**2.** Export parameters and results.

**3.** Repeat at dt/2.

**4.** Repeat at 48^3 or 64^3.

**5.** Compare qualitative structure and primary diagnostics.

**6.** Only then interpret the result.

## 30.2 Deterministic replay

Fix the world/noise seed, source transforms and protocol settings. If repeated runs with the same protocol hash diverge significantly, investigate hidden scene changes, backend nondeterminism or unrecorded object-level overrides.

## 30.3 Convergence is not “it stopped moving”

A body can appear stationary because damping is high, a clamp is active or a constraint is saturated. Use numerical convergence metrics: window range, drift, residual correction, force/torque magnitude and the B6 convergence status.

## 30.4 Parameter sweeps

For hypothesis testing, use systematic sweeps rather than hand-tuning. Record the full range and step size. If a “best” result is selected after seeing experimental data, mark the relevant parameter as CALIBRATED rather than SOURCE or DERIVED.

# 31. Troubleshooting

| **Symptom**                         | **Checks / solution**                                                                                            |
|-------------------------------------|------------------------------------------------------------------------------------------------------------------|
| Plugin does not appear              | Check Blender 5.2, Extensions enabled, correct ZIP and package ID conflict.                                      |
| Torch CUDA does not work            | Use NumPy control run; verify optional PyTorch separately.                                                       |
| Run becomes unstable                | Reduce dt; reduce coupling/feedback; inspect safety clips; use smaller grid for diagnosis.                       |
| Visualization is empty              | Lower Density threshold; raise Maximum points; click Update Visualization.                                       |
| Atlas angles look wrong             | Check nuclear center, VALENCE tags and Direction rule; never measure from screenshot projection.                 |
| B3 field is zero                    | Check bridge enable, source scope, role scope, per-object B3 source and scalar/vector scales.                    |
| B4 does not move objects            | Check feedback enable, anchors, per-object mobility/coupling and locks.                                          |
| B5 locks too strongly               | Reduce stiffness; inspect connectivity, shell preservation and cone; C3 should not fix collective polar tilt.    |
| B6 does not converge                | Do not force Freeze; inspect B4/B5 conflict, tolerances, dt/grid and trajectory oscillation.                     |
| Different result between runs       | Compare protocol hash, deterministic seed, source transforms and all B3/B4/B5 settings.                          |
| Bodies tunnel / contact is unstable | Increase substeps, reduce speed/dt, verify collision primitive and radius/extents.                               |
| Performance collapses               | Inspect profiler; reduce grid/visualization points; simplify dynamics; use bake rather than live heavy playback. |

## 31.1 Debugging order

| Installation -\> baseline preset -\> numerical core -\> visualization -\> object registration -\> dynamics -\> conditional bridges -\> constraints -\> orchestration |
|----------------------------------------------------------------------------------------------------------------------------------------------------------------------|

Debug from the simplest layer upward. Do not start by changing B6 tolerances when the underlying B3 field is zero or a dynamic body was never registered.

# 32. Scientific interpretation and limits

QFG Lab 5.2 deliberately separates five levels: visual result; numerical stability/convergence; pre-declared quantitative prediction; survival under controls/uncertainty; experimental discrimination. Strong physical conclusions require the later levels, not merely the first two.

## 32.1 What B1-B6 establish

- B1/B2 can provide reproducible geometry and deterministic derived measurements from reviewed SOURCE objects.

- B3 is a CONDITIONAL mapping from geometry into a QFG field.

- B4 is a CONDITIONAL feedback mapping from numerical state back to geometry.

- B5 defines an admissible geometric set and can be scientifically useful when its assumptions are explicit.

- B6 makes the protocol blind, repeatable and auditable; it does not transform the conditional dynamics into a first-principles law.

## 32.2 Proxy naming

Atlas scalar energy, B4 work proxy, J proxy, topology proxy, gauge/gravity energy proxies and Molecular Creator terms should retain their proxy labels unless an independent derivation and calibration justifies SI interpretation.

## 32.3 Good evidence language

| **Prefer**                                                        | **Avoid**                                                    |
|-------------------------------------------------------------------|--------------------------------------------------------------|
| “The run converged under the stated B3-B5 protocol.”              | “The visualization proves the theory.”                       |
| “The predicted angle was frozen before the holdout was revealed.” | “We tuned until it matched and then called it a prediction.” |
| “The structure survives dt/grid checks within X tolerance.”       | “It looks stable, therefore it is physical.”                 |
| “This is a reduced/proxy sector.”                                 | “This is a full Maxwell/Einstein/DFT solver.”                |

# Appendix A. SDK and scripting

The extension exposes a world/actor API used by content scripts and by the cinematic demonstration. Blender Extensions may namespace the module under bl_ext.\<repository\>.qfg_lab_52; robust scripts should resolve the enabled package rather than assuming only a top-level import.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th>from qfg_lab_52.sdk import create_world, EngineConfig, WorldConfig, ActorSpec, BodySpec<br />
<br />
world = create_world(<br />
EngineConfig(grid_size=32, dt=0.002, backend="NUMPY"),<br />
WorldConfig(substeps=2, deterministic=True, seed=1337),<br />
)<br />
world.add_field_actor(ActorSpec(center=(0, 0, 0), radius=1.2))<br />
world.add_body(BodySpec(<br />
name="Shard", position=(4, 0, 0), velocity=(0, 1, 0),<br />
field_coupling=2.0, radius=0.25,<br />
))<br />
result = world.step(1)<br />
print(result.profile.to_dict())<br />
print(world.sample_field((0, 0, 0)))</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

## A.1 Current runtime capabilities

- Scalar or reduced spinor field backend.

- Deterministic update order and seeded setup.

- Density and temperature sampling plus gradients.

- Reduced spherical/oriented body collision proxies depending on build.

- Field and thermal force coupling and angular dynamics.

- Gravity, drag, floor/body contacts and event generation.

- Profiling, session export and Blender timeline bake/cache.

## A.2 Scripting advice

- Do not silently replace failed SDK physics with decorative animation if the demo claims QFG-driven motion.

- Log the resolved SDK package path and version.

- Bake or key sampled runtime states into Blender for reproducible rendering.

- Keep presentation effects separate from simulation state.

# Appendix B. Blender extension package and manifest

## B.1 Example manifest fields

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th>schema_version = "1.0.0"<br />
id = "qfg_lab_52"<br />
version = "1.0.0-alpha"<br />
name = "QFG Dynamics 1.0.0 Alpha"<br />
tagline = "Unified QFG field, dynamics and structural simulation"<br />
type = "add-on"<br />
blender_version_min = "5.2.0"<br />
license = ["SPDX:MIT"]<br />
# website, tags and permissions as appropriate for the release</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

Keep the tagline under Blender extension limits and keep permissions minimal. The manifest is part of release engineering: update the version and compatibility fields whenever behavior changes materially.

## B.2 Documentation in the ZIP

It is appropriate to include README.md, LICENSE, a short Quick Start PDF and this manual under docs/. If the full manual grows large, the Git repository can be the canonical location while the ZIP retains a compact quick-start and link.

# Appendix C. Quick reference

| **Goal**                      | **Use**                                                                   |
|-------------------------------|---------------------------------------------------------------------------|
| Check installation            | Two-node collision -\> Initialize -\> Run Steps -\> Update Visualization. |
| Create field source           | Object -\> QFG Actor -\> Gaussian / Hopf / Vortex / Plane Wave.           |
| Run rigid-body dynamics       | Object -\> QFG dynamic body + Dynamics Runtime.                           |
| Check topology                | Spinor mode -\> Topology enabled -\> Compute Topology.                    |
| Run dual-frequency drive      | Thermal and HRM -\> HRM dual drive.                                       |
| Create HRM map                | RF / HRM / Plasma -\> HRM Scan.                                           |
| Analyze Atlas geometry        | Atlas Direct -\> tag -\> Extract Atlas Geometry.                          |
| Build interaction topology    | B2 -\> Source star -\> Build Interaction Graph.                           |
| Feed Atlas into QFG           | B3 -\> Enable -\> Apply Atlas Field.                                      |
| Feed QFG back to geometry     | B4 -\> Capture Anchors -\> Apply Feedback.                                |
| Preserve admissible geometry  | B5 -\> Capture Constraints -\> Apply Constraints.                         |
| Run blind Group-15 prediction | B6 -\> Run Blind Relaxation -\> Freeze -\> Reveal.                        |
| Keep audit trail              | Export Atlas Report + Export Session + Blender file + protocol hash.      |

# Glossary

| **Term**             | **Definition in this manual**                                                              |
|----------------------|--------------------------------------------------------------------------------------------|
| Actor                | A Blender object registered with QFG-specific behavior.                                    |
| Atlas                | Structured representation of tagged BSM-SG source geometry and derived relationships.      |
| B3                   | Conditional Atlas-to-QFG field bridge.                                                     |
| B4                   | Conditional QFG-to-Atlas bounded feedback.                                                 |
| B5                   | Projection/constraint layer defining admissible geometry.                                  |
| B6                   | Blind orchestration and convergence/holdout layer.                                         |
| Field source         | Object or Atlas contribution rasterized into numerical QFG state.                          |
| Jij                  | Interaction graph edge/weight proxy between Atlas sites.                                   |
| Holdout              | Experimental/reference value withheld from prediction and convergence decisions.           |
| Proxy                | Reduced numerical metric used for comparison; not automatically an SI physical observable. |
| Protocol fingerprint | SHA-256 identifier of source transforms and numerical protocol settings.                   |
| SOURCE               | Reviewed input allowed to drive a source-defined protocol.                                 |
| DERIVED              | Deterministic result from source inputs without new fitted parameters.                     |
| CONDITIONAL          | Model bridge/hypothesis requiring explicit assumptions.                                    |
| CALIBRATED           | Parameter fixed from reference/measurement.                                                |
| EXPERIMENTAL         | Independent measured/reference value used for validation.                                  |
| Bake                 | Precompute and cache timeline states for responsive Blender playback/rendering.            |

**End of QFG Dynamics 1.0.0-alpha Full Reference Manual**

For later releases, review UI labels, defaults and scientific-status wording against the installed build before publishing an updated manual.
