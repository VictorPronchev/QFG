# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Fur Dynamics Demo v3 - Blender 5.2+
#
# v3 upgrades the previous fur comparison demo with:
#   - denser / longer fur
#   - clearer split-screen comparison
#   - QFG orbit phase
#   - QFG shock-wave sweep phase
#   - close-up camera on the QFG-driven side
#   - animated wavefront / ring visualization
#
# LEFT  : gravity + collision
# RIGHT : gravity + collision + sampled QFG density-gradient + shock sweep
#
# SCIENTIFIC STATUS
# -----------------
# QFGWorld provides the numerical field and density gradients.
# The fur motion is produced by a custom visualization solver
# (Verlet + distance constraints), not by a validated constitutive model.
#
# Run in Blender 5.2 with QFG Dynamics enabled.
#   Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   //QFG_FUR_DEMO_V3/QFG_Fur_Dynamics_v3.mp4
#   //QFG_FUR_DEMO_V3/QFG_Fur_Dynamics_v3.blend
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
FRAME_END = 576           # 24 seconds
RES_X = 1920
RES_Y = 1080
RES_PERCENT = 50
AUTO_RENDER = False

OUTPUT_DIR = "//QFG_FUR_DEMO_V3/"
OUTPUT_FILE = "QFG_Fur_Dynamics_v3"
BLEND_FILE = "//QFG_FUR_DEMO_V3/QFG_Fur_Dynamics_v3.blend"

# Layout
LEFT_CENTER  = np.array((-3.6, 0.0, 0.0), dtype=np.float64)
RIGHT_CENTER = np.array(( 3.6, 0.0, 0.0), dtype=np.float64)

# Fur
BODY_RADIUS = 1.85
STRAND_COUNT = 150
SEGMENTS = 10
STRAND_LENGTH = 1.70
SEG_LEN = STRAND_LENGTH / (SEGMENTS - 1)
HAIR_RADIUS = 0.018
DAMPING = 0.928
GRAVITY = np.array((0.0, 0.0, -0.84), dtype=np.float64)
CONSTRAINT_ITERS = 6

# QFG coupling
BASE_QFG_FORCE_SCALE = 5.6
FIELD_ROTATION_TURNS = 1.40

# Shock phase
SHOCK_START = 286
SHOCK_END   = 392
SHOCK_CENTER_LOCAL = np.array((0.0, 0.0, 0.0), dtype=np.float64)
SHOCK_WAVE_SPEED = 0.078
SHOCK_WAVE_WIDTH = 0.40
SHOCK_WAVE_GAIN = 4.8

# Pulse phase
PULSE_CENTER_FRAME = 248
PULSE_SIGMA = 18.0
PULSE_GAIN = 1.85

# Collider
COLLIDER_RADIUS = 0.62

# QFG field cache
QFG_GRID = 32
QFG_DOMAIN = 16.0
QFG_DT = 0.002
QFG_STEPS = 18
FIELD_CACHE_N = 23
FIELD_CACHE_HALF = 5.4

# ============================================================
# QFG SDK LOADER
# ============================================================

