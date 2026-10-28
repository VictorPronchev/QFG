# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Field Tomography / Force Probe Lab v1 - Blender 5.2+
#
# A scientific-style Blender visualization for QFG Dynamics:
#   - moving QFG field source
#   - volumetric probe array
#   - density indicators
#   - force / gradient probe arrows
#   - field cloud
#   - scanning-lab presentation
#
# SCIENTIFIC STATUS
# -----------------
# QFG field = numerical runtime
# probe graphics = visualization layer
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_TOMOGRAPHY_LAB_V1/
# ---------------------------------------------------------------------------

import bpy
import math
import os
import sys
import importlib
import numpy as np
from mathutils import Vector

# ============================================================
# CONFIG
# ============================================================

FPS = 24
FRAME_START = 1
FRAME_END = 480
RES_X = 1920
RES_Y = 1080
RES_PERCENT = 50
AUTO_RENDER = False

OUTPUT_DIR_NAME = "QFG_TOMOGRAPHY_LAB_V1"
OUTPUT_FILE = "QFG_Field_Tomography_Force_Probe_Lab_v1"

# Probe volume
VOL_CENTER = np.array((0.0, 0.0, 0.75), dtype=np.float64)
VOL_SIZE_X = 6.8
VOL_SIZE_Y = 4.8
VOL_SIZE_Z = 3.6

PROBE_NX = 7
PROBE_NY = 5
PROBE_NZ = 4

PROBE_SPHERE_BASE = 0.08
ARROW_SHAFT_RADIUS = 0.03
ARROW_TIP_RADIUS = 0.065
ARROW_TIP_DEPTH = 0.16
ARROW_SCALE = 0.90

# QFG forcing / display
FIELD_ROTATION_TURNS = 1.15
PULSE_CENTER = 270
PULSE_SIGMA = 18.0
PULSE_GAIN = 2.0

# QFG world
QFG_GRID = 32
QFG_DOMAIN = 16.0
QFG_DT = 0.002
QFG_STEPS = 18
FIELD_CACHE_N = 25
FIELD_CACHE_HALF = 5.8

# ============================================================
# QFG SDK
# ============================================================

def candidate_roots():
    roots = []
    try:
        for key in bpy.context.preferences.addons.keys():
            if "qfg_lab_52" in key.lower():
                roots.append(key)
    except Exception:
        pass
    roots += [
        "qfg_lab_52",
        "bl_ext.user_default.qfg_lab_52",
        "bl_ext.blender_org.qfg_lab_52",
    ]
    out = []
    for r in roots:
        if r and r not in out:
            out.append(r)
    return out

def load_sdk():
    errors = {}
    for root in candidate_roots():
        try:
            sdk = importlib.import_module(root + ".sdk")
            req = ("create_world", "EngineConfig", "WorldConfig", "ActorSpec")
            if all(hasattr(sdk, n) for n in req):
                print("QFG SDK:", sdk.__name__)
                return root, sdk
        except Exception as exc:
            errors[root] = repr(exc)
    raise RuntimeError(
        "QFG Dynamics SDK not found. Enable QFG Dynamics 1.0.0+.\n" +
        "\n".join(f"{k}: {v}" for k, v in errors.items())
    )

QFG_ROOT, SDK = load_sdk()
create_world = SDK.create_world
EngineConfig = SDK.EngineConfig
WorldConfig = SDK.WorldConfig
ActorSpec = SDK.ActorSpec

# ============================================================
# BLENDER HELPERS
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
    return m

