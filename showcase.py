"""Native QFG cinematic showcase helpers for Blender 5.2.

The 0.4.x showcase layer moves the robust camera/render rules from the external
hero scripts into the add-on.  It deliberately uses procedural materials only,
disables the compositor for generated showcase renders, and uses an unparented
TRACK_TO camera with depth of field disabled.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Tuple

import bpy
from mathutils import Vector

SHOWCASE_PREFIX = "QFG_SHOW_"

QUALITY_CONFIG = {
    "PREVIEW": {"grid": "32", "max_points": 18000, "resolution": (1280, 720), "frames": 120},
    "FINAL": {"grid": "64", "max_points": 42000, "resolution": (1920, 1080), "frames": 180},
}

MODE_CONFIG: Dict[str, Dict[str, object]] = {
    "COLLISION": {
        "camera": (13.0, -16.5, 7.5), "lens": 48.0, "still": 56,
        "settings": {"field_mode": "SCALAR", "dt": 0.002, "steps_per_frame": 5,
                     "lambda_cohesion": 1.0, "kappa_stability": 0.0019,
                     "damping": 0.006, "thermal_enabled": False,
                     "threshold_fraction": 0.10, "point_radius": 0.060},
    },
    "HOPF": {
        "camera": (10.5, -12.5, 8.0), "lens": 58.0, "still": 72,
        "settings": {"field_mode": "SPINOR", "dt": 0.001, "steps_per_frame": 3,
                     "lambda_cohesion": 2.0, "kappa_stability": 0.01,
                     "damping": 0.004, "thermal_enabled": False,
                     "topology_enabled": True, "skyrme_potential_scale": 0.01,
                     "delta_anisotropy": 0.05, "threshold_fraction": 0.075,
                     "point_radius": 0.052},
    },
    "VORTEX": {
        "camera": (10.0, -12.0, 9.5), "lens": 58.0, "still": 72,
        "settings": {"field_mode": "SPINOR", "dt": 0.001, "steps_per_frame": 4,
                     "lambda_cohesion": 1.5, "kappa_stability": 0.02,
                     "damping": 0.005, "topology_enabled": True,
                     "skyrme_potential_scale": 0.02, "threshold_fraction": 0.08,
                     "point_radius": 0.050},
    },
    "HRM_CAVITY": {
        "camera": (12.0, -15.0, 8.0), "lens": 52.0, "still": 76,
        "settings": {"field_mode": "SCALAR", "dt": 0.001, "steps_per_frame": 4,
                     "lambda_cohesion": 1.0, "kappa_stability": 0.5,
                     "damping": 0.02, "thermal_enabled": False, "hrm_enabled": True,
                     "drive_a1": 0.3, "drive_a2": 0.3, "drive_f1": 5.0,
                     "drive_f2": 6.2, "drive_profile": "STANDING_X",
                     "threshold_fraction": 0.10, "point_radius": 0.050},
    },
    "THERMAL": {
        "camera": (13.0, -16.5, 7.5), "lens": 48.0, "still": 58,
        "settings": {"field_mode": "SCALAR", "dt": 0.0015, "steps_per_frame": 4,
                     "lambda_cohesion": 4.5, "kappa_stability": 0.0019,
                     "damping": 0.003, "thermal_enabled": True,
                     "heat_conduction": 0.05, "collision_heating": 0.03,
                     "critical_temperature": 1.5, "temperature_cap": 5.0,
                     "threshold_fraction": 0.09, "point_radius": 0.060},
    },
    "GAUGE_GRAVITY": {
        "camera": (12.0, -15.0, 8.0), "lens": 56.0, "still": 72,
        "settings": {"field_mode": "SPINOR", "dt": 0.001, "steps_per_frame": 3,
                     "lambda_cohesion": 1.5, "kappa_stability": 0.005,
                     "damping": 0.005, "topology_enabled": True,
                     "gauge_enabled": True, "gauge_coupling": 0.05,
                     "gauge_damping": 0.10, "gauge_wave_speed": 1.0,
                     "gauge_backreaction": 0.02, "gravity_enabled": True,
                     "gravity_strength": 0.0001, "gravity_backreaction": 1.0,
                     "threshold_fraction": 0.10, "point_radius": 0.050},
    },
    "PLASMA_BOUNDARY": {
        "camera": (12.0, -15.0, 8.5), "lens": 52.0, "still": 76,
        "settings": {"field_mode": "SCALAR", "dt": 0.001, "steps_per_frame": 4,
                     "lambda_cohesion": 1.0, "kappa_stability": 0.1,
                     "damping": 0.025, "thermal_enabled": True,
                     "heat_conduction": 0.05, "collision_heating": 0.02,
                     "hrm_enabled": True, "drive_f1": 5.0, "drive_f2": 6.2,
                     "drive_a1": 0.3, "drive_a2": 0.3, "drive_profile": "RADIAL",
                     "drive_width": 2.0, "threshold_fraction": 0.07,
                     "point_radius": 0.052},
    },
}


def set_input(node, names, value) -> bool:
    if isinstance(names, str):
        names = (names,)
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            try:
                socket.default_value = value
                return True
            except Exception:
                pass
    return False


def clean_material(name: str):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    return material, nodes, material.node_tree.links


def emission_material(name: str, color, strength: float):
    material, nodes, links = clean_material(name)
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def metal_material(name: str, color, roughness: float = 0.24):
    material, nodes, links = clean_material(name)
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    set_input(principled, "Base Color", color)
    set_input(principled, "Metallic", 0.90)
    set_input(principled, "Roughness", roughness)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def assign_material(obj, material) -> None:
    if hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(material)


def clear_showcase_assets() -> None:
    for obj in list(bpy.data.objects):
        if obj.name.startswith(SHOWCASE_PREFIX):
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (bpy.data.materials, bpy.data.meshes, bpy.data.curves, bpy.data.lights, bpy.data.cameras):
        for datablock in list(collection):
            if datablock.name.startswith(SHOWCASE_PREFIX) and datablock.users == 0:
                collection.remove(datablock)


def select_eevee(scene) -> str:
    available = set()
    try:
        available = {
            item.identifier
            for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
        }
    except Exception:
        pass
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if available and candidate not in available:
            continue
        try:
            scene.render.engine = candidate
            if scene.render.engine == candidate:
                return candidate
        except Exception:
            continue
    raise RuntimeError("QFG showcase could not select Eevee")


def disable_compositor(scene) -> None:
    scene.render.use_compositing = False
    scene.render.film_transparent = False
    if hasattr(scene, "compositing_node_group"):
        try:
            scene.compositing_node_group = None
        except Exception:
            pass
    if hasattr(scene, "use_nodes"):
        try:
            scene.use_nodes = False
        except Exception:
            pass


def hide_editor_proxies(scene) -> None:
    for obj in scene.objects:
        if not hasattr(obj, "qfg_actor"):
            continue
        props = obj.qfg_actor
        if props.enabled and props.actor_type != "DYNAMIC_BODY":
            obj.hide_render = True
            obj.display_type = "WIRE"
            obj.show_in_front = True
    field = bpy.data.objects.get("QFG_Field_Points")
    if field is not None:
        field.hide_render = False


def _add_torus(name: str, radius: float, z: float, material, minor: float = 0.035):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius, minor_radius=minor,
        major_segments=96, minor_segments=12, location=(0.0, 0.0, z),
    )
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, material)
    return obj


def build_stage(scene, mode: str, quality: str) -> None:
    if mode not in MODE_CONFIG:
        raise ValueError(f"Unknown showcase mode: {mode}")
    if quality not in QUALITY_CONFIG:
        raise ValueError(f"Unknown showcase quality: {quality}")
    clear_showcase_assets()
    disable_compositor(scene)
    select_eevee(scene)
    hide_editor_proxies(scene)

    q = QUALITY_CONFIG[quality]
    scene.render.resolution_x, scene.render.resolution_y = q["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.frame_start = 1
    scene.frame_end = int(q["frames"])

    world = scene.world or bpy.data.worlds.new("QFG_SHOW_World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background is not None:
        background.inputs["Color"].default_value = (0.002, 0.004, 0.012, 1.0)
        background.inputs["Strength"].default_value = 0.14

    dark = metal_material("QFG_SHOW_Black_Metal", (0.008, 0.014, 0.026, 1.0))
    cyan = emission_material("QFG_SHOW_Cyan", (0.0, 0.75, 1.0, 1.0), 5.0)
    magenta = emission_material("QFG_SHOW_Magenta", (1.0, 0.02, 0.45, 1.0), 4.0)

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=8.8, depth=0.55, location=(0.0, 0.0, -4.10))
    platform = bpy.context.active_object
    platform.name = "QFG_SHOW_Platform"
    assign_material(platform, dark)
    for index, radius in enumerate((3.6, 5.8, 7.9)):
        _add_torus(f"QFG_SHOW_Floor_Ring_{index}", radius, -3.80, cyan if index != 1 else magenta)

    # Safe unparented camera: no enclosing gate/containment geometry.
    focus = bpy.data.objects.new("QFG_SHOW_Camera_Focus", None)
    focus.location = (0.0, 0.0, -0.35)
    scene.collection.objects.link(focus)
    camera_data = bpy.data.cameras.new("QFG_SHOW_Camera_Data")
    camera_data.lens = float(MODE_CONFIG[mode]["lens"])
    camera_data.sensor_width = 36.0
    camera_data.clip_start = 0.10
    camera_data.clip_end = 500.0
    camera_data.dof.use_dof = False
    camera = bpy.data.objects.new("QFG_SHOW_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = tuple(float(v) for v in MODE_CONFIG[mode]["camera"])
    track = camera.constraints.new("TRACK_TO")
    track.target = focus
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = camera

    for name, location, color, energy, size in (
        ("QFG_SHOW_Key", (8.0, -9.0, 12.0), (0.35, 0.70, 1.0), 1500.0, 7.0),
        ("QFG_SHOW_Rim", (-9.0, 8.0, 8.0), (1.0, 0.10, 0.45), 1200.0, 6.0),
    ):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.color = color
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (Vector((0.0, 0.0, 0.0)) - light.location).to_track_quat("-Z", "Y").to_euler()


def apply_mode_settings(settings, mode: str, quality: str) -> None:
    q = QUALITY_CONFIG[quality]
    settings.grid_size = q["grid"]
    settings.max_points = int(q["max_points"])
    settings.bake_start = 1
    settings.bake_end = int(q["frames"])
    for key, value in MODE_CONFIG[mode]["settings"].items():
        if hasattr(settings, key):
            setattr(settings, key, value)


def render_still(scene, mode: str, frame: int, output_directory: str) -> Path:
    frame = max(scene.frame_start, min(scene.frame_end, int(frame)))
    scene.frame_set(frame)
    output_dir = Path(bpy.path.abspath(output_directory))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"qfg_hero_{mode.lower()}_{frame:04d}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def field_material(mode: str):
    """Procedural density-driven emission used by native hero renders."""
    palettes = {
        "THERMAL": ((0.12, 0.0, 0.0, 1.0), (1.0, 0.7, 0.02, 1.0)),
        "HOPF": ((0.08, 0.0, 0.25, 1.0), (0.0, 0.95, 1.0, 1.0)),
        "VORTEX": ((0.0, 0.08, 0.12, 1.0), (0.8, 0.05, 1.0, 1.0)),
        "PLASMA_BOUNDARY": ((0.15, 0.0, 0.25, 1.0), (1.0, 0.25, 0.02, 1.0)),
    }
    low, high = palettes.get(mode, ((0.0, 0.04, 0.22, 1.0), (0.0, 1.0, 1.0, 1.0)))
    material, nodes, links = clean_material("QFG_SHOW_Field_Material")
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    attribute = nodes.new("ShaderNodeAttribute")
    ramp = nodes.new("ShaderNodeValToRGB")
    floor = nodes.new("ShaderNodeMath")
    strength = nodes.new("ShaderNodeMath")
    attribute.attribute_name = "qfg_density"
    ramp.color_ramp.elements[0].color = low
    ramp.color_ramp.elements[1].color = high
    floor.operation = "MAXIMUM"
    floor.inputs[1].default_value = 0.08
    strength.operation = "MULTIPLY"
    strength.inputs[1].default_value = 12.0
    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(attribute.outputs["Fac"], floor.inputs[0])
    links.new(floor.outputs[0], strength.inputs[0])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])
    links.new(strength.outputs[0], emission.inputs["Strength"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def prepare_field_renderer(point_radius: float, mode: str) -> bool:
    """Make QFG_Field_Points renderable while preserving live mesh updates.

    The modifier keeps the canonical ``QFG Mesh to Points`` name so the normal
    visualization updater can continue to change its radius during playback.
    """
    obj = bpy.data.objects.get("QFG_Field_Points")
    if obj is None:
        return False
    modifier = obj.modifiers.get("QFG Mesh to Points")
    if modifier is None:
        modifier = obj.modifiers.new("QFG Mesh to Points", "NODES")

    old_group = modifier.node_group
    group = bpy.data.node_groups.new("QFG_SHOW_Field_Geometry", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    inp = nodes.new("NodeGroupInput")
    out = nodes.new("NodeGroupOutput")
    points = nodes.new("GeometryNodeMeshToPoints")
    points.name = "QFG Mesh to Points"
    ico = nodes.new("GeometryNodeMeshIcoSphere")
    set_mat = nodes.new("GeometryNodeSetMaterial")
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    named = nodes.new("GeometryNodeInputNamedAttribute")
    map_range = nodes.new("ShaderNodeMapRange")
    combine = nodes.new("ShaderNodeCombineXYZ")
    try:
        points.mode = "VERTICES"
    except Exception:
        pass
    points.inputs["Radius"].default_value = max(float(point_radius), 1e-5)
    ico.inputs["Radius"].default_value = max(float(point_radius), 1e-5)
    ico.inputs["Subdivisions"].default_value = 1
    set_mat.inputs["Material"].default_value = field_material(mode)
    named.data_type = "FLOAT"
    named.inputs["Name"].default_value = "qfg_density"
    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 0.45
    map_range.inputs["To Max"].default_value = 1.45
    map_range.clamp = True
    links.new(inp.outputs["Geometry"], points.inputs["Mesh"])
    links.new(points.outputs["Points"], instance.inputs["Points"])
    links.new(ico.outputs["Mesh"], set_mat.inputs["Geometry"])
    links.new(set_mat.outputs["Geometry"], instance.inputs["Instance"])
    links.new(named.outputs["Attribute"], map_range.inputs["Value"])
    links.new(map_range.outputs["Result"], combine.inputs["X"])
    links.new(map_range.outputs["Result"], combine.inputs["Y"])
    links.new(map_range.outputs["Result"], combine.inputs["Z"])
    links.new(combine.outputs["Vector"], instance.inputs["Scale"])
    links.new(instance.outputs["Instances"], out.inputs["Geometry"])
    modifier.node_group = group
    obj.hide_render = False
    obj.display_type = "SOLID"
    if old_group is not None and old_group.users == 0 and old_group.name.startswith("QFG_SHOW_"):
        bpy.data.node_groups.remove(old_group)
    return True
