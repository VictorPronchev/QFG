"""QFG Dynamics Reactor Showcase v3 for Blender 5.2.

This content script targets QFG Dynamics 0.3 Alpha.  It creates the add-on's
field-coupled body showcase, bakes the runtime, applies cinematic procedural
materials, builds a reactor chamber, camera and lighting, and optionally renders
an image sequence.

No external image textures and no compositor are used.  This avoids Blender's
flat-magenta missing-image/compositor failure mode.
"""
from __future__ import annotations

import bpy
import math
import traceback
from pathlib import Path
from mathutils import Vector

# ---------------------------------------------------------------------------
# USER OPTIONS
# ---------------------------------------------------------------------------

QUALITY = "PREVIEW"  # PREVIEW or FINAL
RUN_MODE = "BUILD_BAKE"  # BUILD_ONLY, BUILD_BAKE, RENDER_STILL, RENDER_ANIMATION
BODY_COUNT = 48
OUTPUT_ROOT = Path.home() / "QFG_Dynamics_Showcase"
STILL_FRAME = 64
SAVE_BLEND = True

QUALITY_CONFIG = {
    "PREVIEW": {
        "grid": "32",
        "frames": 120,
        "resolution": (1280, 720),
        "max_points": 18000,
        "point_radius": 0.055,
        "body_count": min(BODY_COUNT, 48),
    },
    "FINAL": {
        "grid": "64",
        "frames": 180,
        "resolution": (1920, 1080),
        "max_points": 42000,
        "point_radius": 0.045,
        "body_count": BODY_COUNT,
    },
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def require_qfg():
    if not hasattr(bpy.context.scene, "qfg_settings"):
        raise RuntimeError("Install and enable QFG Dynamics first.")
    if not hasattr(bpy.ops.qfg, "create_dynamics_showcase"):
        raise RuntimeError(
            "The installed add-on is older than QFG Dynamics Alpha."
        )


def run_operator(operator, **kwargs):
    result = operator(**kwargs)
    if "CANCELLED" in result:
        raise RuntimeError(f"Operator cancelled: {operator.idname()}")
    return result


def remove_showcase_assets():
    for obj in list(bpy.data.objects):
        if obj.name.startswith("QFG_CINE_"):
            bpy.data.objects.remove(obj, do_unlink=True)
    for collection in (
        bpy.data.materials,
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.lights,
        bpy.data.cameras,
    ):
        for datablock in list(collection):
            if datablock.name.startswith("QFG_CINE_") and datablock.users == 0:
                collection.remove(datablock)


def clean_material(name):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    material.node_tree.nodes.clear()
    return material, material.node_tree.nodes, material.node_tree.links


def set_input(node, names, value):
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


def assign_material(obj, material):
    if hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(material)


def emission_material(name, color, strength):
    material, nodes, links = clean_material(name)
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def metal_material(name, color, roughness=0.22):
    material, nodes, links = clean_material(name)
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    set_input(principled, "Base Color", color)
    set_input(principled, "Metallic", 0.92)
    set_input(principled, "Roughness", roughness)
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return material


def shard_material():
    material, nodes, links = clean_material("QFG_CINE_Shard_Material")
    output = nodes.new("ShaderNodeOutputMaterial")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    attribute = nodes.new("ShaderNodeAttribute")
    ramp = nodes.new("ShaderNodeValToRGB")
    emission = nodes.new("ShaderNodeEmission")
    add = nodes.new("ShaderNodeAddShader")

    attribute.attribute_name = "qfg_temperature"
    set_input(principled, "Base Color", (0.025, 0.045, 0.080, 1.0))
    set_input(principled, "Metallic", 0.90)
    set_input(principled, "Roughness", 0.18)

    ramp.color_ramp.elements[0].color = (0.0, 0.05, 0.30, 1.0)
    ramp.color_ramp.elements[1].color = (1.0, 0.08, 0.01, 1.0)
    emission.inputs["Strength"].default_value = 2.2

    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])
    links.new(principled.outputs["BSDF"], add.inputs[0])
    links.new(emission.outputs["Emission"], add.inputs[1])
    links.new(add.outputs["Shader"], output.inputs["Surface"])
    return material


