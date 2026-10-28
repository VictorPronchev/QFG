# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Granular / Particle Field Demo v1 - Blender 5.2+
#
# LEFT  : gravity + floor + particle-particle repulsion/contact approximation
# RIGHT : same baseline + sampled QFG density-gradient forcing
#
# The particle mechanics use a lightweight custom visualization solver.
# QFGWorld supplies the numerical field and density gradients.
#
# SCIENTIFIC STATUS
# -----------------
# QFG field = numerical runtime
# granular mechanics = custom visualization solver
# This is not a validated DEM/continuum granular-material model.
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_GRANULAR_DEMO_V1/
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

OUTPUT_DIR_NAME = "QFG_GRANULAR_DEMO_V1"
OUTPUT_FILE = "QFG_Granular_Field_v1"

LEFT_CENTER  = np.array((-3.6, 0.0, 0.0), dtype=np.float64)
RIGHT_CENTER = np.array(( 3.6, 0.0, 0.0), dtype=np.float64)

# Granular system
PARTICLE_COUNT = 220
PARTICLE_RADIUS = 0.105
BOX_HALF = 2.45
FLOOR_Z = -2.45
DAMPING = 0.985
GRAVITY = np.array((0.0, 0.0, -1.25), dtype=np.float64)
REPULSION_GAIN = 18.0
CONTACT_DAMP = 0.78

# QFG coupling
QFG_FORCE_SCALE = 7.0
FIELD_ROTATION_TURNS = 1.25

# Pulse / vortex boost
PULSE_CENTER = 275
PULSE_SIGMA = 22.0
PULSE_GAIN = 2.0
TANGENTIAL_GAIN = 2.2

# QFG field
QFG_GRID = 32
QFG_DOMAIN = 16.0
QFG_DT = 0.002
QFG_STEPS = 18
FIELD_CACHE_N = 23
FIELD_CACHE_HALF = 5.4

# ============================================================
# QFG SDK
# ============================================================

def candidate_roots():
    roots=[]
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
            req=("create_world","EngineConfig","WorldConfig","ActorSpec")
            if all(hasattr(sdk,n) for n in req):
                print("QFG SDK:",sdk.__name__)
                return root,sdk
        except Exception as exc:
            errors[root]=repr(exc)

    raise RuntimeError(
        "QFG Dynamics SDK not found. Enable QFG Dynamics 1.0.0+.\n"+
        "\n".join(f"{k}: {v}" for k,v in errors.items())
    )

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