MAT_TEXT = make_material("Text", (0.92, 0.96, 1.00), emission=1.0, roughness=0.30)
MAT_ORANGE = make_material("Orange", (1.00, 0.24, 0.03), emission=3.0, roughness=0.22)
MAT_FIELD = make_material("Field", (0.58, 0.10, 1.00), emission=3.2, roughness=0.20)
MAT_PROBE = make_material("Probe", (0.15, 0.75, 1.00), emission=1.1, metallic=0.10, roughness=0.25)
MAT_DENSITY = make_material("Density", (0.20, 0.95, 1.00), emission=1.0, roughness=0.30)
MAT_FRAME = make_material("Frame", (0.10, 0.14, 0.20), emission=0.0, metallic=0.55, roughness=0.24)
MAT_FLOOR = make_material("Floor", (0.02, 0.03, 0.05), emission=0.0, metallic=0.10, roughness=0.70)
MAT_SOURCE = make_material("Source", (1.00, 0.30, 0.08), emission=3.0, metallic=0.15, roughness=0.20)

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
    o.rotation_euler = (math.pi/2, 0, 0)
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

def add_sphere(name, loc, radius, material, segments=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=loc
    )
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    return o

def add_cylinder(name, loc, radius, depth, material):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=depth,
        location=loc
    )
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    return o

def add_cone(name, loc, radius1, depth, material):
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=radius1,
        depth=depth,
        location=loc
    )
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    return o

def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()

# ============================================================
# QFG FIELD CACHE
# ============================================================

def build_qfg_world():
    ec = EngineConfig(
        grid_size=QFG_GRID,
        domain_length=QFG_DOMAIN,
        dt=QFG_DT,
        backend="NUMPY",
        field_mode="SCALAR",
        thermal_enabled=False,
        topology_enabled=True,
    )
    wc = WorldConfig(
        substeps=2,
        gravity=(0,0,0),
        floor_height=-1000.0,
        body_collisions=False,
        deterministic=True,
        seed=1337,
    )
    world = create_world(ec, wc)
    world.add_field_actor(ActorSpec(
        actor_type="GAUSSIAN",
        center=(0,0,0),
        radius=1.75,
        intensity=1.35,
        velocity=(0,0,0),
        name="TomographyGaussian",
    ))
    world.add_field_actor(ActorSpec(
        actor_type="VORTEX",
        center=(0,0,0),
        radius=2.70,
        intensity=0.78,
        winding_m=1,
        velocity=(0,0,0),
        name="TomographyVortex",
    ))
    world.step(QFG_STEPS)
    return world

def cache_field(world):
    axis = np.linspace(-FIELD_CACHE_HALF, FIELD_CACHE_HALF, FIELD_CACHE_N)
    grad = np.zeros((FIELD_CACHE_N, FIELD_CACHE_N, FIELD_CACHE_N, 3), dtype=np.float32)
    density = np.zeros((FIELD_CACHE_N, FIELD_CACHE_N, FIELD_CACHE_N), dtype=np.float32)
    print("Sampling QFG field cache...")
    for i, x in enumerate(axis):
        for j, y in enumerate(axis):
            for k, z in enumerate(axis):
                s = world.sample_field((float(x), float(y), float(z)))
                grad[i,j,k] = np.asarray(s["density_gradient"], dtype=np.float32)
                density[i,j,k] = float(s["density"])
    print("QFG cache complete.")
    return axis, grad, density

def trilerp_vector(points, axis, grid):
    pts = np.asarray(points, dtype=np.float64)
    n = len(axis)
    lo = float(axis[0]); hi = float(axis[-1]); h = (hi-lo)/(n-1)
    q = np.clip((pts-lo)/h, 0, n-1-1e-8)
    i0 = np.floor(q).astype(np.int32)
    f = q-i0
    i1 = np.minimum(i0+1, n-1)

    x0,y0,z0=i0[...,0],i0[...,1],i0[...,2]
    x1,y1,z1=i1[...,0],i1[...,1],i1[...,2]
    fx,fy,fz=f[...,0][...,None],f[...,1][...,None],f[...,2][...,None]

    c000=grid[x0,y0,z0]; c100=grid[x1,y0,z0]
    c010=grid[x0,y1,z0]; c110=grid[x1,y1,z0]
    c001=grid[x0,y0,z1]; c101=grid[x1,y0,z1]
    c011=grid[x0,y1,z1]; c111=grid[x1,y1,z1]

    c00=c000*(1-fx)+c100*fx
    c10=c010*(1-fx)+c110*fx
    c01=c001*(1-fx)+c101*fx
    c11=c011*(1-fx)+c111*fx
    c0=c00*(1-fy)+c10*fy
    c1=c01*(1-fy)+c11*fy
    return c0*(1-fz)+c1*fz

