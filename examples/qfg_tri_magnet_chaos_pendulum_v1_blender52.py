# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Tri-Magnet Chaos Pendulum v1 - Blender 5.2+
#
# Cinematic scientific demo:
#   - three QFG magnetic attractors
#   - chaotic pendulum-like bob
#   - precomputed trajectory
#   - dynamic string and glowing trail
#   - dark lab presentation
#
# SCIENTIFIC STATUS
# -----------------
# bob motion = numerical trajectory demo
# magnets / trail / lab = presentation layer
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_TRI_MAGNET_CHAOS_V1/
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
FRAME_END = 320
RES_X = 1920
RES_Y = 1080
RES_PERCENT = 60
AUTO_RENDER = False

OUTPUT_DIR_NAME = "QFG_TRI_MAGNET_CHAOS_V1"
OUTPUT_FILE = "QFG_Tri_Magnet_Chaos_Pendulum_v1"

DT = 0.030
SUBSTEPS = 5
LENGTH = 3.25
GRAVITY = 9.0
DAMPING = 0.055
MAGNET_RADIUS = 2.15
MAGNET_STRENGTH = 8.5
MAGNET_SOFTEN = 0.42
TRAIL_LENGTH = 120

MAGNETS = [
    Vector(( 0.0,  2.10, 0.00)),
    Vector((-1.82, -1.05, 0.00)),
    Vector(( 1.82, -1.05, 0.00)),
]
ANCHOR = Vector((0.0, 0.0, 3.35))

POSITIONS = []
BOB_OBJ = None
STRING_OBJ = None
TRAIL_OBJ = None
FIELD_RINGS = []
MAGNET_EMITTERS = []

# ============================================================
# HELPERS
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def safe_set_attr(obj, attr, value):
    try:
        setattr(obj, attr, value)
    except Exception:
        pass