def field_material():
    """Density-coloured field material with a non-zero emission fallback.

    Blender may not always propagate a point-domain named attribute through
    instancing exactly as expected.  The previous shader multiplied emission
    directly by ``qfg_density``, making the entire field black when the
    attribute evaluated to zero.  This version always emits a visible base
    signal and adds density-dependent intensity on top.
    """
    material, nodes, links = clean_material("QFG_CINE_Field_Material")
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    attribute = nodes.new("ShaderNodeAttribute")
    ramp = nodes.new("ShaderNodeValToRGB")
    multiply = nodes.new("ShaderNodeMath")
    add = nodes.new("ShaderNodeMath")

    attribute.attribute_name = "qfg_density"
    multiply.operation = "MULTIPLY"
    multiply.inputs[1].default_value = 18.0 if QUALITY == "FINAL" else 12.0
    add.operation = "ADD"
    add.inputs[1].default_value = 3.5

    colors = [
        (0.00, (0.005, 0.030, 0.120, 1.0)),
        (0.18, (0.000, 0.180, 0.700, 1.0)),
        (0.45, (0.000, 0.950, 1.000, 1.0)),
        (0.72, (0.850, 0.030, 1.000, 1.0)),
        (1.00, (1.000, 0.900, 1.000, 1.0)),
    ]

    color_ramp = ramp.color_ramp
    while len(color_ramp.elements) > 1:
        color_ramp.elements.remove(color_ramp.elements[-1])
    color_ramp.elements[0].position = colors[0][0]
    color_ramp.elements[0].color = colors[0][1]
    for position, color in colors[1:]:
        element = color_ramp.elements.new(position)
        element.color = color

    links.new(attribute.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], emission.inputs["Color"])
    links.new(attribute.outputs["Fac"], multiply.inputs[0])
    links.new(multiply.outputs[0], add.inputs[0])
    links.new(add.outputs[0], emission.inputs["Strength"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def rebuild_field_renderer(point_radius):
    obj = bpy.data.objects.get("QFG_Field_Points")
    if obj is None:
        raise RuntimeError("QFG field display object was not created.")
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)

    modifier = obj.modifiers.new("QFG_CINE_Field_Renderer", "NODES")
    group = bpy.data.node_groups.new("QFG_CINE_Field_Geometry", "GeometryNodeTree")
    modifier.node_group = group
    group.interface.new_socket(
        name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry"
    )
    group.interface.new_socket(
        name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry"
    )

    nodes, links = group.nodes, group.links
    inp = nodes.new("NodeGroupInput")
    out = nodes.new("NodeGroupOutput")
    points = nodes.new("GeometryNodeMeshToPoints")
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
    points.inputs["Radius"].default_value = point_radius
    ico.inputs["Radius"].default_value = point_radius
    ico.inputs["Subdivisions"].default_value = 1
    set_mat.inputs["Material"].default_value = field_material()
    named.data_type = "FLOAT"
    named.inputs["Name"].default_value = "qfg_density"
    map_range.inputs["From Min"].default_value = 0.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 0.40
    map_range.inputs["To Max"].default_value = 1.55
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
    obj.hide_render = False
    obj.show_in_front = False
    obj.display_type = "SOLID"


def hide_qfg_editor_proxies():
    """Hide non-body QFG authoring meshes from camera renders.

    ``QFG_Dynamics_Core`` is a numerical Gaussian emitter represented by a
    normal Blender sphere. In 0.3.0 that sphere could enclose the camera and
    cover the complete render. The computed field remains visible through
    ``QFG_Field_Points``.
    """
    hidden = []
    for obj in bpy.context.scene.objects:
        if not hasattr(obj, "qfg_actor"):
            continue
        props = obj.qfg_actor
        if not props.enabled or props.actor_type == "DYNAMIC_BODY":
            continue
        obj.hide_render = True
        obj.display_type = "WIRE"
        obj.show_in_front = True
        hidden.append(obj.name)

    field = bpy.data.objects.get("QFG_Field_Points")
    if field is not None:
        field.hide_render = False

    print(f"[QFG Dynamics Showcase] Hidden editor proxies: {hidden}")


def select_eevee_engine(scene):
    """Select Eevee explicitly instead of silently retaining Cycles."""
    available = set()
    try:
        enum_items = bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
        available = {item.identifier for item in enum_items}
    except Exception:
        pass

    for engine_id in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if available and engine_id not in available:
            continue
        try:
            scene.render.engine = engine_id
            if scene.render.engine == engine_id:
                print(f"[QFG Dynamics Showcase] Render engine: {engine_id}")
                return engine_id
        except Exception:
            continue

    raise RuntimeError(
        "Could not select Eevee. Available engines: "
        + ", ".join(sorted(available))
    )


def render_preflight():
    scene = bpy.context.scene
    camera = scene.camera
    if camera is None:
        raise RuntimeError("No active render camera.")

    visible = [
        obj.name
        for obj in scene.objects
        if obj.type in {"MESH", "CURVE", "FONT", "VOLUME"}
        and not obj.hide_render
        and not obj.hide_get()
    ]
    if not visible:
        raise RuntimeError("No renderable objects are visible.")

    print("[QFG Dynamics Showcase] Render preflight")
    print(f"  Engine: {scene.render.engine}")
    camera_distance = camera.matrix_world.translation.length
    print(f"  Camera: {camera.name}")
    print(f"  Camera distance from origin: {camera_distance:.3f}")
    if camera_distance < 12.0:
        raise RuntimeError(
            "The active camera is inside or too close to the reactor chamber."
        )
    print(f"  Visible render objects: {len(visible)}")
    print(f"  Sample: {visible[:12]}")


def look_at(obj, target=(0.0, 0.0, 0.0)):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_torus(name, radius, z, material, rotation=(0, 0, 0), minor=0.035):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius,
        minor_radius=minor,
        major_segments=96,
        minor_segments=16,
        location=(0, 0, z),
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    assign_material(obj, material)
    return obj


def build_reactor_stage(frame_end):
    dark = metal_material(
        "QFG_CINE_Black_Metal",
        (0.008, 0.014, 0.026, 1.0),
    )
    cyan = emission_material(
        "QFG_CINE_Cyan",
        (0.0, 0.62, 1.0, 1.0),
        3.0,
    )
    magenta = emission_material(
        "QFG_CINE_Magenta",
        (0.90, 0.015, 0.35, 1.0),
        2.4,
    )

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=128,
        radius=8.6,
        depth=0.65,
        location=(0, 0, -4.15),
    )
    platform = bpy.context.active_object
    platform.name = "QFG_CINE_Reactor_Platform"
    assign_material(platform, dark)

    for radius in (3.6, 5.6, 7.7):
        add_torus(
            f"QFG_CINE_Floor_Ring_{radius}",
            radius,
            -3.80,
            cyan,
            minor=0.022,
        )

    # Two side gates only.  The previous central magenta gate crossed the
    # optical axis and became a solid pink column when the camera moved near it.
    for index, x in enumerate((-4.6, 4.6)):
        ring = add_torus(
            f"QFG_CINE_Field_Gate_{index}",
            3.15,
            0.0,
            cyan if index == 0 else magenta,
            rotation=(0, math.radians(90), 0),
            minor=0.032,
        )
        ring.location.x = x

    # Thin outer containment rings. They frame the field without intersecting
    # the safe camera path.
    containment = (
        ((0, 0, 0), 5.25, cyan),
        ((math.radians(48), 0, math.radians(18)), 5.55, magenta),
        ((0, math.radians(48), math.radians(-18)), 5.85, cyan),
    )
    for index, (rotation, radius, material) in enumerate(containment):
        ring = add_torus(
            f"QFG_CINE_Containment_{index}",
            radius,
            0.0,
            material,
            rotation,
            0.014,
        )
        ring.keyframe_insert("rotation_euler", frame=1)
        ring.rotation_euler.z += math.radians(
            90 if index % 2 == 0 else -90
        )
        ring.keyframe_insert("rotation_euler", frame=frame_end)


