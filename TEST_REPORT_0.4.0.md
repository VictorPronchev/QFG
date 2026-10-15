# QFG Dynamics 0.4.0-alpha Regression Report

## Result

**PASS** — pure numerical suite and Python compilation.

## 0.4.0-specific checks

1. Box inertia matches the analytic cuboid inertia formula.
2. Applied torque changes angular velocity and normalized quaternion orientation.
3. Sphere/OBB off-centre contact conserves total linear and angular momentum (no external force/torque).
4. Off-centre contact produces non-zero box spin.
5. Rotated OBB/OBB collision is detected with SAT; separated OBBs are rejected.
6. Shape-aware floor friction produces angular impulse/torque on a sliding box.
7. Reduced field-alignment torque is opt-in and exported in its own telemetry channel.
8. Torque channels are finite and structurally consistent.
9. Deterministic replay hashes match for identical rotational states and diverge when angular state changes.
10. The complete 0.3.3 regression suite still passes.

## Environment boundary

The suite runs without Blender. Blender 5.2 `bpy`, Geometry Nodes, panel registration, timeline rendering and Eevee output require an in-Blender smoke test.