def trilerp_scalar(points, axis, grid):
    pts = np.asarray(points, dtype=np.float64)
    n = len(axis)
    lo = float(axis[0]); hi = float(axis[-1]); h = (hi-lo)/(n-1)
    q = np.clip((pts-lo)/h, 0, n-1-1e-8)
    i0 = np.floor(q).astype(np.int32)
    f = q-i0
    i1 = np.minimum(i0+1, n-1)

    x0,y0,z0=i0[...,0],i0[...,1],i0[...,2]
    x1,y1,z1=i1[...,0],i1[...,1],i1[...,2]
    fx,fy,fz=f[...,0],f[...,1],f[...,2]

    c000=grid[x0,y0,z0]; c100=grid[x1,y0,z0]
    c010=grid[x0,y1,z0]; c110=grid[x1,y1,z0]
    c001=grid[x0,y0,z1]; c101=grid[x1,y0,z1]
    c011=grid[x0,y1,z1]; c111=grid[x1,y1,z1]

    c00=c000*(1-fx)+c100*fx
    c10=c010*(1-fx)+c110*fx
    c01=c001*(1-fx)+c101*fx
    c11=c011*(1-fx)+c111*fx
    c0=c00*(1-fy)+c10*fy
    c1=c01*(1-fy)+c11*fy
    return c0*(1-fz)+c1*fz

def rotate_z(v, angle):
    c = math.cos(angle); s = math.sin(angle)
    out = np.empty_like(v)
    out[...,0] = c*v[...,0] - s*v[...,1]
    out[...,1] = s*v[...,0] + c*v[...,1]
    out[...,2] = v[...,2]
    return out

# ============================================================
# PROBE GRID + FIELD SAMPLING
# ============================================================

def probe_positions():
    xs = np.linspace(-VOL_SIZE_X/2, VOL_SIZE_X/2, PROBE_NX)
    ys = np.linspace(-VOL_SIZE_Y/2, VOL_SIZE_Y/2, PROBE_NY)
    zs = np.linspace(-VOL_SIZE_Z/2, VOL_SIZE_Z/2, PROBE_NZ)
    pts = []
    for z in zs:
        for y in ys:
            for x in xs:
                pts.append((x, y, z))
    return np.asarray(pts, dtype=np.float64)

PROBE_LOCAL = probe_positions()
PROBE_COUNT = len(PROBE_LOCAL)

def source_position(frame):
    t = (frame-FRAME_START)/(FRAME_END-FRAME_START)
    a = 2.0*math.pi*1.05*t
    r = 2.25 + 0.35*math.sin(4.0*math.pi*t)
    return np.array((
        r*math.cos(a),
        r*math.sin(a),
        0.25 + 0.80*math.sin(2.0*a)
    ), dtype=np.float64)

def pulse_gain(frame):
    x = (frame-PULSE_CENTER)/PULSE_SIGMA
    return 1.0 + PULSE_GAIN*math.exp(-0.5*x*x)