def style_dynamic_bodies():
    material = shard_material()
    for obj in bpy.context.scene.objects:
        if not hasattr(obj, "qfg_actor"):
            continue
        if obj.qfg_actor.enabled and obj.qfg_actor.actor_type == "DYNAMIC_BODY":
            assign_material(obj, material)
            bevel = obj.modifiers.get("QFG_CINE_Bevel") or obj.modifiers.new("QFG_CINE_Bevel", "BEVEL")
            bevel.width = 0.045
            bevel.segments = 2


def add_lights():
    for name, location, color, energy, size in (
        ("QFG_CINE_Key", (8, -9, 12), (0.35, 0.70, 1.0), 1500, 7.0),
        ("QFG_CINE_Rim", (-9, 8, 8), (1.0, 0.10, 0.45), 1200, 6.0),
        ("QFG_CINE_Top", (0, 0, 14), (0.55, 0.75, 1.0), 900, 9.0),
    ):
        data = bpy.data.lights.new(name + "_Data", "AREA")
        data.energy = energy
        data.color = color
        data.shape = "DISK"
        data.size = size
        light = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(light)
        light.location = location
        look_at(light)

    data = bpy.data.lights.new("QFG_CINE_Core_Data", "POINT")
    data.energy = 900
    data.color = (0.15, 0.45, 1.0)
    data.shadow_soft_size = 2.5
    core = bpy.data.objects.new("QFG_CINE_Core_Light", data)
    bpy.context.scene.collection.objects.link(core)
    core.location = (0, 0, 1.0)


