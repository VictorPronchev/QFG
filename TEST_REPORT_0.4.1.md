# QFG Dynamics 0.4.1-alpha Regression Report

## Result

`QFG Dynamics 0.4.1 Alpha pure numerical + playback/debug regression tests: PASS`

## 0.4.1-specific checks

- `TimelineCache.bounds()` and nearest-frame selection.
- Exact cached frame resolution.
- Out-of-range HOLD behavior.
- Out-of-range CLAMP behavior.
- Out-of-range STATUS_ONLY behavior.
- Missing in-range frame fallback.
- Cached world telemetry preservation.
- Contact debug records contain finite 3-D position, normal, normal impulse, friction impulse, and total impulse vectors.
- Shape-aware floor contacts appear in debug telemetry.

The existing 0.4.0 tests for 6-DoF inertia, torque integration, quaternion normalization, Sphere/OBB off-centre impacts, linear/angular momentum conservation, rotated OBB SAT, floor-friction spin, field torque, full cache state, and deterministic rotational hashes continue to pass.
