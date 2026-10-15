"""Pure numerical regression tests; Blender/bpy is not required."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "qfg_lab_52_testpkg"


def load_package():
    pkg = types.ModuleType(PACKAGE_NAME)
    pkg.__path__ = [str(ROOT)]
    pkg.__package__ = PACKAGE_NAME
    sys.modules[PACKAGE_NAME] = pkg


def load_module(name: str):
    full = f"{PACKAGE_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(full, ROOT / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    load_package()
    diagnostics = load_module("diagnostics")
    core = load_module("core")
    dynamics = load_module("dynamics")
    experiments = load_module("experiments")
    yb = load_module("yb")
    molecular = load_module("molecular")
    atlas_geometry = load_module("atlas_geometry")
    atlas_b2 = load_module("atlas_b2")
    atlas_field = load_module("atlas_field")
    atlas_feedback = load_module("atlas_feedback")
    atlas_constraints = load_module("atlas_constraints")
    atlas_blind = load_module("atlas_blind")
    rom = load_module("rom")

    # Scalar 3-D core.
    cfg = core.EngineConfig(
        grid_size=16,
        domain_length=12.0,
        dt=0.002,
        backend="NUMPY",
        thermal_enabled=True,
        hrm_enabled=True,
        drive_profile="GAUSSIAN",
    )
    engine = core.QFGEngine3D(cfg)
    engine.add_actor(core.ActorSpec(center=(-2.0, 0.0, 0.0), velocity=(2.0, 0.0, 0.0)))
    engine.add_actor(core.ActorSpec(center=(2.0, 0.0, 0.0), velocity=(-2.0, 0.0, 0.0)))
    for _ in range(4):
        engine.step()
    d = engine.compute_diagnostics()
    assert np.isfinite(d.energy_proxy)
    assert d.norm > 0.0
    assert engine.density().shape == (16, 16, 16)

    # Spinor/topology/gauge/gravity branches.
    cfg2 = core.EngineConfig(
        grid_size=12,
        domain_length=10.0,
        dt=0.001,
        backend="NUMPY",
        field_mode="SPINOR",
        topology_enabled=True,
        spin_exchange=0.01,
        skyrme_potential_scale=1e-4,
        gauge_enabled=True,
        gauge_coupling=0.01,
        gravity_enabled=True,
        gravity_strength=1e-5,
        thermal_enabled=False,
    )
    engine2 = core.QFGEngine3D(cfg2)
    engine2.add_actor(core.ActorSpec(actor_type="HOPF_RING", ring_radius=1.8, radius=0.6))
    engine2.step()
    d2 = engine2.compute_diagnostics()
    assert np.isfinite(d2.skyrme_energy)
    assert np.isfinite(d2.gauge_energy)
    assert np.isfinite(d2.gravity_energy)
    topology = engine2.topological_diagnostics()
    assert "hopf_proxy" in topology

    # QFG Dynamics world/API, field queries and deterministic body coupling.
    world_cfg = dynamics.WorldConfig(
        substeps=1, gravity=(0.0, 0.0, 0.0), body_collisions=True,
        deterministic=True, seed=7, field_force_scale=0.5,
    )
    world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=12, domain_length=10.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.001,
        ),
        world_cfg,
    )
    world.add_field_actor(core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.2))
    world.add_body(dynamics.BodySpec(
        name="BodyA", position=(2.5, 0.0, 0.0), velocity=(0.0, 0.2, 0.0),
        radius=0.25, field_coupling=1.0, linear_drag=0.0,
    ))
    before = world.bodies[0].position.copy()
    step_result = world.step(3)
    after = world.bodies[0].position.copy()
    assert np.all(np.isfinite(after))
    assert not np.allclose(before, after)
    assert step_result.profile.total_ms >= 0.0
    sample = world.sample_field((0.0, 0.0, 0.0))
    assert np.isfinite(sample["density"])
    assert np.asarray(sample["density_gradient"]).shape == (3,)

    # Same setup must replay deterministically on the NumPy backend.
    world2 = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=12, domain_length=10.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.001,
        ),
        world_cfg,
    )
    world2.add_field_actor(core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.2))
    world2.add_body(dynamics.BodySpec(
        name="BodyA", position=(2.5, 0.0, 0.0), velocity=(0.0, 0.2, 0.0),
        radius=0.25, field_coupling=1.0, linear_drag=0.0,
    ))
    world2.step(3)
    assert np.allclose(world.bodies[0].position, world2.bodies[0].position, atol=1e-8)

    # Collision solver v2: equal/opposite impulses conserve linear momentum
    # and Coulomb friction reduces tangential relative speed.
    contact_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.0,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, 0.0), body_collisions=True,
            position_correction=0.8, penetration_slop=1e-5,
        ),
    )
    contact_world.add_body(dynamics.BodySpec(
        name="ContactA", position=(-0.45, 0.0, 0.0), velocity=(1.0, 0.8, 0.0),
        mass=1.0, radius=0.5, restitution=0.25, friction=0.6, linear_drag=0.0,
    ))
    contact_world.add_body(dynamics.BodySpec(
        name="ContactB", position=(0.45, 0.0, 0.0), velocity=(-1.0, -0.8, 0.0),
        mass=1.0, radius=0.5, restitution=0.25, friction=0.6, linear_drag=0.0,
    ))
    momentum_before = sum(
        (body.spec.mass * body.velocity for body in contact_world.bodies),
        np.zeros(3),
    )
    tangent_before = abs(contact_world.bodies[1].velocity[1] - contact_world.bodies[0].velocity[1])
    contact_world.events = []
    count = contact_world._solve_body_contacts(0.002)
    momentum_after = sum(
        (body.spec.mass * body.velocity for body in contact_world.bodies),
        np.zeros(3),
    )
    tangent_after = abs(contact_world.bodies[1].velocity[1] - contact_world.bodies[0].velocity[1])
    assert count == 1
    assert np.allclose(momentum_before, momentum_after, atol=1e-12)
    assert tangent_after < tangent_before
    assert sum(event.kind == "contact_begin" for event in contact_world.events) == 1
    begin = next(event for event in contact_world.events if event.kind == "contact_begin")
    assert begin.details["normal_impulse"] > 0.0
    assert begin.details["friction_impulse"] > 0.0

    # Stateful contacts do not emit contact_begin every solver call.
    contact_world.events = []
    contact_world._solve_body_contacts(0.002)
    assert not any(event.kind == "contact_begin" for event in contact_world.events)
    contact_world.bodies[1].position[:] = (3.0, 0.0, 0.0)
    contact_world.events = []
    contact_world._solve_body_contacts(0.002)
    assert any(event.kind == "contact_end" for event in contact_world.events)

    # Persistent floor contact also emits begin once and exposes contact force.
    floor_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.0,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, -1.0), floor_height=-1.0,
            body_collisions=False, contact_event_threshold=1e-8,
        ),
    )
    floor_world.add_body(dynamics.BodySpec(
        name="FloorBody", position=(0.0, 0.0, -0.55), velocity=(1.0, 0.0, -0.2),
        mass=2.0, radius=0.5, restitution=0.0, friction=0.5, linear_drag=0.0,
    ))
    floor_world._refresh_query_cache()
    floor_world.events = []
    floor_world._integrate_bodies(0.002)
    assert sum(event.kind == "contact_begin" for event in floor_world.events) == 1
    assert np.linalg.norm(floor_world.bodies[0].force_contact) > 0.0
    floor_world.events = []
    floor_world._integrate_bodies(0.002)
    assert not any(event.kind == "contact_begin" for event in floor_world.events)

    # Force channels are exported per body and sum to the reported total force.
    force_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=12, domain_length=10.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.001,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, -0.2), body_collisions=False,
            field_force_scale=0.5,
        ),
    )
    force_world.add_field_actor(core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.2))
    force_world.add_body(dynamics.BodySpec(
        name="TelemetryBody", position=(2.0, 0.0, 0.0), velocity=(0.0, 0.1, 0.0),
        radius=0.25, field_coupling=1.0, linear_drag=0.02,
    ))
    force_result = force_world.step(2)
    force_snapshot = force_world.body_snapshot()
    for key in (
        "force_gravity", "force_field", "force_thermal", "force_drag",
        "force_contact", "force_total", "contact_impulse",
    ):
        assert force_snapshot[key].shape == (1, 3)
        assert np.all(np.isfinite(force_snapshot[key]))
    summed_force = (
        force_snapshot["force_gravity"][0]
        + force_snapshot["force_field"][0]
        + force_snapshot["force_thermal"][0]
        + force_snapshot["force_drag"][0]
        + force_snapshot["force_contact"][0]
    )
    assert np.allclose(summed_force, force_snapshot["force_total"][0], atol=1e-6)
    assert force_result.profile.max_force >= force_result.profile.mean_force >= 0.0
    assert force_result.profile.kinetic_energy >= 0.0

    # Coupling ON/OFF must produce a measurable trajectory difference.
    def coupling_world(scale):
        w = dynamics.QFGWorld(
            core.EngineConfig(
                grid_size=12, domain_length=10.0, dt=0.002, backend="NUMPY",
                thermal_enabled=False, damping=0.001,
            ),
            dynamics.WorldConfig(
                substeps=1, gravity=(0.0, 0.0, 0.0), body_collisions=False,
                field_force_scale=scale,
            ),
        )
        w.add_field_actor(core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.2))
        w.add_body(dynamics.BodySpec(
            name="Probe", position=(2.0, 0.0, 0.0), velocity=(0.0, 0.0, 0.0),
            radius=0.25, field_coupling=4.0, linear_drag=0.0,
        ))
        return w

    coupled = coupling_world(1.0)
    uncoupled = coupling_world(0.0)
    coupled.step(8)
    uncoupled.step(8)
    assert not np.allclose(coupled.bodies[0].position, uncoupled.bodies[0].position, atol=1e-10)

    # Deterministic replay hashes must match for identical worlds.
    replay_a = coupling_world(0.75)
    replay_b = coupling_world(0.75)
    replay_a.step(5)
    replay_b.step(5)
    assert replay_a.snapshot_hash() == replay_b.snapshot_hash()

    # QFG Dynamics 0.4.0: inertia, torque integration and quaternion orientation.
    torque_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=8, domain_length=8.0, dt=0.01, backend="NUMPY",
            thermal_enabled=False, damping=0.0,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, 0.0), floor_height=-10.0,
            body_collisions=False, max_angular_speed=100.0,
        ),
    )
    torque_world.add_body(dynamics.BodySpec(
        name="TorqueBox", collision_shape="BOX", half_extents=(1.0, 0.5, 0.25),
        mass=2.0, position=(0.0, 0.0, 0.0), external_torque=(0.0, 0.0, 1.0),
        linear_drag=0.0, angular_drag=0.0, field_coupling=0.0,
    ))
    body = torque_world.bodies[0]
    expected_izz = (2.0 / 3.0) * (1.0 ** 2 + 0.5 ** 2)
    assert np.isclose(body.local_inertia_diag()[2], expected_izz)
    q_before = body.orientation.copy()
    torque_world.step(2)
    assert body.angular_velocity[2] > 0.0
    assert not np.allclose(q_before, body.orientation)
    assert np.isclose(np.linalg.norm(body.orientation), 1.0, atol=1e-12)
    assert torque_world.telemetry()["rotational_kinetic_energy"] > 0.0

    # Shape-aware Sphere -> OBB contact: off-centre impulse spins the box while
    # conserving total linear and angular momentum about the world origin.
    shape_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.0,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, 0.0), floor_height=-10.0,
            body_collisions=True, position_correction=0.0,
        ),
    )
    shape_world.add_body(dynamics.BodySpec(
        name="Sphere", collision_shape="SPHERE", radius=0.30,
        position=(-0.70, 0.20, 0.0), velocity=(1.0, 0.0, 0.0),
        mass=1.0, restitution=0.0, friction=0.0, linear_drag=0.0, angular_drag=0.0,
    ))
    shape_world.add_body(dynamics.BodySpec(
        name="Box", collision_shape="BOX", half_extents=(0.50, 0.50, 0.50),
        position=(0.0, 0.0, 0.0), velocity=(0.0, 0.0, 0.0),
        mass=2.0, restitution=0.0, friction=0.0, linear_drag=0.0, angular_drag=0.0,
    ))
    detected = shape_world._detect_contact(shape_world.bodies[0], shape_world.bodies[1])
    assert detected is not None and detected.feature == "SPHERE_BOX"

    def total_linear(world):
        return sum((b.spec.mass * b.velocity for b in world.bodies), np.zeros(3))

    def total_angular(world):
        return sum((
            np.cross(b.position, b.spec.mass * b.velocity)
            + b.inertia_world() @ b.angular_velocity
            for b in world.bodies
        ), np.zeros(3))

    p_before = total_linear(shape_world)
    l_before = total_angular(shape_world)
    shape_world.events = []
    assert shape_world._solve_body_contacts(0.002) == 1
    p_after = total_linear(shape_world)
    l_after = total_angular(shape_world)
    assert np.allclose(p_before, p_after, atol=1e-11)
    assert np.allclose(l_before, l_after, atol=1e-11)
    assert abs(shape_world.bodies[1].angular_velocity[2]) > 1e-8
    event = next(e for e in shape_world.events if e.kind == "contact_begin")
    assert event.details["feature"] == "SPHERE_BOX"

    # OBB-vs-OBB SAT supports rotated boxes and rejects separated boxes.
    box_world = dynamics.QFGWorld(
        core.EngineConfig(grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY", thermal_enabled=False),
        dynamics.WorldConfig(gravity=(0.0, 0.0, 0.0), floor_height=-10.0),
    )
    angle = np.deg2rad(35.0) / 2.0
    qz = (float(np.cos(angle)), 0.0, 0.0, float(np.sin(angle)))
    box_world.add_body(dynamics.BodySpec(
        name="OBB_A", collision_shape="BOX", half_extents=(0.7, 0.3, 0.4),
        position=(0.0, 0.0, 0.0), orientation=(1.0, 0.0, 0.0, 0.0),
    ))
    box_world.add_body(dynamics.BodySpec(
        name="OBB_B", collision_shape="BOX", half_extents=(0.6, 0.35, 0.4),
        position=(0.9, 0.05, 0.0), orientation=qz,
    ))
    sat_contact = box_world._detect_contact(box_world.bodies[0], box_world.bodies[1])
    assert sat_contact is not None and sat_contact.feature == "BOX_BOX_SAT"
    box_world.bodies[1].position[:] = (4.0, 0.0, 0.0)
    assert box_world._detect_contact(box_world.bodies[0], box_world.bodies[1]) is None

    # Shape-aware floor friction acts at the bottom face and generates spin.
    floor_box_world = dynamics.QFGWorld(
        core.EngineConfig(grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY", thermal_enabled=False),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, 0.0), floor_height=0.0,
            body_collisions=False, position_correction=1.0,
        ),
    )
    floor_box_world.add_body(dynamics.BodySpec(
        name="SlidingBox", collision_shape="BOX", half_extents=(0.5, 0.5, 0.5),
        position=(0.0, 0.0, 0.45), velocity=(2.0, 0.0, -1.0), mass=1.0,
        restitution=0.0, friction=0.8, linear_drag=0.0, angular_drag=0.0,
    ))
    floor_box_world._refresh_query_cache()
    floor_box_world.events = []
    floor_box_world._integrate_bodies(0.002)
    sliding = floor_box_world.bodies[0]
    assert abs(sliding.angular_velocity[1]) > 1e-8
    assert np.linalg.norm(sliding.contact_angular_impulse) > 0.0
    assert np.linalg.norm(sliding.torque_contact) > 0.0

    # Field-alignment torque is a reduced opt-in coupling and is exported as a
    # separate torque channel rather than hidden inside the angular integrator.
    align_world = dynamics.QFGWorld(
        core.EngineConfig(
            grid_size=12, domain_length=10.0, dt=0.002, backend="NUMPY",
            thermal_enabled=False, damping=0.001,
        ),
        dynamics.WorldConfig(
            substeps=1, gravity=(0.0, 0.0, 0.0), floor_height=-10.0,
            body_collisions=False, field_torque_scale=1.0,
        ),
    )
    align_world.add_field_actor(core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.2))
    align_world.add_body(dynamics.BodySpec(
        name="AlignProbe", collision_shape="BOX", half_extents=(0.4, 0.2, 0.3),
        position=(2.0, 0.0, 0.0), field_coupling=0.0,
        field_torque_coupling=5.0, linear_drag=0.0, angular_drag=0.0,
    ))
    align_world.step(2)
    align_snap = align_world.body_snapshot()
    assert np.linalg.norm(align_snap["torque_field"][0]) > 0.0
    assert np.linalg.norm(align_snap["angular_velocities"][0]) > 0.0
    for key in ("torque_external", "torque_field", "torque_drag", "torque_contact", "torque_total"):
        assert align_snap[key].shape == (1, 3)
        assert np.all(np.isfinite(align_snap[key]))

    # Rotational state participates in deterministic replay hashing.
    spin_a = dynamics.QFGWorld(
        core.EngineConfig(grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY", thermal_enabled=False),
        dynamics.WorldConfig(gravity=(0.0, 0.0, 0.0), floor_height=-10.0, body_collisions=False),
    )
    spin_b = dynamics.QFGWorld(
        core.EngineConfig(grid_size=8, domain_length=8.0, dt=0.002, backend="NUMPY", thermal_enabled=False),
        dynamics.WorldConfig(gravity=(0.0, 0.0, 0.0), floor_height=-10.0, body_collisions=False),
    )
    spin_spec = dynamics.BodySpec(
        name="Spin", collision_shape="BOX", half_extents=(0.5, 0.25, 0.2),
        angular_velocity=(0.2, -0.4, 1.0), linear_drag=0.0, angular_drag=0.0,
        field_coupling=0.0,
    )
    spin_a.add_body(spin_spec)
    spin_b.add_body(spin_spec)
    spin_a.step(4)
    spin_b.step(4)
    assert spin_a.snapshot_hash() == spin_b.snapshot_hash()
    spin_b.bodies[0].angular_velocity[0] += 1e-4
    assert spin_a.snapshot_hash() != spin_b.snapshot_hash()

    # Timeline cache must preserve the complete 6-DoF state used by baked playback.
    cache = diagnostics.TimelineCache()
    state = align_world.body_snapshot()
    cache.put(
        1, points=np.zeros((1, 3)), weights=np.ones(1),
        density_slice=np.zeros((2, 2)), diagnostics={}, body_state=state,
    )
    cached_state = cache.get(1)["body_state"]
    assert np.allclose(cached_state["orientations"], state["orientations"])
    assert np.allclose(cached_state["angular_velocities"], state["angular_velocities"])
    assert np.allclose(cached_state["torque_total"], state["torque_total"])
    assert cached_state["collision_shapes"] == state["collision_shapes"]

    # QFG Dynamics 0.4.1: cache range resolution is explicit and testable.
    cache.put(
        3, points=np.zeros((1, 3)), weights=np.ones(1),
        density_slice=np.zeros((2, 2)), diagnostics={}, body_state=state,
        telemetry=align_world.telemetry(),
    )
    assert cache.bounds() == (1, 3)
    assert cache.resolve_frame(1, "HOLD_LAST") == (1, "EXACT")
    assert cache.resolve_frame(8, "HOLD_LAST") == (3, "HOLD")
    assert cache.resolve_frame(-5, "CLAMP") == (1, "CLAMP")
    assert cache.resolve_frame(8, "STATUS_ONLY") == (None, "OUTSIDE")
    assert cache.resolve_frame(2, "HOLD_LAST") == (1, "MISSING")
    assert "telemetry" in cache.get(3)

    # Contact debug telemetry carries renderable point/normal/impulse vectors.
    debug_telemetry = contact_world.telemetry()
    assert debug_telemetry["debug_contacts"]
    debug_contact = debug_telemetry["debug_contacts"][0]
    for key in ("position", "normal", "normal_impulse", "friction_impulse", "total_impulse"):
        assert len(debug_contact[key]) == 3
        assert np.all(np.isfinite(np.asarray(debug_contact[key], dtype=float)))

    floor_debug = floor_box_world.telemetry()["debug_contacts"]
    assert any(contact["kind"] == "FLOOR" for contact in floor_debug)

    # HRM and experimental models.
    scan = experiments.hrm_scan(experiments.HRMScanConfig(
        points=3, duration=0.04, dt=0.004, nx=32,
    ))
    assert scan["modevar"].shape == (3, 3)
    assert np.all(np.isfinite(scan["modevar"]))

    plasma = experiments.simulate_glow_plasma(experiments.PlasmaConfig(duration=0.1, dt=0.002))
    assert len(plasma["time"]) == len(plasma["light"])
    cavity = experiments.cavity_shift_sweep(experiments.CavityShiftConfig(powers=20))
    assert len(cavity["power"]) == 20
    mems = experiments.mems_geometry_sweep(experiments.MEMSConfig(points=20))
    assert len(mems["geometry"]) == 20

    # Spectrum/IMD/Allan diagnostics.
    t = np.arange(0, 2.0, 0.001)
    signal = np.sin(2 * np.pi * 5.0 * t) + 0.5 * np.sin(2 * np.pi * 6.2 * t)
    imd = diagnostics.imd_metrics(signal, 0.001, 5.0, 6.2)
    assert "difference" in imd["peaks"]
    allan = diagnostics.allan_deviation(signal, 0.001)
    assert allan["tau"].size > 0

    # Nonlinear RF ROM.
    rf = rom.hysteresis(rom.ROMConfig(points=31, settle_steps=20, dt=0.01))
    assert rf["detuning"].shape == (31,)

    # Yb reduced models.
    ycfg = yb.YbConfig(duration=0.2, dt=0.002, rabi_frequency=2.0)
    rabi = yb.simulate_rabi(ycfg)
    ramsey = yb.simulate_ramsey(ycfg, free_time_max=1.0, points=30)
    odmr = yb.simulate_odmr_sweep(ycfg, frequency_min=-2.0, frequency_max=2.0, points=41)
    qs = yb.q_factor_sweep(ycfg, q_min=1e2, q_max=1e5, points=12)
    assert len(rabi["time"]) > 2 and len(ramsey["free_time"]) == 30
    assert len(odmr["frequency"]) == 41 and len(qs["q_factor"]) == 12

    # Molecular proxy and optimizer.
    atoms = molecular.molecule_preset("H2O")
    mcfg = molecular.MolecularProxyConfig()
    base = molecular.proxy_energy(atoms, mcfg)
    assert np.isfinite(base["proxy_total"])
    result = molecular.optimize_geometry(
        atoms, mcfg, molecular.MolecularTarget(),
        molecular.OptimizationConfig(iterations=8, initial_step=0.02),
    )
    assert len(result["objective_history"]) == 9
    assert np.all(np.isfinite(result["objective_history"]))

    # Atlas Direct pure geometry + blind holdout workflow.
    target_angle = 93.3
    vectors = atlas_geometry.three_arm_vectors_from_pair_angle(target_angle)
    atlas = atlas_geometry.analyze_valence_vectors(
        vectors, names=("P_val_1", "P_val_2", "P_val_3"), element="P",
    )
    assert abs(atlas.mean_pair_angle_deg - target_angle) < 1e-10
    assert atlas.std_pair_angle_deg < 1e-10
    expected_hr = atlas_geometry.c3v_height_ratio_from_pair_angle(target_angle)
    assert expected_hr is not None
    assert abs(atlas.c3v_height_ratio - expected_hr) < 1e-12
    comparison = atlas_geometry.compare_frozen_prediction(atlas.mean_pair_angle_deg, "P")
    assert comparison["reference_provenance"] == "EXPERIMENTAL"
    assert abs(comparison["residual_deg"]) < 1e-10

    # B2: conservative name heuristics never become SOURCE automatically.
    guess = atlas_b2.infer_nucleon_from_name("Deuteron_valence_01")
    assert guess.nucleon_type == "DEUTERON"
    assert guess.role == "VALENCE"
    assert guess.provenance == "DERIVED"
    unresolved = atlas_b2.infer_nucleon_from_name("Mesh.001")
    assert unresolved.nucleon_type == "OTHER" and unresolved.role == "OTHER"

    # B2: minimal source-star graph has exactly three valence↔equatorial edges.
    nodes = [
        atlas_b2.InteractionNode("B1", (1.0, 0.0, 0.0), (1.0, 0.0, 0.0), "VALENCE", "DEUTERON"),
        atlas_b2.InteractionNode("B2", (-0.5, 0.8660254, 0.0), (-0.5, 0.8660254, 0.0), "VALENCE", "DEUTERON"),
        atlas_b2.InteractionNode("B3", (-0.5, -0.8660254, 0.0), (-0.5, -0.8660254, 0.0), "VALENCE", "DEUTERON"),
        atlas_b2.InteractionNode("E", (0.0, 0.0, 0.5), (0.0, 0.0, 1.0), "EQUATORIAL", "DEUTERON"),
    ]
    graph = atlas_b2.build_interaction_graph(nodes, topology="SOURCE_STAR", kernel="TOPOLOGY_ONLY")
    assert len(graph.edges) == 3
    assert graph.provenance == "DERIVED"
    assert abs(graph.total_j_proxy - 3.0) < 1e-12
    graph2 = atlas_b2.build_interaction_graph(
        nodes, topology="SOURCE_STAR", kernel="COSINE_SQUARED_INV_R3", softening=0.1,
    )
    assert graph2.provenance == "CONDITIONAL"
    assert np.all(np.isfinite(np.asarray(graph2.j_proxy_matrix)))

    # B2: plane normals are axial; opposite normals define the same plane.
    planes = atlas_b2.analyze_orbital_planes(
        [(1, 0, 0), (-1, 0, 0), (0, 1, 0)], names=("P1", "P2", "P3"), symmetry_axis=(0, 0, 1),
    )
    assert abs(planes.pair_dihedral_deg[0][1]) < 1e-12
    assert planes.planes[0].tilt_to_symmetry_axis_deg == 90.0

    # B2: integrated Bohr envelope is a finite CONDITIONAL geometry proxy.
    envelope = atlas_b2.estimate_integrated_bohr_envelope(
        [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0)],
        radii=[0.2, 0.2, 0.2, 0.2], padding=1.05,
    )
    assert envelope.provenance == "CONDITIONAL"
    assert envelope.ellipsoid_volume > 0.0
    assert envelope.bounding_sphere_radius > 1.0

    # B3: Atlas geometry rasterizes into finite conditional scalar/vector fields.
    b3_sources = [
        atlas_field.AtlasFieldSource(
            name="P_val_1", position=(1.0, 0.0, 0.0), direction=(1.0, 0.0, 0.0),
            orbital_normal=(0.0, 0.0, 1.0), strength=1.0, radius=0.6, anisotropy=0.5,
            role="VALENCE", nucleon_type="DEUTERON", provenance="SOURCE",
        ),
        atlas_field.AtlasFieldSource(
            name="P_eq", position=(0.0, 0.0, 0.0), direction=(0.0, 0.0, 1.0),
            orbital_normal=(0.0, 1.0, 0.0), strength=0.5, radius=0.8, anisotropy=0.25,
            role="EQUATORIAL", nucleon_type="DEUTERON", provenance="SOURCE",
        ),
    ]
    b3_cfg = atlas_field.AtlasFieldConfig(
        kernel="GAUSSIAN", vector_mode="DIRECTOR", scalar_scale=0.2, vector_scale=0.1,
        orbital_mix=0.5, scene_scale=1.0,
    )
    scalar_b3, vector_b3, summary_b3 = atlas_field.rasterize_atlas_field(
        np.linspace(-4.0, 4.0, 10, endpoint=False), b3_sources, b3_cfg,
    )
    assert scalar_b3.shape == (10, 10, 10)
    assert vector_b3.shape == (3, 10, 10, 10)
    assert np.all(np.isfinite(scalar_b3)) and np.all(np.isfinite(vector_b3))
    assert summary_b3.source_count == 2
    assert summary_b3.provenance == "CONDITIONAL"
    assert summary_b3.scalar_max > 0.0
    assert summary_b3.vector_max > 0.0

    # Rejected inputs never drive the B3 field.
    rejected = atlas_field.AtlasFieldSource(
        name="Rejected", position=(0, 0, 0), direction=(1, 0, 0), orbital_normal=(0, 1, 0),
        strength=100.0, radius=1.0, anisotropy=1.0, provenance="REJECTED",
    )
    zeros_s, zeros_v = atlas_field.evaluate_atlas_field([[0.2, 0.0, 0.0]], [rejected], b3_cfg)
    assert np.allclose(zeros_s, 0.0) and np.allclose(zeros_v, 0.0)

    # The core accepts the B3 bundle explicitly and it measurably changes evolution.
    e_cfg = core.EngineConfig(
        grid_size=10, domain_length=8.0, dt=0.002, backend="NUMPY",
        thermal_enabled=False, damping=0.0,
    )
    e_a = core.QFGEngine3D(e_cfg)
    e_b = core.QFGEngine3D(e_cfg)
    actor = core.ActorSpec(center=(0.0, 0.0, 0.0), radius=1.0, intensity=1.0)
    e_a.add_actor(actor)
    e_b.add_actor(actor)
    sfield, vfield, _ = atlas_field.rasterize_atlas_field(e_a.space, b3_sources, b3_cfg)
    e_a.set_atlas_field(sfield, vfield, metadata={"provenance": "CONDITIONAL"})
    assert np.allclose(e_a.atlas_field_numpy()[0], sfield)
    e_a.step(2)
    e_b.step(2)
    assert not np.allclose(e_a.psi, e_b.psi, atol=1e-9)
    e_a.clear_atlas_field()
    cleared_s, cleared_v = e_a.atlas_field_numpy()
    assert np.allclose(cleared_s, 0.0) and np.allclose(cleared_v, 0.0)

    # Spinor B3 vector projection path stays finite.
    spin_b3 = core.QFGEngine3D(core.EngineConfig(
        grid_size=8, domain_length=6.0, dt=0.001, backend="NUMPY", field_mode="SPINOR",
        thermal_enabled=False, damping=0.0,
    ))
    spin_b3.add_actor(core.ActorSpec(actor_type="GAUSSIAN", radius=1.0, spin_theta=0.7, spin_phi=0.3))
    sb, vb, _ = atlas_field.rasterize_atlas_field(spin_b3.space, b3_sources, b3_cfg)
    spin_b3.set_atlas_field(sb, vb)
    spin_b3.step()
    assert np.all(np.isfinite(spin_b3.psi))


    # B4: a shifted QFG density lobe exerts a deterministic bounded feedback
    # force toward increasing density and an explicit alignment torque.
    n_fb = 16
    L_fb = 8.0
    dx_fb = L_fb / n_fb
    axis_fb = np.linspace(-L_fb / 2.0, L_fb / 2.0, n_fb, endpoint=False)
    Xfb, Yfb, Zfb = np.meshgrid(axis_fb, axis_fb, axis_fb, indexing="ij")
    density_fb = np.exp(-((Xfb - 1.2) ** 2 + Yfb ** 2 + Zfb ** 2) / (2.0 * 0.9 ** 2))
    feedback_source = atlas_feedback.AtlasFeedbackSource(
        name="P_val_1", position=(0.0, 0.0, 0.0), direction=(0.0, 1.0, 0.0),
        orbital_normal=(0.0, 1.0, 0.0), anchor_position=(0.0, 0.0, 0.0),
        anchor_direction=(0.0, 1.0, 0.0), anchor_orbital_normal=(0.0, 1.0, 0.0),
        force_coupling=1.0, torque_coupling=1.0, linear_mobility=1.0,
        angular_mobility=1.0, provenance="SOURCE",
    )
    fb_cfg = atlas_feedback.AtlasFeedbackConfig(
        target_mode="DENSITY_GRADIENT", force_scale=1.0, torque_scale=1.0,
        anchor_strength=0.0, orientation_anchor_strength=0.0,
        orbital_torque_mix=0.0, scene_scale=1.0, dt=0.05,
        max_step=0.02, max_angle_deg=2.0, max_displacement=0.5,
    )
    fb_deltas, fb_summary = atlas_feedback.evaluate_feedback(
        [feedback_source], density=density_fb, domain_length=L_fb, dx=dx_fb, config=fb_cfg,
    )
    assert len(fb_deltas) == 1 and fb_summary.source_count == 1
    fb_delta = fb_deltas[0]
    assert fb_delta.sampled_gradient[0] > 0.0
    assert fb_delta.force[0] > 0.0 and fb_delta.displacement[0] > 0.0
    assert np.linalg.norm(np.asarray(fb_delta.displacement)) <= fb_cfg.max_step + 1e-12
    assert np.linalg.norm(np.asarray(fb_delta.rotation_vector)) <= np.deg2rad(fb_cfg.max_angle_deg) + 1e-12
    assert abs(fb_delta.torque[2]) > 0.0
    assert fb_summary.provenance == "CONDITIONAL"
    assert np.isfinite(fb_summary.total_work_proxy)
    assert abs(fb_summary.total_work_proxy - (fb_summary.force_work_proxy + fb_summary.torque_work_proxy)) < 1e-12

    # B4 uses periodic central differences, consistent with the FFT field box.
    periodic = np.sin(2.0 * np.pi * Xfb / L_fb)
    gx, gy, gz = atlas_feedback.prepare_density_gradient(periodic, dx_fb)
    expected_gx = (np.sin(2.0 * np.pi * (Xfb + dx_fb) / L_fb) - np.sin(2.0 * np.pi * (Xfb - dx_fb) / L_fb)) / (2.0 * dx_fb)
    assert np.allclose(gx, expected_gx, atol=1e-12)
    assert np.allclose(gy, 0.0, atol=1e-12) and np.allclose(gz, 0.0, atol=1e-12)

    # B4 anchor and safety limits prevent runaway displacement.
    displaced_source = atlas_feedback.AtlasFeedbackSource(
        name="Far", position=(0.49, 0.0, 0.0), direction=(1.0, 0.0, 0.0),
        orbital_normal=(0.0, 1.0, 0.0), anchor_position=(0.0, 0.0, 0.0),
        anchor_direction=(1.0, 0.0, 0.0), anchor_orbital_normal=(0.0, 1.0, 0.0),
        force_coupling=100.0, torque_coupling=0.0,
    )
    clip_cfg = atlas_feedback.AtlasFeedbackConfig(
        force_scale=100.0, torque_scale=0.0, anchor_strength=0.0,
        scene_scale=1.0, dt=1.0, max_step=1.0, max_angle_deg=0.0,
        max_displacement=0.5,
    )
    clip_delta, clip_summary = atlas_feedback.evaluate_feedback(
        [displaced_source], density=density_fb, domain_length=L_fb, dx=dx_fb, config=clip_cfg,
    )
    new_pos = np.asarray(displaced_source.position) + np.asarray(clip_delta[0].displacement)
    assert np.linalg.norm(new_pos - np.asarray(displaced_source.anchor_position)) <= 0.5000001
    assert clip_delta[0].anchor_clipped or clip_delta[0].displacement_clipped
    assert clip_summary.clipped_count == 1

    # REJECTED geometry remains audit-only in B4.
    rejected_feedback = atlas_feedback.AtlasFeedbackSource(
        name="Rejected", position=(0, 0, 0), direction=(1, 0, 0), orbital_normal=(0, 1, 0),
        anchor_position=(0, 0, 0), anchor_direction=(1, 0, 0), anchor_orbital_normal=(0, 1, 0),
        provenance="REJECTED",
    )
    rejected_delta, rejected_summary = atlas_feedback.evaluate_feedback(
        [rejected_feedback], density=density_fb, domain_length=L_fb, dx=dx_fb, config=fb_cfg,
    )
    assert len(rejected_delta) == 0 and rejected_summary.source_count == 0

    # Pure Rodrigues helper preserves vector norm and gives the expected 90° rotation.
    rotated = atlas_feedback.rodrigues_rotate((1.0, 0.0, 0.0), (0.0, 0.0, np.pi / 2.0))
    assert np.allclose(rotated, (0.0, 1.0, 0.0), atol=1e-12)

    # B5: captured pair connectivity + shell preservation correct a stretched proposal.
    b5_nodes = [
        atlas_constraints.AtlasConstraintNode(
            name="Core", position=(0.0, 0.0, 0.0), anchor_position=(0.0, 0.0, 0.0),
            movable=False, preserve_radius=False, role="CORE", provenance="SOURCE",
        ),
        atlas_constraints.AtlasConstraintNode(
            name="Val", position=(1.0, 0.0, 0.0), anchor_position=(1.0, 0.0, 0.0),
            movable=True, preserve_radius=True, max_cone_deg=30.0, role="VALENCE", provenance="SOURCE",
        ),
    ]
    b5_pair = atlas_constraints.AtlasDistanceConstraint(
        "Core", "Val", target_distance=1.0, provenance="SOURCE",
    )
    b5_cfg = atlas_constraints.AtlasConstraintConfig(
        iterations=12, distance_stiffness=1.0, shell_stiffness=1.0,
        cone_stiffness=1.0, symmetry_stiffness=1.0, max_correction=0.2,
        convergence_tolerance=1e-9,
    )
    b5_delta, b5_summary = atlas_constraints.project_atlas_constraints(
        b5_nodes, {"Core": (0.0, 0.0, 0.0), "Val": (1.35, 0.0, 0.0)},
        center=(0.0, 0.0, 0.0), distance_constraints=[b5_pair], config=b5_cfg,
    )
    val_pos = np.asarray(next(d.constrained_position for d in b5_delta if d.name == "Val"))
    assert abs(np.linalg.norm(val_pos) - 1.0) < 1e-7
    assert b5_summary.max_pair_error_after < 1e-7
    assert b5_summary.max_shell_error_after < 1e-7
    assert b5_summary.provenance == "CONDITIONAL"

    # B5 angular cone: a 45° proposal is projected inside a 20° admitted cone.
    cone_node = atlas_constraints.AtlasConstraintNode(
        name="Cone", position=(1.0, 0.0, 0.0), anchor_position=(1.0, 0.0, 0.0),
        movable=True, preserve_radius=True, max_cone_deg=20.0, role="VALENCE",
    )
    cone_prop = (np.sqrt(0.5), np.sqrt(0.5), 0.0)
    cone_delta, cone_summary = atlas_constraints.project_atlas_constraints(
        [cone_node], {"Cone": cone_prop}, center=(0.0, 0.0, 0.0),
        config=atlas_constraints.AtlasConstraintConfig(iterations=8, max_correction=1.0, convergence_tolerance=1e-10),
    )
    cone_pos = np.asarray(cone_delta[0].constrained_position)
    cone_angle = np.degrees(np.arccos(np.clip(cone_pos[0] / np.linalg.norm(cone_pos), -1.0, 1.0)))
    assert cone_angle <= 20.000001
    assert cone_summary.max_cone_excess_after_deg < 1e-6

    # B5 C3 symmetry preserves captured azimuths/equivalence but allows the
    # collective polar tilt (and therefore pair angle) to change.
    alpha0 = np.deg2rad(60.0)
    alpha1 = np.deg2rad(50.0)
    az = [0.0, 2.0 * np.pi / 3.0, 4.0 * np.pi / 3.0]
    def arm(alpha, phi, radius=1.0):
        return (radius * np.sin(alpha) * np.cos(phi), radius * np.sin(alpha) * np.sin(phi), radius * np.cos(alpha))
    c3_nodes = [
        atlas_constraints.AtlasConstraintNode(
            name=f"V{i+1}", position=arm(alpha0, phi), anchor_position=arm(alpha0, phi),
            movable=True, preserve_radius=True, max_cone_deg=25.0, symmetry_group="C3",
            role="VALENCE", provenance="SOURCE",
        ) for i, phi in enumerate(az)
    ]
    # Deliberately perturb both polar tilt and azimuth around a new collective
    # tilt.  The projection should restore the captured C3 azimuth pattern at
    # approximately the new mean tilt, not return to alpha0.
    proposals = {
        "V1": arm(np.deg2rad(49.0), az[0] + np.deg2rad(3.0), 1.04),
        "V2": arm(np.deg2rad(51.5), az[1] - np.deg2rad(2.0), 0.97),
        "V3": arm(np.deg2rad(49.5), az[2] + np.deg2rad(1.0), 1.02),
    }
    c3_groups = atlas_constraints.build_symmetry_constraints(c3_nodes, (0.0, 0.0, 0.0))
    assert len(c3_groups) == 1
    c3_delta, c3_summary = atlas_constraints.project_atlas_constraints(
        c3_nodes, proposals, center=(0.0, 0.0, 0.0), symmetry_constraints=c3_groups,
        config=atlas_constraints.AtlasConstraintConfig(
            iterations=20, shell_stiffness=1.0, cone_stiffness=1.0,
            symmetry_stiffness=1.0, max_correction=0.25, convergence_tolerance=1e-9,
        ),
    )
    c3_pos = {d.name: np.asarray(d.constrained_position) for d in c3_delta}
    dirs = [c3_pos[f"V{i+1}"] / np.linalg.norm(c3_pos[f"V{i+1}"]) for i in range(3)]
    pair_angles = []
    for i in range(3):
        for j in range(i + 1, 3):
            pair_angles.append(np.degrees(np.arccos(np.clip(np.dot(dirs[i], dirs[j]), -1.0, 1.0))))
    assert np.std(pair_angles) < 1e-6
    anchor_dirs = [np.asarray(arm(alpha0, phi)) for phi in az]
    anchor_pair = np.degrees(np.arccos(np.clip(np.dot(anchor_dirs[0], anchor_dirs[1]), -1.0, 1.0)))
    assert abs(np.mean(pair_angles) - anchor_pair) > 1.0  # collective tilt really remained free
    assert c3_summary.max_shell_error_after < 1e-6
    assert c3_summary.symmetry_group_count == 1

    # REJECTED nodes cannot enter B5 projection.
    rejected_b5 = atlas_constraints.AtlasConstraintNode(
        name="Rejected", position=(1, 0, 0), anchor_position=(1, 0, 0), provenance="REJECTED",
    )
    rd, rs = atlas_constraints.project_atlas_constraints(
        [rejected_b5], {"Rejected": (2, 0, 0)}, center=(0, 0, 0), config=b5_cfg,
    )
    assert len(rd) == 0 and rs.node_count == 0


    # B6: convergence is determined from prediction trajectory only.
    b6_cfg = atlas_blind.BlindRelaxationConfig(
        max_iterations=80, min_iterations=12, convergence_window=8,
        angle_window_tolerance_deg=0.025,
        angle_slope_tolerance_deg_per_iter=0.004,
        spread_tolerance_deg=0.02,
    )
    b6_samples = []
    for i in range(1, 61):
        angle = 96.0 + 8.0 * np.exp(-i / 6.0)
        spread = 0.3 * np.exp(-i / 5.0)
        b6_samples.append(atlas_blind.BlindRelaxationSample(
            iteration=i, qfg_time=0.01 * i, mean_pair_angle_deg=float(angle),
            std_pair_angle_deg=float(spread), min_pair_angle_deg=float(angle - spread),
            max_pair_angle_deg=float(angle + spread), c3v_height_ratio=0.5,
            max_constraint_correction=float(0.01 * np.exp(-i / 5.0)),
        ))
    b6_summary = atlas_blind.evaluate_blind_convergence(b6_samples, b6_cfg)
    assert b6_summary.converged
    assert b6_summary.window_angle_range_deg < b6_cfg.angle_window_tolerance_deg
    assert abs(b6_summary.window_angle_slope_deg_per_iter) < b6_cfg.angle_slope_tolerance_deg_per_iter
    assert b6_summary.provenance == "CONDITIONAL"

    # A persistent oscillation must not pass the blind convergence gate.
    oscillating = [atlas_blind.BlindRelaxationSample(
        iteration=i, qfg_time=float(i), mean_pair_angle_deg=95.0 + 0.2 * ((-1) ** i),
        std_pair_angle_deg=0.005, min_pair_angle_deg=94.99, max_pair_angle_deg=95.01,
    ) for i in range(1, 30)]
    osc_summary = atlas_blind.evaluate_blind_convergence(oscillating, b6_cfg)
    assert not osc_summary.converged

    # Fingerprints are deterministic and change when protocol settings change.
    fp_a = atlas_blind.protocol_fingerprint({"element": "P", "steps": 1, "source": [1, 2, 3]})
    fp_b = atlas_blind.protocol_fingerprint({"source": [1, 2, 3], "steps": 1, "element": "P"})
    fp_c = atlas_blind.protocol_fingerprint({"element": "P", "steps": 2, "source": [1, 2, 3]})
    assert fp_a == fp_b and fp_a != fp_c and len(fp_a) == 64

    # Frozen-comparison provenance can record a conditional B6 prediction.
    conditional_cmp = atlas_geometry.compare_frozen_prediction(93.3, "P", prediction_provenance="CONDITIONAL")
    assert conditional_cmp["prediction_provenance"] == "CONDITIONAL"

    print("QFG Dynamics 1.0.0 Alpha pure numerical + Atlas B6 blind-relaxation regression tests: PASS")


if __name__ == "__main__":
    main()
