# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Vortex Lattice / Field Tunnel v1 - Blender 5.2+
#
# Scientific-cinematic demo:
#   - numerically advected particles
#   - helical vortex tunnel
#   - QFG core beam
#   - pulsing field rings
#   - dark laboratory / showcase presentation
#
# SCIENTIFIC STATUS
# -----------------
# particle advection = numerical field-driven demo
# tunnel / rings / glow / lab = presentation layer
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_VORTEX_TUNNEL_V1/
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
FRAME_END = 300
RES_X = 1920
RES_Y = 1080
RES_PERCENT = 60
AUTO_RENDER = False

OUTPUT_DIR_NAME = "QFG_VORTEX_TUNNEL_V1"
OUTPUT_FILE = "QFG_Vortex_Lattice_Field_Tunnel_v1"

PARTICLE_COUNT = 180
TRAIL_RING_COUNT = 16
DT = 0.050
SUBSTEPS = 3

TUNNEL_LEN = 10.0
TUNNEL_RADIUS = 2.0
CORE_RADIUS = 0.055

BASE_FORWARD_SPEED = 0.105
SWIRL_STRENGTH = 1.35
RADIAL_RESTORE = 0.55
AXIAL_WOBBLE = 0.18

PARTICLE_POSITIONS = []
PARTICLE_OBJ = None
PULSE_RINGS = []

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
    out.location = (320, 0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (0, 0)
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = strength

    if alpha < 0.999:
        transp = nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (0, -170)
        mix = nodes.new("ShaderNodeMixShader")
        mix.location = (160, 0)
        mix.inputs[0].default_value = 1.0 - alpha
        links.new(transp.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs[0])
        safe_set_attr(mat, "blend_method", "BLEND")
        safe_set_attr(mat, "shadow_method", "NONE")
    else:
        links.new(emission.outputs[0], out.inputs[0])

    return mat

def mat_dark(name, color=(0.02,0.024,0.035), roughness=0.30, metallic=0.12):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (320, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs[0], out.inputs[0])
    return mat

def mat_metal(name, color=(0.14,0.17,0.22), roughness=0.18, metallic=0.82):
    return mat_dark(name, color=color, roughness=roughness, metallic=metallic)

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

def add_cylinder_between(name, start, end, radius, material=None, verts=28):
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
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()

# ============================================================
# MATERIALS
# ============================================================

MAT_FLOOR  = mat_dark("QFG_Floor", color=(0.015,0.020,0.030), roughness=0.16, metallic=0.20)
MAT_WALL   = mat_dark("QFG_Wall", color=(0.010,0.013,0.022), roughness=0.75, metallic=0.0)
MAT_FRAME  = mat_metal("QFG_Frame", color=(0.11,0.15,0.22), roughness=0.18, metallic=0.85)
MAT_TEXT   = mat_emissive("QFG_Text", (0.93,0.97,1.0), 1.2)
MAT_SUB    = mat_emissive("QFG_Sub", (1.0,0.34,0.08), 2.2)
MAT_BEAM   = mat_emissive("QFG_CoreBeam", (0.35,0.78,1.0), 4.8, alpha=0.55)
MAT_BEAM2  = mat_emissive("QFG_CoreBeamGlow", (0.18,0.58,1.0), 2.0, alpha=0.18)
MAT_RING   = mat_emissive("QFG_Ring", (0.40,0.75,1.0), 1.8, alpha=0.25)
MAT_RING_B = mat_emissive("QFG_RingBright", (0.75,0.95,1.0), 3.5, alpha=0.55)
MAT_PART   = mat_emissive("QFG_Particle", (0.15,0.95,1.0), 7.0)
MAT_PART2  = mat_emissive("QFG_ParticleGlow", (0.55,0.75,1.0), 3.0)

# ============================================================
# NUMERICAL FIELD ADVECTION
# ============================================================

def init_particles():
    pts = []
    for i in range(PARTICLE_COUNT):
        theta = (2.0 * math.pi * i) / max(1, PARTICLE_COUNT)
        r = 0.55 + 1.15 * ((i % 17) / 16.0)
        y = -TUNNEL_LEN/2 + TUNNEL_LEN * ((i * 0.61803398875) % 1.0)
        x = r * math.cos(theta)
        z = r * math.sin(theta)
        pts.append(Vector((x, y, z)))
    return pts

def advect_particle(p, t):
    # tunnel axis is Y
    radial = Vector((p.x, 0.0, p.z))
    r = max(1e-6, radial.length)
    radial_dir = radial / r

    # swirl around Y-axis
    tangent = Vector((-radial_dir.z, 0.0, radial_dir.x))

    # numerical QFG-style vortex field
    swirl = tangent * (SWIRL_STRENGTH / (0.55 + r))
    restore = -radial_dir * RADIAL_RESTORE * (r - 1.15)
    forward = Vector((0.0, BASE_FORWARD_SPEED + 0.02 * math.sin(1.8*t + 1.7*r), 0.0))
    wobble = Vector((
        0.08 * math.sin(2.2 * p.y + 1.5 * t),
        0.0,
        0.08 * math.cos(2.7 * p.y - 1.1 * t),
    ))
    accel = swirl + restore + forward + wobble

    return p + accel * DT

def compute_particles():
    particles = init_particles()
    frames = []

    for frame in range(FRAME_START, FRAME_END + 1):
        t = (frame - FRAME_START) / FPS
        for _ in range(SUBSTEPS):
            for i, p in enumerate(particles):
                np1 = advect_particle(p, t)
                # wrap in tunnel
                if np1.y > TUNNEL_LEN/2:
                    np1.y = -TUNNEL_LEN/2
                elif np1.y < -TUNNEL_LEN/2:
                    np1.y = TUNNEL_LEN/2

                # limit radius gently
                rr = math.sqrt(np1.x*np1.x + np1.z*np1.z)
                if rr > TUNNEL_RADIUS:
                    scale = TUNNEL_RADIUS / rr
                    np1.x *= scale
                    np1.z *= scale

                particles[i] = np1
        frames.append([Vector(p) for p in particles])

    return frames

# ============================================================
# PARTICLE MESH / INSTANCING
# ============================================================

def make_points_mesh(name, points):
    mesh = bpy.data.meshes.new(name + "_Mesh")
    mesh.from_pydata([tuple(p) for p in points], [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def make_instance_object(name, radius, material):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=radius, location=(0,0,0))
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    o.hide_viewport = True
    o.hide_render = True
    return o

def add_points_instancer(points_obj, instance_obj):
    mod = points_obj.modifiers.new("PointsGN", "NODES")
    ng = bpy.data.node_groups.new(points_obj.name + "_GN", "GeometryNodeTree")
    mod.node_group = ng

    nodes = ng.nodes
    links = ng.links
    nodes.clear()

    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    gi   = nodes.new("NodeGroupInput")
    go   = nodes.new("NodeGroupOutput")
    m2p  = nodes.new("GeometryNodeMeshToPoints")
    oi   = nodes.new("GeometryNodeObjectInfo")
    inst = nodes.new("GeometryNodeInstanceOnPoints")
    real = nodes.new("GeometryNodeRealizeInstances")

    gi.location = (-700, 0)
    m2p.location = (-420, 0)
    oi.location = (-420, -180)
    inst.location = (-120, 0)
    real.location = (140, 0)
    go.location = (380, 0)

    m2p.mode = 'VERTICES'
    oi.inputs["Object"].default_value = instance_obj

    links.new(gi.outputs["Geometry"], m2p.inputs["Mesh"])
    links.new(m2p.outputs["Points"], inst.inputs["Points"])
    links.new(oi.outputs["Geometry"], inst.inputs["Instance"])
    links.new(inst.outputs["Instances"], real.inputs["Geometry"])
    links.new(real.outputs["Geometry"], go.inputs["Geometry"])

def update_points_object(obj, points):
    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata([tuple(map(float, p)) for p in points], [], [])
    mesh.update()

# ============================================================
# FRAME HANDLER
# ============================================================

def vortex_handler(scene):
    idx = max(0, min(scene.frame_current - FRAME_START, len(PARTICLE_POSITIONS)-1))

    if PARTICLE_OBJ is not None:
        update_points_object(PARTICLE_OBJ, PARTICLE_POSITIONS[idx])

    # pulse and rotate rings
    t = (scene.frame_current - FRAME_START) / max(1, (FRAME_END - FRAME_START))
    for j, ring in enumerate(PULSE_RINGS):
        s = 1.0 + 0.08 * math.sin(2.0 * math.pi * (t * 2.2 + j * 0.12))
        ring.scale = (s, 1.0, s)
        ring.rotation_euler[1] = 2.0 * math.pi * (t * 0.35 + j * 0.03)

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "vortex_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(vortex_handler)

# ============================================================
# SCENE
# ============================================================

def build_lab():
    add_cube("LabFloor", (0, 0, -2.55), (6.0, 8.0, 0.16), MAT_FLOOR)
    add_cube("BackWall", (0, 6.15, 0.8), (6.2, 0.12, 3.6), MAT_WALL)
    add_cube("LeftWall", (-6.05, 0, 0.8), (0.12, 6.4, 3.6), MAT_WALL)
    add_cube("RightWall", (6.05, 0, 0.8), (0.12, 6.4, 3.6), MAT_WALL)

def build_tunnel():
    # QFG field frame
    add_cube("TunnelBase", (0, 0, -2.05), (2.55, 6.0, 0.07), MAT_FRAME)

    # core beam
    add_cylinder_between("CoreBeamGlow", (0, -TUNNEL_LEN/2, 0), (0, TUNNEL_LEN/2, 0), 0.17, MAT_BEAM2, verts=30)
    add_cylinder_between("CoreBeam", (0, -TUNNEL_LEN/2, 0), (0, TUNNEL_LEN/2, 0), CORE_RADIUS, MAT_BEAM, verts=30)

    # tunnel rings
    ys = np.linspace(-TUNNEL_LEN/2, TUNNEL_LEN/2, TRAIL_RING_COUNT)
    for i, y in enumerate(ys):
        major = TUNNEL_RADIUS + 0.12 * math.sin(i * 0.55)
        mat = MAT_RING_B if i % 4 == 0 else MAT_RING
        ring = add_torus(f"FieldRing_{i:02d}", (0, float(y), 0), major, 0.025 if i % 4 == 0 else 0.014, mat)
        ring.rotation_euler = (math.pi/2, 0, 0)
        PULSE_RINGS.append(ring)

def build_camera_and_lights():
    sc = bpy.context.scene

    bpy.ops.object.camera_add(location=(0, -14.4, 4.6))
    cam = bpy.context.object
    cam.name = "QFGCamera"
    sc.camera = cam
    cam.data.lens = 72

    try:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = 11.0
        cam.data.dof.aperture_fstop = 2.2
    except Exception:
        pass

    keys = [
        (1,   (0.0, -14.4, 4.6), (0, 0, 0), 72),
        (70,  (-1.1, -12.2, 4.1), (0, 0, 0), 68),
        (140, (1.4, -9.5, 3.0), (0, 0, 0), 78),
        (205, (3.2, -6.7, 2.0), (0, 1.2, 0), 92),
        (260, (0.8, -9.2, 3.5), (0, 0, 0), 76),
        (300, (0.0, -14.7, 4.8), (0, 0, 0), 74),
    ]
    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    bpy.ops.object.light_add(type="AREA", location=(-6.5, -5.0, 7.0))
    key = bpy.context.object
    key.data.energy = 1850
    key.data.size = 6.3
    key.data.color = (0.42, 0.72, 1.0)
    look_at(key, (0, 0, 0))

    bpy.ops.object.light_add(type="AREA", location=(5.2, -0.5, 6.6))
    fill = bpy.context.object
    fill.data.energy = 1100
    fill.data.size = 5.4
    fill.data.color = (1.0, 0.22, 0.82)
    look_at(fill, (0, 0, 0))

    bpy.ops.object.light_add(type="AREA", location=(0.0, -8.8, 3.2))
    rim = bpy.context.object
    rim.data.energy = 920
    rim.data.size = 3.0
    rim.data.color = (1.0, 0.40, 0.12)
    look_at(rim, (0, 0, 0))

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

    sc.world.color = (0.001, 0.002, 0.006)

    build_lab()
    build_tunnel()
    build_camera_and_lights()

    add_text("Title", "QFG VORTEX LATTICE / FIELD TUNNEL", (0, 0, 4.55), 0.41, MAT_TEXT)
    add_text("Subtitle", "Helical field transport // numerical particle advection // QFG vortex core", (0, 0, 4.00), 0.18, MAT_SUB)
    add_text("Status", "particle advection = numerical field demo   |   tunnel / rings / glow = presentation layer", (0, 0, -4.48), 0.155, MAT_TEXT)

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

print("\n================================================")
print(" QFG VORTEX LATTICE / FIELD TUNNEL v1")
print("================================================\n")

clear_scene()
scene = setup_scene()

PARTICLE_POSITIONS = compute_particles()

PARTICLE_OBJ = make_points_mesh("QFGParticles", PARTICLE_POSITIONS[0])
particle_instance = make_instance_object("QFGParticleInstance", 0.060, MAT_PART)
add_points_instancer(PARTICLE_OBJ, particle_instance)

scene["demo"] = "QFG Vortex Lattice / Field Tunnel v1"
scene["particle_count"] = PARTICLE_COUNT
scene["scientific_status"] = "field-driven numerical particle advection; cinematic presentation layer"

install_handler()
configure_output(scene)

out = resolve_output_dir()
blend_path = os.path.join(out, "QFG_Vortex_Lattice_Field_Tunnel_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
vortex_handler(scene)

print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Particles:", scene["particle_count"])
print("Preview: SPACE")
print("Render: Ctrl+F12")
print("Recommended: RES_PERCENT=100 for final export.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
