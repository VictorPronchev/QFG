# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Phase Transition / Thermal Matter Lab v2 AAA - Blender 5.2+
#
# AAA cinematic version:
#   - QFG ice cube voxel simulation
#   - QFG thermal melt / puddle behavior
#   - laser-like heat beam
#   - dark lab presentation
#   - render-ready setup
#
# SCIENTIFIC STATUS
# -----------------
# thermal / matter evolution = numerical simulation layer
# cinematic ice / laser / lab visuals = presentation layer
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_PHASE_TRANSITION_V2_AAA/
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
RES_PERCENT = 60
AUTO_RENDER = False

OUTPUT_DIR_NAME = "QFG_PHASE_TRANSITION_V2_AAA"
OUTPUT_FILE = "QFG_Phase_Transition_Thermal_Matter_Lab_v2_AAA"

NX = 30
NY = 30
NZ = 30

WORLD_SCALE = 0.22
FLOOR_K = 3

GRAVITY_STRENGTH = 0.23
HEAT_DIFFUSION = 0.085
COOLING_RATE = 0.003
MELTING_POINT = 0.30

HEAT_START_FRAME = 42
HEAT_END_FRAME = 162
HEAT_RADIUS = 5
HEAT_POWER = 0.34

MAX_SOLID_POINTS = 1500
MAX_HOT_POINTS = 1500
SOLID_THRESHOLD = 0.10
HOT_THRESHOLD = 0.10

SOLID_FRAMES = []
HOT_FRAMES = []
SOLID_OBJ = None
HOT_OBJ = None
LASER_CORE = None
LASER_GLOW = None
LASER_SOURCE = None
IMPACT_GLOW = None

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
    out.location = (300,0)
    emission = nodes.new("ShaderNodeEmission")
    emission.location = (0,0)
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = strength
    if alpha < 0.999:
        transp = nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (0,-180)
        mix = nodes.new("ShaderNodeMixShader")
        mix.location = (150,0)
        mix.inputs[0].default_value = 1.0 - alpha
        links.new(transp.outputs[0], mix.inputs[1])
        links.new(emission.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs[0])
        safe_set_attr(mat, "blend_method", "BLEND")
        safe_set_attr(mat, "shadow_method", "NONE")
    else:
        links.new(emission.outputs[0], out.inputs[0])
    return mat

def mat_metal(name, color=(0.12,0.14,0.2), metallic=0.7, roughness=0.25):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300,0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0,0)
    bsdf.inputs["Base Color"].default_value = (*color,1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    links.new(bsdf.outputs[0], out.inputs[0])
    return mat

def mat_dark_surface(name, color=(0.02,0.024,0.035), roughness=0.22, metallic=0.15):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300,0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0,0)
    bsdf.inputs["Base Color"].default_value = (*color,1)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    links.new(bsdf.outputs[0], out.inputs[0])
    return mat

def mat_ice(name):
    # Ice-like glossy/transmissive shader
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (550,0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (200,0)
    principled.inputs["Base Color"].default_value = (0.78,0.92,1.0,1.0)
    principled.inputs["Roughness"].default_value = 0.05
    if "Transmission Weight" in principled.inputs:
        principled.inputs["Transmission Weight"].default_value = 1.0
    elif "Transmission" in principled.inputs:
        principled.inputs["Transmission"].default_value = 1.0
    principled.inputs["IOR"].default_value = 1.31

    volume_abs = nodes.new("ShaderNodeVolumeAbsorption")
    volume_abs.location = (220,-210)
    volume_abs.inputs["Color"].default_value = (0.72,0.92,1.0,1.0)
    volume_abs.inputs["Density"].default_value = 0.08

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-40,160)
    bump.inputs["Strength"].default_value = 0.03
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-280,160)
    noise.inputs["Scale"].default_value = 8.0
    noise.inputs["Detail"].default_value = 8.0
    noise.inputs["Roughness"].default_value = 0.45

    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])
    links.new(principled.outputs[0], out.inputs["Surface"])
    links.new(volume_abs.outputs[0], out.inputs["Volume"])
    return mat

