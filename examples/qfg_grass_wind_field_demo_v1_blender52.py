# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Grass / Wheat Field Demo v1 - Blender 5.2+
#
# LEFT  : conventional wind-driven grass
# RIGHT : same wind + sampled QFG density-gradient forcing
#
# QFGWorld supplies the numerical field.
# Grass bending is a custom visualization solver.
#
# SCIENTIFIC STATUS
# -----------------
# QFG field = numerical runtime
# grass mechanics = custom visualization model
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_GRASS_DEMO_V1/
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

OUTPUT_DIR_NAME = "QFG_GRASS_DEMO_V1"
OUTPUT_FILE = "QFG_Grass_Field_v1"

LEFT_CENTER  = np.array((-3.6, 0.0, 0.0), dtype=np.float64)
RIGHT_CENTER = np.array(( 3.6, 0.0, 0.0), dtype=np.float64)

GRID_X = 17
GRID_Y = 13
SPACING = 0.28
BLADE_SEGMENTS = 5
BLADE_HEIGHT = 1.45
BLADE_RADIUS = 0.018
BLADE_COUNT = GRID_X * GRID_Y

WIND_GAIN = 0.48
QFG_GAIN = 2.9
FIELD_ROTATION_TURNS = 1.2

PULSE_CENTER = 265
PULSE_SIGMA = 20.0
PULSE_GAIN = 2.1

QFG_GRID = 32
QFG_DOMAIN = 16.0
QFG_DT = 0.002
QFG_STEPS = 18
FIELD_CACHE_N = 23
FIELD_CACHE_HALF = 5.2

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
    out=[]
    for r in roots:
        if r and r not in out:
            out.append(r)
    return out

def load_sdk():
    errors={}
    for root in candidate_roots():
        try:
            sdk=importlib.import_module(root+".sdk")
            if all(hasattr(sdk,n) for n in ("create_world","EngineConfig","WorldConfig","ActorSpec")):
                print("QFG SDK:",sdk.__name__)
                return root,sdk
        except Exception as exc:
            errors[root]=repr(exc)
    raise RuntimeError("QFG Dynamics SDK not found.\n"+"\n".join(f"{k}: {v}" for k,v in errors.items()))

QFG_ROOT,SDK=load_sdk()
create_world=SDK.create_world
EngineConfig=SDK.EngineConfig
WorldConfig=SDK.WorldConfig
ActorSpec=SDK.ActorSpec