def make_material(name,color,emission=0.0,metallic=0.0,roughness=0.35):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value=(*color[:3],1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value=metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value=roughness
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value=(*color[:3],1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value=(*color[:3],1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value=emission
    return m

MAT_LEFT=make_material("LeftParticles",(0.72,0.78,0.86),0.10,0.15,0.4)
MAT_RIGHT=make_material("RightParticles",(0.03,0.72,1.00),1.6,0.15,0.30)
MAT_FIELD=make_material("Field",(0.55,0.10,1.00),3.0,0,0.2)
MAT_ORANGE=make_material("Orange",(1.00,0.24,0.03),3.0,0,0.2)
MAT_TEXT=make_material("Text",(0.92,0.96,1.00),1.0,0,0.3)
MAT_FLOOR=make_material("Floor",(0.03,0.04,0.06),0.0,0.2,0.55)
MAT_WALL=make_material("Wall",(0.08,0.11,0.16),0.0,0.45,0.35)

def add_text(name,body,loc,size=0.28,material=None):
    c=bpy.data.curves.new(name+"_Curve","FONT")
    c.body=body
    c.align_x="CENTER"
    c.align_y="CENTER"
    c.size=size
    c.extrude=0.004
    o=bpy.data.objects.new(name,c)
    bpy.context.collection.objects.link(o)
    o.location=loc
    o.rotation_euler=(math.pi/2,0,0)
    if material:
        o.data.materials.append(material)
    return o

def add_cube(name,loc,scale,material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o=bpy.context.object
    o.name=name
    o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if material:
        o.data.materials.append(material)
    return o

def add_sphere(name,loc,radius,material,segments=16,rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,radius=radius,location=loc)
    o=bpy.context.object
    o.name=name
    if material:
        o.data.materials.append(material)
    return o

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

# ============================================================
# QFG FIELD CACHE
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
        radius=1.8,
        intensity=1.35,
        velocity=(0,0,0),
        name="GranularGaussian"
    ))
    world.add_field_actor(ActorSpec(
        actor_type="VORTEX",
        center=(0,0,0),
        radius=2.8,
        intensity=0.85,
        winding_m=1,
        velocity=(0,0,0),
        name="GranularVortex"
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
                sample=world.sample_field((float(x),float(y),float(z)))
                grad[i,j,k]=np.asarray(sample["density_gradient"],dtype=np.float32)
                density[i,j,k]=float(sample["density"])
    print("Field cache complete.")
    return axis,grad,density

def trilerp_vector(points,axis,grid):
    pts=np.asarray(points,dtype=np.float64)
    n=len(axis)
    lo=float(axis[0]); hi=float(axis[-1]); h=(hi-lo)/(n-1)

    q=np.clip((pts-lo)/h,0,n-1-1e-8)
    i0=np.floor(q).astype(np.int32)
    f=q-i0
    i1=np.minimum(i0+1,n-1)

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
    c=math.cos(angle)
    s=math.sin(angle)
    out=np.empty_like(v)
    out[...,0]=c*v[...,0]-s*v[...,1]
    out[...,1]=s*v[...,0]+c*v[...,1]
    out[...,2]=v[...,2]
    return out

# ============================================================
# PARTICLE INITIALIZATION
# ============================================================

def initial_particles():
    rng=np.random.default_rng(1337)
    pts=[]

    # compact mound above floor
    while len(pts)<PARTICLE_COUNT:
        x=rng.uniform(-1.65,1.65)
        y=rng.uniform(-1.65,1.65)
        z=rng.uniform(FLOOR_Z+PARTICLE_RADIUS,0.6)

        # prefer mound/sphere-like volume
        if (x*x+y*y)/3.2 + ((z+1.0)**2)/2.0 < 1.0:
            pts.append((x,y,z))

    return np.asarray(pts,dtype=np.float64)

INITIAL=initial_particles()

def source_pos(frame):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
    a=2*math.pi*1.1*t
    r=2.3+0.35*math.sin(4*math.pi*t)
    return np.array((r*math.cos(a),r*math.sin(a),-0.5+0.7*math.sin(2*a)),dtype=np.float64)

def pulse_gain(frame):
    x=(frame-PULSE_CENTER)/PULSE_SIGMA
    return 1.0+PULSE_GAIN*math.exp(-0.5*x*x)

# ============================================================
# PARTICLE SOLVER
# ============================================================

def pairwise_repulsion(pos):
    # O(N^2) but fine for 220 particles.
    n=len(pos)
    force=np.zeros_like(pos)
    min_dist=2.0*PARTICLE_RADIUS

    for i in range(n):
        d=pos[i]-pos
        dist=np.linalg.norm(d,axis=1)
        mask=(dist>1e-9)&(dist<min_dist)
        if not np.any(mask):
            continue
        dirs=d[mask]/dist[mask][:,None]
        pen=(min_dist-dist[mask])[:,None]
        force[i]+=np.sum(dirs*pen*REPULSION_GAIN,axis=0)

    return force

def confine(pos,vel):
    # Floor
    below=pos[:,2] < FLOOR_Z+PARTICLE_RADIUS
    pos[below,2]=FLOOR_Z+PARTICLE_RADIUS
    vel[below,2]*=-0.20
    vel[below,:2]*=CONTACT_DAMP

    # Side walls
    for axis in (0,1):
        low=pos[:,axis] < -BOX_HALF+PARTICLE_RADIUS
        high=pos[:,axis] > BOX_HALF-PARTICLE_RADIUS
        pos[low,axis]=-BOX_HALF+PARTICLE_RADIUS
        pos[high,axis]=BOX_HALF-PARTICLE_RADIUS
        vel[low|high,axis]*=-0.25
        other=1-axis
        vel[low|high,other]*=CONTACT_DAMP
    return pos,vel

def simulate_pair(axis,grad_grid):
    dt=1.0/FPS

    lp=INITIAL.copy()
    lv=np.zeros_like(lp)

    rp=INITIAL.copy()
    rv=np.zeros_like(rp)

    nframes=FRAME_END-FRAME_START+1
    left=np.zeros((nframes,PARTICLE_COUNT,3),dtype=np.float32)
    right=np.zeros_like(left)
    left[0]=lp
    right[0]=rp

    print("Simulating granular comparison...")
    for oi,frame in enumerate(range(FRAME_START+1,FRAME_END+1),start=1):
        # LEFT
        lf=pairwise_repulsion(lp)+GRAVITY[None,:]
        lv=(lv+lf*dt)*DAMPING
        lp=lp+lv*dt
        lp,lv=confine(lp,lv)

        # RIGHT
        rf=pairwise_repulsion(rp)+GRAVITY[None,:]

        src=source_pos(frame)
        qpts=rp-src[None,:]
        qgrad=trilerp_vector(qpts,axis,grad_grid)

        t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
        qgrad=rotate_z(qgrad,2*math.pi*FIELD_ROTATION_TURNS*t)

        mag=np.linalg.norm(qgrad,axis=1,keepdims=True)
        qforce=qgrad/(1.0+0.75*mag)

        # extra tangential vortex component around Z
        radial=rp-src[None,:]
        tangent=np.stack((-radial[:,1],radial[:,0],np.zeros(len(rp))),axis=1)
        tl=np.linalg.norm(tangent,axis=1,keepdims=True)
        tangent=np.divide(tangent,np.maximum(tl,1e-9))

        gain=pulse_gain(frame)
        rf += (QFG_FORCE_SCALE*gain)*qforce + (TANGENTIAL_GAIN*gain)*tangent

        rv=(rv+rf*dt)*DAMPING
        rp=rp+rv*dt
        rp,rv=confine(rp,rv)

        left[oi]=lp.astype(np.float32)
        right[oi]=rp.astype(np.float32)

        if oi%72==0:
            print(f"  frame {frame}/{FRAME_END}")

    print("Granular simulation complete.")
    return left,right

# ============================================================
# BLENDER PARTICLES / HANDLER
# ============================================================

LEFT_OBJS=[]
RIGHT_OBJS=[]
LEFT_STATES=None
RIGHT_STATES=None

def build_particles(prefix,state,center,material):
    objs=[]
    for i,p in enumerate(state):
        o=add_sphere(f"{prefix}_{i:03d}",center+p,PARTICLE_RADIUS,material,12,6)
        objs.append(o)
    return objs

def update_particles(objs,state,center):
    for o,p in zip(objs,state):
        o.location=tuple(center+p)

def qfg_granular_v1_handler(scene):
    if LEFT_STATES is None or RIGHT_STATES is None:
        return
    idx=max(0,min(scene.frame_current-FRAME_START,LEFT_STATES.shape[0]-1))
    update_particles(LEFT_OBJS,LEFT_STATES[idx],LEFT_CENTER)
    update_particles(RIGHT_OBJS,RIGHT_STATES[idx],RIGHT_CENTER)

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h,"__name__","")=="qfg_granular_v1_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(qfg_granular_v1_handler)

# ============================================================
# VISUALS
# ============================================================

def build_container(center,prefix):
    # floor
    add_cube(prefix+"_Floor",tuple(center+np.array((0,0,FLOOR_Z-0.06))),
             (BOX_HALF+0.1,BOX_HALF+0.1,0.06),MAT_FLOOR)

    # subtle walls
    h=2.7
    add_cube(prefix+"_Back",tuple(center+np.array((0,BOX_HALF+0.05,-0.1))),
             (BOX_HALF+0.1,0.05,h),MAT_WALL)
    add_cube(prefix+"_Left",tuple(center+np.array((-BOX_HALF-0.05,0,-0.1))),
             (0.05,BOX_HALF+0.1,h),MAT_WALL)
    add_cube(prefix+"_Right",tuple(center+np.array((BOX_HALF+0.05,0,-0.1))),
             (0.05,BOX_HALF+0.1,h),MAT_WALL)

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
                if val<threshold or count>=160:
                    continue
                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=1,
                    radius=0.022+0.05*min(1.0,val/max(vmax,1e-9)),
                    location=(float(axis[i]),float(axis[j]),float(axis[k]))
                )
                o=bpy.context.object
                o.parent=parent
                o.data.materials.append(MAT_FIELD)
                count+=1

    parent.scale=(0.58,0.58,0.58)

    for f in range(FRAME_START,FRAME_END+1,12):
        parent.location=RIGHT_CENTER+source_pos(f)
        t=(f-FRAME_START)/(FRAME_END-FRAME_START)
        parent.rotation_euler=(0,0,2*math.pi*FIELD_ROTATION_TURNS*t)

        g=pulse_gain(f)
        s=0.58*(1+0.06*(g-1))
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

    build_container(LEFT_CENTER,"Left")
    build_container(RIGHT_CENTER,"Right")

    add_cube("Divider",(0,0,0),(0.018,0.12,3.9),MAT_ORANGE)

    add_text("Title","QFG GRANULAR / PARTICLE FIELD",(0,0,4.35),0.46,MAT_TEXT)
    add_text("LeftLabel","CONTROL // GRAVITY + CONTACTS",tuple(LEFT_CENTER+np.array((0,0,3.2))),0.22,MAT_TEXT)
    add_text("RightLabel","QFG // FIELD + VORTEX + CONTACTS",tuple(RIGHT_CENTER+np.array((0,0,3.2))),0.22,MAT_FIELD)
    add_text("Status",
             "QFG field = numerical runtime   |   granular mechanics = custom visualization solver",
             (0,0,-3.7),0.17,MAT_ORANGE)

    bpy.ops.object.camera_add(location=(0,-16.5,6.0))
    cam=bpy.context.object
    cam.name="QFG_Granular_Camera"
    sc.camera=cam
    cam.data.lens=58
    look_at(cam,(0,0,-0.2))

    keys=[
        (1,(0,-16.5,6.0),(0,0,-0.2),58),
        (120,(-1.0,-14.5,5.0),(0,0,-0.3),54),
        (250,(1.7,-12.5,4.2),(1.8,0,-0.2),52),
        (330,(4.2,-9.5,3.2),(3.6,0,-0.3),66),
        (410,(1.0,-12.8,4.5),(1.0,0,-0.2),54),
        (480,(0,-16.8,6.1),(0,0,-0.2),58),
    ]

    for f,loc,tgt,lens in keys:
        cam.location=loc
        look_at(cam,tgt)
        cam.data.lens=lens
        cam.keyframe_insert("location",frame=f)
        cam.keyframe_insert("rotation_euler",frame=f)
        cam.data.keyframe_insert("lens",frame=f)

    bpy.ops.object.light_add(type="AREA",location=(-5,-5,8))
    key=bpy.context.object
    key.data.energy=1250
    key.data.size=5.8
    key.data.color=(0.12,0.38,1.0)
    look_at(key,(0,0,0))

    bpy.ops.object.light_add(type="AREA",location=(5,-1,7))
    fill=bpy.context.object
    fill.data.energy=1000
    fill.data.size=5.2
    fill.data.color=(0.55,0.10,1.0)
    look_at(fill,(0,0,0))

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
        try:
            img.media_type="VIDEO"
        except Exception:
            pass

    ff=sc.render.ffmpeg
    for attr,val in (
        ("format","MPEG4"),
        ("codec","H264"),
        ("constant_rate_factor","HIGH"),
        ("ffmpeg_preset","GOOD"),
    ):
        try:
            setattr(ff,attr,val)
        except Exception:
            pass

# ============================================================
# MAIN
# ============================================================

print("\n============================================")
print(" QFG GRANULAR / PARTICLE FIELD DEMO v1")
print("============================================\n")

clear_scene()
scene=setup_scene()

print("[1/4] Building QFG field...")
world=build_qfg_world()
axis,grad_grid,density_grid=cache_field(world)

print("[2/4] Simulating particles...")
LEFT_STATES,RIGHT_STATES=simulate_pair(axis,grad_grid)

print("[3/4] Building Blender particles...")
LEFT_OBJS=build_particles("Particle_Left",LEFT_STATES[0],LEFT_CENTER,MAT_LEFT)
RIGHT_OBJS=build_particles("Particle_Right",RIGHT_STATES[0],RIGHT_CENTER,MAT_RIGHT)
install_handler()
build_field_cloud(axis,density_grid)

scene["demo"]="QFG Granular / Particle Field v1"
scene["qfg_namespace"]=QFG_ROOT
scene["qfg_grid"]=QFG_GRID
scene["qfg_dt"]=QFG_DT
scene["particle_count"]=PARTICLE_COUNT
scene["left_case"]="gravity + contact approximation"
scene["right_case"]="gravity + contact approximation + sampled QFG field"
scene["scientific_status"]="QFG field numerical; granular mechanics visualization/demo"

print("[4/4] Saving...")
configure_output(scene)
out=resolve_output_dir()
blend_path=os.path.join(out,"QFG_Granular_Field_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)

scene.frame_set(FRAME_START)
qfg_granular_v1_handler(scene)

print("\nDONE")
print("QFG namespace:",QFG_ROOT)
print("Blend:",blend_path)
print("Video:",scene.render.filepath)
print("Particles:",PARTICLE_COUNT)
print("SPACE = preview | Ctrl+F12 = render")
print("Set RES_PERCENT=100 for final render.\n")

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