def candidate_roots():
    roots = []
    try:
        for key in bpy.context.preferences.addons.keys():
            if "qfg_lab_52" in key.lower():
                roots.append(key)
    except Exception:
        pass

    for mod_name in list(sys.modules):
        if mod_name.endswith("qfg_lab_52"):
            roots.append(mod_name)

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

    details = "\n".join(f"  {k}: {v}" for k, v in errors.items())
    raise RuntimeError(
        "QFG Dynamics SDK not found. Enable QFG Dynamics 1.0.0.\n" + details
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
    # Blender 5.2 removed legacy Material.shadow_method and may expose
    # transparency/render settings differently depending on the build.
    # Keep the material setup API-safe; alpha is still passed to Principled BSDF.
    if hasattr(m, "blend_method"):
        try:
            m.blend_method = "BLEND"
        except Exception:
            pass
    if hasattr(m, "shadow_method"):
        try:
            m.shadow_method = "HASHED"
        except Exception:
            pass
    return m

MAT_LEFT_BODY = None
MAT_RIGHT_BODY = None
MAT_LEFT_HAIR = None
MAT_RIGHT_HAIR = None
MAT_FIELD = None
MAT_COLLIDER = None
MAT_TEXT = None
MAT_ORANGE = None
MAT_BG = None
MAT_RING = None
MAT_DIM = None

def init_materials():
    global MAT_LEFT_BODY, MAT_RIGHT_BODY, MAT_LEFT_HAIR, MAT_RIGHT_HAIR
    global MAT_FIELD, MAT_COLLIDER, MAT_TEXT, MAT_ORANGE, MAT_BG, MAT_RING, MAT_DIM

    MAT_LEFT_BODY  = make_material("LeftBody",  (0.05,0.08,0.14), metallic=0.45, roughness=0.30)
    MAT_RIGHT_BODY = make_material("RightBody", (0.03,0.08,0.20), emission=0.15, metallic=0.45, roughness=0.26)

    MAT_LEFT_HAIR  = make_material("LeftHair",  (0.78,0.82,0.90), emission=0.12, roughness=0.45)
    MAT_RIGHT_HAIR = make_material("RightHair", (0.03,0.74,1.00), emission=1.8, roughness=0.28)

    MAT_FIELD    = make_material("Field",    (0.55,0.09,1.00), emission=3.2, roughness=0.22)
    MAT_COLLIDER = make_material("Collider", (0.08,1.00,0.30), emission=2.0, metallic=0.25, roughness=0.24)
    MAT_TEXT     = make_material("Text",     (0.90,0.95,1.00), emission=1.0, roughness=0.30)
    MAT_ORANGE   = make_material("Orange",   (1.00,0.24,0.03), emission=3.2, roughness=0.22)
    MAT_BG       = make_material("BG",       (0.01,0.015,0.025), roughness=0.65)
    MAT_RING     = make_material("Ring",     (1.00,0.22,0.04), emission=4.0, roughness=0.18, alpha=0.55)
    MAT_DIM      = make_material("Dim",      (0.24,0.28,0.35), emission=0.0, roughness=0.65)

def add_text(name, body, loc, size=0.30, material=None):
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

def add_sphere(name, loc, radius, material, segments=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, radius=radius, location=loc
    )
    o = bpy.context.object
    o.name = name
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

def add_torus(name, loc, major_radius, minor_radius, material):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=72,
        minor_segments=18,
        major_radius=major_radius,
        minor_radius=minor_radius,
        location=loc,
        rotation=(math.pi/2, 0, 0),
    )
    o = bpy.context.object
    o.name = name
    if material:
        o.data.materials.append(material)
    return o

def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

# ============================================================
# QFG WORLD + FIELD CACHE
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
        gravity=(0.0, 0.0, 0.0),
        floor_height=-1000.0,
        body_collisions=False,
        deterministic=True,
        seed=1337,
    )

    world = create_world(ec, wc)

    world.add_field_actor(ActorSpec(
        actor_type="GAUSSIAN",
        center=(0.0,0.0,0.0),
        velocity=(0.0,0.0,0.0),
        radius=1.75,
        intensity=1.35,
        name="Fur_Gaussian",
    ))
    world.add_field_actor(ActorSpec(
        actor_type="VORTEX",
        center=(0.0,0.0,0.0),
        velocity=(0.0,0.0,0.0),
        radius=2.65,
        intensity=0.75,
        winding_m=1,
        name="Fur_Vortex",
    ))

    world.step(QFG_STEPS)
    return world

def cache_qfg_field(world):
    axis = np.linspace(-FIELD_CACHE_HALF, FIELD_CACHE_HALF, FIELD_CACHE_N)
    grad = np.zeros((FIELD_CACHE_N,FIELD_CACHE_N,FIELD_CACHE_N,3), dtype=np.float32)
    density = np.zeros((FIELD_CACHE_N,FIELD_CACHE_N,FIELD_CACHE_N), dtype=np.float32)

    print("Sampling QFG field cache...")
    for i,x in enumerate(axis):
        for j,y in enumerate(axis):
            for k,z in enumerate(axis):
                sample = world.sample_field((float(x), float(y), float(z)))
                grad[i,j,k] = np.asarray(sample["density_gradient"], dtype=np.float32)
                density[i,j,k] = float(sample["density"])
    print("QFG field cache complete.")
    return axis, grad, density

