# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Genesis / Emergent Matter Field v1 - Blender 5.2+
#
# Inspired by the C++ "GENESIS" scene:
#   - phi field = vacuum / background field
#   - psi field = emergent matter field
#   - 3D Gray-Scott style reaction-diffusion update
#   - central "Big Bang" seed
#
# This Blender version turns the simulation into a cinematic scientific demo:
#   VOID -> BIG BANG -> EMERGENT STRUCTURES -> ROTATING FIELD REVEAL
#
# SCIENTIFIC STATUS
# -----------------
# φ/Ψ field evolution = numerical simulation layer
# point-cloud / halo / core rendering = visualization layer
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_GENESIS_DEMO_V1/
# ---------------------------------------------------------------------------

import bpy
import math
import os
import numpy as np
from mathutils import Vector

# ============================================================
# CONFIG
# ============================================================

FPS = 24
FRAME_START = 1
FRAME_END = 240
RES_X = 1920
RES_Y = 1080
RES_PERCENT = 50
AUTO_RENDER = False

OUTPUT_DIR_NAME = "QFG_GENESIS_DEMO_V1"
OUTPUT_FILE = "QFG_Genesis_Emergent_Matter_Field_v1"

# Simulation grid
NX = 28
NY = 28
NZ = 28
DT = 0.08
STEPS_PER_FRAME = 3

# Genesis parameters (adapted from your C++ scene)
DIFF_PHI = 0.80
DIFF_PSI = 0.05
FEED = 0.035
KILL = 0.062

# Visualization thresholds
HALO_THRESHOLD = 0.08
CORE_THRESHOLD = 0.34
MAX_HALO_POINTS = 1700
MAX_CORE_POINTS = 700
WORLD_SCALE = 0.24

# Globals for frame handler
GENESIS_HALO_FRAMES = []
GENESIS_CORE_FRAMES = []
HALO_OBJ = None
CORE_OBJ = None
BLAST_OBJ = None
FRAME_OBJ = None

# ============================================================
# MATERIALS / HELPERS
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def make_material(name, color, emission=0.0, metallic=0.0, roughness=0.35, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (*color[:3], alpha)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*color[:3], alpha)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*color[:3], alpha)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = alpha

    if hasattr(m, "blend_method"):
        try:
            m.blend_method = "BLEND"
        except Exception:
            pass
    if hasattr(m, "shadow_method"):
        try:
            m.shadow_method = "NONE"
        except Exception:
            pass
    return m

MAT_HALO   = make_material("GenesisHalo",   (0.18, 0.55, 1.00), emission=2.3, metallic=0.0, roughness=0.2, alpha=1.0)
MAT_CORE   = make_material("GenesisCore",   (1.00, 0.88, 0.42), emission=4.0, metallic=0.0, roughness=0.15, alpha=1.0)
MAT_FRAME  = make_material("GenesisFrame",  (0.12, 0.18, 0.25), emission=0.0, metallic=0.55, roughness=0.25, alpha=1.0)
MAT_TEXT   = make_material("GenesisText",   (0.92, 0.96, 1.00), emission=1.0, metallic=0.0, roughness=0.3, alpha=1.0)
MAT_ORANGE = make_material("GenesisOrange", (1.00, 0.24, 0.03), emission=3.0, metallic=0.0, roughness=0.2, alpha=1.0)
MAT_BLAST  = make_material("GenesisBlast",  (1.00, 0.55, 0.10), emission=5.0, metallic=0.0, roughness=0.15, alpha=0.35)
MAT_FLOOR  = make_material("GenesisFloor",  (0.01, 0.015, 0.03), emission=0.0, metallic=0.1, roughness=0.75, alpha=1.0)

def add_text(name, body, loc, size=0.28, material=None):
    c = bpy.data.curves.new(name+"_Curve", "FONT")
    c.body = body
    c.align_x = "CENTER"
    c.align_y = "CENTER"
    c.size = size
    c.extrude = 0.004
    o = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi / 2, 0, 0)
    if material:
        o.data.materials.append(material)
    return o