def mat_hot_liquid(name):
    mat, nodes, links = make_material(name)
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (520,0)

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (180,80)
    principled.inputs["Base Color"].default_value = (1.0,0.28,0.05,1)
    principled.inputs["Roughness"].default_value = 0.12
    principled.inputs["Metallic"].default_value = 0.0
    if "Emission Color" in principled.inputs:
        principled.inputs["Emission Color"].default_value = (1.0,0.34,0.08,1)
    elif "Emission" in principled.inputs:
        principled.inputs["Emission"].default_value = (1.0,0.34,0.08,1)
    if "Emission Strength" in principled.inputs:
        principled.inputs["Emission Strength"].default_value = 2.6

    volume = nodes.new("ShaderNodeVolumeAbsorption")
    volume.location = (180,-170)
    volume.inputs["Color"].default_value = (1.0,0.22,0.04,1)
    volume.inputs["Density"].default_value = 0.20

    links.new(principled.outputs[0], out.inputs["Surface"])
    links.new(volume.outputs[0], out.inputs["Volume"])
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

def add_plane(name, loc=(0,0,0), size=2.0, material=None):
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc)
    o = bpy.context.object
    o.name = name
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

def add_cylinder_between(name, start, end, radius, material=None):
    start = Vector(start)
    end = Vector(end)
    vec = end - start
    length = vec.length
    mid = (start + end) * 0.5

    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=radius, depth=length, location=mid)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = vec.to_track_quat("Z", "Y").to_euler()
    if material:
        o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o