def trilerp_vector(points, axis, grid):
    pts = np.asarray(points, dtype=np.float64)
    n = len(axis)
    lo = float(axis[0])
    hi = float(axis[-1])
    h = (hi - lo) / (n - 1)

    q = np.clip((pts - lo) / h, 0, n - 1 - 1e-8)
    i0 = np.floor(q).astype(np.int32)
    f = q - i0
    i1 = np.minimum(i0 + 1, n - 1)

    x0,y0,z0 = i0[...,0],i0[...,1],i0[...,2]
    x1,y1,z1 = i1[...,0],i1[...,1],i1[...,2]
    fx,fy,fz = f[...,0][...,None],f[...,1][...,None],f[...,2][...,None]

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

def rotate_z_vectors(v, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    out = np.empty_like(v)
    out[...,0] = c*v[...,0] - s*v[...,1]
    out[...,1] = s*v[...,0] + c*v[...,1]
    out[...,2] = v[...,2]
    return out

# ============================================================
# FUR ROOTS + TIMELINE DRIVERS
# ============================================================

def fibonacci_sphere(n):
    pts = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n):
        y = 1.0 - (2.0 * i / max(n - 1, 1))
        r = math.sqrt(max(0.0, 1.0 - y*y))
        a = golden * i
        pts.append((math.cos(a)*r, y, math.sin(a)*r))
    return np.asarray(pts, dtype=np.float64)

ROOT_NORMALS = fibonacci_sphere(STRAND_COUNT)
LOCAL_ROOTS = ROOT_NORMALS * BODY_RADIUS

def source_position_local(frame):
    t = (frame - FRAME_START) / (FRAME_END - FRAME_START)

    if frame < SHOCK_START:
        a = 2.0*math.pi*(1.25*t)
        r = 3.10 + 0.34*math.sin(4.0*math.pi*t)
        return np.array((r*math.cos(a), r*math.sin(a), 0.82*math.sin(2.0*a)), dtype=np.float64)

    # During shock phase, the source moves closer for a stronger disturbance.
    t2 = (frame - SHOCK_START) / max(SHOCK_END - SHOCK_START, 1)
    a = 2.0*math.pi*(1.25*t)
    r = 2.15 - 0.20*math.sin(math.pi*t2)
    return np.array((r*math.cos(a), r*math.sin(a), 0.55*math.sin(2.0*a)), dtype=np.float64)

def collider_position_local(frame):
    t = (frame - FRAME_START) / (FRAME_END - FRAME_START)
    x = -3.10 + 6.20*t
    y = -0.55 + 0.92*math.sin(2.0*math.pi*t)
    z = 0.42*math.sin(math.pi*t)
    return np.array((x, y, z), dtype=np.float64)

def pulse_gain(frame):
    x = (frame - PULSE_CENTER_FRAME) / PULSE_SIGMA
    return 1.0 + PULSE_GAIN * math.exp(-0.5*x*x)

def shock_ring_radius(frame):
    if frame < SHOCK_START:
        return 0.0
    return max(0.0, (frame - SHOCK_START) * SHOCK_WAVE_SPEED)

# ============================================================
# CUSTOM STRAND SOLVER
# ============================================================

def initial_strands():
    pos = np.zeros((STRAND_COUNT, SEGMENTS, 3), dtype=np.float64)
    for j in range(SEGMENTS):
        pos[:,j,:] = LOCAL_ROOTS + ROOT_NORMALS*(SEG_LEN*j)
    return pos

def solve_constraints(new, collider_local):
    for _ in range(CONSTRAINT_ITERS):
        new[:,0,:] = LOCAL_ROOTS

        for j in range(1, SEGMENTS):
            d = new[:,j,:] - new[:,j-1,:]
            L = np.linalg.norm(d, axis=1, keepdims=True)
            L = np.maximum(L, 1e-9)
            correction = d*(1.0 - SEG_LEN/L)

            if j == 1:
                new[:,j,:] -= correction
            else:
                new[:,j-1,:] += 0.5*correction
                new[:,j,:]   -= 0.5*correction

        free = new[:,1:,:]

        # Body collision.
        rr = np.linalg.norm(free, axis=-1, keepdims=True)
        inside = rr < BODY_RADIUS
        projected = free / np.maximum(rr, 1e-9) * BODY_RADIUS
        free[:] = np.where(inside, projected, free)

        # Collider collision.
        rel = free - collider_local[None,None,:]
        cr = np.linalg.norm(rel, axis=-1, keepdims=True)
        inside_c = cr < COLLIDER_RADIUS
        projected_c = collider_local[None,None,:] + rel / np.maximum(cr, 1e-9) * COLLIDER_RADIUS
        free[:] = np.where(inside_c, projected_c, free)

    return new