# ============================================================
# BLENDER HELPERS
# ============================================================

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def make_material(name,color,emission=0.0,roughness=0.4):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value=(*color,1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value=roughness
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value=(*color,1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value=(*color,1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value=emission
    return m

MAT_GRASS_LEFT  = make_material("GrassLeft",(0.16,0.36,0.08),0.05,0.58)
MAT_GRASS_RIGHT = make_material("GrassRight",(0.05,0.60,0.22),0.8,0.42)
MAT_FIELD       = make_material("Field",(0.52,0.08,1.00),3.0,0.22)
MAT_TEXT        = make_material("Text",(0.92,0.96,1.00),1.0,0.3)
MAT_ORANGE      = make_material("Orange",(1.00,0.24,0.03),3.0,0.22)
MAT_SOIL        = make_material("Soil",(0.07,0.04,0.02),0.0,0.82)

def add_text(name,body,loc,size=0.28,material=None):
    c=bpy.data.curves.new(name+"_Curve","FONT")
    c.body=body
    c.align_x="CENTER"; c.align_y="CENTER"
    c.size=size; c.extrude=0.004
    o=bpy.data.objects.new(name,c)
    bpy.context.collection.objects.link(o)
    o.location=loc
    o.rotation_euler=(math.pi/2,0,0)
    if material: o.data.materials.append(material)
    return o

def add_cube(name,loc,scale,material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if material: o.data.materials.append(material)
    return o

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

# ============================================================
# QFG FIELD
# ============================================================

def build_qfg_world():
    ec=EngineConfig(
        grid_size=QFG_GRID,
        domain_length=QFG_DOMAIN,
        dt=QFG_DT,
        backend="NUMPY",
        field_mode="SCALAR",
        thermal_enabled=False,
        topology_enabled=True,
    )
    wc=WorldConfig(
        substeps=2,
        gravity=(0,0,0),
        floor_height=-1000.0,
        body_collisions=False,
        deterministic=True,
        seed=1337,
    )
    world=create_world(ec,wc)
    world.add_field_actor(ActorSpec(
        actor_type="GAUSSIAN",
        center=(0,0,0),
        radius=1.7,
        intensity=1.25,
        velocity=(0,0,0),
        name="GrassGaussian",
    ))
    world.add_field_actor(ActorSpec(
        actor_type="VORTEX",
        center=(0,0,0),
        radius=2.5,
        intensity=0.68,
        winding_m=1,
        velocity=(0,0,0),
        name="GrassVortex",
    ))
    world.step(QFG_STEPS)
    return world

def cache_field(world):
    axis=np.linspace(-FIELD_CACHE_HALF,FIELD_CACHE_HALF,FIELD_CACHE_N)
    grad=np.zeros((FIELD_CACHE_N,FIELD_CACHE_N,FIELD_CACHE_N,3),dtype=np.float32)
    density=np.zeros((FIELD_CACHE_N,FIELD_CACHE_N,FIELD_CACHE_N),dtype=np.float32)
    print("Sampling QFG field cache...")
    for i,x in enumerate(axis):
        for j,y in enumerate(axis):
            for k,z in enumerate(axis):
                s=world.sample_field((float(x),float(y),float(z)))
                grad[i,j,k]=np.asarray(s["density_gradient"],dtype=np.float32)
                density[i,j,k]=float(s["density"])
    return axis,grad,density

def trilerp_vector(points,axis,grid):
    pts=np.asarray(points,dtype=np.float64)
    n=len(axis); lo=float(axis[0]); hi=float(axis[-1]); h=(hi-lo)/(n-1)
    q=np.clip((pts-lo)/h,0,n-1-1e-8)
    i0=np.floor(q).astype(np.int32); f=q-i0; i1=np.minimum(i0+1,n-1)

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

def rotate_z(v,angle):
    c=math.cos(angle); s=math.sin(angle)
    out=np.empty_like(v)
    out[...,0]=c*v[...,0]-s*v[...,1]
    out[...,1]=s*v[...,0]+c*v[...,1]
    out[...,2]=v[...,2]
    return out

# ============================================================
# GRASS MODEL
# ============================================================

ROOTS=[]
for j in range(GRID_Y):
    for i in range(GRID_X):
        x=(i-(GRID_X-1)/2)*SPACING
        y=(j-(GRID_Y-1)/2)*SPACING
        ROOTS.append((x,y,0.0))
ROOTS=np.asarray(ROOTS,dtype=np.float64)

def source_pos(frame):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
    x=-2.8+5.6*t
    y=1.4*math.sin(2*math.pi*t)
    z=0.8+0.35*math.sin(4*math.pi*t)
    return np.array((x,y,z),dtype=np.float64)

def pulse_gain(frame):
    x=(frame-PULSE_CENTER)/PULSE_SIGMA
    return 1.0+PULSE_GAIN*math.exp(-0.5*x*x)

def wind_vector(frame):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
    return np.array((
        0.55+0.18*math.sin(2*math.pi*1.3*t),
        0.15*math.sin(2*math.pi*0.7*t),
        0.0
    ),dtype=np.float64)*WIND_GAIN

def build_states(axis,grad_grid):
    nframes=FRAME_END-FRAME_START+1
    left=np.zeros((nframes,BLADE_COUNT,BLADE_SEGMENTS,3),dtype=np.float32)
    right=np.zeros_like(left)

    seg_len=BLADE_HEIGHT/(BLADE_SEGMENTS-1)

    # rest positions
    rest=np.zeros((BLADE_COUNT,BLADE_SEGMENTS,3),dtype=np.float64)
    for b,root in enumerate(ROOTS):
        for s in range(BLADE_SEGMENTS):
            rest[b,s]=root+np.array((0,0,seg_len*s))

    for idx,frame in enumerate(range(FRAME_START,FRAME_END+1)):
        w=wind_vector(frame)

        # left
        for b,root in enumerate(ROOTS):
            for s in range(BLADE_SEGMENTS):
                frac=s/(BLADE_SEGMENTS-1)
                bend=w*(frac**1.7)*0.95
                left[idx,b,s]=rest[b,s]+bend

        # right
        src=source_pos(frame)
        tips=rest[:,-1,:]
        qpts=tips-src[None,:]
        qgrad=trilerp_vector(qpts,axis,grad_grid)
        t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
        qgrad=rotate_z(qgrad,2*math.pi*FIELD_ROTATION_TURNS*t)
        mag=np.linalg.norm(qgrad,axis=1,keepdims=True)
        qforce=qgrad/(1.0+0.75*mag)
        gain=QFG_GAIN*pulse_gain(frame)

        for b,root in enumerate(ROOTS):
            q=qforce[b]*gain
            q[2]*=0.25
            for s in range(BLADE_SEGMENTS):
                frac=s/(BLADE_SEGMENTS-1)
                bend=(w+q)*(frac**1.7)*0.95
                right[idx,b,s]=rest[b,s]+bend

    return left,right

# ============================================================
# BLENDER CURVES
# ============================================================

LEFT_SPLINES=[]
RIGHT_SPLINES=[]
LEFT_STATES=None
RIGHT_STATES=None

def build_grass_object(name,state,center,material):
    curve=bpy.data.curves.new(name+"_CurveData","CURVE")
    curve.dimensions="3D"
    curve.bevel_depth=BLADE_RADIUS
    curve.bevel_resolution=2

    splines=[]
    for b in range(BLADE_COUNT):
        spl=curve.splines.new("POLY")
        spl.points.add(BLADE_SEGMENTS-1)
        for s in range(BLADE_SEGMENTS):
            p=state[b,s]
            spl.points[s].co=(*p,1.0)
        splines.append(spl)

    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj)
    obj.location=center
    curve.materials.append(material)
    return obj,splines

def update_splines(splines,state):
    for b,spl in enumerate(splines):
        for s,p in enumerate(state[b]):
            spl.points[s].co=(float(p[0]),float(p[1]),float(p[2]),1.0)

def qfg_grass_handler(scene):
    if LEFT_STATES is None or RIGHT_STATES is None:
        return
    idx=max(0,min(scene.frame_current-FRAME_START,LEFT_STATES.shape[0]-1))
    update_splines(LEFT_SPLINES,LEFT_STATES[idx])
    update_splines(RIGHT_SPLINES,RIGHT_STATES[idx])

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h,"__name__","")=="qfg_grass_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(qfg_grass_handler)

# ============================================================
# VISUALS
# ============================================================

def build_field_cloud(axis,density):
    parent=bpy.data.objects.new("QFG_Field_Cloud",None)
    bpy.context.collection.objects.link(parent)

    vmax=float(np.max(density))
    threshold=float(np.quantile(density,0.945))
    count=0

    for i in range(0,len(axis),2):
        for j in range(0,len(axis),2):
            for k in range(0,len(axis),2):
                val=float(density[i,j,k])
                if val<threshold or count>=150:
                    continue
                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=1,
                    radius=0.018+0.045*min(1.0,val/max(vmax,1e-9)),
                    location=(float(axis[i]),float(axis[j]),float(axis[k]))
                )
                o=bpy.context.object
                o.parent=parent
                o.data.materials.append(MAT_FIELD)
                count+=1

    parent.scale=(0.48,0.48,0.48)

    for f in range(FRAME_START,FRAME_END+1,12):
        parent.location=RIGHT_CENTER+source_pos(f)
        t=(f-FRAME_START)/(FRAME_END-FRAME_START)
        parent.rotation_euler=(0,0,2*math.pi*FIELD_ROTATION_TURNS*t)
        g=pulse_gain(f)
        s=0.48*(1+0.05*(g-1))
        parent.scale=(s,s,s)
        parent.keyframe_insert("location",frame=f)
        parent.keyframe_insert("rotation_euler",frame=f)
        parent.keyframe_insert("scale",frame=f)

def setup_scene():
    sc=bpy.context.scene
    sc.frame_start=FRAME_START
    sc.frame_end=FRAME_END
    sc.render.fps=FPS
    sc.render.resolution_x=RES_X
    sc.render.resolution_y=RES_Y
    sc.render.resolution_percentage=RES_PERCENT
    sc.world.color=(0.001,0.002,0.006)

    try:
        ids=[x.identifier for x in sc.render.bl_rna.properties["engine"].enum_items]
    except Exception:
        ids=[]
    if "BLENDER_EEVEE_NEXT" in ids:
        sc.render.engine="BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in ids:
        sc.render.engine="BLENDER_EEVEE"

    try:
        sc.view_settings.look="AgX - Medium High Contrast"
    except Exception:
        pass

    # soil plots
    plot_x=GRID_X*SPACING*0.55
    plot_y=GRID_Y*SPACING*0.55
    add_cube("Soil_Left",tuple(LEFT_CENTER+np.array((0,0,-0.08))),(plot_x,plot_y,0.08),MAT_SOIL)
    add_cube("Soil_Right",tuple(RIGHT_CENTER+np.array((0,0,-0.08))),(plot_x,plot_y,0.08),MAT_SOIL)
    add_cube("Divider",(0,0,1.4),(0.018,0.10,2.1),MAT_ORANGE)

    add_text("Title","QFG GRASS / WIND FIELD",(0,0,4.05),0.48,MAT_TEXT)
    add_text("LeftLabel","CONTROL // WIND",tuple(LEFT_CENTER+np.array((0,0,2.95))),0.23,MAT_TEXT)
    add_text("RightLabel","QFG // WIND + FIELD",tuple(RIGHT_CENTER+np.array((0,0,2.95))),0.23,MAT_FIELD)
    add_text("Status","QFG field = numerical runtime   |   grass bending = visualization model",(0,0,-1.0),0.17,MAT_ORANGE)

    bpy.ops.object.camera_add(location=(0,-13.5,5.0))
    cam=bpy.context.object
    cam.name="QFG_Grass_Camera"
    sc.camera=cam
    cam.data.lens=56
    look_at(cam,(0,0,0.8))

    keys=[
        (1,(0,-13.5,5.0),(0,0,0.8),56),
        (120,(-1,-11.8,4.2),(0,0,0.8),52),
        (240,(1.6,-10.0,3.3),(1.8,0,0.9),54),
        (320,(4.2,-7.8,2.7),(3.6,0,0.9),68),
        (400,(1.0,-10.8,3.8),(1.0,0,0.8),54),
        (480,(0,-13.8,5.2),(0,0,0.8),58),
    ]
    for f,loc,tgt,lens in keys:
        cam.location=loc
        look_at(cam,tgt)
        cam.data.lens=lens
        cam.keyframe_insert("location",frame=f)
        cam.keyframe_insert("rotation_euler",frame=f)
        cam.data.keyframe_insert("lens",frame=f)

    bpy.ops.object.light_add(type="AREA",location=(-5,-4,7))
    key=bpy.context.object
    key.data.energy=1200
    key.data.size=6
    key.data.color=(0.18,0.42,1.0)
    look_at(key,(0,0,0.8))

    bpy.ops.object.light_add(type="AREA",location=(5,-1,6))
    fill=bpy.context.object
    fill.data.energy=950
    fill.data.size=5.0
    fill.data.color=(0.50,0.10,1.0)
    look_at(fill,(0,0,0.8))

    return sc

# ============================================================
# OUTPUT
# ============================================================

def resolve_output_dir():
    if bpy.data.filepath:
        base=os.path.dirname(bpy.data.filepath)
    else:
        home=os.path.expanduser("~")
        docs=os.path.join(home,"Documents")
        base=docs if os.path.isdir(docs) else home
    out=os.path.join(base,OUTPUT_DIR_NAME)
    os.makedirs(out,exist_ok=True)
    return out

def configure_output(sc):
    out=resolve_output_dir()
    sc.render.filepath=os.path.join(out,OUTPUT_FILE)
    sc.render.use_file_extension=True
    img=sc.render.image_settings
    if hasattr(img,"media_type"):
        try: img.media_type="VIDEO"
        except Exception: pass
    ff=sc.render.ffmpeg
    for attr,val in (("format","MPEG4"),("codec","H264"),("constant_rate_factor","HIGH"),("ffmpeg_preset","GOOD")):
        try: setattr(ff,attr,val)
        except Exception: pass

# ============================================================
# MAIN
# ============================================================

print("\n=== QFG GRASS / WIND FIELD DEMO v1 ===\n")

clear_scene()
scene=setup_scene()

world=build_qfg_world()
axis,grad_grid,density_grid=cache_field(world)

LEFT_STATES,RIGHT_STATES=build_states(axis,grad_grid)

left_obj,LEFT_SPLINES=build_grass_object("Grass_Left",LEFT_STATES[0],LEFT_CENTER,MAT_GRASS_LEFT)
right_obj,RIGHT_SPLINES=build_grass_object("Grass_Right",RIGHT_STATES[0],RIGHT_CENTER,MAT_GRASS_RIGHT)

install_handler()
build_field_cloud(axis,density_grid)

scene["demo"]="QFG Grass / Wind Field v1"
scene["qfg_namespace"]=QFG_ROOT
scene["blade_count"]=BLADE_COUNT
scene["left_case"]="wind"
scene["right_case"]="wind + sampled QFG density gradient"
scene["scientific_status"]="QFG field numerical; grass mechanics visualization model"

configure_output(scene)
out=resolve_output_dir()
blend_path=os.path.join(out,"QFG_Grass_Field_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
qfg_grass_handler(scene)

print("Blend:",blend_path)
print("Video:",scene.render.filepath)
print("Blades per side:",BLADE_COUNT)
print("SPACE = preview | Ctrl+F12 = render")
print("Set RES_PERCENT=100 for final render.")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
