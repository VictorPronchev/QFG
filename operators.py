"""Blender operators for QFG Lab 5.2."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import sys
import traceback
import numpy as np
import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Matrix, Quaternion, Vector

from . import runtime
from .atlas_geometry import (
    analyze_valence_vectors, compare_frozen_prediction, reference_for_element,
)
from .atlas_b2 import (
    InteractionNode, analyze_orbital_planes, build_interaction_graph,
    estimate_integrated_bohr_envelope, infer_nucleon_from_name,
)
from .atlas_field import AtlasFieldConfig, AtlasFieldSource, rasterize_atlas_field
from .atlas_feedback import AtlasFeedbackConfig, AtlasFeedbackSource, evaluate_feedback
from .atlas_constraints import (
    AtlasConstraintConfig, AtlasConstraintNode, AtlasDistanceConstraint, AtlasSymmetryConstraint,
    build_symmetry_constraints, project_atlas_constraints,
)
from .atlas_blind import (
    BlindRelaxationConfig, BlindRelaxationSample, evaluate_blind_convergence, protocol_fingerprint,
)
from .core import ActorSpec, EngineConfig, QFGEngine3D
from .dynamics import BodySpec, QFGWorld, WorldConfig
from .diagnostics import (
    save_snapshot_npz, timestamped_directory, write_diagnostics_csv,
    write_json, write_rows_csv,
)
from .experiments import (
    CavityShiftConfig, HRMScanConfig, MEMSConfig, PlasmaConfig,
    cavity_shift_sweep, hrm_scan, mems_geometry_sweep,
    simulate_glow_plasma, validation_program_summary,
)
from .molecular import (
    AtomSpec, MolecularProxyConfig, MolecularTarget, OptimizationConfig,
    infer_bonds, molecule_preset, optimize_geometry, proxy_energy,
)
from .presets import PRESETS
from .showcase import (
    MODE_CONFIG as SHOWCASE_MODE_CONFIG, apply_mode_settings, build_stage,
    prepare_field_renderer, render_still,
)
from .rom import ROMConfig, hysteresis
from .yb import (
    YbConfig, q_factor_sweep, simulate_odmr_sweep, simulate_rabi,
    simulate_ramsey, two_ion_phase_proxy,
)
from .visualization import (
    DISPLAY_OBJECT_NAME, SLICE_IMAGE_NAME, central_slice, create_bond_curves,
    create_curve_plot, create_image_plane, create_orbital_plane_rings, density_to_points,
    update_display_object, update_named_heatmap, update_slice_image,
)

ACTOR_COLLECTION = "QFG Actors"
MOLECULE_COLLECTION = "QFG Molecule"


def scene_config(settings) -> EngineConfig:
    return EngineConfig(
        grid_size=int(settings.grid_size), domain_length=settings.domain_length,
        dt=settings.dt, rho0=settings.rho0,
        lambda_cohesion=settings.lambda_cohesion,
        kappa_stability=settings.kappa_stability,
        alpha_dielectric=settings.alpha_dielectric, zeta_em=settings.zeta_em,
        damping=settings.damping, delta_anisotropy=settings.delta_anisotropy,
        field_mode=settings.field_mode, backend=settings.backend,
        thermal_enabled=settings.thermal_enabled,
        heat_conduction=settings.heat_conduction,
        collision_heating=settings.collision_heating,
        critical_temperature=settings.critical_temperature,
        temperature_cap=settings.temperature_cap,
        hrm_enabled=settings.hrm_enabled, drive_a1=settings.drive_a1,
        drive_a2=settings.drive_a2, drive_f1=settings.drive_f1,
        drive_f2=settings.drive_f2, drive_profile=settings.drive_profile,
        drive_width=settings.drive_width,
        topology_enabled=settings.topology_enabled,
        spin_exchange=settings.spin_exchange,
        skyrme_potential_scale=settings.skyrme_potential_scale,
        external_b=tuple(float(v) for v in settings.external_b),
        gauge_enabled=settings.gauge_enabled,
        gauge_coupling=settings.gauge_coupling,
        gauge_damping=settings.gauge_damping,
        gauge_wave_speed=settings.gauge_wave_speed,
        gauge_backreaction=settings.gauge_backreaction,
        gravity_enabled=settings.gravity_enabled,
        gravity_strength=settings.gravity_strength,
        gravity_backreaction=settings.gravity_backreaction,
        noise_enabled=settings.noise_enabled,
        noise_amplitude=settings.noise_amplitude,
        noise_seed=settings.noise_seed,
    )


def actor_from_object(obj: bpy.types.Object) -> ActorSpec:
    props = obj.qfg_actor
    return ActorSpec(
        actor_type=props.actor_type,
        center=tuple(float(v) for v in obj.matrix_world.translation),
        velocity=tuple(float(v) for v in props.velocity),
        radius=float(props.radius), intensity=float(props.intensity),
        spin_theta=float(props.spin_theta), spin_phi=float(props.spin_phi),
        winding_m=int(props.winding_m), winding_n=int(props.winding_n),
        ring_radius=float(props.ring_radius),
        boundary_shape=props.boundary_shape,
        boundary_size=tuple(float(max(v, 1e-4)) for v in obj.dimensions),
        boundary_potential=float(props.boundary_potential),
        boundary_damping=float(props.boundary_damping), name=obj.name,
    )


def world_config(settings) -> WorldConfig:
    return WorldConfig(
        substeps=int(settings.dynamics_substeps),
        gravity=tuple(float(v) for v in settings.dynamics_gravity),
        floor_height=float(settings.dynamics_floor_height),
        body_collisions=bool(settings.dynamics_body_collisions),
        deterministic=bool(settings.dynamics_deterministic),
        seed=int(settings.dynamics_seed),
        max_body_speed=float(settings.dynamics_max_speed),
        max_angular_speed=float(settings.dynamics_max_angular_speed),
        field_force_scale=float(settings.dynamics_field_force_scale),
        thermal_force_scale=float(settings.dynamics_thermal_force_scale),
        field_torque_scale=float(settings.dynamics_field_torque_scale),
        field_event_threshold=float(settings.dynamics_field_event_threshold),
        contact_event_threshold=float(settings.dynamics_contact_event_threshold),
        penetration_slop=float(settings.dynamics_penetration_slop),
        position_correction=float(settings.dynamics_position_correction),
    )


def body_from_object(obj: bpy.types.Object) -> BodySpec:
    p = obj.qfg_actor
    q = obj.matrix_world.to_quaternion()
    return BodySpec(
        name=obj.name,
        position=tuple(float(v) for v in obj.matrix_world.translation),
        velocity=tuple(float(v) for v in p.velocity),
        orientation=(float(q.w), float(q.x), float(q.y), float(q.z)),
        angular_velocity=tuple(float(v) for v in p.angular_velocity),
        mass=float(p.body_mass),
        radius=float(p.collision_radius),
        collision_shape=str(p.collision_shape),
        half_extents=tuple(float(v) for v in p.collision_half_extents),
        field_coupling=float(p.field_coupling),
        thermal_coupling=float(p.thermal_coupling),
        field_torque_coupling=float(p.field_torque_coupling),
        external_torque=tuple(float(v) for v in p.external_torque),
        linear_drag=float(p.linear_drag),
        angular_drag=float(p.angular_drag),
        restitution=float(p.restitution),
        friction=float(p.friction),
        kinematic=bool(p.kinematic_body),
        phase_transition_temperature=float(p.phase_transition_temperature),
    )


def update_dynamics_metrics(settings, profile) -> None:
    settings.last_field_ms = float(profile.field_ms)
    settings.last_body_ms = float(profile.body_ms)
    settings.last_query_ms = float(profile.query_ms)
    settings.last_total_ms = float(profile.total_ms)
    settings.last_body_count = int(profile.body_count)
    settings.last_contact_count = int(profile.contact_count)
    settings.last_event_count = int(profile.event_count)
    settings.last_kinetic_energy = float(getattr(profile, "kinetic_energy", 0.0))
    settings.last_linear_kinetic_energy = float(getattr(profile, "linear_kinetic_energy", 0.0))
    settings.last_rotational_kinetic_energy = float(getattr(profile, "rotational_kinetic_energy", 0.0))
    settings.last_mean_force = float(getattr(profile, "mean_force", 0.0))
    settings.last_max_force = float(getattr(profile, "max_force", 0.0))
    settings.last_mean_torque = float(getattr(profile, "mean_torque", 0.0))
    settings.last_max_torque = float(getattr(profile, "max_torque", 0.0))


def update_world_telemetry(settings, telemetry: Dict[str, Any]) -> None:
    momentum = telemetry.get("momentum", (0.0, 0.0, 0.0))
    angular = telemetry.get("angular_momentum", (0.0, 0.0, 0.0))
    settings.last_body_momentum = tuple(float(v) for v in momentum)
    settings.last_body_angular_momentum = tuple(float(v) for v in angular)
    settings.last_active_body_contacts = int(telemetry.get("active_body_contacts", 0))
    settings.last_active_floor_contacts = int(telemetry.get("active_floor_contacts", 0))


def apply_body_state(scene: bpy.types.Scene, body_state: Dict[str, Any]) -> None:
    names = body_state.get("names", [])
    positions = np.asarray(body_state.get("positions", []), dtype=np.float64)
    velocities = np.asarray(body_state.get("velocities", []), dtype=np.float64)
    orientations = np.asarray(body_state.get("orientations", []), dtype=np.float64)
    angular_velocities = np.asarray(body_state.get("angular_velocities", []), dtype=np.float64)
    temperatures = np.asarray(body_state.get("temperature", []), dtype=np.float64)
    force_field = np.asarray(body_state.get("force_field", []), dtype=np.float64)
    force_thermal = np.asarray(body_state.get("force_thermal", []), dtype=np.float64)
    force_gravity = np.asarray(body_state.get("force_gravity", []), dtype=np.float64)
    force_drag = np.asarray(body_state.get("force_drag", []), dtype=np.float64)
    force_contact = np.asarray(body_state.get("force_contact", []), dtype=np.float64)
    force_total = np.asarray(body_state.get("force_total", []), dtype=np.float64)
    torque_external = np.asarray(body_state.get("torque_external", []), dtype=np.float64)
    torque_field = np.asarray(body_state.get("torque_field", []), dtype=np.float64)
    torque_drag = np.asarray(body_state.get("torque_drag", []), dtype=np.float64)
    torque_contact = np.asarray(body_state.get("torque_contact", []), dtype=np.float64)
    torque_total = np.asarray(body_state.get("torque_total", []), dtype=np.float64)
    contact_impulse = np.asarray(body_state.get("contact_impulse", []), dtype=np.float64)
    contact_angular_impulse = np.asarray(body_state.get("contact_angular_impulse", []), dtype=np.float64)
    phases = body_state.get("phase_state", [])
    shapes = body_state.get("collision_shapes", [])
    for index, name in enumerate(names):
        obj = scene.objects.get(name)
        if obj is None:
            continue
        if index < len(positions):
            obj.location = tuple(float(v) for v in positions[index])
        if index < len(orientations) and len(orientations[index]) == 4:
            q = orientations[index]
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        if index < len(velocities):
            obj["qfg_velocity"] = tuple(float(v) for v in velocities[index])
        if index < len(angular_velocities):
            obj["qfg_angular_velocity"] = tuple(float(v) for v in angular_velocities[index])
        if index < len(temperatures):
            obj["qfg_temperature"] = float(temperatures[index])
        if index < len(shapes):
            obj["qfg_collision_shape"] = str(shapes[index])
        for key, values in (
            ("qfg_force_field", force_field),
            ("qfg_force_thermal", force_thermal),
            ("qfg_force_gravity", force_gravity),
            ("qfg_force_drag", force_drag),
            ("qfg_force_contact", force_contact),
            ("qfg_force_total", force_total),
            ("qfg_torque_external", torque_external),
            ("qfg_torque_field", torque_field),
            ("qfg_torque_drag", torque_drag),
            ("qfg_torque_contact", torque_contact),
            ("qfg_torque_total", torque_total),
            ("qfg_contact_impulse", contact_impulse),
            ("qfg_contact_angular_impulse", contact_angular_impulse),
        ):
            if index < len(values):
                obj[key] = tuple(float(v) for v in values[index])
        if index < len(phases):
            obj["qfg_phase_state"] = str(phases[index])

def update_metrics(settings, diagnostics) -> None:
    settings.last_time = diagnostics.time
    settings.last_max_density = diagnostics.max_density
    settings.last_norm = diagnostics.norm
    settings.last_mode_variance = diagnostics.mode_variance
    settings.last_energy = diagnostics.energy_proxy
    settings.last_temperature = diagnostics.max_temperature
    settings.last_gauge_energy = diagnostics.gauge_energy
    settings.last_gravity_energy = diagnostics.gravity_energy
    settings.last_atlas_energy = getattr(diagnostics, "atlas_scalar_energy", 0.0)
    settings.last_momentum = (
        diagnostics.momentum_x, diagnostics.momentum_y, diagnostics.momentum_z,
    )


def update_visuals(scene: bpy.types.Scene) -> None:
    if runtime.engine is None:
        return
    settings = scene.qfg_settings
    density = runtime.engine.density()
    points, weights = density_to_points(
        density, settings.domain_length, settings.threshold_fraction,
        settings.max_points,
    )
    update_display_object(scene, points, weights, settings.point_radius)
    update_slice_image(central_slice(density, settings.slice_axis))


def initialize_engine(scene: bpy.types.Scene) -> Tuple[QFGEngine3D, int]:
    settings = scene.qfg_settings
    field_specs: List[ActorSpec] = []
    body_specs: List[BodySpec] = []
    for obj in scene.objects:
        if not hasattr(obj, "qfg_actor") or not obj.qfg_actor.enabled:
            continue
        actor_type = obj.qfg_actor.actor_type
        if actor_type in {"GAUSSIAN", "HOPF_RING", "VORTEX", "PLANE_WAVE", "BOUNDARY"}:
            field_specs.append(actor_from_object(obj))
        elif actor_type == "DYNAMIC_BODY":
            body_specs.append(body_from_object(obj))

    if settings.dynamics_enabled:
        world = QFGWorld(scene_config(settings), world_config(settings))
        for spec in field_specs:
            world.add_field_actor(spec)
        for spec in body_specs:
            world.add_body(spec)
        runtime.world = world
        runtime.engine = world.engine
        settings.status = (
            f"Initialized QFGWorld with {len(field_specs)} field actors and "
            f"{len(body_specs)} dynamic bodies"
        )
    else:
        engine = QFGEngine3D(scene_config(settings))
        for spec in field_specs:
            engine.add_actor(spec)
        runtime.world = None
        runtime.engine = engine
        settings.status = f"Initialized with {len(field_specs)} field actors"

    engine = runtime.engine
    if settings.atlas_field_enabled and settings.atlas_field_auto_apply:
        try:
            apply_atlas_field_to_engine(scene, engine)
        except Exception as exc:
            settings.atlas_field_status = f"B3 auto-apply skipped: {exc}"
            runtime.last_atlas_field = None
    elif engine is not None:
        engine.clear_atlas_field()
        runtime.last_atlas_field = None

    runtime.cache.clear()
    settings.backend_status = f"{engine.backend_name} / {engine.device}"
    diag = engine.compute_diagnostics()
    update_metrics(settings, diag)
    if runtime.world is not None:
        settings.last_body_count = len(runtime.world.bodies)
        initial_state = runtime.world.body_snapshot()
        apply_body_state(scene, initial_state)
        telemetry = runtime.world.telemetry()
        update_world_telemetry(settings, telemetry)
        runtime.debug_payload = {
            "source": "LIVE", "requested_frame": scene.frame_current,
            "displayed_frame": scene.frame_current, "body_state": initial_state,
            "telemetry": telemetry, "events": [],
        }
    else:
        settings.last_body_count = 0
        settings.last_active_body_contacts = 0
        settings.last_active_floor_contacts = 0
        runtime.debug_payload = None
    update_visuals(scene)
    return engine, len(field_specs)


def ensure_collection(scene: bpy.types.Scene, name: str):
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        scene.collection.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    collection.objects.link(obj)


def clear_collection(name: str) -> None:
    collection = bpy.data.collections.get(name)
    if collection is None:
        return
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def add_uv_sphere(scene, name, location, scale=(1.0, 1.0, 1.0), collection_name=ACTOR_COLLECTION):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    move_to_collection(obj, ensure_collection(scene, collection_name))
    return obj


def add_torus(scene, name, location, major_radius=2.0, minor_radius=0.35):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius, minor_radius=minor_radius,
        major_segments=48, minor_segments=12, location=location,
    )
    obj = bpy.context.active_object
    obj.name = name
    move_to_collection(obj, ensure_collection(scene, ACTOR_COLLECTION))
    return obj


def add_cube(scene, name, location, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    move_to_collection(obj, ensure_collection(scene, ACTOR_COLLECTION))
    return obj


def configure_editor_proxy(obj: bpy.types.Object) -> bpy.types.Object:
    """Keep QFG authoring meshes visible in the editor but out of final renders.

    The calculated field is rendered through ``QFG_Field_Points``. Gaussian,
    Hopf, vortex and boundary meshes are editor gizmos. Rendering a broad
    Gaussian proxy can put the camera inside an opaque sphere and cover the
    entire image with a pale blue/grey surface.
    """
    obj.display_type = "WIRE"
    obj.show_in_front = True
    obj.hide_render = True
    return obj


def molecule_atoms_from_scene(scene) -> Tuple[List[AtomSpec], List[bpy.types.Object]]:
    atoms: List[AtomSpec] = []
    objects: List[bpy.types.Object] = []
    for obj in scene.objects:
        if not hasattr(obj, "qfg_actor"):
            continue
        p = obj.qfg_actor
        if p.enabled and p.actor_type == "MOLECULE_ATOM":
            atoms.append(AtomSpec(
                name=obj.name, atomic_number=p.atomic_number,
                position=tuple(float(v) for v in obj.matrix_world.translation),
                charge=p.atomic_charge, covalent_radius=p.covalent_radius,
            ))
            objects.append(obj)
    return atoms, objects


def molecular_config(s) -> MolecularProxyConfig:
    return MolecularProxyConfig(
        coulomb_scale=s.mol_coulomb_scale,
        overlap_scale=s.mol_overlap_scale,
        gradient_scale=s.mol_gradient_scale,
        kinetic_scale=s.mol_kinetic_scale,
        topology_scale=s.mol_topology_scale,
        softening=s.mol_softening,
        bond_tolerance=s.mol_bond_tolerance,
        bond_stiffness=s.mol_bond_stiffness,
    )


def atlas_objects(scene, role: str | None = None) -> List[bpy.types.Object]:
    objects: List[bpy.types.Object] = []
    for obj in scene.objects:
        if not hasattr(obj, "qfg_actor"):
            continue
        p = obj.qfg_actor
        if not (p.enabled and p.actor_type == "ATLAS_NUCLEON"):
            continue
        if role is not None and p.atlas_role != role:
            continue
        objects.append(obj)
    return objects


def atlas_center(scene, settings) -> np.ndarray:
    if settings.atlas_center_mode == "WORLD_ORIGIN":
        return np.zeros(3, dtype=np.float64)
    if settings.atlas_center_mode == "CENTER_OBJECT":
        obj = settings.atlas_center_object
        if obj is None:
            raise ValueError("Atlas center mode is CENTER_OBJECT but no center object is assigned")
        return np.asarray(tuple(float(v) for v in obj.matrix_world.translation), dtype=np.float64)

    core = atlas_objects(scene, "CORE")
    if not core:
        raise ValueError("No Atlas CORE objects tagged; tag the nucleus core or choose another center mode")
    positions = np.asarray([tuple(float(v) for v in obj.matrix_world.translation) for obj in core], dtype=np.float64)
    return np.mean(positions, axis=0)


def atlas_object_direction(obj: bpy.types.Object, center: np.ndarray) -> np.ndarray:
    mode = obj.qfg_actor.atlas_direction_mode
    if mode == "RADIAL":
        vector = np.asarray(tuple(float(v) for v in obj.matrix_world.translation), dtype=np.float64) - center
    else:
        axis_index = {"LOCAL_X": 0, "LOCAL_Y": 1, "LOCAL_Z": 2, "NEG_X": 0, "NEG_Y": 1, "NEG_Z": 2}[mode]
        sign = -1.0 if mode.startswith("NEG_") else 1.0
        column = obj.matrix_world.to_3x3().col[axis_index]
        vector = sign * np.asarray(tuple(float(v) for v in column), dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError(f"Atlas valence direction for {obj.name!r} has zero length")
    return vector


def extract_atlas_geometry(scene):
    settings = scene.qfg_settings
    valence = atlas_objects(scene, "VALENCE")
    if len(valence) < 2:
        raise ValueError("Tag at least two Atlas nucleons as Free valence")
    center = atlas_center(scene, settings)
    vectors = [atlas_object_direction(obj, center) for obj in valence]
    result = analyze_valence_vectors(
        vectors, names=[obj.name for obj in valence], element=settings.atlas_element, provenance="DERIVED",
    )
    return result, center, valence




def atlas_safe_direction(obj: bpy.types.Object, center: np.ndarray) -> np.ndarray:
    """Return an Atlas direction, falling back to local +Z for center objects."""
    try:
        return atlas_object_direction(obj, center)
    except ValueError:
        column = obj.matrix_world.to_3x3().col[2]
        vector = np.asarray(tuple(float(v) for v in column), dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if norm <= 1e-12:
            return np.array((0.0, 0.0, 1.0), dtype=np.float64)
        return vector / norm


def atlas_orbital_normal(obj: bpy.types.Object, center: np.ndarray) -> Tuple[np.ndarray, str]:
    mode = obj.qfg_actor.atlas_orbital_normal_mode
    if mode == "VALENCE_VECTOR":
        return atlas_safe_direction(obj, center), "CONDITIONAL"
    axis_index = {"LOCAL_X": 0, "LOCAL_Y": 1, "LOCAL_Z": 2, "NEG_X": 0, "NEG_Y": 1, "NEG_Z": 2}[mode]
    sign = -1.0 if mode.startswith("NEG_") else 1.0
    column = obj.matrix_world.to_3x3().col[axis_index]
    vector = sign * np.asarray(tuple(float(v) for v in column), dtype=np.float64)
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError(f"Orbital-plane normal for {obj.name!r} has zero length")
    provenance = "SOURCE" if obj.qfg_actor.atlas_provenance == "SOURCE" else "DERIVED"
    return vector / norm, provenance


def atlas_object_radius(obj: bpy.types.Object, settings) -> float:
    mode = settings.atlas_bohr_radius_mode
    if mode == "POINTS_ONLY":
        return 0.0
    if mode == "FIXED":
        return float(settings.atlas_bohr_fixed_radius)
    dims = np.asarray(tuple(abs(float(v)) for v in obj.dimensions), dtype=np.float64)
    return 0.5 * float(np.max(dims)) if dims.size else 0.0


def atlas_graph_nodes(scene, settings) -> Tuple[List[InteractionNode], List[bpy.types.Object], np.ndarray]:
    center = atlas_center(scene, settings)
    objects = atlas_objects(scene)
    topology = settings.atlas_graph_topology
    if topology == "SOURCE_STAR":
        objects = [obj for obj in objects if obj.qfg_actor.atlas_role in {"VALENCE", "EQUATORIAL"}]
    elif topology == "VALENCE_ONLY":
        objects = [obj for obj in objects if obj.qfg_actor.atlas_role == "VALENCE"]
    if len(objects) < 2:
        raise ValueError("Not enough tagged Atlas objects for the selected graph topology")
    nodes: List[InteractionNode] = []
    for obj in objects:
        p = obj.qfg_actor
        position = tuple(float(v) for v in obj.matrix_world.translation)
        direction = tuple(float(v) for v in atlas_safe_direction(obj, center))
        nodes.append(InteractionNode(
            name=obj.name,
            position=position,
            direction=direction,
            role=p.atlas_role,
            nucleon_type=p.atlas_nucleon_type,
            provenance=p.atlas_provenance,
        ))
    return nodes, objects, center


def atlas_field_config(settings) -> AtlasFieldConfig:
    return AtlasFieldConfig(
        kernel=settings.atlas_field_kernel,
        vector_mode=settings.atlas_field_vector_mode,
        softening=float(settings.atlas_field_softening),
        scalar_scale=float(settings.atlas_field_scalar_scale),
        vector_scale=float(settings.atlas_field_vector_scale),
        orbital_mix=float(settings.atlas_field_orbital_mix),
        scene_scale=float(settings.atlas_field_scene_scale),
        clip_abs=float(settings.atlas_field_clip_abs),
    )


def atlas_field_sources(scene, settings) -> Tuple[List[AtlasFieldSource], List[bpy.types.Object]]:
    if settings.atlas_field_source_scope == "SOURCE_ONLY":
        allowed_provenance = {"SOURCE"}
    elif settings.atlas_field_source_scope == "SOURCE_DERIVED":
        allowed_provenance = {"SOURCE", "DERIVED"}
    else:
        allowed_provenance = {"SOURCE", "DERIVED", "CONDITIONAL", "CALIBRATED", "EXPERIMENTAL"}

    if settings.atlas_field_role_scope == "VALENCE_EQ":
        allowed_roles = {"VALENCE", "EQUATORIAL"}
    elif settings.atlas_field_role_scope == "VALENCE":
        allowed_roles = {"VALENCE"}
    else:
        allowed_roles = {"CORE", "VALENCE", "BOUND", "EQUATORIAL", "OTHER"}

    center = atlas_center(scene, settings)
    sources: List[AtlasFieldSource] = []
    objects: List[bpy.types.Object] = []
    for obj in atlas_objects(scene):
        p = obj.qfg_actor
        if not p.atlas_field_enabled:
            continue
        if p.atlas_provenance not in allowed_provenance or p.atlas_provenance == "REJECTED":
            continue
        if p.atlas_role not in allowed_roles:
            continue
        direction = atlas_safe_direction(obj, center)
        normal, normal_provenance = atlas_orbital_normal(obj, center)
        provenance = p.atlas_provenance
        # A valence-vector convenience normal is itself a conditional bridge.
        if normal_provenance == "CONDITIONAL" and provenance == "SOURCE":
            provenance = "CONDITIONAL"
        sources.append(AtlasFieldSource(
            name=obj.name,
            position=tuple(float(v) for v in obj.matrix_world.translation),
            direction=tuple(float(v) for v in direction),
            orbital_normal=tuple(float(v) for v in normal),
            strength=float(p.atlas_field_strength),
            radius=float(p.atlas_field_radius),
            anisotropy=float(p.atlas_field_anisotropy),
            role=p.atlas_role,
            nucleon_type=p.atlas_nucleon_type,
            provenance=provenance,
        ))
        objects.append(obj)
    return sources, objects


def apply_atlas_field_to_engine(scene, engine: QFGEngine3D | None = None) -> Dict[str, Any]:
    settings = scene.qfg_settings
    target = engine or runtime.engine
    if target is None:
        raise ValueError("Initialize the QFG engine before applying the B3 Atlas field")
    sources, objects = atlas_field_sources(scene, settings)
    if not sources:
        raise ValueError("No Atlas sources pass the current B3 provenance/role filters")
    cfg = atlas_field_config(settings)
    scalar, vector, summary = rasterize_atlas_field(target.space, sources, cfg)
    payload = {
        "summary": summary.to_dict(),
        "config": asdict(cfg),
        "sources": [src.to_dict() for src in sources],
        "field_mode": target.config.field_mode,
        "grid_size": int(target.N),
        "domain_length": float(target.L),
        "provenance": "CONDITIONAL",
        "note": (
            "B3 Atlas field is a reduced dimensionless bridge. Source geometry is audited, "
            "but kernel/anisotropy/strength normalization are not claimed as first-principles BSM-SG energy laws."
        ),
    }
    target.set_atlas_field(scalar, vector, metadata=payload)
    runtime.last_atlas_field = payload
    settings.atlas_field_source_count = int(summary.source_count)
    settings.atlas_field_scalar_min = float(summary.scalar_min)
    settings.atlas_field_scalar_max = float(summary.scalar_max)
    settings.atlas_field_scalar_rms = float(summary.scalar_rms)
    settings.atlas_field_vector_max = float(summary.vector_max)
    settings.atlas_field_vector_rms = float(summary.vector_rms)
    settings.atlas_field_status = (
        f"CONDITIONAL B3: {summary.source_count} source(s), "
        f"V=[{summary.scalar_min:.3g},{summary.scalar_max:.3g}], |B|max={summary.vector_max:.3g}"
    )
    mid = scalar.shape[2] // 2
    update_named_heatmap("QFG_Atlas_Field_Slice", scalar[:, :, mid])
    for obj in objects:
        obj["qfg_b3_field_applied"] = True
        obj["qfg_b3_field_provenance"] = "CONDITIONAL"
    return payload



def _compose_world_matrix(location, rotation, scale):
    scale_matrix = Matrix.Diagonal((float(scale[0]), float(scale[1]), float(scale[2]), 1.0))
    return Matrix.Translation(Vector(location)) @ rotation.to_matrix().to_4x4() @ scale_matrix


def capture_atlas_feedback_anchors(scene) -> int:
    """Capture current reviewed Atlas geometry as the B4 relaxation anchor."""
    settings = scene.qfg_settings
    center = atlas_center(scene, settings)
    count = 0
    for obj in atlas_objects(scene):
        p = obj.qfg_actor
        if not p.atlas_feedback_enabled or p.atlas_provenance == "REJECTED":
            continue
        direction = atlas_safe_direction(obj, center)
        normal, _ = atlas_orbital_normal(obj, center)
        loc, rot, scale = obj.matrix_world.decompose()
        obj["qfg_b4_anchor_position"] = tuple(float(v) for v in loc)
        obj["qfg_b4_anchor_quaternion"] = (float(rot.w), float(rot.x), float(rot.y), float(rot.z))
        obj["qfg_b4_anchor_scale"] = tuple(float(v) for v in scale)
        obj["qfg_b4_anchor_direction"] = tuple(float(v) for v in direction)
        obj["qfg_b4_anchor_orbital_normal"] = tuple(float(v) for v in normal)
        obj["qfg_b4_anchor_captured"] = True
        count += 1
    settings.atlas_feedback_status = f"B4 anchors captured for {count} Atlas source(s)"
    return count


def reset_atlas_feedback_anchors(scene) -> int:
    count = 0
    for obj in atlas_objects(scene):
        if not bool(obj.get("qfg_b4_anchor_captured", False)):
            continue
        position = tuple(float(v) for v in obj.get("qfg_b4_anchor_position", (0.0, 0.0, 0.0)))
        q = tuple(float(v) for v in obj.get("qfg_b4_anchor_quaternion", (1.0, 0.0, 0.0, 0.0)))
        scale = tuple(float(v) for v in obj.get("qfg_b4_anchor_scale", (1.0, 1.0, 1.0)))
        obj.matrix_world = _compose_world_matrix(position, Quaternion(q), scale)
        obj["qfg_b4_last_force"] = (0.0, 0.0, 0.0)
        obj["qfg_b4_last_torque"] = (0.0, 0.0, 0.0)
        count += 1
    scene.qfg_settings.atlas_feedback_status = f"B4 reset {count} Atlas source(s) to captured anchors"
    return count


def atlas_state_snapshot(scene) -> Dict[str, Any]:
    names, positions, orientations, scales = [], [], [], []
    for obj in atlas_objects(scene):
        loc, rot, scale = obj.matrix_world.decompose()
        names.append(obj.name)
        positions.append(tuple(float(v) for v in loc))
        orientations.append((float(rot.w), float(rot.x), float(rot.y), float(rot.z)))
        scales.append(tuple(float(v) for v in scale))
    return {
        "names": names,
        "positions": np.asarray(positions, dtype=np.float32),
        "orientations": np.asarray(orientations, dtype=np.float32),
        "scales": np.asarray(scales, dtype=np.float32),
    }


def apply_atlas_state(scene, state: Dict[str, Any]) -> None:
    names = list(state.get("names", []))
    positions = np.asarray(state.get("positions", []), dtype=np.float64)
    orientations = np.asarray(state.get("orientations", []), dtype=np.float64)
    scales = np.asarray(state.get("scales", []), dtype=np.float64)
    for index, name in enumerate(names):
        obj = scene.objects.get(name)
        if obj is None or index >= len(positions) or index >= len(orientations) or index >= len(scales):
            continue
        obj.matrix_world = _compose_world_matrix(
            tuple(float(v) for v in positions[index]),
            Quaternion(tuple(float(v) for v in orientations[index])),
            tuple(float(v) for v in scales[index]),
        )


def atlas_feedback_config(settings, dt: float) -> AtlasFeedbackConfig:
    return AtlasFeedbackConfig(
        target_mode=settings.atlas_feedback_target_mode,
        force_scale=float(settings.atlas_feedback_force_scale),
        torque_scale=float(settings.atlas_feedback_torque_scale),
        anchor_strength=float(settings.atlas_feedback_anchor_strength),
        orientation_anchor_strength=float(settings.atlas_feedback_orientation_anchor),
        orbital_torque_mix=float(settings.atlas_feedback_orbital_mix),
        spin_mix=float(settings.atlas_feedback_spin_mix),
        scene_scale=float(settings.atlas_field_scene_scale),
        dt=float(dt),
        max_step=float(settings.atlas_feedback_max_step),
        max_angle_deg=float(settings.atlas_feedback_max_angle),
        max_displacement=float(settings.atlas_feedback_max_displacement),
    )


def atlas_feedback_sources(scene, settings) -> Tuple[List[AtlasFeedbackSource], List[bpy.types.Object]]:
    if settings.atlas_field_source_scope == "SOURCE_ONLY":
        allowed_provenance = {"SOURCE"}
    elif settings.atlas_field_source_scope == "SOURCE_DERIVED":
        allowed_provenance = {"SOURCE", "DERIVED"}
    else:
        allowed_provenance = {"SOURCE", "DERIVED", "CONDITIONAL", "CALIBRATED", "EXPERIMENTAL"}
    if settings.atlas_field_role_scope == "VALENCE_EQ":
        allowed_roles = {"VALENCE", "EQUATORIAL"}
    elif settings.atlas_field_role_scope == "VALENCE":
        allowed_roles = {"VALENCE"}
    else:
        allowed_roles = {"CORE", "VALENCE", "BOUND", "EQUATORIAL", "OTHER"}

    if settings.atlas_feedback_auto_capture:
        missing = [
            obj for obj in atlas_objects(scene)
            if obj.qfg_actor.atlas_feedback_enabled
            and obj.qfg_actor.atlas_provenance in allowed_provenance
            and obj.qfg_actor.atlas_role in allowed_roles
            and not bool(obj.get("qfg_b4_anchor_captured", False))
        ]
        if missing:
            capture_atlas_feedback_anchors(scene)

    center = atlas_center(scene, settings)
    sources: List[AtlasFeedbackSource] = []
    objects: List[bpy.types.Object] = []
    for obj in atlas_objects(scene):
        p = obj.qfg_actor
        if not p.atlas_feedback_enabled or p.atlas_provenance == "REJECTED":
            continue
        if p.atlas_provenance not in allowed_provenance or p.atlas_role not in allowed_roles:
            continue
        if not bool(obj.get("qfg_b4_anchor_captured", False)):
            raise ValueError(f"B4 anchor missing for {obj.name!r}; capture anchors or enable Auto-capture")
        direction = atlas_safe_direction(obj, center)
        normal, normal_provenance = atlas_orbital_normal(obj, center)
        provenance = p.atlas_provenance
        if normal_provenance == "CONDITIONAL" and provenance == "SOURCE":
            provenance = "CONDITIONAL"
        sources.append(AtlasFeedbackSource(
            name=obj.name,
            position=tuple(float(v) for v in obj.matrix_world.translation),
            direction=tuple(float(v) for v in direction),
            orbital_normal=tuple(float(v) for v in normal),
            anchor_position=tuple(float(v) for v in obj.get("qfg_b4_anchor_position")),
            anchor_direction=tuple(float(v) for v in obj.get("qfg_b4_anchor_direction")),
            anchor_orbital_normal=tuple(float(v) for v in obj.get("qfg_b4_anchor_orbital_normal")),
            force_coupling=float(p.atlas_feedback_force_coupling),
            torque_coupling=float(p.atlas_feedback_torque_coupling),
            linear_mobility=float(p.atlas_feedback_linear_mobility),
            angular_mobility=float(p.atlas_feedback_angular_mobility),
            lock_position=bool(p.atlas_feedback_lock_position),
            lock_rotation=bool(p.atlas_feedback_lock_rotation),
            role=p.atlas_role,
            nucleon_type=p.atlas_nucleon_type,
            provenance=provenance,
        ))
        objects.append(obj)
    return sources, objects



def atlas_constraint_config(settings) -> AtlasConstraintConfig:
    return AtlasConstraintConfig(
        iterations=int(settings.atlas_constraints_iterations),
        distance_stiffness=float(settings.atlas_constraints_distance_stiffness),
        shell_stiffness=float(settings.atlas_constraints_shell_stiffness),
        cone_stiffness=float(settings.atlas_constraints_cone_stiffness),
        symmetry_stiffness=float(settings.atlas_constraints_symmetry_stiffness),
        shell_tolerance=float(settings.atlas_constraints_shell_tolerance),
        convergence_tolerance=float(settings.atlas_constraints_tolerance),
        max_correction=float(settings.atlas_constraints_max_correction),
        preserve_movable_centroid=bool(settings.atlas_constraints_preserve_centroid),
    )


def _b5_snapshot(scene) -> Dict[str, Any] | None:
    raw = scene.get("qfg_b5_constraints_json", "")
    if not raw:
        return None
    try:
        data = json.loads(str(raw))
    except Exception as exc:
        raise ValueError(f"Invalid B5 constraint snapshot: {exc}") from exc
    if not isinstance(data, dict) or int(data.get("version", 0)) != 1:
        raise ValueError("Unsupported B5 constraint snapshot; recapture B5 constraints")
    return data


def _pair_provenance(a, b, fallback: str) -> str:
    pa = str(a.qfg_actor.atlas_provenance).upper()
    pb = str(b.qfg_actor.atlas_provenance).upper()
    if fallback == "SOURCE" and pa == "SOURCE" and pb == "SOURCE":
        return "SOURCE"
    return fallback


def capture_atlas_constraints(scene) -> Dict[str, Any]:
    """Capture reviewed Atlas geometry as the B5 admissible-set snapshot."""
    settings = scene.qfg_settings
    center = np.asarray(atlas_center(scene, settings), dtype=np.float64)
    objects = [
        obj for obj in atlas_objects(scene)
        if obj.qfg_actor.atlas_constraint_enabled and obj.qfg_actor.atlas_provenance != "REJECTED"
    ]
    if not objects:
        raise ValueError("No non-rejected Atlas objects are enabled for B5 constraints")
    objects_by_name = {obj.name: obj for obj in objects}
    nodes = []
    pure_nodes = []
    for obj in objects:
        p = obj.qfg_actor
        pos = tuple(float(v) for v in obj.matrix_world.translation)
        movable = bool(
            not p.atlas_constraint_fixed
            and p.atlas_feedback_enabled
            and not p.atlas_feedback_lock_position
        )
        item = {
            "name": obj.name,
            "anchor_position": pos,
            "movable": movable,
            "preserve_radius": bool(p.atlas_constraint_preserve_radius),
            "max_cone_deg": float(p.atlas_constraint_max_cone_deg),
            "symmetry_group": str(p.atlas_constraint_symmetry_group).strip(),
            "role": p.atlas_role,
            "provenance": p.atlas_provenance,
        }
        nodes.append(item)
        pure_nodes.append(AtlasConstraintNode(position=pos, **item))

    pairs: list[AtlasDistanceConstraint] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(a_name: str, b_name: str, provenance: str, note: str) -> None:
        if a_name == b_name or a_name not in objects_by_name or b_name not in objects_by_name:
            return
        key = tuple(sorted((a_name, b_name)))
        if key in seen:
            return
        seen.add(key)
        pa = np.asarray(objects_by_name[key[0]].matrix_world.translation, dtype=np.float64)
        pb = np.asarray(objects_by_name[key[1]].matrix_world.translation, dtype=np.float64)
        target = float(np.linalg.norm(pb - pa))
        pairs.append(AtlasDistanceConstraint(
            a=key[0], b=key[1], target_distance=target,
            stiffness=1.0, provenance=provenance, note=note,
        ))

    mode = str(settings.atlas_constraints_pair_mode)
    if mode == "MANUAL_NEIGHBORS":
        for obj in objects:
            for token in str(obj.qfg_actor.atlas_constraint_neighbors).replace(";", ",").split(","):
                neighbour = token.strip()
                if neighbour:
                    other = objects_by_name.get(neighbour)
                    if other is not None:
                        add_pair(obj.name, neighbour, _pair_provenance(obj, other, "SOURCE"), "manual reviewed neighbour")
    elif mode == "PARENT_CHILD":
        for obj in objects:
            parent = obj.parent
            if parent is not None and parent.name in objects_by_name:
                add_pair(obj.name, parent.name, "DERIVED", "Atlas Blender parent-child relation")
    elif mode == "SOURCE_STAR":
        valence = [o for o in objects if o.qfg_actor.atlas_role == "VALENCE"]
        equatorial = [o for o in objects if o.qfg_actor.atlas_role == "EQUATORIAL"]
        for a in valence:
            for b in equatorial:
                add_pair(a.name, b.name, "DERIVED", "B2 source-star VALENCE↔EQUATORIAL topology")
    elif mode != "NONE":
        raise ValueError(f"Unsupported B5 pair mode: {mode}")

    groups = build_symmetry_constraints(pure_nodes, center)
    snapshot = {
        "version": 1,
        "capture_center": [float(v) for v in center],
        "pair_mode": mode,
        "nodes": nodes,
        "pairs": [edge.to_dict() for edge in pairs],
        "symmetry_groups": [group.to_dict() for group in groups],
        "provenance": "SOURCE" if all(n["provenance"] == "SOURCE" for n in nodes) and mode == "MANUAL_NEIGHBORS" else "DERIVED",
        "note": (
            "B5 capture stores reviewed geometry/topology only. Projection stiffness, tolerance and iterative "
            "relaxation remain CONDITIONAL. Symmetry groups preserve captured azimuth while allowing collective polar tilt."
        ),
    }
    scene["qfg_b5_constraints_json"] = json.dumps(snapshot, sort_keys=True)
    runtime.last_atlas_constraints = {"snapshot": snapshot, "last_projection": None}
    settings.atlas_constraints_node_count = len(nodes)
    settings.atlas_constraints_pair_count = len(pairs)
    settings.atlas_constraints_group_count = len(groups)
    settings.atlas_constraints_status = (
        f"B5 captured: nodes={len(nodes)}, pairs={len(pairs)}, symmetry groups={len(groups)}; mode={mode}"
    )
    return snapshot


def clear_atlas_constraints(scene) -> None:
    if "qfg_b5_constraints_json" in scene:
        del scene["qfg_b5_constraints_json"]
    runtime.last_atlas_constraints = None
    s = scene.qfg_settings
    s.atlas_constraints_node_count = 0
    s.atlas_constraints_pair_count = 0
    s.atlas_constraints_group_count = 0
    s.atlas_constraints_iterations_used = 0
    s.atlas_constraints_max_pair_error = 0.0
    s.atlas_constraints_max_shell_error = 0.0
    s.atlas_constraints_max_cone_excess = 0.0
    s.atlas_constraints_max_correction_used = 0.0
    s.atlas_constraints_pair_angle_before = 0.0
    s.atlas_constraints_pair_angle_after = 0.0
    s.atlas_constraints_status = "No B5 constraints captured"


def _symmetry_from_dict(item: Dict[str, Any]) -> AtlasSymmetryConstraint:
    return AtlasSymmetryConstraint(
        name=str(item["name"]),
        members=tuple(str(v) for v in item.get("members", [])),
        axis=tuple(float(v) for v in item.get("axis", (0.0, 0.0, 1.0))),
        azimuth_directions=tuple(
            (str(pair[0]), tuple(float(v) for v in pair[1]))
            for pair in item.get("azimuth_directions", [])
        ),
        provenance=str(item.get("provenance", "DERIVED")),
    )


def evaluate_atlas_constraints(
    scene, proposed_positions: Dict[str, Tuple[float, float, float]] | None = None,
) -> Tuple[Dict[str, Tuple[float, float, float]], Dict[str, Any]]:
    """Evaluate B5 projection without mutating Blender object transforms."""
    settings = scene.qfg_settings
    snapshot = _b5_snapshot(scene)
    if snapshot is None and settings.atlas_constraints_auto_capture:
        snapshot = capture_atlas_constraints(scene)
    if snapshot is None:
        raise ValueError("B5 constraint snapshot missing; capture constraints or enable Auto-capture")
    object_map = {obj.name: obj for obj in atlas_objects(scene)}
    nodes: list[AtlasConstraintNode] = []
    proposals: Dict[str, Tuple[float, float, float]] = {}
    for item in snapshot.get("nodes", []):
        name = str(item.get("name", ""))
        obj = object_map.get(name)
        if obj is None:
            continue
        p = obj.qfg_actor
        current = tuple(float(v) for v in obj.matrix_world.translation)
        # Runtime locks remain authoritative; topology requires recapture when
        # source declarations such as max cone or symmetry group are changed.
        movable = bool(item.get("movable", True)) and not bool(p.atlas_constraint_fixed) and not bool(p.atlas_feedback_lock_position)
        nodes.append(AtlasConstraintNode(
            name=name,
            position=current,
            anchor_position=tuple(float(v) for v in item.get("anchor_position", current)),
            movable=movable,
            preserve_radius=bool(item.get("preserve_radius", True)),
            max_cone_deg=float(item.get("max_cone_deg", 0.0)),
            symmetry_group=str(item.get("symmetry_group", "")),
            role=str(item.get("role", p.atlas_role)),
            provenance=str(item.get("provenance", p.atlas_provenance)),
        ))
        proposals[name] = tuple(float(v) for v in (proposed_positions or {}).get(name, current))
    pairs = tuple(AtlasDistanceConstraint(
        a=str(item["a"]), b=str(item["b"]), target_distance=float(item["target_distance"]),
        stiffness=float(item.get("stiffness", 1.0)), provenance=str(item.get("provenance", "SOURCE")),
        note=str(item.get("note", "")),
    ) for item in snapshot.get("pairs", []))
    groups = tuple(_symmetry_from_dict(item) for item in snapshot.get("symmetry_groups", []))
    center = tuple(float(v) for v in atlas_center(scene, settings))
    cfg = atlas_constraint_config(settings)
    deltas, summary = project_atlas_constraints(
        nodes, proposals, center=center, distance_constraints=pairs,
        symmetry_constraints=groups, config=cfg,
    )
    position_map = {d.name: tuple(float(v) for v in d.constrained_position) for d in deltas}
    payload = {
        "snapshot": snapshot,
        "config": asdict(cfg),
        "summary": summary.to_dict(),
        "deltas": [d.to_dict() for d in deltas],
        "provenance": "CONDITIONAL",
        "note": summary.note,
    }
    runtime.last_atlas_constraints = payload
    settings.atlas_constraints_node_count = int(summary.node_count)
    settings.atlas_constraints_pair_count = int(summary.pair_constraint_count)
    settings.atlas_constraints_group_count = int(summary.symmetry_group_count)
    settings.atlas_constraints_iterations_used = int(summary.iterations_performed)
    settings.atlas_constraints_max_pair_error = float(summary.max_pair_error_after)
    settings.atlas_constraints_max_shell_error = float(summary.max_shell_error_after)
    settings.atlas_constraints_max_cone_excess = float(summary.max_cone_excess_after_deg)
    settings.atlas_constraints_max_correction_used = float(summary.max_correction_norm)
    settings.atlas_constraints_pair_angle_before = float(summary.mean_symmetry_pair_angle_before_deg)
    settings.atlas_constraints_pair_angle_after = float(summary.mean_symmetry_pair_angle_after_deg)
    settings.atlas_constraints_status = (
        f"CONDITIONAL B5: nodes={summary.node_count}, pairs={summary.pair_constraint_count}, "
        f"groups={summary.symmetry_group_count}, iter={summary.iterations_performed}, "
        f"pair err={summary.max_pair_error_after:.3g}, cone excess={summary.max_cone_excess_after_deg:.3g}°"
    )
    return position_map, payload


def apply_atlas_constraints_to_scene(scene) -> Dict[str, Any]:
    position_map, payload = evaluate_atlas_constraints(scene)
    for name, position in position_map.items():
        obj = scene.objects.get(name)
        if obj is None:
            continue
        loc, rot, scale = obj.matrix_world.decompose()
        obj.matrix_world = _compose_world_matrix(position, rot, scale)
        delta = next((d for d in payload["deltas"] if d["name"] == name), None)
        if delta is not None:
            obj["qfg_b5_last_correction"] = tuple(float(v) for v in delta["correction"])
            obj["qfg_b5_constraint_provenance"] = "CONDITIONAL"
    if scene.qfg_settings.atlas_field_enabled and runtime.engine is not None:
        apply_atlas_field_to_engine(scene, runtime.engine)
    return payload


def apply_atlas_feedback(scene, engine: QFGEngine3D | None = None, *, effective_dt: float | None = None) -> Dict[str, Any]:
    settings = scene.qfg_settings
    target = engine or runtime.engine
    if target is None:
        raise ValueError("Initialize the QFG engine before applying B4 feedback")
    if not settings.atlas_feedback_enabled:
        raise ValueError("B4 bidirectional feedback is disabled")
    sources, objects = atlas_feedback_sources(scene, settings)
    if not sources:
        raise ValueError("No Atlas sources pass the B4 feedback filters")
    dt = float(effective_dt if effective_dt is not None else target.config.dt)
    cfg = atlas_feedback_config(settings, dt)
    density = np.asarray(target.density(), dtype=np.float64)
    spin_texture = target.spin_texture() if target.config.field_mode == "SPINOR" else None
    deltas, summary = evaluate_feedback(
        sources, density=density, domain_length=float(target.L), dx=float(target.dx),
        config=cfg, spin_texture=spin_texture,
    )
    object_by_name = {obj.name: obj for obj in objects}
    proposed_positions: Dict[str, Tuple[float, float, float]] = {}
    proposed_rotations: Dict[str, Quaternion] = {}
    for delta in deltas:
        obj = object_by_name.get(delta.name)
        if obj is None:
            continue
        loc, rot, _scale = obj.matrix_world.decompose()
        displacement = np.asarray(delta.displacement, dtype=np.float64)
        proposed_positions[delta.name] = (
            float(loc.x + displacement[0]), float(loc.y + displacement[1]), float(loc.z + displacement[2])
        )
        rv = np.asarray(delta.rotation_vector, dtype=np.float64)
        angle = float(np.linalg.norm(rv))
        new_rotation = rot
        if angle > 1.0e-15:
            axis = Vector(tuple(float(v) for v in rv / angle))
            new_rotation = Quaternion(axis, angle) @ rot
        proposed_rotations[delta.name] = new_rotation

    b5_payload = None
    constrained_positions = dict(proposed_positions)
    if settings.atlas_constraints_enabled:
        constrained_positions, b5_payload = evaluate_atlas_constraints(scene, proposed_positions)

    # Apply constrained B5 positions and B4 rotations in one transform update.
    affected_names = set(constrained_positions) | set(proposed_positions)
    for name in affected_names:
        obj = scene.objects.get(name)
        if obj is None:
            continue
        loc, rot, scale = obj.matrix_world.decompose()
        location = constrained_positions.get(name, proposed_positions.get(name, tuple(float(v) for v in loc)))
        rotation = proposed_rotations.get(name, rot)
        obj.matrix_world = _compose_world_matrix(location, rotation, scale)

    b5_delta_map = {} if b5_payload is None else {d["name"]: d for d in b5_payload.get("deltas", [])}
    for delta in deltas:
        obj = object_by_name.get(delta.name)
        if obj is None:
            continue
        obj["qfg_b4_last_density"] = float(delta.sampled_density)
        obj["qfg_b4_last_gradient"] = tuple(float(v) for v in delta.sampled_gradient)
        obj["qfg_b4_last_spin"] = tuple(float(v) for v in delta.sampled_spin)
        obj["qfg_b4_last_target"] = tuple(float(v) for v in delta.target_direction)
        obj["qfg_b4_last_force"] = tuple(float(v) for v in delta.force)
        obj["qfg_b4_last_torque"] = tuple(float(v) for v in delta.torque)
        obj["qfg_b4_feedback_provenance"] = "CONDITIONAL"
    for name, item in b5_delta_map.items():
        obj = scene.objects.get(name)
        if obj is None:
            continue
        obj["qfg_b5_last_correction"] = tuple(float(v) for v in item["correction"])
        obj["qfg_b5_constraint_provenance"] = "CONDITIONAL"

    payload = {
        "summary": summary.to_dict(),
        "config": asdict(cfg),
        "deltas": [delta.to_dict() for delta in deltas],
        "sources": [source.to_dict() for source in sources],
        "b5_constraints": b5_payload,
        "provenance": "CONDITIONAL",
        "note": summary.note + (" B5 geometric admissibility projection applied." if b5_payload is not None else ""),
    }
    runtime.last_atlas_feedback = payload
    settings.atlas_feedback_source_count = int(summary.source_count)
    settings.atlas_feedback_moved_count = int(summary.moved_count)
    settings.atlas_feedback_rotated_count = int(summary.rotated_count)
    settings.atlas_feedback_clipped_count = int(summary.clipped_count)
    settings.atlas_feedback_mean_force = float(summary.mean_force)
    settings.atlas_feedback_max_force = float(summary.max_force)
    settings.atlas_feedback_mean_torque = float(summary.mean_torque)
    settings.atlas_feedback_max_torque = float(summary.max_torque)
    settings.atlas_feedback_force_work = float(summary.force_work_proxy)
    settings.atlas_feedback_torque_work = float(summary.torque_work_proxy)
    settings.atlas_feedback_total_work = float(summary.total_work_proxy)
    settings.atlas_feedback_max_anchor_displacement = float(summary.max_anchor_displacement)
    settings.atlas_feedback_status = (
        f"CONDITIONAL B4: {summary.source_count} source(s), moved={summary.moved_count}, "
        f"rotated={summary.rotated_count}, clipped={summary.clipped_count}, "
        f"max|F|={summary.max_force:.3g}, W*={summary.total_work_proxy:.3g}"
    )
    if settings.atlas_feedback_rerasterize and settings.atlas_field_enabled:
        apply_atlas_field_to_engine(scene, target)
    return payload

def atlas_blind_config(settings) -> BlindRelaxationConfig:
    return BlindRelaxationConfig(
        max_iterations=int(settings.atlas_blind_max_iterations),
        min_iterations=int(settings.atlas_blind_min_iterations),
        convergence_window=int(settings.atlas_blind_window),
        angle_window_tolerance_deg=float(settings.atlas_blind_angle_tolerance),
        angle_slope_tolerance_deg_per_iter=float(settings.atlas_blind_slope_tolerance),
        spread_tolerance_deg=float(settings.atlas_blind_spread_tolerance),
        correction_tolerance=float(settings.atlas_blind_correction_tolerance),
    )


def atlas_blind_protocol_payload(scene) -> Dict[str, Any]:
    """Return the source/config snapshot fingerprinted before a B6 run.

    No experimental holdout value is included here.
    """
    s = scene.qfg_settings
    source_objects = []
    for obj in sorted(atlas_objects(scene), key=lambda item: item.name):
        p = obj.qfg_actor
        loc, rot, scale = obj.matrix_world.decompose()
        source_objects.append({
            "name": obj.name,
            "position": [float(v) for v in loc],
            "rotation_quaternion": [float(rot.w), float(rot.x), float(rot.y), float(rot.z)],
            "scale": [float(v) for v in scale],
            "nucleon_type": p.atlas_nucleon_type,
            "role": p.atlas_role,
            "direction_mode": p.atlas_direction_mode,
            "provenance": p.atlas_provenance,
            "field": {
                "enabled": bool(p.atlas_field_enabled), "strength": float(p.atlas_field_strength),
                "radius": float(p.atlas_field_radius), "anisotropy": float(p.atlas_field_anisotropy),
                "orbital_normal_mode": p.atlas_orbital_normal_mode,
            },
            "feedback": {
                "enabled": bool(p.atlas_feedback_enabled),
                "force_coupling": float(p.atlas_feedback_force_coupling),
                "torque_coupling": float(p.atlas_feedback_torque_coupling),
                "linear_mobility": float(p.atlas_feedback_linear_mobility),
                "angular_mobility": float(p.atlas_feedback_angular_mobility),
                "lock_position": bool(p.atlas_feedback_lock_position),
                "lock_rotation": bool(p.atlas_feedback_lock_rotation),
            },
            "constraints": {
                "enabled": bool(p.atlas_constraint_enabled), "fixed": bool(p.atlas_constraint_fixed),
                "preserve_radius": bool(p.atlas_constraint_preserve_radius),
                "max_cone_deg": float(p.atlas_constraint_max_cone_deg),
                "neighbors": str(p.atlas_constraint_neighbors),
                "symmetry_group": str(p.atlas_constraint_symmetry_group),
            },
        })
    cfg = atlas_blind_config(s)
    return {
        "protocol": "B6_GROUP15_BLIND_RELAXATION",
        "element": str(s.atlas_element),
        "source_objects": source_objects,
        "b3": {
            "kernel": s.atlas_field_kernel, "source_scope": s.atlas_field_source_scope,
            "role_scope": s.atlas_field_role_scope, "softening": float(s.atlas_field_softening),
            "scalar_scale": float(s.atlas_field_scalar_scale), "vector_scale": float(s.atlas_field_vector_scale),
            "vector_mode": s.atlas_field_vector_mode, "orbital_mix": float(s.atlas_field_orbital_mix),
            "scene_scale": float(s.atlas_field_scene_scale), "clip_abs": float(s.atlas_field_clip_abs),
        },
        "b4": {
            "target_mode": s.atlas_feedback_target_mode, "force_scale": float(s.atlas_feedback_force_scale),
            "torque_scale": float(s.atlas_feedback_torque_scale),
            "anchor_strength": float(s.atlas_feedback_anchor_strength),
            "orientation_anchor": float(s.atlas_feedback_orientation_anchor),
            "orbital_mix": float(s.atlas_feedback_orbital_mix), "spin_mix": float(s.atlas_feedback_spin_mix),
            "max_step": float(s.atlas_feedback_max_step), "max_angle": float(s.atlas_feedback_max_angle),
            "max_displacement": float(s.atlas_feedback_max_displacement),
        },
        "b5": {
            "pair_mode": s.atlas_constraints_pair_mode,
            "distance_stiffness": float(s.atlas_constraints_distance_stiffness),
            "shell_stiffness": float(s.atlas_constraints_shell_stiffness),
            "cone_stiffness": float(s.atlas_constraints_cone_stiffness),
            "symmetry_stiffness": float(s.atlas_constraints_symmetry_stiffness),
            "shell_tolerance": float(s.atlas_constraints_shell_tolerance),
            "iterations": int(s.atlas_constraints_iterations),
            "tolerance": float(s.atlas_constraints_tolerance),
            "max_correction": float(s.atlas_constraints_max_correction),
            "preserve_centroid": bool(s.atlas_constraints_preserve_centroid),
        },
        "b6": asdict(cfg) | {
            "steps_per_iteration": int(s.atlas_blind_steps_per_iteration),
            "reset_to_anchors": bool(s.atlas_blind_reset_to_anchors),
            "recapture_constraints": bool(s.atlas_blind_recapture_constraints),
        },
        "qfg": {
            "field_mode": s.field_mode, "grid_size": int(s.grid_size),
            "domain_length": float(s.domain_length), "dt": float(s.dt),
            "lambda_cohesion": float(s.lambda_cohesion), "kappa_stability": float(s.kappa_stability),
            "damping": float(s.damping), "delta_anisotropy": float(s.delta_anisotropy),
        },
        "provenance": "CONDITIONAL",
        "note": "B6 convergence uses predicted geometry only; no experimental holdout value is present in this protocol snapshot.",
    }


def _store_atlas_geometry_result(scene, result, center, valence, *, provenance: str = "DERIVED") -> Dict[str, Any]:
    s = scene.qfg_settings
    payload = result.to_dict()
    payload["provenance"] = str(provenance).upper()
    payload["center"] = [float(v) for v in center]
    payload["source_objects"] = [
        {
            "name": obj.name, "nucleon_type": obj.qfg_actor.atlas_nucleon_type,
            "role": obj.qfg_actor.atlas_role, "direction_mode": obj.qfg_actor.atlas_direction_mode,
            "provenance": obj.qfg_actor.atlas_provenance, "source_note": obj.qfg_actor.atlas_source_note,
        } for obj in valence
    ]
    runtime.last_atlas_result = payload
    s.atlas_mean_angle = float(result.mean_pair_angle_deg)
    s.atlas_angle_spread = float(result.std_pair_angle_deg)
    s.atlas_min_angle = float(result.min_pair_angle_deg)
    s.atlas_max_angle = float(result.max_pair_angle_deg)
    s.atlas_height_ratio = float(result.c3v_height_ratio or 0.0)
    return payload


def reset_atlas_blind_run(scene) -> None:
    s = scene.qfg_settings
    runtime.last_atlas_blind_run = None
    s.atlas_blind_running = False
    s.atlas_blind_converged = False
    s.atlas_blind_iterations_used = 0
    s.atlas_blind_final_angle = 0.0
    s.atlas_blind_final_spread = 0.0
    s.atlas_blind_window_range = 0.0
    s.atlas_blind_window_slope = 0.0
    s.atlas_blind_protocol_hash = ""
    s.atlas_blind_status = "No B6 blind run"


def yb_config(s) -> YbConfig:
    return YbConfig(
        duration=s.yb_duration, dt=s.yb_dt,
        rabi_frequency=s.yb_rabi_frequency, detuning=s.yb_detuning,
        dephasing=s.yb_dephasing, relaxation=s.yb_relaxation,
        q_factor=s.yb_q_factor, cavity_power=s.yb_cavity_power,
        alpha=s.alpha_dielectric, density_offset=s.yb_density_offset,
        qfg_correction_scale=s.yb_correction_scale,
        texture_coupling=s.yb_texture_coupling,
        texture_divergence=s.yb_texture_divergence,
        ac_stark_scale=s.yb_ac_stark_scale,
    )


class QFG_OT_Initialize(bpy.types.Operator):
    bl_idname = "qfg.initialize"
    bl_label = "Initialize QFG Engine"
    bl_description = "Build the numerical field from QFG actors"
    bl_options = {"REGISTER"}

    def execute(self, context):
        try:
            _engine, count = initialize_engine(context.scene)
            s = context.scene.qfg_settings
            if runtime.world is not None:
                message = f"Initialized QFGWorld: {count} fields, {s.last_body_count} bodies"
            else:
                message = f"Initialized {count} QFG field actors"
            self.report({"INFO" if count else "WARNING"}, message)
            return {"FINISHED"}
        except Exception as exc:
            context.scene.qfg_settings.status = f"Initialization failed: {exc}"
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_Step(bpy.types.Operator):
    bl_idname = "qfg.step"
    bl_label = "Run QFG Steps"
    bl_description = "Advance the solver and update the viewport"

    def execute(self, context):
        if runtime.engine is None:
            self.report({"ERROR"}, "Initialize the engine first")
            return {"CANCELLED"}
        try:
            s = context.scene.qfg_settings
            if s.atlas_field_enabled and s.atlas_field_live_update:
                apply_atlas_field_to_engine(context.scene, runtime.engine)
            if s.atlas_feedback_enabled:
                if not s.atlas_field_enabled:
                    raise ValueError("B4 bidirectional feedback requires the B3 Atlas field bridge to be enabled")
                result = None
                for _ in range(int(s.steps_per_action)):
                    if runtime.world is not None:
                        result = runtime.world.step(1)
                        diag = result.diagnostics
                        effective_dt = runtime.engine.config.dt * runtime.world.world_config.substeps
                    else:
                        diag = runtime.engine.step(1)
                        effective_dt = runtime.engine.config.dt
                    apply_atlas_feedback(context.scene, runtime.engine, effective_dt=effective_dt)
                if runtime.world is not None and result is not None:
                    update_dynamics_metrics(s, result.profile)
                    update_world_telemetry(s, result.telemetry)
                    body_state = runtime.world.body_snapshot()
                    apply_body_state(context.scene, body_state)
                    runtime.debug_payload = {
                        "source": "LIVE", "requested_frame": context.scene.frame_current,
                        "displayed_frame": context.scene.frame_current, "body_state": body_state,
                        "atlas_state": atlas_state_snapshot(context.scene),
                        "atlas_feedback": runtime.last_atlas_feedback or {},
                        "atlas_constraints": runtime.last_atlas_constraints or {},
                        "telemetry": result.telemetry,
                        "events": [event.to_dict() for event in result.events],
                    }
                    s.status = (
                        f"B4/B5 world step {runtime.world.step_index} at t={runtime.world.time:.6g}; "
                        f"Atlas moved={s.atlas_feedback_moved_count}, rotated={s.atlas_feedback_rotated_count}, "
                        f"B5={s.atlas_constraints_node_count if s.atlas_constraints_enabled else 0}"
                    )
                else:
                    s.status = (
                        f"B4/B5 step {runtime.engine.step_index} at t={runtime.engine.time:.6g}; "
                        f"Atlas moved={s.atlas_feedback_moved_count}, rotated={s.atlas_feedback_rotated_count}, "
                        f"B5={s.atlas_constraints_node_count if s.atlas_constraints_enabled else 0}"
                    )
            elif runtime.world is not None:
                result = runtime.world.step(s.steps_per_action)
                diag = result.diagnostics
                update_dynamics_metrics(s, result.profile)
                update_world_telemetry(s, result.telemetry)
                body_state = runtime.world.body_snapshot()
                apply_body_state(context.scene, body_state)
                runtime.debug_payload = {
                    "source": "LIVE", "requested_frame": context.scene.frame_current,
                    "displayed_frame": context.scene.frame_current, "body_state": body_state,
                    "telemetry": result.telemetry,
                    "events": [event.to_dict() for event in result.events],
                }
                s.status = (
                    f"World step {runtime.world.step_index} at t={runtime.world.time:.6g}; "
                    f"bodies={len(runtime.world.bodies)}, events={len(result.events)}"
                )
            else:
                diag = runtime.engine.step(s.steps_per_action)
                s.status = f"Step {runtime.engine.step_index} at t={runtime.engine.time:.6g}"
            update_metrics(s, diag)
            update_visuals(context.scene)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_Reset(bpy.types.Operator):
    bl_idname = "qfg.reset"
    bl_label = "Reset from Scene"

    def execute(self, context):
        try:
            initialize_engine(context.scene)
            self.report({"INFO"}, "QFG state reset from scene actors")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_UpdateVisualization(bpy.types.Operator):
    bl_idname = "qfg.update_visualization"
    bl_label = "Refresh Visualization"

    def execute(self, context):
        if runtime.engine is None:
            self.report({"ERROR"}, "Initialize the engine first")
            return {"CANCELLED"}
        update_visuals(context.scene)
        return {"FINISHED"}


class QFG_OT_BakeTimeline(bpy.types.Operator):
    bl_idname = "qfg.bake_timeline"
    bl_label = "Bake QFG Timeline"
    bl_description = "Compute frames explicitly; playback only displays cached results"

    def execute(self, context):
        s = context.scene.qfg_settings
        if s.bake_end < s.bake_start:
            self.report({"ERROR"}, "Bake end must be >= bake start")
            return {"CANCELLED"}
        try:
            engine, count = initialize_engine(context.scene)
            total = s.bake_end - s.bake_start + 1
            wm = context.window_manager
            wm.progress_begin(0, total)
            try:
                for index, frame in enumerate(range(s.bake_start, s.bake_end + 1)):
                    body_state = None
                    events = None
                    profile = None
                    telemetry = None
                    atlas_state = None
                    if s.atlas_feedback_enabled:
                        if not s.atlas_field_enabled:
                            raise ValueError("B4 timeline bake requires the B3 Atlas field bridge")
                        result = None
                        for _ in range(int(s.steps_per_frame)):
                            if runtime.world is not None:
                                result = runtime.world.step(1)
                                diag = result.diagnostics
                                effective_dt = engine.config.dt * runtime.world.world_config.substeps
                            else:
                                diag = engine.step(1)
                                effective_dt = engine.config.dt
                            apply_atlas_feedback(context.scene, engine, effective_dt=effective_dt)
                        atlas_state = atlas_state_snapshot(context.scene)
                        if runtime.world is not None and result is not None:
                            body_state = runtime.world.body_snapshot()
                            events = [event.to_dict() for event in result.events]
                            profile = result.profile.to_dict()
                            telemetry = result.telemetry
                            update_dynamics_metrics(s, result.profile)
                            update_world_telemetry(s, result.telemetry)
                    elif runtime.world is not None:
                        result = runtime.world.step(s.steps_per_frame)
                        diag = result.diagnostics
                        body_state = runtime.world.body_snapshot()
                        events = [event.to_dict() for event in result.events]
                        profile = result.profile.to_dict()
                        telemetry = result.telemetry
                        update_dynamics_metrics(s, result.profile)
                        update_world_telemetry(s, result.telemetry)
                    else:
                        diag = engine.step(s.steps_per_frame)
                    density = engine.density()
                    points, weights = density_to_points(
                        density, s.domain_length, s.threshold_fraction, s.max_points,
                    )
                    runtime.cache.put(
                        frame, points=points, weights=weights,
                        density_slice=central_slice(density, s.slice_axis),
                        diagnostics=diag.to_dict(),
                        body_state=body_state, atlas_state=atlas_state, events=events, profile=profile, telemetry=telemetry,
                    )
                    wm.progress_update(index + 1)
            finally:
                wm.progress_end()
            context.scene.frame_start = s.bake_start
            context.scene.frame_end = s.bake_end
            context.scene.frame_set(s.bake_start)
            s.status = f"Baked {total} frames from {count} field actors and {s.last_body_count} bodies"
            self.report({"INFO"}, s.status)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_ClearCache(bpy.types.Operator):
    bl_idname = "qfg.clear_cache"
    bl_label = "Clear Timeline Cache"

    def execute(self, context):
        runtime.cache.clear()
        runtime.debug_payload = None
        context.scene.qfg_settings.status = "Timeline cache cleared"
        return {"FINISHED"}


class QFG_OT_Topology(bpy.types.Operator):
    bl_idname = "qfg.compute_topology"
    bl_label = "Compute Topology Proxies"

    def execute(self, context):
        if runtime.engine is None:
            self.report({"ERROR"}, "Initialize the engine first")
            return {"CANCELLED"}
        result = runtime.engine.topological_diagnostics()
        s = context.scene.qfg_settings
        s.hopf_proxy = result["hopf_proxy"]
        s.skyrme_proxy = result["skyrme_energy_proxy"]
        s.orientation_variance = result["orientation_variance"]
        s.status = "Topology proxies computed; convergence study is required"
        self.report({"INFO"}, f"Hopf proxy: {s.hopf_proxy:.6g}")
        return {"FINISHED"}


class QFG_OT_ExportSession(bpy.types.Operator):
    bl_idname = "qfg.export_session"
    bl_label = "Export Complete QFG Session"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            session = timestamped_directory(bpy.path.abspath(s.output_directory))
            metadata: Dict[str, Any] = {
                "add_on": "QFG Lab 5.2",
                "version": "1.0.0-alpha",
                "scientific_status": "Reduced research models; candidate signatures are not experimental confirmation",
                "blender_version": bpy.app.version_string,
                "validation_program": validation_program_summary(),
            }
            if runtime.engine is not None:
                snapshot = runtime.engine.snapshot()
                metadata.update({
                    "backend": runtime.engine.backend_name,
                    "device": runtime.engine.device,
                    "config": snapshot["config"],
                    "actors": [asdict(actor) for actor in runtime.engine.actors],
                    "diagnostics": snapshot["diagnostics"],
                    "topology": snapshot["topology"],
                })
                write_diagnostics_csv(session / "field_diagnostics.csv", runtime.engine.history)
                save_snapshot_npz(session / "field_snapshot.npz", snapshot)
            if runtime.world is not None:
                world_snapshot = runtime.world.snapshot()
                metadata["dynamics_runtime"] = {
                    "world_config": world_snapshot["world_config"],
                    "bodies": world_snapshot["bodies"],
                    "event_count": len(world_snapshot["events"]),
                    "profile_samples": len(world_snapshot["profile"]),
                    "telemetry": world_snapshot.get("telemetry", {}),
                    "state_hash": world_snapshot.get("state_hash", ""),
                }
                write_rows_csv(session / "dynamics_events.csv", world_snapshot["events"])
                write_rows_csv(session / "dynamics_profile.csv", world_snapshot["profile"])
                body_state = world_snapshot["body_state"]
                np.savez_compressed(
                    session / "dynamics_body_state.npz",
                    names=np.asarray(body_state["names"]),
                    collision_shapes=np.asarray(body_state["collision_shapes"]),
                    phase_state=np.asarray(body_state["phase_state"]),
                    positions=body_state["positions"],
                    velocities=body_state["velocities"],
                    orientations=body_state["orientations"],
                    angular_velocities=body_state["angular_velocities"],
                    half_extents=body_state["half_extents"],
                    density=body_state["density"],
                    temperature=body_state["temperature"],
                    force_gravity=body_state["force_gravity"],
                    force_field=body_state["force_field"],
                    force_thermal=body_state["force_thermal"],
                    force_drag=body_state["force_drag"],
                    force_contact=body_state["force_contact"],
                    force_total=body_state["force_total"],
                    torque_external=body_state["torque_external"],
                    torque_field=body_state["torque_field"],
                    torque_drag=body_state["torque_drag"],
                    torque_contact=body_state["torque_contact"],
                    torque_total=body_state["torque_total"],
                    contact_impulse=body_state["contact_impulse"],
                    contact_angular_impulse=body_state["contact_angular_impulse"],
                )
            write_json(session / "metadata.json", metadata)

            exports = {
                "rf_rom": runtime.last_rom_result,
                "hrm_scan": runtime.last_hrm_scan,
                "plasma": runtime.last_plasma_result,
                "cavity_shift": runtime.last_cavity_shift,
                "mems": runtime.last_mems_result,
                "yb": runtime.last_yb_result,
                "molecular": runtime.last_molecular_result,
                "atlas_direct": runtime.last_atlas_result,
                "atlas_interaction_graph": runtime.last_atlas_graph,
                "atlas_orbital_planes": runtime.last_atlas_planes,
                "atlas_bohr_envelope": runtime.last_bohr_envelope,
                "atlas_field": runtime.last_atlas_field,
                "atlas_feedback": runtime.last_atlas_feedback,
                "atlas_constraints": runtime.last_atlas_constraints,
                "atlas_blind_run": runtime.last_atlas_blind_run,
            }
            for name, result in exports.items():
                if result is None:
                    continue
                arrays = {k: v for k, v in result.items() if isinstance(v, np.ndarray)}
                if arrays:
                    np.savez_compressed(session / f"{name}.npz", **arrays)
                write_json(session / f"{name}.json", result)
            s.status = f"Exported to {session}"
            self.report({"INFO"}, s.status)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_CreatePreset(bpy.types.Operator):
    bl_idname = "qfg.create_preset"
    bl_label = "Create QFG Preset"
    preset: EnumProperty(
        name="Preset",
        items=[
            ("COLLISION", "Two-node collision", "Opposing Gaussian nodes"),
            ("HOPF", "Hopf-ring prototype", "Spinor ring ansatz"),
            ("VORTEX", "Vortex prototype", "Spinor vortex ansatz"),
            ("HRM_CAVITY", "HRM cavity", "Central mode and cavity boundary"),
            ("THERMAL", "Thermal collision", "Collision with thermal feedback"),
            ("GAUGE_GRAVITY", "Gauge + gravity", "Reduced U(1) and Poisson sectors"),
            ("PLASMA_BOUNDARY", "Plasma boundary", "Dual drive and dielectric region"),
        ], default="COLLISION",
    )

    def execute(self, context):
        scene, s = context.scene, context.scene.qfg_settings
        clear_collection(ACTOR_COLLECTION)
        s.dynamics_enabled = False
        for key, value in PRESETS[self.preset].items():
            if hasattr(s, key):
                setattr(s, key, value)

        if self.preset in {"COLLISION", "THERMAL", "GAUGE_GRAVITY"}:
            left = configure_editor_proxy(
                add_uv_sphere(scene, "QFG_Node_A", (-3.0, 0.0, 0.0))
            )
            right = configure_editor_proxy(
                add_uv_sphere(scene, "QFG_Node_B", (3.0, 0.0, 0.0))
            )
            for obj, velocity, theta in ((left, (4.0, 0.0, 0.0), 0.0), (right, (-4.0, 0.0, 0.0), np.pi)):
                obj.qfg_actor.enabled = True
                obj.qfg_actor.actor_type = "GAUSSIAN"
                obj.qfg_actor.velocity = velocity
                obj.qfg_actor.radius = 0.75
                obj.qfg_actor.intensity = 1.0
                obj.qfg_actor.spin_theta = theta
        elif self.preset == "HOPF":
            ring = configure_editor_proxy(
                add_torus(scene, "QFG_Hopf_Ring", (0.0, 0.0, 0.0), 2.0, 0.35)
            )
            ring.qfg_actor.enabled = True
            ring.qfg_actor.actor_type = "HOPF_RING"
            ring.qfg_actor.radius = 0.45
            ring.qfg_actor.ring_radius = 2.0
            ring.qfg_actor.intensity = 1.0
        elif self.preset == "VORTEX":
            node = configure_editor_proxy(
                add_uv_sphere(scene, "QFG_Vortex", (0.0, 0.0, 0.0))
            )
            node.qfg_actor.enabled = True
            node.qfg_actor.actor_type = "VORTEX"
            node.qfg_actor.radius = 1.5
            node.qfg_actor.winding_m = 1
            node.qfg_actor.winding_n = 1
        elif self.preset in {"HRM_CAVITY", "PLASMA_BOUNDARY"}:
            node = configure_editor_proxy(
                add_uv_sphere(scene, "QFG_Cavity_Mode", (0.0, 0.0, 0.0))
            )
            node.qfg_actor.enabled = True
            node.qfg_actor.actor_type = "GAUSSIAN"
            node.qfg_actor.radius = 1.1
            boundary = configure_editor_proxy(
                add_cube(scene, "QFG_Cavity_Boundary", (0.0, 0.0, 0.0), (3.5, 3.5, 3.5))
            )
            boundary.qfg_actor.enabled = True
            boundary.qfg_actor.actor_type = "BOUNDARY"
            boundary.qfg_actor.boundary_shape = "BOX"
            boundary.qfg_actor.boundary_potential = 0.15 if self.preset == "HRM_CAVITY" else 0.30
            boundary.qfg_actor.boundary_damping = 0.0
        s.status = f"Created {self.preset} preset; initialize before running"
        runtime.reset_runtime()
        self.report({"INFO"}, s.status)
        return {"FINISHED"}


class QFG_OT_CreateDynamicsShowcase(bpy.types.Operator):
    bl_idname = "qfg.create_dynamics_showcase"
    bl_label = "Create QFG Dynamics Showcase"
    bl_description = "Create field emitters and deterministic field-coupled bodies"

    body_count: bpy.props.IntProperty(name="Body count", default=36, min=4, max=256)

    def execute(self, context):
        scene, s = context.scene, context.scene.qfg_settings
        clear_collection(ACTOR_COLLECTION)
        for key, value in PRESETS["COLLISION"].items():
            if hasattr(s, key):
                setattr(s, key, value)
        s.dynamics_enabled = True
        s.dynamics_substeps = 2
        s.dynamics_gravity = (0.0, 0.0, 0.0)
        s.dynamics_floor_height = -3.75
        s.dynamics_body_collisions = True
        s.dynamics_deterministic = True
        s.dynamics_seed = 1337
        s.dynamics_field_force_scale = 1.0
        s.dynamics_field_event_threshold = 0.05
        s.damping = 0.006
        s.thermal_enabled = False

        left = configure_editor_proxy(
            add_uv_sphere(scene, "QFG_Node_A", (-3.0, 0.0, 0.0))
        )
        right = configure_editor_proxy(
            add_uv_sphere(scene, "QFG_Node_B", (3.0, 0.0, 0.0))
        )
        for obj, velocity in ((left, (4.0, 0.0, 0.0)), (right, (-4.0, 0.0, 0.0))):
            p = obj.qfg_actor
            p.enabled = True
            p.actor_type = "GAUSSIAN"
            p.velocity = velocity
            p.radius = 1.0
            p.intensity = 1.0

        # A broad, lower-intensity field core provides a visible field gradient
        # for the dynamic bodies while the two primary nodes collide.
        core = configure_editor_proxy(
            add_uv_sphere(
                scene,
                "QFG_Dynamics_Core",
                (0.0, 0.0, 0.0),
                scale=(0.35, 0.35, 0.35),
            )
        )
        core.qfg_actor.enabled = True
        core.qfg_actor.actor_type = "GAUSSIAN"
        core.qfg_actor.velocity = (0.0, 0.0, 0.0)
        core.qfg_actor.radius = 3.2
        core.qfg_actor.intensity = 0.35

        rng = np.random.default_rng(s.dynamics_seed)
        count = int(self.body_count)
        for index in range(count):
            angle = 2.0 * np.pi * index / count
            ring = 4.8 + float(rng.normal(0.0, 0.22))
            z = float(rng.uniform(-1.8, 2.3))
            position = (ring * np.cos(angle), ring * np.sin(angle), z)
            obj = add_cube(
                scene, f"QFG_Dynamic_Shard_{index:03d}", position,
                scale=tuple(float(v) for v in rng.uniform(0.12, 0.34, size=3)),
            )
            obj.rotation_euler = tuple(float(v) for v in rng.uniform(0.0, np.pi, size=3))
            p = obj.qfg_actor
            p.enabled = True
            p.actor_type = "DYNAMIC_BODY"
            tangent = np.asarray((-np.sin(angle), np.cos(angle), 0.0))
            inward = np.asarray((-np.cos(angle), -np.sin(angle), 0.0))
            velocity = 0.75 * tangent + 0.05 * inward + rng.normal(0.0, 0.08, size=3)
            p.velocity = tuple(float(v) for v in velocity)
            p.body_mass = float(rng.uniform(0.4, 1.6))
            p.collision_shape = "BOX"
            p.collision_half_extents = tuple(float(abs(v)) for v in obj.scale)
            p.collision_radius = float(max(p.collision_half_extents))
            p.angular_velocity = tuple(float(v) for v in rng.uniform(-1.2, 1.2, size=3))
            p.field_coupling = float(rng.uniform(50.0, 100.0))
            p.thermal_coupling = 0.0
            p.field_torque_coupling = float(rng.uniform(0.0, 0.12))
            p.linear_drag = float(rng.uniform(0.02, 0.05))
            p.angular_drag = float(rng.uniform(0.02, 0.06))
            p.restitution = float(rng.uniform(0.25, 0.50))
            p.friction = 0.30
            p.phase_transition_temperature = 1.2

        runtime.reset_runtime()
        s.status = f"Created QFG Dynamics showcase with {count} field-coupled bodies"
        self.report({"INFO"}, s.status)
        return {"FINISHED"}


class QFG_OT_CreateHeroShowcase(bpy.types.Operator):
    bl_idname = "qfg.create_hero_showcase"
    bl_label = "Build Native QFG Hero Showcase"
    bl_description = "Build a safe procedural showcase stage from the selected QFG mode"

    bake_after_build: BoolProperty(name="Bake after build", default=False)
    render_after_bake: BoolProperty(name="Render still", default=False)

    def execute(self, context):
        scene, s = context.scene, context.scene.qfg_settings
        mode = s.showcase_mode
        quality = s.showcase_quality
        try:
            if mode == "COLLISION":
                result = bpy.ops.qfg.create_dynamics_showcase(body_count=s.showcase_body_count)
            else:
                result = bpy.ops.qfg.create_preset(preset=mode)
            if "CANCELLED" in result:
                raise RuntimeError(f"Could not create {mode} preset")

            apply_mode_settings(s, mode, quality)
            if mode == "COLLISION":
                s.dynamics_enabled = True
                s.dynamics_substeps = max(1, s.dynamics_substeps)
            build_stage(scene, mode, quality)
            recommended = int(SHOWCASE_MODE_CONFIG[mode]["still"])
            s.showcase_still_frame = min(s.bake_end, max(s.bake_start, recommended))

            result = bpy.ops.qfg.initialize()
            if "CANCELLED" in result:
                raise RuntimeError("Showcase initialization was cancelled")
            prepare_field_renderer(s.point_radius, mode)
            s.status = f"Native {mode} showcase built and initialized ({quality})"

            if self.bake_after_build:
                result = bpy.ops.qfg.bake_timeline()
                if "CANCELLED" in result:
                    raise RuntimeError("Showcase bake was cancelled")
                prepare_field_renderer(s.point_radius, mode)
                scene.frame_set(s.bake_start)
                if self.render_after_bake:
                    path = render_still(scene, mode, s.showcase_still_frame, s.output_directory)
                    s.status = f"Native {mode} hero still rendered: {path}"
            self.report({"INFO"}, s.status)
            return {"FINISHED"}
        except Exception as exc:
            s.status = f"Showcase build failed: {exc}"
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_RenderHeroStill(bpy.types.Operator):
    bl_idname = "qfg.render_hero_still"
    bl_label = "Render QFG Hero Still"
    bl_description = "Render the selected baked frame with the native safe camera"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            path = render_still(context.scene, s.showcase_mode, s.showcase_still_frame, s.output_directory)
            s.status = f"Hero still rendered: {path}"
            self.report({"INFO"}, s.status)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_CheckBackend(bpy.types.Operator):
    bl_idname = "qfg.check_backend"
    bl_label = "Check Numerical Backend"

    def execute(self, context):
        torch_ok = QFGEngine3D.torch_available()
        cuda_ok = QFGEngine3D.cuda_available()
        blender_version = ".".join(str(v) for v in bpy.app.version)
        python_version = sys.version.split()[0]
        status = (
            f"Blender={blender_version}; Python={python_version}; NumPy=yes; "
            f"PyTorch={'yes' if torch_ok else 'no'}; CUDA={'yes' if cuda_ok else 'no'}"
        )
        context.scene.qfg_settings.backend_status = status
        self.report({"INFO"}, status)
        return {"FINISHED"}


class QFG_OT_CopyTorchCommand(bpy.types.Operator):
    bl_idname = "qfg.copy_torch_command"
    bl_label = "Copy Optional PyTorch Command"

    def execute(self, context):
        context.window_manager.clipboard = f'"{sys.executable}" -m pip install torch'
        self.report({"INFO"}, "Copied. PyTorch is optional; select a build compatible with Blender Python and your GPU.")
        return {"FINISHED"}


class QFG_OT_RunROM(bpy.types.Operator):
    bl_idname = "qfg.run_rom"
    bl_label = "Run RF Resonator Sweep"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            cfg = ROMConfig(
                detuning_min=s.rom_detuning_min, detuning_max=s.rom_detuning_max,
                points=s.rom_points, drive_amplitude=s.rom_drive,
                linear_loss=s.rom_linear_loss, nonlinear_loss=s.rom_nonlinear_loss,
                duffing=s.rom_duffing, external_coupling=s.rom_external_coupling,
                dt=s.rom_dt, settle_steps=s.rom_settle_steps,
                second_tone_ratio=s.rom_second_tone_ratio,
                second_tone_offset=s.rom_second_tone_offset,
            )
            result = hysteresis(cfg)
            runtime.last_rom_result = result
            create_curve_plot(context.scene, "QFG_RF_Forward", result["detuning"], result["forward_db"], location=(0.0, 7.0, 0.0))
            create_curve_plot(context.scene, "QFG_RF_Reverse", result["detuning"], result["reverse_db"], location=(0.0, 7.0, 0.0))
            s.status = "RF forward/reverse sweep completed"
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_RunHRMScan(bpy.types.Operator):
    bl_idname = "qfg.run_hrm_scan"
    bl_label = "Run HRM Frequency Scan"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            cfg = HRMScanConfig(
                f1_min=s.scan_f1_min, f1_max=s.scan_f1_max,
                f2_min=s.scan_f2_min, f2_max=s.scan_f2_max,
                points=s.scan_points, duration=s.scan_duration,
                dt=s.scan_dt, nx=s.scan_nx,
                rho0=s.rho0, lambda_cohesion=s.lambda_cohesion,
                damping=s.damping, a1=s.drive_a1, a2=s.drive_a2,
                alpha=s.alpha_dielectric, zeta_em=s.zeta_em,
                noise_amplitude=s.noise_amplitude if s.noise_enabled else 0.0,
                seed=s.noise_seed,
            )
            result = hrm_scan(cfg)
            runtime.last_hrm_scan = result
            image = update_named_heatmap("QFG_HRM_ModeVar", result["modevar"])
            create_image_plane(context.scene, "QFG_HRM_Heatmap", image, location=(0.0, 15.0, 0.0), size=(8.0, 8.0))
            s.scan_best = f"f1={result['best_f1']:.3g}, f2={result['best_f2']:.3g}, |Δf|={result['best_difference']:.3g}, modeVar={result['best_modevar']:.4g}"
            s.status = "HRM scan complete; minima are candidate locking regions"
            self.report({"INFO"}, s.scan_best)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_RunPlasma(bpy.types.Operator):
    bl_idname = "qfg.run_plasma"
    bl_label = "Run Glow-Plasma Proxy"

    def execute(self, context):
        s = context.scene.qfg_settings
        cfg = PlasmaConfig(
            duration=max(s.scan_duration, 1.0), dt=s.scan_dt,
            f1=s.drive_f1, f2=s.drive_f2, a1=s.drive_a1, a2=s.drive_a2,
            ionization_gain=s.plasma_ionization,
            recombination=s.plasma_recombination,
            boundary_factor=s.plasma_boundary_factor,
        )
        result = simulate_glow_plasma(cfg)
        runtime.last_plasma_result = result
        create_curve_plot(context.scene, "QFG_Plasma_Light", result["time"], result["light"], location=(10.0, 7.0, 0.0))
        s.status = "Glow-plasma envelope proxy completed"
        return {"FINISHED"}


class QFG_OT_RunCavityShift(bpy.types.Operator):
    bl_idname = "qfg.run_cavity_shift"
    bl_label = "Run Cavity Shift Comparison"

    def execute(self, context):
        s = context.scene.qfg_settings
        cfg = CavityShiftConfig(
            power_max=s.cavity_power_max, alpha=s.alpha_dielectric,
            density_per_power=s.cavity_density_per_power,
            thermal_coefficient=s.cavity_thermal_coefficient,
            q_factor=s.cavity_q_factor,
        )
        result = cavity_shift_sweep(cfg)
        runtime.last_cavity_shift = result
        create_curve_plot(context.scene, "QFG_Cavity_QFG_Shift", result["power"], result["qfg_shift"], location=(10.0, 14.0, 0.0))
        create_curve_plot(context.scene, "QFG_Cavity_Thermal_Shift", result["power"], result["thermal_shift"], location=(10.0, 14.0, 0.0))
        s.status = "Cavity power/Q comparison completed"
        return {"FINISHED"}


class QFG_OT_RunMEMS(bpy.types.Operator):
    bl_idname = "qfg.run_mems"
    bl_label = "Run MEMS Geometry Sweep"

    def execute(self, context):
        s = context.scene.qfg_settings
        result = mems_geometry_sweep(MEMSConfig(
            base_q=s.mems_base_q,
            qfg_geometry_scale=s.mems_geometry_scale,
        ))
        runtime.last_mems_result = result
        create_curve_plot(context.scene, "QFG_MEMS_Q", result["geometry"], result["q_factor"], location=(20.0, 7.0, 0.0))
        s.status = "MEMS geometry/Q proxy completed"
        return {"FINISHED"}


class QFG_OT_RunYb(bpy.types.Operator):
    bl_idname = "qfg.run_yb"
    bl_label = "Run Yb Control Suite"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            cfg = yb_config(s)
            rabi = simulate_rabi(cfg)
            ramsey = simulate_ramsey(cfg, s.yb_ramsey_free_time)
            odmr = simulate_odmr_sweep(cfg, s.yb_odmr_min, s.yb_odmr_max, s.yb_odmr_points)
            q_sweep = q_factor_sweep(cfg)
            two_ion = two_ion_phase_proxy(cfg)
            runtime.last_yb_result = {
                "rabi_time": rabi["time"], "rabi_population": rabi["excited_population"],
                "ramsey_time": ramsey["free_time"], "ramsey_population": ramsey["excited_population"],
                "odmr_frequency": odmr["frequency"], "odmr_fluorescence": odmr["fluorescence"],
                "q_factor": q_sweep["q_factor"], "q_shift": q_sweep["shift"],
                "two_ion_phase": two_ion["modulation_phase"], "two_ion_offset": two_ion["phase_offset"],
                "qfg_shift": float(rabi["qfg_shift"]),
            }
            create_curve_plot(context.scene, "QFG_Yb_Rabi", rabi["time"], rabi["excited_population"], location=(0.0, 23.0, 0.0))
            create_curve_plot(context.scene, "QFG_Yb_Ramsey", ramsey["free_time"], ramsey["excited_population"], location=(9.0, 23.0, 0.0))
            create_curve_plot(context.scene, "QFG_Yb_ODMR", odmr["frequency"], odmr["fluorescence"], location=(18.0, 23.0, 0.0))
            create_curve_plot(context.scene, "QFG_Yb_QShift", np.log10(q_sweep["q_factor"]), q_sweep["shift"], location=(27.0, 23.0, 0.0))
            s.status = f"Yb suite complete; candidate model shift={float(rabi['qfg_shift']):.6g}"
            self.report({"INFO"}, s.status)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}


class QFG_OT_TagAtlasSelected(bpy.types.Operator):
    bl_idname = "qfg.tag_atlas_selected"
    bl_label = "Tag Selected Atlas Objects"
    bl_description = "Tag selected Blender objects as BSM-SG/Atlas source structures"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(
        name="Atlas role",
        items=[
            ("CORE", "Core", "Contributes to nuclear center"),
            ("VALENCE", "Free valence", "Used for Atlas Direct valence geometry"),
            ("BOUND", "Bound", "Excluded from principal valence"),
            ("EQUATORIAL", "Equatorial", "Equatorial source structure"),
            ("OTHER", "Other", "Other Atlas role"),
        ],
        default="VALENCE",
    )

    def execute(self, context):
        selected = list(context.selected_objects)
        if not selected:
            self.report({"ERROR"}, "Select one or more Blender objects")
            return {"CANCELLED"}
        nucleon_type = context.scene.qfg_settings.atlas_tag_nucleon_type
        for obj in selected:
            p = obj.qfg_actor
            p.enabled = True
            p.actor_type = "ATLAS_NUCLEON"
            p.atlas_role = self.role
            p.atlas_nucleon_type = nucleon_type
            p.atlas_provenance = "SOURCE"
            if not p.atlas_source_note:
                p.atlas_source_note = "BSM-SG Atlas"
        context.scene.qfg_settings.atlas_status = f"Tagged {len(selected)} object(s) as {self.role} / {nucleon_type}"
        return {"FINISHED"}


class QFG_OT_ExtractAtlasGeometry(bpy.types.Operator):
    bl_idname = "qfg.extract_atlas_geometry"
    bl_label = "Extract Atlas Geometry"
    bl_description = "Compute blind valence-vector geometry from tagged Atlas objects only"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            result, center, valence = extract_atlas_geometry(context.scene)
            payload = result.to_dict()
            payload["center"] = [float(v) for v in center]
            payload["source_objects"] = [
                {
                    "name": obj.name,
                    "nucleon_type": obj.qfg_actor.atlas_nucleon_type,
                    "role": obj.qfg_actor.atlas_role,
                    "direction_mode": obj.qfg_actor.atlas_direction_mode,
                    "provenance": obj.qfg_actor.atlas_provenance,
                    "source_note": obj.qfg_actor.atlas_source_note,
                }
                for obj in valence
            ]
            runtime.last_atlas_result = payload

            s.atlas_mean_angle = result.mean_pair_angle_deg
            s.atlas_angle_spread = result.std_pair_angle_deg
            s.atlas_min_angle = result.min_pair_angle_deg
            s.atlas_max_angle = result.max_pair_angle_deg
            s.atlas_height_ratio = result.c3v_height_ratio or 0.0
            s.atlas_status = (
                f"DERIVED {len(valence)} valence vectors: mean={result.mean_pair_angle_deg:.4f}°, "
                f"σ={result.std_pair_angle_deg:.4f}°"
            )

            scale = float(s.atlas_vector_scale)
            unit = np.asarray(result.unit_vectors, dtype=np.float64)
            positions = np.vstack([center, center[None, :] + scale * unit])
            bonds = [(0, i + 1, scale) for i in range(len(unit))]
            create_bond_curves(context.scene, "QFG_Atlas_Valence_Vectors", positions, bonds)

            for obj, vector in zip(valence, result.unit_vectors):
                obj["qfg_atlas_unit_vector"] = tuple(float(v) for v in vector)
                obj["qfg_atlas_geometry_provenance"] = "DERIVED"
            self.report({"INFO"}, s.atlas_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_status = f"Atlas extraction failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}




class QFG_OT_AutoDetectAtlasSelected(bpy.types.Operator):
    bl_idname = "qfg.auto_detect_atlas_selected"
    bl_label = "Auto-detect Selected"
    bl_description = "Conservative name-based nucleon/role tagging; DERIVED heuristic that must be reviewed"
    bl_options = {"REGISTER", "UNDO"}

    overwrite_source: BoolProperty(
        name="Overwrite SOURCE tags",
        description="Allow the heuristic to replace explicit SOURCE tags (normally leave disabled)",
        default=False,
    )

    def execute(self, context):
        selected = list(context.selected_objects)
        if not selected:
            self.report({"ERROR"}, "Select one or more named Blender objects")
            return {"CANCELLED"}
        tagged = 0
        skipped_source = 0
        unresolved = 0
        for obj in selected:
            p = obj.qfg_actor
            if p.enabled and p.actor_type == "ATLAS_NUCLEON" and p.atlas_provenance == "SOURCE" and not self.overwrite_source:
                skipped_source += 1
                continue
            guess = infer_nucleon_from_name(obj.name)
            if guess.nucleon_type == "OTHER" and guess.role == "OTHER":
                unresolved += 1
                p.atlas_inference_confidence = 0.0
                p.atlas_inference_note = "; ".join(guess.evidence)
                continue
            p.enabled = True
            p.actor_type = "ATLAS_NUCLEON"
            if guess.nucleon_type != "OTHER":
                p.atlas_nucleon_type = guess.nucleon_type
            if guess.role != "OTHER":
                p.atlas_role = guess.role
            p.atlas_provenance = "DERIVED"
            p.atlas_inference_confidence = float(guess.confidence)
            p.atlas_inference_note = "; ".join(guess.evidence)
            p.atlas_source_note = "B2 name heuristic — review before treating as SOURCE"
            tagged += 1
        s = context.scene.qfg_settings
        s.atlas_status = (
            f"B2 auto-detect: {tagged} tagged, {unresolved} unresolved, "
            f"{skipped_source} SOURCE tag(s) preserved"
        )
        self.report({"INFO"}, s.atlas_status)
        return {"FINISHED"}


class QFG_OT_BuildAtlasInteractionGraph(bpy.types.Operator):
    bl_idname = "qfg.build_atlas_interaction_graph"
    bl_label = "Build Interaction Graph"
    bl_description = "Build Atlas topology and optional conditional J_ij geometry proxy"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            nodes, objects, _center = atlas_graph_nodes(context.scene, s)
            graph = build_interaction_graph(
                nodes,
                topology=s.atlas_graph_topology,
                kernel=s.atlas_graph_kernel,
                softening=s.atlas_graph_softening,
            )
            runtime.last_atlas_graph = graph.to_dict()
            s.atlas_graph_edge_count = len(graph.edges)
            s.atlas_graph_total_proxy = float(graph.total_j_proxy)
            s.atlas_graph_mean_proxy = float(graph.mean_abs_j_proxy)
            s.atlas_graph_status = (
                f"{graph.provenance} {graph.topology}: {len(graph.edges)} edge(s), "
                f"kernel={graph.kernel}"
            )
            positions = np.asarray(
                [tuple(float(v) for v in obj.matrix_world.translation) for obj in objects],
                dtype=np.float64,
            )
            bonds = [(edge.i, edge.j, edge.distance) for edge in graph.edges]
            create_bond_curves(context.scene, "QFG_Atlas_Interaction_Graph", positions, bonds)
            self.report({"INFO"}, s.atlas_graph_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_graph_status = f"B2 graph failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ExtractAtlasOrbitalPlanes(bpy.types.Operator):
    bl_idname = "qfg.extract_atlas_orbital_planes"
    bl_label = "Extract Orbital Planes"
    bl_description = "Extract orbital-plane normals from tagged object local axes or a conditional valence-vector bridge"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            center = atlas_center(context.scene, s)
            objects = [
                obj for obj in atlas_objects(context.scene)
                if obj.qfg_actor.atlas_role in {"VALENCE", "EQUATORIAL"}
            ]
            if len(objects) < 2:
                raise ValueError("Tag at least two VALENCE/EQUATORIAL Atlas objects")

            valence = atlas_objects(context.scene, "VALENCE")
            if len(valence) >= 2:
                vectors = [atlas_object_direction(obj, center) for obj in valence]
                geometry = analyze_valence_vectors(
                    vectors, names=[obj.name for obj in valence],
                    element=s.atlas_element, provenance="DERIVED",
                )
                symmetry_axis = geometry.symmetry_axis
            else:
                symmetry_axis = (0.0, 0.0, 1.0)

            normals = []
            provenances = []
            for obj in objects:
                normal, provenance = atlas_orbital_normal(obj, center)
                normals.append(normal)
                provenances.append(provenance)
            overall_provenance = "CONDITIONAL" if "CONDITIONAL" in provenances else (
                "SOURCE" if all(p == "SOURCE" for p in provenances) else "DERIVED"
            )
            result = analyze_orbital_planes(
                normals,
                names=[obj.name for obj in objects],
                symmetry_axis=symmetry_axis,
                provenance=overall_provenance,
            )
            payload = result.to_dict()
            payload["normal_modes"] = [obj.qfg_actor.atlas_orbital_normal_mode for obj in objects]
            runtime.last_atlas_planes = payload
            s.atlas_plane_mean_dihedral = float(result.mean_pair_dihedral_deg)
            s.atlas_plane_spread = float(result.std_pair_dihedral_deg)
            s.atlas_plane_status = (
                f"{result.provenance} {len(result.planes)} plane(s): mean dihedral="
                f"{result.mean_pair_dihedral_deg:.3f}°"
            )
            centers = np.asarray(
                [tuple(float(v) for v in obj.matrix_world.translation) for obj in objects],
                dtype=np.float64,
            )
            normal_array = np.asarray(normals, dtype=np.float64)
            create_orbital_plane_rings(
                context.scene,
                "QFG_Atlas_Orbital_Planes",
                centers,
                normal_array,
                radius=float(s.atlas_plane_scale),
            )
            for obj, normal, provenance in zip(objects, normal_array, provenances):
                obj["qfg_atlas_orbital_normal"] = tuple(float(v) for v in normal)
                obj["qfg_atlas_orbital_plane_provenance"] = provenance
            self.report({"INFO"}, s.atlas_plane_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_plane_status = f"Orbital-plane extraction failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_BuildIntegratedBohrEnvelope(bpy.types.Operator):
    bl_idname = "qfg.build_integrated_bohr_envelope"
    bl_label = "Build Bohr Envelope Proxy"
    bl_description = "Build an oriented geometric envelope around tagged Atlas structures; CONDITIONAL proxy, not a solved field surface"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            objects = atlas_objects(context.scene)
            if not objects:
                raise ValueError("Tag at least one Atlas object")
            positions = [tuple(float(v) for v in obj.matrix_world.translation) for obj in objects]
            radii = [atlas_object_radius(obj, s) for obj in objects]
            envelope = estimate_integrated_bohr_envelope(
                positions, radii=radii, padding=s.atlas_bohr_padding,
            )
            payload = envelope.to_dict()
            payload["source_objects"] = [obj.name for obj in objects]
            payload["radius_mode"] = s.atlas_bohr_radius_mode
            runtime.last_bohr_envelope = payload
            s.atlas_bohr_volume = float(envelope.ellipsoid_volume)
            s.atlas_bohr_sphere_radius = float(envelope.bounding_sphere_radius)
            s.atlas_bohr_status = (
                f"CONDITIONAL envelope: axes="
                f"({envelope.axes[0]:.3g}, {envelope.axes[1]:.3g}, {envelope.axes[2]:.3g})"
            )

            old = bpy.data.objects.get("QFG_Atlas_Bohr_Envelope")
            if old is not None:
                bpy.data.objects.remove(old, do_unlink=True)
            obj = add_uv_sphere(
                context.scene,
                "QFG_Atlas_Bohr_Envelope",
                envelope.center,
                scale=envelope.axes,
                collection_name="QFG Results",
            )
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = Matrix(envelope.rotation_matrix).to_quaternion()
            obj.display_type = "WIRE"
            obj.show_in_front = True
            obj.hide_render = True
            obj["qfg_provenance"] = "CONDITIONAL"
            obj["qfg_scientific_note"] = envelope.note
            self.report({"INFO"}, s.atlas_bohr_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_bohr_status = f"Bohr-envelope proxy failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ApplyAtlasField(bpy.types.Operator):
    bl_idname = "qfg.apply_atlas_field"
    bl_label = "Build / Apply Atlas Field"
    bl_description = "Rasterize tagged Atlas geometry into the reduced QFG scalar/vector field; CONDITIONAL bridge"

    def execute(self, context):
        s = context.scene.qfg_settings
        try:
            payload = apply_atlas_field_to_engine(context.scene)
            summary = payload["summary"]
            self.report({"INFO"}, s.atlas_field_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_field_status = f"B3 field failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ClearAtlasField(bpy.types.Operator):
    bl_idname = "qfg.clear_atlas_field"
    bl_label = "Clear Atlas Field"
    bl_description = "Remove the B3 Atlas scalar/vector field from the live QFG engine"

    def execute(self, context):
        if runtime.engine is not None:
            runtime.engine.clear_atlas_field()
        runtime.last_atlas_field = None
        s = context.scene.qfg_settings
        s.atlas_field_source_count = 0
        s.atlas_field_scalar_min = 0.0
        s.atlas_field_scalar_max = 0.0
        s.atlas_field_scalar_rms = 0.0
        s.atlas_field_vector_max = 0.0
        s.atlas_field_vector_rms = 0.0
        s.atlas_field_status = "B3 Atlas field cleared"
        self.report({"INFO"}, s.atlas_field_status)
        return {"FINISHED"}



class QFG_OT_CaptureAtlasFeedbackAnchors(bpy.types.Operator):
    bl_idname = "qfg.capture_atlas_feedback_anchors"
    bl_label = "Capture B4 Anchors"
    bl_description = "Capture current reviewed Atlas transforms/directions as the bounded B4 relaxation reference"

    def execute(self, context):
        try:
            count = capture_atlas_feedback_anchors(context.scene)
            self.report({"INFO"}, f"Captured {count} B4 Atlas anchor(s)")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ResetAtlasFeedbackAnchors(bpy.types.Operator):
    bl_idname = "qfg.reset_atlas_feedback_anchors"
    bl_label = "Reset to B4 Anchors"
    bl_description = "Restore tagged Atlas sources to the transforms captured for B4 feedback"

    def execute(self, context):
        try:
            count = reset_atlas_feedback_anchors(context.scene)
            if context.scene.qfg_settings.atlas_field_enabled and runtime.engine is not None:
                apply_atlas_field_to_engine(context.scene, runtime.engine)
            self.report({"INFO"}, f"Restored {count} B4 Atlas source(s)")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ApplyAtlasFeedback(bpy.types.Operator):
    bl_idname = "qfg.apply_atlas_feedback"
    bl_label = "Apply B4 Feedback Once"
    bl_description = "Sample the current QFG field and apply one bounded conditional force/torque relaxation update to Atlas sources"

    def execute(self, context):
        s = context.scene.qfg_settings
        if runtime.engine is None:
            self.report({"ERROR"}, "Initialize the QFG engine first")
            return {"CANCELLED"}
        if not s.atlas_feedback_enabled:
            self.report({"ERROR"}, "Enable B4 bidirectional feedback first")
            return {"CANCELLED"}
        try:
            dt = runtime.engine.config.dt * (runtime.world.world_config.substeps if runtime.world is not None else 1)
            apply_atlas_feedback(context.scene, runtime.engine, effective_dt=dt)
            self.report({"INFO"}, s.atlas_feedback_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_feedback_status = f"B4 feedback failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}



class QFG_OT_CaptureAtlasConstraints(bpy.types.Operator):
    bl_idname = "qfg.capture_atlas_constraints"
    bl_label = "Capture B5 Constraints"
    bl_description = "Capture current reviewed Atlas shell/connectivity/angular/symmetry geometry as the B5 admissible set"

    def execute(self, context):
        try:
            capture_atlas_constraints(context.scene)
            self.report({"INFO"}, context.scene.qfg_settings.atlas_constraints_status)
            return {"FINISHED"}
        except Exception as exc:
            context.scene.qfg_settings.atlas_constraints_status = f"B5 capture failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ClearAtlasConstraints(bpy.types.Operator):
    bl_idname = "qfg.clear_atlas_constraints"
    bl_label = "Clear B5 Constraints"
    bl_description = "Clear the captured B5 constraint snapshot without changing Atlas transforms"

    def execute(self, context):
        clear_atlas_constraints(context.scene)
        self.report({"INFO"}, "B5 constraint snapshot cleared")
        return {"FINISHED"}


class QFG_OT_ApplyAtlasConstraints(bpy.types.Operator):
    bl_idname = "qfg.apply_atlas_constraints"
    bl_label = "Project Into B5 Constraints"
    bl_description = "Project current Atlas positions into the captured B5 admissible geometry without advancing the QFG field"

    def execute(self, context):
        s = context.scene.qfg_settings
        if not s.atlas_constraints_enabled:
            self.report({"ERROR"}, "Enable B5 geometry constraints first")
            return {"CANCELLED"}
        try:
            apply_atlas_constraints_to_scene(context.scene)
            self.report({"INFO"}, s.atlas_constraints_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_constraints_status = f"B5 projection failed: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_RunBlindAtlasRelaxation(bpy.types.Operator):
    bl_idname = "qfg.run_blind_atlas_relaxation"
    bl_label = "Run B6 Blind Relaxation"
    bl_description = "Run the end-to-end Group-15 Atlas/QFG relaxation until prediction-only convergence; experimental references remain hidden"

    def execute(self, context):
        scene = context.scene
        s = scene.qfg_settings
        if s.atlas_element == "CUSTOM":
            self.report({"ERROR"}, "Choose N, P, As or Sb for B6 Group-15 blind relaxation")
            return {"CANCELLED"}
        if s.atlas_reference_revealed:
            self.report({"ERROR"}, "Experimental holdout is already revealed. Reset Atlas Holdout before a strict B6 blind run")
            return {"CANCELLED"}
        if s.atlas_frozen:
            self.report({"ERROR"}, "A prediction is already frozen. Reset Atlas Holdout before starting a new B6 run")
            return {"CANCELLED"}
        if not (s.atlas_field_enabled and s.atlas_feedback_enabled and s.atlas_constraints_enabled):
            self.report({"ERROR"}, "B6 requires B3 field, B4 feedback and B5 constraints to be enabled")
            return {"CANCELLED"}

        cfg = atlas_blind_config(s)
        try:
            cfg.validate()
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}

        s.atlas_blind_running = True
        s.atlas_blind_status = "B6 preparing blind run; experimental reference hidden"
        samples: list[BlindRelaxationSample] = []
        wm = context.window_manager
        try:
            initial_result, initial_center, initial_valence = extract_atlas_geometry(scene)
            if len(initial_valence) != 3:
                raise ValueError(f"B6 Group-15 protocol requires exactly three VALENCE objects; found {len(initial_valence)}")
            if any(obj.qfg_actor.atlas_provenance == "REJECTED" for obj in initial_valence):
                raise ValueError("REJECTED geometry cannot enter a B6 blind prediction")

            captured = [obj for obj in atlas_objects(scene) if bool(obj.get("qfg_b4_anchor_captured", False))]
            if s.atlas_blind_reset_to_anchors:
                if captured:
                    reset_atlas_feedback_anchors(scene)
                else:
                    capture_atlas_feedback_anchors(scene)
            elif not captured:
                capture_atlas_feedback_anchors(scene)

            if s.atlas_blind_recapture_constraints:
                capture_atlas_constraints(scene)
            elif _b5_snapshot(scene) is None:
                if s.atlas_constraints_auto_capture:
                    capture_atlas_constraints(scene)
                else:
                    raise ValueError("B5 constraint snapshot missing; capture constraints or enable B6 recapture")

            # Re-extract after optional reset, then freeze the source/config protocol.
            initial_result, initial_center, initial_valence = extract_atlas_geometry(scene)
            initial_payload = initial_result.to_dict()
            initial_payload["center"] = [float(v) for v in initial_center]
            protocol = atlas_blind_protocol_payload(scene)
            fingerprint = protocol_fingerprint(protocol)
            s.atlas_blind_protocol_hash = fingerprint

            if s.atlas_blind_auto_initialize or runtime.engine is None:
                initialize_engine(scene)
            if runtime.engine is None:
                raise ValueError("B6 requires an initialized QFG engine")
            # B6 always builds the starting field explicitly, independent of the ordinary B3 auto-apply preference.
            apply_atlas_field_to_engine(scene, runtime.engine)

            wm.progress_begin(0, int(cfg.max_iterations))
            summary = evaluate_blind_convergence(samples, cfg)
            for iteration in range(1, int(cfg.max_iterations) + 1):
                for _ in range(int(s.atlas_blind_steps_per_iteration)):
                    if runtime.world is not None:
                        step_result = runtime.world.step(1)
                        effective_dt = runtime.engine.config.dt * runtime.world.world_config.substeps
                    else:
                        runtime.engine.step(1)
                        effective_dt = runtime.engine.config.dt
                    apply_atlas_feedback(scene, runtime.engine, effective_dt=effective_dt)

                result, center, valence = extract_atlas_geometry(scene)
                if len(valence) != 3:
                    raise ValueError("VALENCE object count changed during B6 run; aborting blind protocol")
                samples.append(BlindRelaxationSample(
                    iteration=iteration,
                    qfg_time=float(runtime.engine.time),
                    mean_pair_angle_deg=float(result.mean_pair_angle_deg),
                    std_pair_angle_deg=float(result.std_pair_angle_deg),
                    min_pair_angle_deg=float(result.min_pair_angle_deg),
                    max_pair_angle_deg=float(result.max_pair_angle_deg),
                    c3v_height_ratio=None if result.c3v_height_ratio is None else float(result.c3v_height_ratio),
                    max_constraint_correction=float(s.atlas_constraints_max_correction_used),
                    feedback_work_proxy=float(s.atlas_feedback_total_work),
                ))
                summary = evaluate_blind_convergence(samples, cfg)
                s.atlas_blind_iterations_used = iteration
                s.atlas_blind_final_angle = float(summary.final_angle_deg)
                s.atlas_blind_final_spread = float(summary.final_spread_deg)
                s.atlas_blind_window_range = float(summary.window_angle_range_deg if np.isfinite(summary.window_angle_range_deg) else 0.0)
                s.atlas_blind_window_slope = float(summary.window_angle_slope_deg_per_iter if np.isfinite(summary.window_angle_slope_deg_per_iter) else 0.0)
                s.atlas_blind_status = (
                    f"B6 blind iter {iteration}/{cfg.max_iterations}: angle={summary.final_angle_deg:.5f}°, "
                    f"window={summary.window_angle_range_deg:.4g}°, drift={summary.window_angle_slope_deg_per_iter:+.3g}°/iter"
                )
                wm.progress_update(iteration)
                if summary.converged:
                    break

            final_result, final_center, final_valence = extract_atlas_geometry(scene)
            final_payload = _store_atlas_geometry_result(scene, final_result, final_center, final_valence, provenance="CONDITIONAL")
            # Draw only the final vectors; the iterative trajectory stays data-only.
            scale = float(s.atlas_vector_scale)
            unit = np.asarray(final_result.unit_vectors, dtype=np.float64)
            positions = np.vstack([final_center, final_center[None, :] + scale * unit])
            bonds = [(0, i + 1, scale) for i in range(len(unit))]
            create_bond_curves(scene, "QFG_Atlas_Valence_Vectors", positions, bonds)

            run_payload = {
                "protocol": protocol,
                "protocol_sha256": fingerprint,
                "config": asdict(cfg) | {"steps_per_iteration": int(s.atlas_blind_steps_per_iteration)},
                "initial_geometry": initial_payload,
                "samples": [sample.to_dict() for sample in samples],
                "summary": summary.to_dict(),
                "final_geometry": dict(final_payload),
                "reference_consulted": False,
                "provenance": "CONDITIONAL",
                "note": (
                    "B6 stopped using prediction-only convergence gates. The experimental Group-15 registry "
                    "was not consulted by the run or convergence detector."
                ),
            }
            runtime.last_atlas_blind_run = run_payload
            final_payload["b6_blind_run"] = run_payload
            s.atlas_blind_converged = bool(summary.converged)
            if summary.converged and s.atlas_blind_freeze_on_convergence:
                s.atlas_frozen = True
                s.atlas_reference_revealed = False
                s.atlas_frozen_angle = float(summary.final_angle_deg)
                s.atlas_frozen_spread = float(summary.final_spread_deg)
                s.atlas_frozen_element = str(s.atlas_element)
                s.atlas_reference_angle = 0.0
                s.atlas_residual_angle = 0.0
                s.atlas_residual_percent = 0.0
                scene["qfg_atlas_frozen_prediction"] = {
                    "element": s.atlas_frozen_element,
                    "angle_deg": s.atlas_frozen_angle,
                    "spread_deg": s.atlas_frozen_spread,
                    "provenance": "CONDITIONAL",
                    "protocol": "B6_GROUP15_BLIND_RELAXATION",
                    "protocol_sha256": fingerprint,
                }
                s.atlas_status = (
                    f"B6 FROZEN {s.atlas_frozen_element}: {s.atlas_frozen_angle:.4f}°; "
                    "experimental reference still hidden"
                )
            elif summary.converged:
                s.atlas_status = f"B6 converged at {summary.final_angle_deg:.4f}°; freeze manually before reveal"
            else:
                s.atlas_status = f"B6 NOT CONVERGED after {len(samples)} iterations; prediction not auto-frozen"
            s.atlas_blind_status = (
                f"B6 {'CONVERGED' if summary.converged else 'OPEN'}: angle={summary.final_angle_deg:.5f}°, "
                f"σ={summary.final_spread_deg:.4g}°, {summary.reason}; hash={fingerprint[:12]}"
            )
            update_metrics(s, runtime.engine.compute_diagnostics())
            update_visuals(scene)
            self.report({"INFO" if summary.converged else "WARNING"}, s.atlas_blind_status)
            return {"FINISHED"}
        except Exception as exc:
            s.atlas_blind_status = f"B6 blind run failed: {exc}"
            self.report({"ERROR"}, str(exc))
            traceback.print_exc()
            return {"CANCELLED"}
        finally:
            s.atlas_blind_running = False
            try:
                wm.progress_end()
            except Exception:
                pass


class QFG_OT_ResetBlindAtlasRun(bpy.types.Operator):
    bl_idname = "qfg.reset_blind_atlas_run"
    bl_label = "Reset B6 Run Record"
    bl_description = "Clear B6 convergence history/status without changing Atlas geometry or experimental holdout state"

    def execute(self, context):
        reset_atlas_blind_run(context.scene)
        self.report({"INFO"}, "B6 blind-run record cleared; Atlas geometry unchanged")
        return {"FINISHED"}


class QFG_OT_FreezeAtlasPrediction(bpy.types.Operator):
    bl_idname = "qfg.freeze_atlas_prediction"
    bl_label = "Freeze Blind Prediction"
    bl_description = "Lock the current derived angle before revealing an experimental reference"

    def execute(self, context):
        s = context.scene.qfg_settings
        result = runtime.last_atlas_result
        if result is None:
            self.report({"ERROR"}, "Extract Atlas geometry before freezing")
            return {"CANCELLED"}
        if s.atlas_element == "CUSTOM":
            self.report({"ERROR"}, "Choose N, P, As or Sb for the built-in blind holdout workflow")
            return {"CANCELLED"}
        if str(result.get("element", "")).upper() != str(s.atlas_element).upper():
            self.report({"ERROR"}, "Holdout element changed after extraction; extract geometry again before freezing")
            return {"CANCELLED"}
        s.atlas_frozen = True
        s.atlas_reference_revealed = False
        s.atlas_frozen_angle = float(result["mean_pair_angle_deg"])
        s.atlas_frozen_spread = float(result["std_pair_angle_deg"])
        s.atlas_frozen_element = s.atlas_element
        s.atlas_reference_angle = 0.0
        s.atlas_residual_angle = 0.0
        s.atlas_residual_percent = 0.0
        context.scene["qfg_atlas_frozen_prediction"] = {
            "element": s.atlas_frozen_element,
            "angle_deg": s.atlas_frozen_angle,
            "spread_deg": s.atlas_frozen_spread,
            "provenance": "DERIVED",
        }
        s.atlas_status = f"FROZEN {s.atlas_frozen_element}: {s.atlas_frozen_angle:.4f}°; reference still hidden"
        self.report({"INFO"}, s.atlas_status)
        return {"FINISHED"}


class QFG_OT_RevealAtlasReference(bpy.types.Operator):
    bl_idname = "qfg.reveal_atlas_reference"
    bl_label = "Reveal Experimental Holdout"
    bl_description = "Reveal the built-in experimental reference only after a blind prediction is frozen"

    def execute(self, context):
        s = context.scene.qfg_settings
        if not s.atlas_frozen:
            self.report({"ERROR"}, "Freeze a blind prediction first")
            return {"CANCELLED"}
        try:
            frozen_payload = context.scene.get("qfg_atlas_frozen_prediction", {})
            prediction_provenance = str(frozen_payload.get("provenance", "DERIVED")) if hasattr(frozen_payload, "get") else "DERIVED"
            comparison = compare_frozen_prediction(
                s.atlas_frozen_angle, s.atlas_frozen_element, prediction_provenance=prediction_provenance,
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        s.atlas_reference_revealed = True
        s.atlas_reference_angle = float(comparison["reference_deg"])
        s.atlas_residual_angle = float(comparison["residual_deg"])
        s.atlas_residual_percent = float(comparison["relative_residual_percent"])
        if runtime.last_atlas_result is None:
            runtime.last_atlas_result = {}
        runtime.last_atlas_result["frozen_holdout"] = comparison
        s.atlas_status = (
            f"HOLDOUT {comparison['molecule']}: predicted={comparison['prediction_deg']:.4f}°, "
            f"experimental={comparison['reference_deg']:.4f}°, Δ={comparison['residual_deg']:+.4f}°"
        )
        self.report({"INFO"}, s.atlas_status)
        return {"FINISHED"}


class QFG_OT_ResetAtlasHoldout(bpy.types.Operator):
    bl_idname = "qfg.reset_atlas_holdout"
    bl_label = "Reset Atlas Holdout"
    bl_description = "Clear the blind freeze/reference reveal state without changing geometry tags"

    def execute(self, context):
        s = context.scene.qfg_settings
        s.atlas_frozen = False
        s.atlas_reference_revealed = False
        s.atlas_frozen_angle = 0.0
        s.atlas_frozen_spread = 0.0
        s.atlas_frozen_element = ""
        s.atlas_reference_angle = 0.0
        s.atlas_residual_angle = 0.0
        s.atlas_residual_percent = 0.0
        if "qfg_atlas_frozen_prediction" in context.scene:
            del context.scene["qfg_atlas_frozen_prediction"]
        if runtime.last_atlas_result is not None:
            runtime.last_atlas_result.pop("frozen_holdout", None)
        s.atlas_status = "Atlas holdout reset; source tags preserved"
        return {"FINISHED"}


class QFG_OT_ExportAtlasReport(bpy.types.Operator):
    bl_idname = "qfg.export_atlas_report"
    bl_label = "Export Atlas Report"
    bl_description = "Export Atlas Direct geometry, provenance and holdout result as JSON/CSV"

    def execute(self, context):
        s = context.scene.qfg_settings
        if runtime.last_atlas_result is None:
            self.report({"ERROR"}, "No Atlas result to export")
            return {"CANCELLED"}
        try:
            base = bpy.path.abspath(s.output_directory)
            session = timestamped_directory(base, "qfg_atlas")
            payload = dict(runtime.last_atlas_result)
            payload["blind_workflow"] = {
                "frozen": bool(s.atlas_frozen),
                "frozen_element": s.atlas_frozen_element,
                "frozen_angle_deg": float(s.atlas_frozen_angle),
                "reference_revealed": bool(s.atlas_reference_revealed),
                "reference_angle_deg": float(s.atlas_reference_angle) if s.atlas_reference_revealed else None,
                "residual_deg": float(s.atlas_residual_angle) if s.atlas_reference_revealed else None,
                "residual_percent": float(s.atlas_residual_percent) if s.atlas_reference_revealed else None,
            }
            payload["b2"] = {
                "interaction_graph": runtime.last_atlas_graph,
                "orbital_planes": runtime.last_atlas_planes,
                "integrated_bohr_envelope": runtime.last_bohr_envelope,
            }
            payload["b3"] = {"atlas_field": runtime.last_atlas_field}
            payload["b4"] = {"atlas_feedback": runtime.last_atlas_feedback}
            payload["b5"] = {"atlas_constraints": runtime.last_atlas_constraints}
            payload["b6"] = {"blind_relaxation": runtime.last_atlas_blind_run}
            write_json(session / "atlas_geometry.json", payload)
            rows = payload.get("pair_angles", [])
            if rows:
                write_rows_csv(session / "atlas_pair_angles.csv", rows)
            if runtime.last_atlas_graph is not None:
                write_json(session / "atlas_interaction_graph.json", runtime.last_atlas_graph)
                edge_rows = runtime.last_atlas_graph.get("edges", [])
                if edge_rows:
                    write_rows_csv(session / "atlas_interaction_edges.csv", edge_rows)
            if runtime.last_atlas_planes is not None:
                write_json(session / "atlas_orbital_planes.json", runtime.last_atlas_planes)
            if runtime.last_bohr_envelope is not None:
                write_json(session / "atlas_bohr_envelope.json", runtime.last_bohr_envelope)
            if runtime.last_atlas_field is not None:
                write_json(session / "atlas_b3_field.json", runtime.last_atlas_field)
            if runtime.last_atlas_feedback is not None:
                write_json(session / "atlas_b4_feedback.json", runtime.last_atlas_feedback)
            if runtime.last_atlas_constraints is not None:
                write_json(session / "atlas_b5_constraints.json", runtime.last_atlas_constraints)
            if runtime.last_atlas_blind_run is not None:
                write_json(session / "atlas_b6_blind_run.json", runtime.last_atlas_blind_run)
                sample_rows = runtime.last_atlas_blind_run.get("samples", [])
                if sample_rows:
                    write_rows_csv(session / "atlas_b6_trajectory.csv", sample_rows)
            s.atlas_status = f"Atlas/B5 report exported to {session}"
            self.report({"INFO"}, s.atlas_status)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_CreateMolecule(bpy.types.Operator):
    bl_idname = "qfg.create_molecule"
    bl_label = "Create Molecule Preset"
    molecule: EnumProperty(
        name="Molecule",
        items=[("H2", "H₂", ""), ("H2O", "H₂O", ""), ("BENZENE", "Benzene", "")],
        default="H2O",
    )

    def execute(self, context):
        scene = context.scene
        clear_collection(MOLECULE_COLLECTION)
        atoms = molecule_preset(self.molecule)
        for atom in atoms:
            radius = max(0.15, atom.covalent_radius * 0.45)
            obj = add_uv_sphere(scene, f"QFG_Atom_{atom.name}", atom.position, scale=(radius, radius, radius), collection_name=MOLECULE_COLLECTION)
            obj.qfg_actor.enabled = True
            obj.qfg_actor.actor_type = "MOLECULE_ATOM"
            obj.qfg_actor.atomic_number = atom.atomic_number
            obj.qfg_actor.atomic_charge = atom.charge
            obj.qfg_actor.covalent_radius = atom.covalent_radius
        context.scene.qfg_settings.molecular_status = f"Created {self.molecule}; evaluate or optimize"
        return {"FINISHED"}


class QFG_OT_EvaluateMolecule(bpy.types.Operator):
    bl_idname = "qfg.evaluate_molecule"
    bl_label = "Evaluate Molecular Proxy"

    def execute(self, context):
        s = context.scene.qfg_settings
        atoms, _objects = molecule_atoms_from_scene(context.scene)
        if not atoms:
            self.report({"ERROR"}, "No molecular atoms in the scene")
            return {"CANCELLED"}
        result = proxy_energy(atoms, molecular_config(s))
        runtime.last_molecular_result = result
        bonds = infer_bonds(atoms, s.mol_bond_tolerance)
        create_bond_curves(context.scene, "QFG_Molecular_Bonds", np.asarray([a.position for a in atoms]), bonds)
        s.molecular_status = (
            f"E={result['proxy_total']:.4g}; gap={result['band_gap_proxy_ev']:.4g} eV; "
            f"λ={result['wavelength_proxy_nm']:.4g} nm; bonds={len(bonds)}"
        )
        self.report({"INFO"}, s.molecular_status)
        return {"FINISHED"}


class QFG_OT_OptimizeMolecule(bpy.types.Operator):
    bl_idname = "qfg.optimize_molecule"
    bl_label = "Optimize Molecular Geometry"

    def execute(self, context):
        s = context.scene.qfg_settings
        atoms, objects = molecule_atoms_from_scene(context.scene)
        if not atoms:
            self.report({"ERROR"}, "No molecular atoms in the scene")
            return {"CANCELLED"}
        target = MolecularTarget(
            target_energy=s.mol_target_energy,
            target_band_gap=s.mol_target_band_gap,
            target_wavelength_nm=s.mol_target_wavelength,
            target_oscillator_strength=s.mol_target_oscillator,
        )
        result = optimize_geometry(
            atoms, molecular_config(s), target,
            OptimizationConfig(iterations=s.mol_opt_iterations, initial_step=s.mol_opt_step),
        )
        for obj, pos in zip(objects, result["positions"]):
            obj.location = tuple(float(v) for v in pos)
        runtime.last_molecular_result = {
            **result["result"],
            "objective_history": result["objective_history"],
            "optimized_positions": result["positions"],
        }
        bonds = infer_bonds(result["atoms"], s.mol_bond_tolerance)
        create_bond_curves(context.scene, "QFG_Molecular_Bonds", result["positions"], bonds)
        create_curve_plot(context.scene, "QFG_Molecular_Objective", np.arange(len(result["objective_history"])), result["objective_history"], location=(20.0, 15.0, 0.0))
        s.molecular_status = f"Optimized objective={result['result']['target_objective']:.5g}"
        self.report({"INFO"}, s.molecular_status)
        return {"FINISHED"}


class QFG_OT_RunValidationSuite(bpy.types.Operator):
    bl_idname = "qfg.run_validation_suite"
    bl_label = "Run Reduced Validation Suite"
    bl_description = "Run RF, HRM, plasma, cavity, MEMS, and Yb prototype models"

    def execute(self, context):
        sequence = [
            bpy.ops.qfg.run_rom,
            bpy.ops.qfg.run_hrm_scan,
            bpy.ops.qfg.run_plasma,
            bpy.ops.qfg.run_cavity_shift,
            bpy.ops.qfg.run_mems,
            bpy.ops.qfg.run_yb,
        ]
        try:
            for operation in sequence:
                result = operation()
                if "CANCELLED" in result:
                    raise RuntimeError("A validation module was cancelled")
            context.scene.qfg_settings.status = "Reduced validation suite completed"
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class QFG_OT_ClearResults(bpy.types.Operator):
    bl_idname = "qfg.clear_results"
    bl_label = "Clear QFG Results"

    def execute(self, context):
        prefixes = ("QFG_",)
        protected = {obj.name for obj in bpy.data.objects if hasattr(obj, "qfg_actor") and obj.qfg_actor.enabled}
        for obj in list(bpy.data.objects):
            if obj.name in protected:
                continue
            if obj.name.startswith(prefixes):
                bpy.data.objects.remove(obj, do_unlink=True)
        for image in list(bpy.data.images):
            if image.name.startswith("QFG_"):
                bpy.data.images.remove(image)
        runtime.cache.clear()
        runtime.engine = None
        runtime.world = None
        runtime.debug_payload = None
        context.scene.qfg_settings.status = "QFG visual results cleared"
        return {"FINISHED"}


CLASSES = (
    QFG_OT_Initialize, QFG_OT_Step, QFG_OT_Reset,
    QFG_OT_UpdateVisualization, QFG_OT_BakeTimeline, QFG_OT_ClearCache,
    QFG_OT_Topology, QFG_OT_ExportSession, QFG_OT_CreatePreset,
    QFG_OT_CreateDynamicsShowcase, QFG_OT_CreateHeroShowcase, QFG_OT_RenderHeroStill,
    QFG_OT_CheckBackend, QFG_OT_CopyTorchCommand,
    QFG_OT_RunROM, QFG_OT_RunHRMScan, QFG_OT_RunPlasma,
    QFG_OT_RunCavityShift, QFG_OT_RunMEMS, QFG_OT_RunYb,
    QFG_OT_TagAtlasSelected, QFG_OT_AutoDetectAtlasSelected, QFG_OT_ExtractAtlasGeometry,
    QFG_OT_BuildAtlasInteractionGraph, QFG_OT_ExtractAtlasOrbitalPlanes,
    QFG_OT_BuildIntegratedBohrEnvelope,
    QFG_OT_ApplyAtlasField, QFG_OT_ClearAtlasField,
    QFG_OT_CaptureAtlasFeedbackAnchors, QFG_OT_ResetAtlasFeedbackAnchors, QFG_OT_ApplyAtlasFeedback,
    QFG_OT_CaptureAtlasConstraints, QFG_OT_ClearAtlasConstraints, QFG_OT_ApplyAtlasConstraints,
    QFG_OT_RunBlindAtlasRelaxation, QFG_OT_ResetBlindAtlasRun,
    QFG_OT_FreezeAtlasPrediction, QFG_OT_RevealAtlasReference,
    QFG_OT_ResetAtlasHoldout, QFG_OT_ExportAtlasReport,
    QFG_OT_CreateMolecule, QFG_OT_EvaluateMolecule,
    QFG_OT_OptimizeMolecule, QFG_OT_RunValidationSuite,
    QFG_OT_ClearResults,
)


def register_operators() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister_operators() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