def simulate_pair(axis, grad_grid):
    left_pos = initial_strands()
    left_prev = left_pos.copy()

    right_pos = initial_strands()
    right_prev = right_pos.copy()

    nframes = FRAME_END - FRAME_START + 1
    left_states = np.zeros((nframes, STRAND_COUNT, SEGMENTS, 3), dtype=np.float32)
    right_states = np.zeros_like(left_states)

    left_states[0] = left_pos
    right_states[0] = right_pos

    dt = 1.0 / FPS

    print("Simulating fur systems...")
    for out_i, frame in enumerate(range(FRAME_START+1, FRAME_END+1), start=1):
        collider = collider_position_local(frame)

        # LEFT = control / gravity only.
        vel = (left_pos - left_prev) * DAMPING
        new = left_pos + vel
        left_prev[:] = left_pos
        new[:,1:,:] += GRAVITY[None,None,:] * (dt*dt*5.0)
        new = solve_constraints(new, collider)
        left_pos[:] = new

        # RIGHT = gravity + QFG + shock-wave.
        vel = (right_pos - right_prev) * DAMPING
        new = right_pos + vel
        right_prev[:] = right_pos

        source = source_position_local(frame)
        qpts = new[:,1:,:] - source[None,None,:]
        qgrad = trilerp_vector(qpts, axis, grad_grid)

        t = (frame - FRAME_START) / (FRAME_END - FRAME_START)
        rot_angle = 2.0*math.pi*FIELD_ROTATION_TURNS*t
        qgrad = rotate_z_vectors(qgrad, rot_angle)

        mag = np.linalg.norm(qgrad, axis=-1, keepdims=True)
        qforce = qgrad / (1.0 + 0.75*mag)

        gain = pulse_gain(frame)

        # Shock wave = radial sweep from local center.
        rel = new[:,1:,:] - SHOCK_CENTER_LOCAL[None,None,:]
        rr = np.linalg.norm(rel, axis=-1, keepdims=True)
        rr_safe = np.maximum(rr, 1e-9)
        shock_normal = rel / rr_safe
        ring_r = shock_ring_radius(frame)
        if frame >= SHOCK_START:
            envelope = np.exp(-0.5*((rr - ring_r)/SHOCK_WAVE_WIDTH)**2)
            shock_force = SHOCK_WAVE_GAIN * envelope * shock_normal
        else:
            shock_force = np.zeros_like(rel)

        accel = (
            GRAVITY[None,None,:]
            + (BASE_QFG_FORCE_SCALE*gain)*qforce
            + shock_force
        )

        new[:,1:,:] += accel * (dt*dt*5.0)
        new = solve_constraints(new, collider)
        right_pos[:] = new

        left_states[out_i] = left_pos.astype(np.float32)
        right_states[out_i] = right_pos.astype(np.float32)

        if out_i % 72 == 0:
            print(f"  frame {frame}/{FRAME_END}")

    print("Fur simulation complete.")
    return left_states, right_states

# ============================================================
# CURVES + HANDLER
# ============================================================

LEFT_SPLINES = []
RIGHT_SPLINES = []
LEFT_STATES = None
RIGHT_STATES = None

