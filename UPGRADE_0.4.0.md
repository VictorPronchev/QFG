# Upgrading QFG Dynamics 0.3.3 -> 0.4.0

## Compatibility

Existing 0.3.3 dynamic bodies remain valid. The new collision shape defaults to
`SPHERE`, so an older scene continues to use its `collision_radius` until the
body is explicitly switched to `BOX`.

## New body properties

- `collision_shape`: `SPHERE` or `BOX`;
- `collision_half_extents`: local OBB half-size;
- `angular_velocity`: world-space initial angular velocity;
- `angular_drag`;
- `external_torque`;
- `field_torque_coupling`.

## New world properties

- `dynamics_max_angular_speed`;
- `dynamics_field_torque_scale`.

## Cache/export change

0.4.0 baked body states include quaternion orientations, angular velocities,
shape metadata, force channels, torque channels and linear/angular contact
impulses. Old in-memory caches should be rebaked after updating the add-on.

## Collision showcase

Newly generated Collision showcase shards use OBB shapes derived from their
visual half-extents and receive deterministic seeded angular velocities.
