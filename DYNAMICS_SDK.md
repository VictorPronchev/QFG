# QFG Dynamics SDK 0.4.1 Alpha

## Purpose

QFG Dynamics exposes a stable world/actor API around the spectral QFG solver.
Version 0.4.1 keeps the public surface backend-neutral while retaining the small
deterministic 6-DoF rigid-body layer.

```python
from qfg_lab_52.sdk import create_world, EngineConfig, WorldConfig, ActorSpec, BodySpec

world = create_world(
    EngineConfig(grid_size=32, dt=0.002, backend="NUMPY"),
    WorldConfig(substeps=2, deterministic=True, seed=1337),
)
world.add_field_actor(ActorSpec(center=(0, 0, 0), radius=1.2))
world.add_body(BodySpec(
    name="Shard",
    position=(4, 0, 0),
    velocity=(0, 1, 0),
    angular_velocity=(0, 0, 1.5),
    collision_shape="BOX",
    half_extents=(0.35, 0.18, 0.12),
    mass=1.0,
    field_coupling=2.0,
    field_torque_coupling=0.1,
))
result = world.step(1)
print(result.telemetry)
print(world.body_snapshot()["orientations"])
print(world.body_snapshot()["torque_contact"])
print(world.snapshot_hash())
```

## 0.4.0 runtime capabilities

- quaternion orientation and world-space angular velocity;
- sphere and oriented-box (OBB) collision shapes;
- shape-derived sphere/box inertia tensors;
- Sphere/Sphere, Sphere/Box and rotated Box/Box SAT contacts;
- shape-aware floor contacts;
- contact-point impulses with angular response (`r x J`);
- impulse-based Coulomb friction that can generate spin;
- external torque and opt-in reduced field-alignment torque;
- linear/angular drag and configurable speed clamps;
- per-body force and torque channels;
- linear, rotational and total kinetic-energy telemetry;
- total linear/angular momentum telemetry;
- deterministic replay hash including orientation and angular velocity;
- stateful contact begin/end, field-entry and phase-transition events;
- Blender bake/cache playback of position and orientation.

## Deliberate limitations

This is a research runtime, not a mature general-purpose physics SDK. It does
not yet include convex hull/GJK-EPA, triangle meshes, joints/constraints, CCD,
broad-phase acceleration, sleeping islands, deformables, fracture, vehicles or
validated engineering contact parameters. Box/box contact uses SAT with a
single representative contact point rather than a full contact manifold.


## 0.4.1 playback/debug additions

The Blender layer now caches `QFGWorld.telemetry()` beside each baked body state. The viewport debug overlay consumes only these cached/live snapshots and never steps the solver. `TimelineCache.resolve_frame()` provides deterministic HOLD/CLAMP/STATUS_ONLY resolution for out-of-range timeline requests.