def add_cube(name, loc, scale, material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    return o

def add_sphere(name, loc, radius, material, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    return o

def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()

# ============================================================
# GENESIS NUMERICAL MODEL
# ============================================================

def big_bang_seed(phi, psi):
    cx = NX // 2
    cy = NY // 2
    cz = NZ // 2

    for z in range(cz - 4, cz + 5):
        for y in range(cy - 4, cy + 5):
            for x in range(cx - 4, cx + 5):
                dist = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
                if dist < 4.0:
                    psi[x, y, z] = 1.0
                    phi[x, y, z] = 0.0

def laplacian(arr):
    return (
        np.roll(arr,  1, axis=0) + np.roll(arr, -1, axis=0) +
        np.roll(arr,  1, axis=1) + np.roll(arr, -1, axis=1) +
        np.roll(arr,  1, axis=2) + np.roll(arr, -1, axis=2) -
        6.0 * arr
    )

def run_genesis_simulation():
    print("Running Genesis φ/Ψ simulation...")

    phi = np.ones((NX, NY, NZ), dtype=np.float32)
    psi = np.zeros((NX, NY, NZ), dtype=np.float32)

    big_bang_seed(phi, psi)

    halo_frames = []
    core_frames = []

    grid_center = np.array([NX/2.0, NY/2.0, NZ/2.0], dtype=np.float32)

    for frame in range(FRAME_START, FRAME_END + 1):
        for _ in range(STEPS_PER_FRAME):
            lap_u = laplacian(phi)
            lap_v = laplacian(psi)

            reaction = phi * psi * psi
            du = DIFF_PHI * lap_u - reaction + FEED * (1.0 - phi)
            dv = DIFF_PSI * lap_v + reaction - (FEED + KILL) * psi

            phi = np.clip(phi + du * DT, 0.0, 1.0)
            psi = np.clip(psi + dv * DT, 0.0, 1.0)

        # halo points
        halo_mask = psi > HALO_THRESHOLD
        halo_idx = np.argwhere(halo_mask)
        if len(halo_idx):
            halo_vals = psi[halo_mask]
            if len(halo_idx) > MAX_HALO_POINTS:
                pick = np.argpartition(halo_vals, -MAX_HALO_POINTS)[-MAX_HALO_POINTS:]
                halo_idx = halo_idx[pick]
            halo_pts = (halo_idx.astype(np.float32) - grid_center) * WORLD_SCALE
        else:
            halo_pts = np.zeros((0, 3), dtype=np.float32)

        # core points
        core_mask = psi > CORE_THRESHOLD
        core_idx = np.argwhere(core_mask)
        if len(core_idx):
            core_vals = psi[core_mask]
            if len(core_idx) > MAX_CORE_POINTS:
                pick = np.argpartition(core_vals, -MAX_CORE_POINTS)[-MAX_CORE_POINTS:]
                core_idx = core_idx[pick]
            core_pts = (core_idx.astype(np.float32) - grid_center) * WORLD_SCALE
        else:
            core_pts = np.zeros((0, 3), dtype=np.float32)

        halo_frames.append(halo_pts)
        core_frames.append(core_pts)

        if frame % 40 == 0:
            print(f"  simulated frame {frame}/{FRAME_END}")

    print("Genesis simulation complete.")
    return halo_frames, core_frames

# ============================================================
# POINT CLOUD OBJECTS
# ============================================================

def make_points_mesh(name, points):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata([tuple(p) for p in points], [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def ensure_hidden(obj):
    try:
        obj.hide_viewport = True
        obj.hide_render = True
    except Exception:
        pass

def make_instance_object(name, radius, material):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=(0,0,0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.clear()
    obj.data.materials.append(material)
    ensure_hidden(obj)
    return obj

def add_points_instancer(points_obj, instance_obj):
    # Geometry Nodes: mesh verts -> points -> instance object
    mod = points_obj.modifiers.new("GenesisPointsGN", "NODES")
    ng = bpy.data.node_groups.new(points_obj.name + "_GN", 'GeometryNodeTree')
    mod.node_group = ng

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    group_in = nodes.new("NodeGroupInput")
    group_in.location = (-700, 0)
    group_out = nodes.new("NodeGroupOutput")
    group_out.location = (420, 0)

    ng.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

    mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.location = (-430, 0)
    mesh_to_points.mode = 'VERTICES'
    mesh_to_points.inputs["Radius"].default_value = 0.01

    obj_info = nodes.new("GeometryNodeObjectInfo")
    obj_info.location = (-430, -170)
    obj_info.transform_space = 'RELATIVE'
    obj_info.inputs["Object"].default_value = instance_obj

    instance_on_points = nodes.new("GeometryNodeInstanceOnPoints")
    instance_on_points.location = (-120, 0)

    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (140, 0)

    links.new(group_in.outputs["Geometry"], mesh_to_points.inputs["Mesh"])
    links.new(mesh_to_points.outputs["Points"], instance_on_points.inputs["Points"])
    links.new(obj_info.outputs["Geometry"], instance_on_points.inputs["Instance"])
    links.new(instance_on_points.outputs["Instances"], realize.inputs["Geometry"])
    links.new(realize.outputs["Geometry"], group_out.inputs["Geometry"])

def update_points_object(obj, points):
    mesh = obj.data
    mesh.clear_geometry()
    verts = [tuple(map(float, p)) for p in points]
    mesh.from_pydata(verts, [], [])
    mesh.update()

# ============================================================
# FRAME HANDLER
# ============================================================

def genesis_handler(scene):
    idx = max(0, min(scene.frame_current - FRAME_START, len(GENESIS_HALO_FRAMES) - 1))

    if HALO_OBJ is not None:
        update_points_object(HALO_OBJ, GENESIS_HALO_FRAMES[idx])

    if CORE_OBJ is not None:
        update_points_object(CORE_OBJ, GENESIS_CORE_FRAMES[idx])

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "genesis_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(genesis_handler)

# ============================================================
# SCENE SETUP
# ============================================================

def build_wire_volume():
    # Use a thin cube with wireframe modifier
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.0))
    obj = bpy.context.object
    obj.name = "GenesisVolumeFrame"
    obj.scale = ((NX * WORLD_SCALE) / 2.0, (NY * WORLD_SCALE) / 2.0, (NZ * WORLD_SCALE) / 2.0)

    if MAT_FRAME:
        obj.data.materials.append(MAT_FRAME)

    wire = obj.modifiers.new("Wireframe", "WIREFRAME")
    wire.thickness = 0.015
    wire.use_replace = True
    wire.use_even_offset = True
    return obj

def animate_blast():
    global BLAST_OBJ
    BLAST_OBJ = add_sphere("GenesisBlast", (0, 0, 0), 0.25, MAT_BLAST, 32, 16)
    BLAST_OBJ.display_type = 'SOLID'
    BLAST_OBJ.scale = (0.05, 0.05, 0.05)
    BLAST_OBJ.keyframe_insert("scale", frame=1)

    BLAST_OBJ.scale = (2.2, 2.2, 2.2)
    BLAST_OBJ.keyframe_insert("scale", frame=30)

    BLAST_OBJ.scale = (3.1, 3.1, 3.1)
    BLAST_OBJ.keyframe_insert("scale", frame=70)

    BLAST_OBJ.scale = (3.5, 3.5, 3.5)
    BLAST_OBJ.keyframe_insert("scale", frame=120)

def setup_scene():
    sc = bpy.context.scene
    sc.frame_start = FRAME_START
    sc.frame_end = FRAME_END
    sc.render.fps = FPS
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.resolution_percentage = RES_PERCENT
    sc.world.color = (0.0008, 0.0015, 0.0055)

    try:
        ids = [x.identifier for x in sc.render.bl_rna.properties["engine"].enum_items]
    except Exception:
        ids = []

    if "BLENDER_EEVEE_NEXT" in ids:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in ids:
        sc.render.engine = "BLENDER_EEVEE"

    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    # base
    add_cube("Floor", (0, 0, -4.0), (8.0, 8.0, 0.06), MAT_FLOOR)
    build_wire_volume()

    add_text("Title", "QFG GENESIS / EMERGENT MATTER FIELD", (0, 0, 4.45), 0.44, MAT_TEXT)
    add_text("SubTitle", "Void → Big Bang seed → emergent φ/Ψ structures", (0, 0, 3.95), 0.19, MAT_HALO)
    add_text("Status", "φ/Ψ evolution = numerical simulation   |   point cloud = visualization layer", (0, 0, -4.45), 0.17, MAT_ORANGE)

    # camera
    bpy.ops.object.camera_add(location=(0, -13.2, 5.8))
    cam = bpy.context.object
    cam.name = "GenesisCamera"
    sc.camera = cam
    cam.data.lens = 56
    look_at(cam, (0, 0, 0.0))

    keys = [
        (1,   (0,   -13.2, 5.8), (0, 0, 0.0), 56),
        (60,  (-1.1,-11.5, 4.7), (0, 0, 0.0), 52),
        (120, (1.4, -10.2, 3.7), (0, 0, 0.2), 54),
        (170, (3.1,  -7.8, 2.8), (0, 0, 0.2), 68),
        (215, (0.8, -10.0, 4.1), (0, 0, 0.1), 56),
        (240, (0,   -13.4, 5.9), (0, 0, 0.0), 58),
    ]
    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    # lights
    bpy.ops.object.light_add(type="AREA", location=(-6, -5, 8))
    key = bpy.context.object
    key.data.energy = 1300
    key.data.size = 6.0
    key.data.color = (0.15, 0.38, 1.0)
    look_at(key, (0, 0, 0))

    bpy.ops.object.light_add(type="AREA", location=(5, -1, 7))
    fill = bpy.context.object
    fill.data.energy = 1050
    fill.data.size = 5.2
    fill.data.color = (0.60, 0.15, 1.0)
    look_at(fill, (0, 0, 0))

    bpy.ops.object.light_add(type="POINT", location=(0, 0, 0))
    burst = bpy.context.object
    burst.data.energy = 2200
    burst.data.color = (1.00, 0.55, 0.08)
    burst.data.keyframe_insert("energy", frame=1)
    burst.data.energy = 3800
    burst.data.keyframe_insert("energy", frame=18)
    burst.data.energy = 850
    burst.data.keyframe_insert("energy", frame=60)

    animate_blast()

    return sc

# ============================================================
# OUTPUT
# ============================================================

def resolve_output_dir():
    if bpy.data.filepath:
        base = os.path.dirname(bpy.data.filepath)
    else:
        home = os.path.expanduser("~")
        docs = os.path.join(home, "Documents")
        base = docs if os.path.isdir(docs) else home
    out = os.path.join(base, OUTPUT_DIR_NAME)
    os.makedirs(out, exist_ok=True)
    return out

def configure_output(sc):
    out = resolve_output_dir()
    sc.render.filepath = os.path.join(out, OUTPUT_FILE)
    sc.render.use_file_extension = True

    img = sc.render.image_settings
    if hasattr(img, "media_type"):
        try:
            img.media_type = "VIDEO"
        except Exception:
            pass

    ff = sc.render.ffmpeg
    for attr, val in (
        ("format", "MPEG4"),
        ("codec", "H264"),
        ("constant_rate_factor", "HIGH"),
        ("ffmpeg_preset", "GOOD"),
    ):
        try:
            setattr(ff, attr, val)
        except Exception:
            pass

# ============================================================
# MAIN
# ============================================================

print("\n==============================================")
print(" QFG GENESIS / EMERGENT MATTER FIELD v1")
print("==============================================\n")

clear_scene()
scene = setup_scene()

GENESIS_HALO_FRAMES, GENESIS_CORE_FRAMES = run_genesis_simulation()

# Create point cloud drivers
halo_seed = GENESIS_HALO_FRAMES[0] if GENESIS_HALO_FRAMES else np.zeros((0,3), dtype=np.float32)
core_seed = GENESIS_CORE_FRAMES[0] if GENESIS_CORE_FRAMES else np.zeros((0,3), dtype=np.float32)

HALO_OBJ = make_points_mesh("GenesisHaloPoints", halo_seed)
CORE_OBJ = make_points_mesh("GenesisCorePoints", core_seed)

halo_instance = make_instance_object("GenesisHaloInstance", 0.040, MAT_HALO)
core_instance = make_instance_object("GenesisCoreInstance", 0.060, MAT_CORE)

add_points_instancer(HALO_OBJ, halo_instance)
add_points_instancer(CORE_OBJ, core_instance)

scene["demo"] = "QFG Genesis / Emergent Matter Field v1"
scene["sim_grid"] = f"{NX}x{NY}x{NZ}"
scene["steps_per_frame"] = STEPS_PER_FRAME
scene["scientific_status"] = "φ/Ψ numerical evolution; cloud visualization layer"

install_handler()
configure_output(scene)

out = resolve_output_dir()
blend_path = os.path.join(out, "QFG_Genesis_Emergent_Matter_Field_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
genesis_handler(scene)

print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Grid:", scene["sim_grid"])
print("Preview: SPACE")
print("Render: Ctrl+F12")
print("Set RES_PERCENT=100 for final render.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
