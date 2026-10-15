# QFG Dynamics 0.3.3-alpha Regression Report

Executed with the package pure-Python test runner on the build workspace.

## Result

**PASS** — `python3 tests/run_pure_tests.py`

## 0.3.3-specific checks

- body/body impulse conserves linear momentum for an isolated two-body contact;
- Coulomb friction reduces tangential relative speed;
- persistent contacts emit one `contact_begin` and a later `contact_end`;
- resting floor contact does not repeat `contact_begin`;
- floor contact produces non-zero contact-force telemetry;
- gravity/field/thermal/drag/contact force channels sum to `force_total`;
- force profiler values remain finite and non-negative where required;
- field coupling ON and OFF produce measurably different probe trajectories;
- identical deterministic worlds produce identical SHA-256 runtime state hashes;
- the pre-existing scalar, spinor/topology/gauge/gravity, HRM, plasma, RF, Yb and molecular tests still pass.

## Static check

**PASS** — `python3 -m compileall -q .`

Blender UI/operator execution still requires Blender 5.2 itself; the pure test suite intentionally does not import `bpy`.