def sample_states(axis, grad_grid, density_grid):
    frames = FRAME_END - FRAME_START + 1
    grads = np.zeros((frames, PROBE_COUNT, 3), dtype=np.float32)
    dens = np.zeros((frames, PROBE_COUNT), dtype=np.float32)
    srcs = np.zeros((frames, 3), dtype=np.float32)

    print("Sampling probe array over timeline...")
    for idx, frame in enumerate(range(FRAME_START, FRAME_END+1)):
        src = source_position(frame)
        srcs[idx] = src
        pts = PROBE_LOCAL - src[None,:]
        g = trilerp_vector(pts, axis, grad_grid)
        d = trilerp_scalar(pts, axis, density_grid)

        t = (frame-FRAME_START)/(FRAME_END-FRAME_START)
        g = rotate_z(g, 2.0*math.pi*FIELD_ROTATION_TURNS*t)
        g = g * pulse_gain(frame)

        grads[idx] = g.astype(np.float32)
        dens[idx] = d.astype(np.float32)

        if idx % 72 == 0 and idx > 0:
            print(f"  frame {frame}/{FRAME_END}")
    print("Probe sampling complete.")
    return grads, dens, srcs

# ============================================================
# PROBE OBJECTS + HANDLER
# ============================================================

PROBE_STRUCTS = []
PROBE_GRADS = None
PROBE_DENS = None
SOURCE_OBJ = None
SOURCE_PATH_CLOUD = None
SOURCE_STATES = None

def create_probe_object(name, location):
    root = bpy.data.objects.new(name+"_Root", None)
    bpy.context.collection.objects.link(root)
    root.location = tuple(VOL_CENTER + location)

    sphere = add_sphere(name+"_Density", root.location, PROBE_SPHERE_BASE, MAT_DENSITY, 16, 8)
    sphere.parent = root
    sphere.location = (0.0, 0.0, 0.0)

    shaft = add_cylinder(name+"_Shaft", root.location, ARROW_SHAFT_RADIUS, 0.40, MAT_PROBE)
    shaft.parent = root
    shaft.location = (0.0, 0.0, 0.20)

    tip = add_cone(name+"_Tip", root.location, ARROW_TIP_RADIUS, ARROW_TIP_DEPTH, MAT_PROBE)
    tip.parent = root
    tip.location = (0.0, 0.0, 0.48)

    return {
        "root": root,
        "sphere": sphere,
        "shaft": shaft,
        "tip": tip,
    }

def update_probe_struct(ps, grad, dens):
    root = ps["root"]
    sphere = ps["sphere"]
    shaft = ps["shaft"]
    tip = ps["tip"]

    g = np.asarray(grad, dtype=np.float64)
    gm = float(np.linalg.norm(g))

    direction = g / gm if gm > 1e-8 else np.array((0.0, 0.0, 1.0))
    end = Vector(direction.tolist())
    quat = end.to_track_quat("Z", "Y")
    root.rotation_euler = quat.to_euler()

    arrow_len = 0.15 + ARROW_SCALE * min(1.65, gm*0.55)
    shaft.scale = (1.0, 1.0, max(0.08, arrow_len))
    shaft.location = (0.0, 0.0, max(0.08, arrow_len)/2.0)

    tip.location = (0.0, 0.0, max(0.08, arrow_len) + ARROW_TIP_DEPTH/2.0)

    dens_mag = max(0.0, float(dens))
    sphere_scale = 0.80 + min(1.8, dens_mag*1.10)
    sphere.scale = (sphere_scale, sphere_scale, sphere_scale)

def qfg_tomography_handler(scene):
    if PROBE_GRADS is None or PROBE_DENS is None:
        return
    idx = max(0, min(scene.frame_current-FRAME_START, PROBE_GRADS.shape[0]-1))

    for i, ps in enumerate(PROBE_STRUCTS):
        update_probe_struct(ps, PROBE_GRADS[idx, i], PROBE_DENS[idx, i])

    if SOURCE_OBJ is not None and SOURCE_STATES is not None:
        SOURCE_OBJ.location = tuple(VOL_CENTER + SOURCE_STATES[idx])

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "qfg_tomography_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(qfg_tomography_handler)

# ============================================================
# VISUALS
# ============================================================