def build_curve_object(name, initial, material, location):
    curve = bpy.data.curves.new(name+"_CurveData", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = HAIR_RADIUS
    curve.bevel_resolution = 2
    curve.resolution_u = 1

    splines = []
    for i in range(STRAND_COUNT):
        spl = curve.splines.new("POLY")
        spl.points.add(SEGMENTS-1)
        for j in range(SEGMENTS):
            p = initial[i,j]
            spl.points[j].co = (*p, 1.0)
        splines.append(spl)

    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    curve.materials.append(material)
    return obj, splines

def update_splines(splines, state):
    for i, spl in enumerate(splines):
        for j, p in enumerate(state[i]):
            spl.points[j].co = (float(p[0]), float(p[1]), float(p[2]), 1.0)

def qfg_fur_v3_handler(scene):
    if LEFT_STATES is None or RIGHT_STATES is None:
        return
    idx = max(0, min(scene.frame_current - FRAME_START, LEFT_STATES.shape[0]-1))
    update_splines(LEFT_SPLINES, LEFT_STATES[idx])
    update_splines(RIGHT_SPLINES, RIGHT_STATES[idx])

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "qfg_fur_v3_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(qfg_fur_v3_handler)

# ============================================================
# VISUAL EXTRAS
# ============================================================

def build_field_cloud(axis, density):
    parent = bpy.data.objects.new("QFG_Field_Cloud", None)
    bpy.context.collection.objects.link(parent)
    parent.location = RIGHT_CENTER

    vmax = float(np.max(density))
    threshold = float(np.quantile(density, 0.945))
    count = 0

    for i in range(0, len(axis), 2):
        for j in range(0, len(axis), 2):
            for k in range(0, len(axis), 2):
                val = float(density[i,j,k])
                if val < threshold or count >= 210:
                    continue
                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=1,
                    radius=0.022 + 0.055*min(1.0, val/max(vmax, 1e-9)),
                    location=(float(axis[i]), float(axis[j]), float(axis[k]))
                )
                o = bpy.context.object
                o.name = f"FieldPoint_{count:03d}"
                o.parent = parent
                o.data.materials.append(MAT_FIELD)
                count += 1

    parent.scale = (0.70, 0.70, 0.70)

    for f in range(FRAME_START, FRAME_END+1, 12):
        p = source_position_local(f)
        parent.location = RIGHT_CENTER + p
        t = (f - FRAME_START) / (FRAME_END - FRAME_START)
        parent.rotation_euler = (0, 0, 2.0*math.pi*FIELD_ROTATION_TURNS*t)

        s = 0.70
        if abs(f - PULSE_CENTER_FRAME) < 45:
            g = pulse_gain(f)
            s = 0.70 * (1.0 + 0.05*(g-1.0))
        parent.scale = (s,s,s)

        parent.keyframe_insert("location", frame=f)
        parent.keyframe_insert("rotation_euler", frame=f)
        parent.keyframe_insert("scale", frame=f)

    return parent

def build_colliders():
    left = add_sphere("Collider_Left", LEFT_CENTER + collider_position_local(FRAME_START),
                      COLLIDER_RADIUS, MAT_COLLIDER)
    right = add_sphere("Collider_Right", RIGHT_CENTER + collider_position_local(FRAME_START),
                       COLLIDER_RADIUS, MAT_COLLIDER)

    for f in range(FRAME_START, FRAME_END+1, 12):
        lp = collider_position_local(f)
        left.location = LEFT_CENTER + lp
        right.location = RIGHT_CENTER + lp
        left.keyframe_insert("location", frame=f)
        right.keyframe_insert("location", frame=f)
    return left, right

def build_shock_ring():
    ring = add_torus("ShockRing", RIGHT_CENTER, 0.01, 0.035, MAT_RING)
    ring.scale = (1.0, 1.0, 1.0)
    ring.hide_render = True
    ring.hide_viewport = True
    ring.keyframe_insert("hide_render", frame=SHOCK_START-2)
    ring.keyframe_insert("hide_viewport", frame=SHOCK_START-2)
    ring.hide_render = False
    ring.hide_viewport = False
    ring.keyframe_insert("hide_render", frame=SHOCK_START)
    ring.keyframe_insert("hide_viewport", frame=SHOCK_START)

    for f in range(SHOCK_START, SHOCK_END+1, 6):
        rr = max(0.01, shock_ring_radius(f))
        ring.location = tuple(RIGHT_CENTER + SHOCK_CENTER_LOCAL)
        ring.scale = (rr, rr, 1.0)
        ring.keyframe_insert("location", frame=f)
        ring.keyframe_insert("scale", frame=f)

    ring.keyframe_insert("hide_render", frame=SHOCK_END)
    ring.keyframe_insert("hide_viewport", frame=SHOCK_END)
    ring.hide_render = True
    ring.hide_viewport = True
    ring.keyframe_insert("hide_render", frame=SHOCK_END+2)
    ring.keyframe_insert("hide_viewport", frame=SHOCK_END+2)
    return ring