def _set_linear_camera_interpolation(camera):
    action = getattr(camera.animation_data, "action", None)
    if action is None:
        return
    for fcurve in action.fcurves:
        for key in fcurve.keyframe_points:
            key.interpolation = "BEZIER"


def add_camera(frame_end):
    """Create a camera that always remains outside the reactor chamber.

    The v2 camera was parented to an animated rig and then its local location
    was animated. In the saved scene that combination could collapse the camera
    toward the origin, placing it inside the containment rings.  This version
    keyframes world-space camera locations directly and uses Track To only for
    orientation.
    """
    focus = bpy.data.objects.new("QFG_CINE_Camera_Focus", None)
    bpy.context.scene.collection.objects.link(focus)
    focus.location = (0.0, 0.0, -0.35)

    data = bpy.data.cameras.new("QFG_CINE_Camera_Data")
    data.lens = 58.0
    data.sensor_width = 36.0
    data.clip_start = 0.10
    data.clip_end = 500.0

    # Keep the complete field and fragments readable in the technical hero
    # render. A controlled DOF pass can be added later as a separate shot.
    data.dof.use_dof = False

    camera = bpy.data.objects.new("QFG_CINE_Camera", data)
    bpy.context.scene.collection.objects.link(camera)

    constraint = camera.constraints.new("TRACK_TO")
    constraint.target = focus
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"

    distance = 22.5
    keyframes = (
        (1, math.radians(-24.0), 7.4),
        (max(2, frame_end // 2), math.radians(0.0), 6.8),
        (frame_end, math.radians(24.0), 7.8),
    )

    for frame, angle, height in keyframes:
        camera.location = (
            distance * math.sin(angle),
            -distance * math.cos(angle),
            height,
        )
        camera.keyframe_insert("location", frame=frame)

    _set_linear_camera_interpolation(camera)
    bpy.context.scene.camera = camera

    # Safety check: the outer containment ring is below radius 6.
    minimum_distance = min(
        (Vector(camera.location) - focus.location).length
        for _frame, _angle, _height in keyframes
    )
    if minimum_distance < 12.0:
        raise RuntimeError(
            f"Unsafe cinematic camera distance: {minimum_distance:.2f}"
        )
    return camera


def setup_render(output_dir, frame_end):
    scene = bpy.context.scene
    config = QUALITY_CONFIG[QUALITY]
    width, height = config["resolution"]
    select_eevee_engine(scene)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(output_dir / "frames" / "qfg_dynamics_")
    scene.frame_start = 1
    scene.frame_end = frame_end
    scene.render.film_transparent = False
    scene.render.use_compositing = False
    if hasattr(scene, "compositing_node_group"):
        try:
            scene.compositing_node_group = None
        except Exception:
            pass
    try:
        scene.view_settings.view_transform = "AgX"
    except Exception:
        pass
    for look in ("Medium High Contrast", "AgX - Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except Exception:
            pass
    scene.view_settings.exposure = -0.35

    world = scene.world or bpy.data.worlds.new("QFG_CINE_World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if background:
        background.inputs["Color"].default_value = (0.001, 0.002, 0.008, 1.0)
        background.inputs["Strength"].default_value = 0.035

    (output_dir / "frames").mkdir(parents=True, exist_ok=True)


def main():
    require_qfg()
    if QUALITY not in QUALITY_CONFIG:
        raise ValueError(f"Unknown QUALITY: {QUALITY}")

    config = QUALITY_CONFIG[QUALITY]
    output_dir = OUTPUT_ROOT / QUALITY.lower()
    output_dir.mkdir(parents=True, exist_ok=True)

    remove_showcase_assets()
    run_operator(bpy.ops.qfg.clear_results)
    run_operator(
        bpy.ops.qfg.create_dynamics_showcase,
        body_count=config["body_count"],
    )
    hide_qfg_editor_proxies()

    settings = bpy.context.scene.qfg_settings
    settings.backend = "AUTO"
    settings.grid_size = config["grid"]
    settings.max_points = config["max_points"]
    settings.point_radius = config["point_radius"]
    settings.threshold_fraction = 0.09
    settings.dt = 0.002
    settings.steps_per_frame = 5
    settings.bake_start = 1
    settings.bake_end = config["frames"]
    settings.output_directory = str(output_dir / "qfg_results")
    settings.dynamics_substeps = 1
    settings.dynamics_gravity = (0.0, 0.0, 0.0)
    settings.dynamics_field_force_scale = 1.0
    settings.dynamics_max_speed = 18.0

    setup_render(output_dir, config["frames"])
    run_operator(bpy.ops.qfg.initialize)
    rebuild_field_renderer(settings.point_radius)
    style_dynamic_bodies()
    build_reactor_stage(config["frames"])
    add_lights()
    add_camera(config["frames"])
    hide_qfg_editor_proxies()
    render_preflight()

    if RUN_MODE != "BUILD_ONLY":
        run_operator(bpy.ops.qfg.bake_timeline)
        bpy.context.scene.frame_set(1)

    if SAVE_BLEND:
        bpy.ops.wm.save_as_mainfile(
            filepath=str(output_dir / "qfg_dynamics_reactor_showcase.blend")
        )

    if RUN_MODE == "RENDER_STILL":
        frame = min(config["frames"], max(1, STILL_FRAME))
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = str(
            output_dir / f"qfg_dynamics_reactor_frame_{frame:04d}.png"
        )
        hide_qfg_editor_proxies()
        render_preflight()
        bpy.ops.render.render(write_still=True)
    elif RUN_MODE == "RENDER_ANIMATION":
        bpy.context.scene.frame_set(1)
        hide_qfg_editor_proxies()
        render_preflight()
        bpy.ops.render.render(animation=True)

    print("[QFG Dynamics Showcase] Complete")
    print(f"[QFG Dynamics Showcase] Output: {output_dir}")
    print("[QFG Dynamics Showcase] Compositor disabled; procedural materials only")


try:
    main()
except Exception as exc:
    print("[QFG Dynamics Showcase] ERROR:", exc)
    traceback.print_exc()
    raise