def look_at(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

# ============================================================
# MATERIALS
# ============================================================

MAT_ICE      = mat_ice("QFG_Ice")
MAT_HOT      = mat_hot_liquid("QFG_HotLiquid")
MAT_FRAME    = mat_metal("QFG_Frame", (0.10,0.14,0.20), metallic=0.72, roughness=0.18)
MAT_TEXT     = mat_emissive("QFG_Text", (0.93,0.97,1.0), 1.1)
MAT_ORANGE   = mat_emissive("QFG_Orange", (1.0,0.32,0.08), 2.2)
MAT_FLOOR    = mat_dark_surface("QFG_Floor", (0.018,0.022,0.032), roughness=0.16, metallic=0.20)
MAT_WALL     = mat_dark_surface("QFG_Wall", (0.010,0.014,0.024), roughness=0.70, metallic=0.0)
MAT_LASER    = mat_emissive("QFG_LaserCore", (1.0,0.08,0.55), 8.5, alpha=0.92)
MAT_LASER_G  = mat_emissive("QFG_LaserGlow", (1.0,0.16,0.75), 2.2, alpha=0.18)
MAT_SOURCE   = mat_emissive("QFG_LaserSource", (1.0,0.15,0.72), 12.0)
MAT_IMPACT   = mat_emissive("QFG_ImpactGlow", (1.0,0.35,0.08), 9.0, alpha=0.70)

# ============================================================
# NUMERICAL MODEL
# ============================================================

def init_fields():
    psi = np.zeros((NX, NY, NZ), dtype=np.float32)
    temp = np.zeros_like(psi)

    size = 12
    sx = NX//2 - size//2
    sy = NY//2 - size//2
    sz = FLOOR_K + 7
    psi[sx:sx+size, sy:sy+size, sz:sz+size] = 1.0
    return psi, temp

def diffuse_temperature(temp):
    lap = (
        np.roll(temp, 1, 0) + np.roll(temp, -1, 0) +
        np.roll(temp, 1, 1) + np.roll(temp, -1, 1) +
        np.roll(temp, 1, 2) + np.roll(temp, -1, 2) -
        6.0 * temp
    )
    out = temp + HEAT_DIFFUSION * lap - COOLING_RATE * temp
    return np.clip(out, 0.0, 3.0)

def inject_heat(temp, frame):
    if not (HEAT_START_FRAME <= frame <= HEAT_END_FRAME):
        return

    tx = NX//2
    ty = NY//2
    tz = FLOOR_K + 11

    for z in range(tz-HEAT_RADIUS, tz+HEAT_RADIUS+1):
        for y in range(ty-HEAT_RADIUS, ty+HEAT_RADIUS+1):
            for x in range(tx-HEAT_RADIUS, tx+HEAT_RADIUS+1):
                if 0 <= x < NX and 0 <= y < NY and 0 <= z < NZ:
                    d = math.sqrt((x-tx)**2 + (y-ty)**2 + (z-tz)**2)
                    if d <= HEAT_RADIUS:
                        temp[x,y,z] += HEAT_POWER * (1.0 - d/(HEAT_RADIUS+1e-6))

def matter_step(psi, temp):
    out = np.zeros_like(psi)

    for z in range(NZ):
        for y in range(NY):
            for x in range(NX):
                amount = float(psi[x,y,z])
                if amount <= 0.001:
                    continue

                heat = float(temp[x,y,z])

                if heat < MELTING_POINT:
                    out[x,y,z] += amount
                    continue

                remaining = amount

                if z > FLOOR_K:
                    down_cap = max(0.0, 1.0 - out[x,y,z-1])
                    flow_down = min(remaining * GRAVITY_STRENGTH, down_cap)
                    out[x,y,z-1] += flow_down
                    remaining -= flow_down

                heat_factor = min(1.0, max(0.0, (heat - MELTING_POINT) / 0.9))
                spread_fraction = 0.05 + 0.18 * heat_factor

                candidates = []
                if x+1 < NX: candidates.append((x+1,y,z))
                if x-1 >= 0: candidates.append((x-1,y,z))
                if y+1 < NY: candidates.append((x,y+1,z))
                if y-1 >= 0: candidates.append((x,y-1,z))

                if remaining > 0.0 and candidates:
                    budget = remaining * spread_fraction
                    share = budget / len(candidates)
                    moved = 0.0
                    for nx,ny,nz in candidates:
                        cap = max(0.0, 1.0 - out[nx,ny,nz])
                        f = min(share, cap)
                        out[nx,ny,nz] += f
                        moved += f
                    remaining -= moved

                out[x,y,z] += remaining

    return np.clip(out, 0.0, 1.0)

def collect_points(psi, temp):
    center = np.array([NX/2.0, NY/2.0, NZ/2.0], dtype=np.float32)

    matter_mask = psi > SOLID_THRESHOLD
    coords = np.argwhere(matter_mask)

    solid_pts = np.zeros((0,3), dtype=np.float32)
    hot_pts = np.zeros((0,3), dtype=np.float32)

    if len(coords):
        vals_temp = temp[matter_mask]
        solid_sel = coords[vals_temp < MELTING_POINT]
        hot_sel = coords[vals_temp >= MELTING_POINT]

        if len(solid_sel) > MAX_SOLID_POINTS:
            step = max(1, len(solid_sel)//MAX_SOLID_POINTS)
            solid_sel = solid_sel[::step][:MAX_SOLID_POINTS]
        if len(hot_sel) > MAX_HOT_POINTS:
            step = max(1, len(hot_sel)//MAX_HOT_POINTS)
            hot_sel = hot_sel[::step][:MAX_HOT_POINTS]

        if len(solid_sel):
            solid_pts = (solid_sel.astype(np.float32)-center)*WORLD_SCALE
        if len(hot_sel):
            hot_pts = (hot_sel.astype(np.float32)-center)*WORLD_SCALE

    return solid_pts, hot_pts

def run_simulation():
    psi, temp = init_fields()
    solid_frames = []
    hot_frames = []

    print("Running QFG AAA thermal melt simulation...")
    for frame in range(FRAME_START, FRAME_END+1):
        inject_heat(temp, frame)
        for _ in range(2):
            temp = diffuse_temperature(temp)
        psi = matter_step(psi, temp)
        solid, hot = collect_points(psi, temp)
        solid_frames.append(solid)
        hot_frames.append(hot)
        if frame % 40 == 0:
            print(f"  simulated frame {frame}/{FRAME_END}")
    print("Simulation complete.")
    return solid_frames, hot_frames

# ============================================================
# POINT-CLOUD VISUALIZATION
# ============================================================

def make_points_mesh(name, points):
    mesh = bpy.data.meshes.new(name+"_Mesh")
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
    ng = bpy.data.node_groups.new(points_obj.name+"_GN", "GeometryNodeTree")
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

    gi.location = (-700,0)
    m2p.location = (-420,0)
    oi.location = (-420,-180)
    inst.location = (-120,0)
    real.location = (140,0)
    go.location = (380,0)

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
    mesh.from_pydata([tuple(map(float,p)) for p in points], [], [])
    mesh.update()

def phase_handler(scene):
    idx = max(0, min(scene.frame_current - FRAME_START, len(SOLID_FRAMES)-1))

    if SOLID_OBJ is not None:
        update_points_object(SOLID_OBJ, SOLID_FRAMES[idx])
    if HOT_OBJ is not None:
        update_points_object(HOT_OBJ, HOT_FRAMES[idx])

    active = HEAT_START_FRAME <= scene.frame_current <= HEAT_END_FRAME
    vis = not active
    if LASER_CORE:
        LASER_CORE.hide_viewport = vis
        LASER_CORE.hide_render = vis
    if LASER_GLOW:
        LASER_GLOW.hide_viewport = vis
        LASER_GLOW.hide_render = vis
    if LASER_SOURCE:
        LASER_SOURCE.hide_viewport = vis
        LASER_SOURCE.hide_render = vis
    if IMPACT_GLOW:
        IMPACT_GLOW.hide_viewport = vis
        IMPACT_GLOW.hide_render = vis

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "phase_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(phase_handler)

# ============================================================
# SCENE / RENDER
# ============================================================

def world_floor_z():
    return (FLOOR_K - NZ/2.0) * WORLD_SCALE

def build_lab_chamber():
    # Base table
    add_cube("LabTable", (0,0,world_floor_z()-0.16), (4.4, 4.4, 0.16), MAT_FLOOR)
    # Back wall
    wall = add_cube("BackWall", (0,3.85,1.15), (4.4,0.10,2.55), MAT_WALL)
    # Side hints
    add_cube("LeftWall", (-4.28,0,1.15), (0.10,3.8,2.55), MAT_WALL)
    add_cube("RightWall", (4.28,0,1.15), (0.10,3.8,2.55), MAT_WALL)

    # Chamber wire volume
    bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
    frame = bpy.context.object
    frame.name = "QFGChamber"
    frame.scale = (NX*WORLD_SCALE/2, NY*WORLD_SCALE/2, NZ*WORLD_SCALE/2)
    frame.data.materials.append(MAT_FRAME)
    wire = frame.modifiers.new("Wireframe", "WIREFRAME")
    wire.thickness = 0.018
    wire.use_replace = True
    wire.use_even_offset = True
    return frame

def add_laser():
    global LASER_CORE, LASER_GLOW, LASER_SOURCE, IMPACT_GLOW

    laser_start = (0, -5.15, 4.55)
    laser_end   = (0,  0.0, -0.15)

    LASER_GLOW = add_cylinder_between("QFGLaserGlow", laser_start, laser_end, 0.10, MAT_LASER_G)
    LASER_CORE = add_cylinder_between("QFGLaserCore", laser_start, laser_end, 0.032, MAT_LASER)
    LASER_SOURCE = add_uv_sphere("QFGLaserSource", laser_start, 0.17, MAT_SOURCE)
    IMPACT_GLOW = add_uv_sphere("QFGImpactGlow", laser_end, 0.13, MAT_IMPACT)

    for obj in (LASER_CORE, LASER_GLOW, LASER_SOURCE, IMPACT_GLOW):
        obj.hide_viewport = True
        obj.hide_render = True

def setup_scene():
    sc = bpy.context.scene
    sc.frame_start = FRAME_START
    sc.frame_end = FRAME_END
    sc.render.fps = FPS
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.resolution_percentage = RES_PERCENT

    # Renderer
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
        safe_set_attr(sc.cycles, "transmission_bounces", 8)
        safe_set_attr(sc.cycles, "volume_bounces", 2)
    elif "BLENDER_EEVEE_NEXT" in ids:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in ids:
        sc.render.engine = "BLENDER_EEVEE"

    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass

    sc.world.color = (0.001, 0.002, 0.006)

    # Environment
    build_lab_chamber()

    add_text("Title", "QFG PHASE TRANSITION / THERMAL MATTER LAB", (0,0,4.58), 0.40, MAT_TEXT)
    add_text("Subtitle", "AAA QFG Demo // Ice cube → laser heating → melt → puddle", (0,0,4.05), 0.18, MAT_ORANGE)
    add_text("Status", "thermal / matter evolution = numerical simulation   |   cinematic ice / laser = presentation layer", (0,0,-4.42), 0.155, MAT_TEXT)

    add_laser()

    # Camera
    bpy.ops.object.camera_add(location=(0,-12.2,4.9))
    cam = bpy.context.object
    cam.name = "QFGCamera"
    sc.camera = cam
    cam.data.lens = 80
    safe_set_attr(cam.data, "dof", cam.data.dof)
    try:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = 10.0
        cam.data.dof.aperture_fstop = 2.2
    except Exception:
        pass
    look_at(cam, (0,0,0.4))

    keys = [
        (1,   (0.0,-12.2,4.9), (0,0,0.4), 80),
        (46,  (-0.8,-10.8,4.3), (0,0,0.5), 72),
        (92,  (1.2,-9.4,3.8), (0,0,0.0), 70),
        (138, (2.4,-7.9,2.6), (0,0,-0.2), 85),
        (190, (0.6,-9.6,3.5), (0,0,-0.35), 76),
        (240, (0.0,-12.4,5.1), (0,0,0.2), 82),
    ]
    for f, loc, tgt, lens in keys:
        cam.location = loc
        look_at(cam, tgt)
        cam.data.lens = lens
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.keyframe_insert("lens", frame=f)

    # Lighting
    bpy.ops.object.light_add(type="AREA", location=(-6.2,-5.0,7.8))
    key = bpy.context.object
    key.data.energy = 2200
    key.data.size = 6.0
    key.data.color = (0.48,0.72,1.0)
    look_at(key, (0,0,0))

    bpy.ops.object.light_add(type="AREA", location=(4.7,-0.7,6.8))
    fill = bpy.context.object
    fill.data.energy = 1250
    fill.data.size = 5.0
    fill.data.color = (0.95,0.25,1.0)
    look_at(fill, (0,0,0))

    bpy.ops.object.light_add(type="AREA", location=(0,-6.8,4.3))
    rim = bpy.context.object
    rim.data.energy = 820
    rim.data.size = 3.0
    rim.data.color = (1.0,0.40,0.12)
    look_at(rim, (0,0,-0.1))

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

print("\n====================================================")
print(" QFG PHASE TRANSITION / THERMAL MATTER LAB v2 AAA")
print("====================================================\n")

clear_scene()
scene = setup_scene()

SOLID_FRAMES, HOT_FRAMES = run_simulation()

SOLID_OBJ = make_points_mesh("QFGSolidPoints", SOLID_FRAMES[0])
HOT_OBJ   = make_points_mesh("QFGHotPoints", HOT_FRAMES[0])

solid_instance = make_instance_object("QFGSolidInstance", 0.078, MAT_ICE)
hot_instance   = make_instance_object("QFGHotInstance",   0.095, MAT_HOT)

add_points_instancer(SOLID_OBJ, solid_instance)
add_points_instancer(HOT_OBJ, hot_instance)

scene["demo"] = "QFG Phase Transition / Thermal Matter Lab v2 AAA"
scene["grid"] = f"{NX}x{NY}x{NZ}"
scene["melting_point"] = MELTING_POINT
scene["scientific_status"] = "thermal/matter numerical evolution; cinematic AAA rendering layer"

install_handler()
configure_output(scene)

out = resolve_output_dir()
blend_path = os.path.join(out, "QFG_Phase_Transition_Thermal_Matter_Lab_v2_AAA.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
phase_handler(scene)

print("Blend:", blend_path)
print("Video:", scene.render.filepath)
print("Grid:", scene["grid"])
print("Preview: SPACE")
print("Render: Ctrl+F12")
print("Recommended: RES_PERCENT=100 for final export.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