def build_tip_markers(states, center, prefix, material, step=8):
    # Sparse markers to make strand-tip wavefront motion readable.
    objs = []
    tips = states[0,:,SEGMENTS-1,:]
    for i in range(0, STRAND_COUNT, step):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.032, location=tuple(center + tips[i]))
        o = bpy.context.object
        o.name = f"{prefix}_Tip_{i:03d}"
        o.data.materials.append(material)
        objs.append((o, i))

    for f in range(FRAME_START, FRAME_END+1, 4):
        idx = f - FRAME_START
        idx = max(0, min(idx, states.shape[0]-1))
        tips = states[idx,:,SEGMENTS-1,:]
        for o, i in objs:
            o.location = tuple(center + tips[i])
            o.keyframe_insert("location", frame=f)

    return [o for o, _ in objs]

# ============================================================
# SCENE + CAMERA
# ============================================================

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

    # Bodies
    add_sphere("Body_Left", LEFT_CENTER, BODY_RADIUS, MAT_LEFT_BODY)
    add_sphere("Body_Right", RIGHT_CENTER, BODY_RADIUS, MAT_RIGHT_BODY)

    # Floor
    add_cube("Floor", (0,0,-3.35), (10.0,7.5,0.07), MAT_BG)

    # Split divider
    add_cube("Divider", (0,0,0), (0.018,0.12,3.8), MAT_ORANGE)

    # Soft background side plates for readability
    add_cube("Plate_Left",  (-3.6, 0, 0.0), (2.6,0.02,3.4), MAT_DIM)
    add_cube("Plate_Right", ( 3.6, 0, 0.0), (2.6,0.02,3.4), MAT_DIM)

    # Labels
    add_text("MainTitle", "QFG FUR DYNAMICS // v3", (0,0,4.25), 0.50, MAT_TEXT)
    add_text("LeftLabel",  "CONTROL  //  GRAVITY + COLLISION", tuple(LEFT_CENTER  + np.array((0,0,3.28))), 0.22, MAT_TEXT)
    add_text("RightLabel", "QFG  //  FIELD + SHOCK + COLLISION", tuple(RIGHT_CENTER + np.array((0,0,3.28))), 0.22, MAT_FIELD)

    add_text(
        "Status",
        "QFG field = numerical runtime    |    fur motion = custom visualization solver",
        (0,0,-3.78), 0.17, MAT_ORANGE
    )

    # Phase callouts
    orbit = add_text("OrbitLabel", "ORBIT + VORTEX PHASE", tuple(RIGHT_CENTER + np.array((0,0,-2.95))), 0.20, MAT_FIELD)
    pulse = add_text("PulseLabel", "QFG DRIVE PULSE", tuple(RIGHT_CENTER + np.array((0,0,-2.95))), 0.20, MAT_ORANGE)
    shock = add_text("ShockLabel", "SHOCK-WAVE SWEEP", tuple(RIGHT_CENTER + np.array((0,0,-2.95))), 0.20, MAT_ORANGE)

    def visible_range(obj, start, end):
        obj.hide_render = True
        obj.hide_viewport = True
        obj.keyframe_insert("hide_render", frame=max(FRAME_START, start-2))
        obj.keyframe_insert("hide_viewport", frame=max(FRAME_START, start-2))
        obj.hide_render = False
        obj.hide_viewport = False
        obj.keyframe_insert("hide_render", frame=start)
        obj.keyframe_insert("hide_viewport", frame=start)
        obj.keyframe_insert("hide_render", frame=end)
        obj.keyframe_insert("hide_viewport", frame=end)
        obj.hide_render = True
        obj.hide_viewport = True
        obj.keyframe_insert("hide_render", frame=min(FRAME_END, end+2))
        obj.keyframe_insert("hide_viewport", frame=min(FRAME_END, end+2))

    visible_range(orbit, FRAME_START, 220)
    visible_range(pulse, 220, 282)
    visible_range(shock, SHOCK_START, SHOCK_END+10)

    # Camera
    bpy.ops.object.camera_add(location=(0,-16.0,5.8))
    cam = bpy.context.object
    cam.name = "QFG_Fur_v3_Camera"
    sc.camera = cam
    cam.data.lens = 56
    look_at(cam, (0,0,0.2))

    # Wider, then progressive move toward right-side close-up during shock.
    keys = [
        (1,   (0.0,-16.0,5.8), (0.0,0.0,0.2), 58),
        (110, (-0.8,-14.2,4.8), (0.0,0.0,0.1), 54),
        (220, (1.1,-12.7,4.1), (1.3,0.0,0.0), 52),
        (285, (2.4,-10.2,3.4), (3.6,0.0,0.1), 58),
        (330, (4.6,-8.1,2.7), (3.6,0.0,0.1), 68),
        (382, (3.6,-7.6,2.4), (3.6,0.0,0.05), 72),
        (450, (1.0,-12.8,4.4), (1.0,0.0,0.1), 54),
        (576, (0.0,-16.4,6.0), (0.0,0.0,0.2), 58),
    ]
    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    # Lights
    bpy.ops.object.light_add(type="AREA", location=(-5,-5,7))
    key = bpy.context.object
    key.data.energy = 1250
    key.data.size = 5.6
    key.data.color = (0.12,0.38,1.0)
    look_at(key, (0,0,0))

    bpy.ops.object.light_add(type="AREA", location=(5,-1,6.5))
    fill = bpy.context.object
    fill.data.energy = 980
    fill.data.size = 5.1
    fill.data.color = (0.55,0.10,1.0)
    look_at(fill, (0,0,0))

    bpy.ops.object.light_add(type="POINT", location=(0,-3,2.5))
    rim = bpy.context.object
    rim.data.energy = 540
    rim.data.color = (0.05,0.85,1.0)

    return sc