def build_volume_frame():
    add_cube("Floor", (0,0,-1.55), (6.0,5.0,0.08), MAT_FLOOR)

    # outer frame
    add_cube("Frame_Bottom", tuple(VOL_CENTER + np.array((0,0,-VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)
    add_cube("Frame_Top",    tuple(VOL_CENTER + np.array((0,0, VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)

    # side pillars
    pillar_offsets = [
        (-VOL_SIZE_X/2, -VOL_SIZE_Y/2, 0),
        ( VOL_SIZE_X/2, -VOL_SIZE_Y/2, 0),
        (-VOL_SIZE_X/2,  VOL_SIZE_Y/2, 0),
        ( VOL_SIZE_X/2,  VOL_SIZE_Y/2, 0),
    ]
    for idx, off in enumerate(pillar_offsets):
        add_cube(f"Pillar_{idx}", tuple(VOL_CENTER + np.array(off)), (0.02, 0.02, VOL_SIZE_Z/2), MAT_FRAME)

    # back/top crossbars
    add_cube("BackTop", tuple(VOL_CENTER + np.array((0, VOL_SIZE_Y/2, VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)
    add_cube("BackBottom", tuple(VOL_CENTER + np.array((0, VOL_SIZE_Y/2, -VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)
    add_cube("FrontTop", tuple(VOL_CENTER + np.array((0, -VOL_SIZE_Y/2, VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)
    add_cube("FrontBottom", tuple(VOL_CENTER + np.array((0, -VOL_SIZE_Y/2, -VOL_SIZE_Z/2))), (VOL_SIZE_X/2, 0.02, 0.02), MAT_FRAME)

def build_probe_array():
    global PROBE_STRUCTS
    PROBE_STRUCTS = []
    for i, p in enumerate(PROBE_LOCAL):
        PROBE_STRUCTS.append(create_probe_object(f"Probe_{i:03d}", p))

def build_field_cloud(axis, density):
    parent = bpy.data.objects.new("QFG_Field_Cloud", None)
    bpy.context.collection.objects.link(parent)

    vmax = float(np.max(density))
    threshold = float(np.quantile(density, 0.945))
    count = 0

    for i in range(0, len(axis), 2):
        for j in range(0, len(axis), 2):
            for k in range(0, len(axis), 2):
                val = float(density[i,j,k])
                if val < threshold or count >= 180:
                    continue
                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=1,
                    radius=0.018 + 0.050*min(1.0, val/max(vmax, 1e-9)),
                    location=(float(axis[i]), float(axis[j]), float(axis[k]))
                )
                o = bpy.context.object
                o.parent = parent
                o.data.materials.append(MAT_FIELD)
                count += 1

    parent.scale = (0.52, 0.52, 0.52)
    return parent

def setup_scene():
    sc = bpy.context.scene
    sc.frame_start = FRAME_START
    sc.frame_end = FRAME_END
    sc.render.fps = FPS
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.resolution_percentage = RES_PERCENT
    sc.world.color = (0.001, 0.002, 0.006)

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

    build_volume_frame()

    add_text("Title", "QFG FIELD TOMOGRAPHY / FORCE PROBE LAB", (0,0,4.35), 0.44, MAT_TEXT)
    add_text("Subtitle", "Density indicators + sampled gradient vectors + moving field source", (0,0,3.85), 0.20, MAT_FIELD)
    add_text("Status", "QFG field = numerical runtime   |   probe graphics = visualization layer", (0,0,-2.55), 0.17, MAT_ORANGE)

    # camera
    bpy.ops.object.camera_add(location=(0,-12.0,5.8))
    cam = bpy.context.object
    cam.name = "QFG_Tomography_Camera"
    sc.camera = cam
    cam.data.lens = 56
    look_at(cam, (0,0,0.85))

    keys = [
        (1,   (0,-12.0,5.8), (0,0,0.85), 56),
        (110, (-1.0,-10.5,5.0), (0,0,0.85), 52),
        (220, (1.0,-9.5,4.3), (0.8,0,0.85), 52),
        (305, (3.0,-7.0,3.3), (0.0,0.0,0.95), 68),
        (380, (0.0,-8.8,4.0), (0.0,0.0,0.9), 58),
        (480, (0,-12.2,6.0), (0,0,0.85), 58),
    ]
    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    bpy.ops.object.light_add(type="AREA", location=(-5,-5,8))
    key = bpy.context.object
    key.data.energy = 1250
    key.data.size = 5.8
    key.data.color = (0.14,0.38,1.0)
    look_at(key, (0,0,0.9))

    bpy.ops.object.light_add(type="AREA", location=(5,-1,7))
    fill = bpy.context.object
    fill.data.energy = 1000
    fill.data.size = 5.2
    fill.data.color = (0.56,0.10,1.0)
    look_at(fill, (0,0,0.9))

    bpy.ops.object.light_add(type="POINT", location=(0,-2,2.5))
    rim = bpy.context.object
    rim.data.energy = 450
    rim.data.color = (0.08,0.92,1.0)

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

print("\n==============================================")
print(" QFG FIELD TOMOGRAPHY / FORCE PROBE LAB v1")
print("==============================================\n")

clear_scene()
scene = setup_scene()

print("[1/4] Building QFG field...")
world = build_qfg_world()
axis, grad_grid, density_grid = cache_field(world)

print("[2/4] Sampling probes over time...")
PROBE_GRADS, PROBE_DENS, SOURCE_STATES = sample_states(axis, grad_grid, density_grid)

print("[3/4] Building lab objects...")
build_probe_array()
SOURCE_PATH_CLOUD = build_field_cloud(axis, density_grid)
SOURCE_OBJ = add_sphere("FieldSource", tuple(VOL_CENTER + SOURCE_STATES[0]), 0.15, MAT_SOURCE, 24, 12)

# animate field cloud parent + source
for f in range(FRAME_START, FRAME_END+1, 12):
    idx = f - FRAME_START
    p = SOURCE_STATES[idx]
    SOURCE_PATH_CLOUD.location = tuple(VOL_CENTER + p)
    t = (f-FRAME_START)/(FRAME_END-FRAME_START)
    SOURCE_PATH_CLOUD.rotation_euler = (0,0,2.0*math.pi*FIELD_ROTATION_TURNS*t)
    g = pulse_gain(f)
    s = 0.52*(1.0 + 0.05*(g-1.0))
    SOURCE_PATH_CLOUD.scale = (s,s,s)
    SOURCE_PATH_CLOUD.keyframe_insert("location", frame=f)
    SOURCE_PATH_CLOUD.keyframe_insert("rotation_euler", frame=f)
    SOURCE_PATH_CLOUD.keyframe_insert("scale", frame=f)

    SOURCE_OBJ.location = tuple(VOL_CENTER + p)
    SOURCE_OBJ.scale = (1.0 + 0.10*(g-1.0),) * 3
    SOURCE_OBJ.keyframe_insert("location", frame=f)
    SOURCE_OBJ.keyframe_insert("scale", frame=f)

install_handler()

scene["demo"] = "QFG Field Tomography / Force Probe Lab v1"
scene["qfg_namespace"] = QFG_ROOT
scene["probe_count"] = PROBE_COUNT
scene["probe_grid"] = f"{PROBE_NX}x{PROBE_NY}x{PROBE_NZ}"
scene["qfg_grid"] = QFG_GRID
scene["scientific_status"] = "QFG field numerical; probe arrows and density spheres are visualization layers"

print("[4/4] Saving...")
configure_output(scene)
out = resolve_output_dir()
blend_path = os.path.join(out, "QFG_Field_Tomography_Force_Probe_Lab_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
qfg_tomography_handler(scene)

print("\nDONE")
print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Probe count:", PROBE_COUNT)
print("SPACE = preview | Ctrl+F12 = render")
print("Set RES_PERCENT=100 for final render.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