def make_material(name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    return mat, nodes, links

def mat_emissive(name, color=(1,1,1), strength=1.0, alpha=1.0):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (320,0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (0,0)
    emission.inputs["Color"].default_value = (*color,1.0)
    emission.inputs["Strength"].default_value = strength

    if alpha < 0.999:
        transp = nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (0,-170)
        mix = nodes.new("ShaderNodeMixShader")
        mix.location = (160,0)
        mix.inputs[0].default_value = 1.0 - alpha
        links.new(transp.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs[0])
        safe_set_attr(mat, "blend_method", "BLEND")
        safe_set_attr(mat, "shadow_method", "NONE")
    else:
        links.new(emission.outputs[0], out.inputs[0])

    return mat

def mat_dark(name, color=(0.02,0.024,0.035), roughness=0.28, metallic=0.12):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (320,0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0,0)
    bsdf.inputs["Base Color"].default_value = (*color,1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs[0], out.inputs[0])
    return mat

def mat_metal(name, color=(0.15,0.17,0.23), roughness=0.20, metallic=0.78):
    return mat_dark(name, color=color, roughness=roughness, metallic=metallic)

def mat_bob(name):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (460,0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (120,0)
    principled.inputs["Base Color"].default_value = (0.78,0.90,1.00,1)
    principled.inputs["Roughness"].default_value = 0.08
    principled.inputs["Metallic"].default_value = 0.10
    if "Emission Color" in principled.inputs:
        principled.inputs["Emission Color"].default_value = (0.25,0.70,1.0,1)
    elif "Emission" in principled.inputs:
        principled.inputs["Emission"].default_value = (0.25,0.70,1.0,1)
    if "Emission Strength" in principled.inputs:
        principled.inputs["Emission Strength"].default_value = 0.6
    principled.inputs["IOR"].default_value = 1.25

    volume = nodes.new("ShaderNodeVolumeAbsorption")
    volume.location = (120,-180)
    volume.inputs["Color"].default_value = (0.55,0.82,1.0,1)
    volume.inputs["Density"].default_value = 0.05

    links.new(principled.outputs[0], out.inputs["Surface"])
    links.new(volume.outputs[0], out.inputs["Volume"])
    return mat

def mat_trail(name):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (450,0)

    emission = nodes.new("ShaderNodeEmission")
    emission.location = (150,0)
    emission.inputs["Color"].default_value = (0.20,0.85,1.0,1)
    emission.inputs["Strength"].default_value = 4.5

    links.new(emission.outputs[0], out.inputs[0])
    safe_set_attr(mat, "blend_method", "BLEND")
    safe_set_attr(mat, "shadow_method", "NONE")
    return mat

def add_text(name, body, loc, size=0.28, material=None):
    c = bpy.data.curves.new(name+"_Curve", "FONT")
    c.body = body
    c.align_x = "CENTER"
    c.align_y = "CENTER"
    c.size = size
    c.extrude = 0.005
    o = bpy.data.objects.new(name, c)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (math.pi/2, 0, 0)
    if material:
        o.data.materials.append(material)
    return o

def add_cube(name, loc, scale, material=None):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        o.data.materials.append(material)
    return o

def add_uv_sphere(name, loc, radius, material=None, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o

def add_cylinder_between(name, start, end, radius, material=None, verts=24):
    start = Vector(start)
    end = Vector(end)
    vec = end - start
    length = vec.length
    mid = (start + end) * 0.5

    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=length, location=mid)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = vec.to_track_quat("Z", "Y").to_euler()
    if material:
        o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o

def add_torus(name, loc, major, minor, material=None):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc)
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o

def look_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

# ============================================================
# MATERIALS
# ============================================================

MAT_FLOOR   = mat_dark("QFG_Floor", color=(0.016,0.020,0.030), roughness=0.18, metallic=0.20)
MAT_WALL    = mat_dark("QFG_Wall",  color=(0.010,0.013,0.022), roughness=0.75, metallic=0.0)
MAT_FRAME   = mat_metal("QFG_Frame", color=(0.12,0.16,0.22), roughness=0.18, metallic=0.82)
MAT_TEXT    = mat_emissive("QFG_Text", (0.93,0.97,1.0), 1.2)
MAT_SUB     = mat_emissive("QFG_Sub", (1.0,0.33,0.10), 2.4)
MAT_BOB     = mat_bob("QFG_Bob")
MAT_TRAIL   = mat_trail("QFG_Trail")
MAT_STRING  = mat_metal("QFG_String", color=(0.44,0.52,0.62), roughness=0.12, metallic=0.95)
MAT_ANCHOR  = mat_metal("QFG_Anchor", color=(0.70,0.74,0.78), roughness=0.10, metallic=1.0)
MAT_RING    = mat_emissive("QFG_Ring", (0.42,0.70,1.0), 1.8, alpha=0.28)
MAT_MAG_1   = mat_emissive("QFG_Mag1", (1.0,0.28,0.18), 4.6)
MAT_MAG_2   = mat_emissive("QFG_Mag2", (0.18,1.0,0.66), 4.6)
MAT_MAG_3   = mat_emissive("QFG_Mag3", (0.45,0.50,1.0), 4.6)

MAG_MATS = [MAT_MAG_1, MAT_MAG_2, MAT_MAG_3]

# ============================================================
# CHAOTIC NUMERICAL TRAJECTORY
# ============================================================

def tangent_project(pos, vec):
    n = pos.normalized()
    return vec - n * vec.dot(n)

def compute_trajectory():
    positions = []

    rel = Vector((0.92, -0.18, -0.34))
    rel.normalize()
    pos = ANCHOR + rel * LENGTH
    vel = Vector((0.0, 0.35, 0.0))

    for frame in range(FRAME_START, FRAME_END + 1):
        for _ in range(SUBSTEPS):
            rel = pos - ANCHOR
            n = rel.normalized()

            a = Vector((0.0, 0.0, -GRAVITY))

            # QFG / tri-magnet conceptual attractors
            for mp in MAGNETS:
                d = mp - pos
                r = d.length
                if r > 1e-6:
                    a += d.normalized() * (MAGNET_STRENGTH / ((r * r) + MAGNET_SOFTEN))

            # keep only tangent-plane acceleration
            a = tangent_project(rel, a)

            vel += a * DT
            vel *= (1.0 - DAMPING * DT)

            # keep velocity tangent
            vel = tangent_project(rel, vel)

            pos += vel * DT

            # sphere constraint
            rel = pos - ANCHOR
            if rel.length == 0.0:
                rel = Vector((0.0, 0.0, -1.0))
            rel = rel.normalized() * LENGTH
            pos = ANCHOR + rel

            # project velocity back to tangent after constraint
            vel = tangent_project(rel, vel)

        positions.append(pos.copy())

    return positions

# ============================================================
# DYNAMIC GEOMETRY
# ============================================================

def make_polyline_curve(name, points, bevel_depth=0.015, material=None):
    curve = bpy.data.curves.new(name+"_Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 4

    spline = curve.splines.new("POLY")
    spline.points.add(len(points)-1)
    for i, p in enumerate(points):
        spline.points[i].co = (p[0], p[1], p[2], 1.0)

    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    return obj

def update_polyline_curve(obj, points):
    curve = obj.data
    while len(curve.splines):
        curve.splines.remove(curve.splines[0])

    spline = curve.splines.new("POLY")
    spline.points.add(len(points)-1)
    for i, p in enumerate(points):
        spline.points[i].co = (float(p[0]), float(p[1]), float(p[2]), 1.0)

def chaos_handler(scene):
    idx = max(0, min(scene.frame_current - FRAME_START, len(POSITIONS)-1))
    p = POSITIONS[idx]

    if BOB_OBJ is not None:
        BOB_OBJ.location = p

    if STRING_OBJ is not None:
        update_polyline_curve(STRING_OBJ, [ANCHOR, p])

    if TRAIL_OBJ is not None:
        start = max(0, idx - TRAIL_LENGTH)
        pts = POSITIONS[start:idx+1]
        if len(pts) < 2:
            pts = [p, p + Vector((0.001,0,0))]
        update_polyline_curve(TRAIL_OBJ, pts)

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "chaos_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(chaos_handler)

# ============================================================
# SCENE SETUP
# ============================================================

def build_lab():
    add_cube("LabTable", (0,0,-0.18), (4.8,4.8,0.18), MAT_FLOOR)
    add_cube("BackWall", (0,4.15,1.30), (4.8,0.10,2.85), MAT_WALL)
    add_cube("LeftWall", (-4.65,0,1.30), (0.10,4.2,2.85), MAT_WALL)
    add_cube("RightWall", (4.65,0,1.30), (0.10,4.2,2.85), MAT_WALL)

    # base platform
    add_cube("QFGBase", (0,0,0.02), (2.95,2.95,0.05), MAT_FRAME)

def build_anchor_frame():
    # central support
    add_cylinder_between("SupportPole", (0,0,0.05), ANCHOR, 0.055, MAT_FRAME, verts=28)
    add_uv_sphere("AnchorCap", ANCHOR, 0.13, MAT_ANCHOR)
    add_cube("TopCrossbar", (0,0,ANCHOR.z + 0.18), (1.55,0.05,0.05), MAT_FRAME)

def build_magnets():
    for i, mp in enumerate(MAGNETS):
        add_uv_sphere(f"Magnet_{i+1}", mp, 0.28, MAG_MATS[i], 24, 14)
        ring1 = add_torus(f"MagRing_{i+1}_A", mp, 0.46, 0.012, MAT_RING)
        ring2 = add_torus(f"MagRing_{i+1}_B", mp, 0.70, 0.010, MAT_RING)
        ring1.rotation_euler = (math.pi/2, 0, 0)
        ring2.rotation_euler = (0, math.pi/2, 0)
        FIELD_RINGS.extend([ring1, ring2])

def build_camera_and_lights():
    sc = bpy.context.scene

    bpy.ops.object.camera_add(location=(0, -10.8, 5.2))
    cam = bpy.context.object
    cam.name = "QFGCamera"
    sc.camera = cam
    cam.data.lens = 78

    try:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = 9.8
        cam.data.dof.aperture_fstop = 2.0
    except Exception:
        pass

    keys = [
        (1,   (0.0,-10.8,5.2), (0,0,1.0), 78),
        (70,  (-0.8,-9.6,4.7), (0,0,0.9), 72),
        (135, (1.6,-8.2,3.5), (0,0,0.7), 86),
        (200, (2.8,-6.6,2.4), (0,0,0.55), 95),
        (260, (0.8,-8.8,3.9), (0,0,0.8), 78),
        (320, (0.0,-11.0,5.3), (0,0,0.9), 80),
    ]

    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    # lights
    bpy.ops.object.light_add(type="AREA", location=(-5.8,-4.8,7.8))
    key = bpy.context.object
    key.data.energy = 1900
    key.data.size = 6.0
    key.data.color = (0.42,0.70,1.0)
    look_at(key, (0,0,0.9))

    bpy.ops.object.light_add(type="AREA", location=(4.5,-0.5,7.0))
    fill = bpy.context.object
    fill.data.energy = 1150
    fill.data.size = 5.0
    fill.data.color = (1.0,0.24,0.82)
    look_at(fill, (0,0,0.9))

    bpy.ops.object.light_add(type="AREA", location=(0.0,-7.0,4.2))
    rim = bpy.context.object
    rim.data.energy = 850
    rim.data.size = 3.0
    rim.data.color = (1.0,0.42,0.12)
    look_at(rim, (0,0,0.4))

def setup_scene():
    sc = bpy.context.scene
    sc.frame_start = FRAME_START
    sc.frame_end = FRAME_END
    sc.render.fps = FPS
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.resolution_percentage = RES_PERCENT

    try:
        ids = [x.identifier for x in sc.render.bl_rna.properties["engine"].enum_items]
    except Exception:
        ids = []

    if "CYCLES" in ids:
        sc.render.engine = "CYCLES"
        safe_set_attr(sc.cycles, "samples", 128)
        safe_set_attr(sc.cycles, "preview_samples", 48)
        safe_set_attr(sc.cycles, "use_denoising", True)
        safe_set_attr(sc.cycles, "max_bounces", 10)
        safe_set_attr(sc.cycles, "transparent_max_bounces", 10)
    elif "BLENDER_EEVEE_NEXT" in ids:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in ids:
        sc.render.engine = "BLENDER_EEVEE"

    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    sc.world.color = (0.001,0.002,0.006)

    build_lab()
    build_anchor_frame()
    build_magnets()
    build_camera_and_lights()

    add_text("Title", "QFG TRI-MAGNET CHAOS PENDULUM", (0,0,4.72), 0.42, MAT_TEXT)
    add_text("Subtitle", "Three QFG attractors // nonlinear motion // chaotic trajectory", (0,0,4.12), 0.18, MAT_SUB)
    add_text("Status", "bob motion = numerical trajectory demo   |   lab / trail / glow = presentation layer", (0,0,-4.48), 0.16, MAT_TEXT)

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
        ("format","MPEG4"),
        ("codec","H264"),
        ("constant_rate_factor","HIGH"),
        ("ffmpeg_preset","GOOD"),
    ):
        try:
            setattr(ff, attr, val)
        except Exception:
            pass

# ============================================================
# MAIN
# ============================================================

print("\n================================================")
print(" QFG TRI-MAGNET CHAOS PENDULUM v1")
print("================================================\n")

clear_scene()
scene = setup_scene()

POSITIONS = compute_trajectory()

BOB_OBJ = add_uv_sphere("QFGBob", POSITIONS[0], 0.26, MAT_BOB, 30, 18)
STRING_OBJ = make_polyline_curve("QFGString", [ANCHOR, POSITIONS[0]], bevel_depth=0.014, material=MAT_STRING)
TRAIL_OBJ = make_polyline_curve("QFGTrail", [POSITIONS[0], POSITIONS[0] + Vector((0.001,0,0))], bevel_depth=0.020, material=MAT_TRAIL)

scene["demo"] = "QFG Tri-Magnet Chaos Pendulum v1"
scene["trajectory_frames"] = len(POSITIONS)
scene["scientific_status"] = "chaotic bob trajectory; cinematic presentation layer"

install_handler()
configure_output(scene)

out = resolve_output_dir()
blend_path = os.path.join(out, "QFG_Tri_Magnet_Chaos_Pendulum_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
chaos_handler(scene)

print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Frames:", scene["trajectory_frames"])
print("Preview: SPACE")
print("Render: Ctrl+F12")
print("Recommended: RES_PERCENT=100 for final export.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