def configure_output(sc):
    absdir = bpy.path.abspath(OUTPUT_DIR)
    os.makedirs(absdir, exist_ok=True)
    sc.render.filepath = os.path.join(absdir, OUTPUT_FILE)
    sc.render.use_file_extension = True

    img = sc.render.image_settings
    if hasattr(img, "media_type"):
        try:
            img.media_type = "VIDEO"
        except Exception:
            pass
    else:
        try:
            img.file_format = "FFMPEG"
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

print("\\n================================================")
print(" QFG FUR DYNAMICS DEMO v3")
print("================================================\\n")

clear_scene()
init_materials()
scene = setup_scene()

print("[1/4] Creating QFG field...")
world = build_qfg_world()
axis, grad_grid, density_grid = cache_qfg_field(world)

print("[2/4] Simulating fur comparison...")
LEFT_STATES, RIGHT_STATES = simulate_pair(axis, grad_grid)

print("[3/4] Building curves and visuals...")
left_obj, LEFT_SPLINES = build_curve_object("Fur_Left", LEFT_STATES[0], MAT_LEFT_HAIR, LEFT_CENTER)
right_obj, RIGHT_SPLINES = build_curve_object("Fur_Right", RIGHT_STATES[0], MAT_RIGHT_HAIR, RIGHT_CENTER)

install_handler()
build_field_cloud(axis, density_grid)
build_colliders()
build_shock_ring()
build_tip_markers(RIGHT_STATES, RIGHT_CENTER, "Right", MAT_ORANGE, step=10)

scene["demo"] = "QFG Fur Dynamics v3"
scene["qfg_namespace"] = QFG_ROOT
scene["qfg_grid"] = QFG_GRID
scene["qfg_dt"] = QFG_DT
scene["qfg_steps"] = QFG_STEPS
scene["strand_count"] = STRAND_COUNT
scene["segments_per_strand"] = SEGMENTS
scene["fur_solver"] = "custom Verlet + distance constraints"
scene["left_case"] = "gravity + collision"
scene["right_case"] = "gravity + collision + sampled QFG density gradient + shock sweep"
scene["scientific_status"] = "QFG field numerical; fur mechanics is a visualization/demo solver"

print("[4/4] Saving scene...")
configure_output(scene)
blend_path = bpy.path.abspath(BLEND_FILE)
os.makedirs(os.path.dirname(blend_path), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
qfg_fur_v3_handler(scene)

print("\\nDONE")
print("QFG namespace:", QFG_ROOT)
print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Frames:", FRAME_START, "..", FRAME_END, "@", FPS, "fps")
print("Features: split-screen, orbit phase, pulse phase, shock-wave sweep, right-side close-up")
print("\\nSPACE = preview")
print("Ctrl+F12 = Render Animation")
print("Set RES_PERCENT=100 for final quality.\\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
