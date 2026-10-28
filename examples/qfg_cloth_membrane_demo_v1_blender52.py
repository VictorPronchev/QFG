# SPDX-License-Identifier: GPL-3.0-or-later
# QFG Cloth / Membrane Demo v1 - Blender 5.2+
#
# LEFT  : gravity + conventional wind-like forcing
# RIGHT : gravity + same baseline + sampled QFG density-gradient forcing
#
# The membrane solver is a custom position-based visualization solver.
# QFGWorld supplies the numerical field and density gradients.
#
# SCIENTIFIC STATUS
# -----------------
# QFG field = numerical runtime
# membrane mechanics = custom visualization solver
# This is not a validated constitutive model of real cloth.
#
# Run:
#   Blender 5.2 -> Scripting -> Open -> Run Script
#   SPACE = preview
#   Ctrl+F12 = render
#
# Output:
#   ~/Documents/QFG_CLOTH_DEMO_V1/  (if .blend is unsaved)
#   or next to the saved .blend file.

import bpy, math, os, sys, importlib
import numpy as np
from mathutils import Vector

FPS=24
FRAME_START=1
FRAME_END=480
RES_X=1920
RES_Y=1080
RES_PERCENT=50
AUTO_RENDER=False

OUTPUT_DIR_NAME="QFG_CLOTH_DEMO_V1"
OUTPUT_FILE="QFG_Cloth_Membrane_v1"

LEFT_CENTER=np.array((-3.4,0.0,0.0),dtype=np.float64)
RIGHT_CENTER=np.array((3.4,0.0,0.0),dtype=np.float64)

NX=19
NY=19
WIDTH=4.6
HEIGHT=4.6
DX=WIDTH/(NX-1)
DY=HEIGHT/(NY-1)
DAMPING=0.965
GRAVITY=np.array((0.0,0.0,-0.55),dtype=np.float64)
CONSTRAINT_ITERS=7
WIND_GAIN=0.75
QFG_FORCE_SCALE=4.8
FIELD_ROTATION_TURNS=1.1
PULSE_CENTER=270
PULSE_SIGMA=18.0
PULSE_GAIN=2.1
COLLIDER_RADIUS=0.62

QFG_GRID=32
QFG_DOMAIN=16.0
QFG_DT=0.002
QFG_STEPS=18
FIELD_CACHE_N=23
FIELD_CACHE_HALF=5.4

def candidate_roots():
    roots=[]
    try:
        for key in bpy.context.preferences.addons.keys():
            if "qfg_lab_52" in key.lower():
                roots.append(key)
    except Exception:
        pass
    roots += ["qfg_lab_52","bl_ext.user_default.qfg_lab_52","bl_ext.blender_org.qfg_lab_52"]
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

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

def make_material(name,color,emission=0.0,metallic=0.0,roughness=0.35,alpha=1.0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    bsdf=m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs: bsdf.inputs["Base Color"].default_value=(*color[:3],alpha)
        if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value=metallic
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=roughness
        if "Emission Color" in bsdf.inputs: bsdf.inputs["Emission Color"].default_value=(*color[:3],alpha)
        elif "Emission" in bsdf.inputs: bsdf.inputs["Emission"].default_value=(*color[:3],alpha)
        if "Emission Strength" in bsdf.inputs: bsdf.inputs["Emission Strength"].default_value=emission
        if "Alpha" in bsdf.inputs: bsdf.inputs["Alpha"].default_value=alpha
    if hasattr(m,"blend_method"):
        try: m.blend_method="BLEND"
        except Exception: pass
    return m

MAT_LEFT=make_material("LeftCloth",(0.70,0.76,0.84),0.10,0,0.5)
MAT_RIGHT=make_material("RightCloth",(0.03,0.68,1.00),1.25,0,0.32)
MAT_FRAME=make_material("Frame",(0.12,0.18,0.24),0,0.65,0.25)
MAT_TEXT=make_material("Text",(0.92,0.96,1.00),1.0)
MAT_FIELD=make_material("Field",(0.55,0.10,1.00),3.0)
MAT_ORANGE=make_material("Orange",(1.00,0.24,0.03),3.0)
MAT_COLLIDER=make_material("Collider",(0.10,1.00,0.32),1.7,0.2,0.24)
MAT_BG=make_material("BG",(0.01,0.015,0.025),0,0,0.7)

def add_text(name,body,loc,size=0.28,material=None):
    c=bpy.data.curves.new(name+"_Curve","FONT")
    c.body=body; c.align_x="CENTER"; c.align_y="CENTER"; c.size=size; c.extrude=0.004
    o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o)
    o.location=loc; o.rotation_euler=(math.pi/2,0,0)
    if material: o.data.materials.append(material)
    return o

def add_cube(name,loc,scale,material):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if material: o.data.materials.append(material)
    return o

def add_sphere(name,loc,radius,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=20,radius=radius,location=loc)
    o=bpy.context.object; o.name=name
    if material: o.data.materials.append(material)
    return o

def look_at(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler()

def build_qfg_world():
    ec=EngineConfig(grid_size=QFG_GRID,domain_length=QFG_DOMAIN,dt=QFG_DT,backend="NUMPY",
                    field_mode="SCALAR",thermal_enabled=False,topology_enabled=True)
    wc=WorldConfig(substeps=2,gravity=(0,0,0),floor_height=-1000.0,body_collisions=False,
                   deterministic=True,seed=1337)
    world=create_world(ec,wc)
    world.add_field_actor(ActorSpec(actor_type="GAUSSIAN",center=(0,0,0),radius=1.7,intensity=1.3,
                                    velocity=(0,0,0),name="ClothGaussian"))
    world.add_field_actor(ActorSpec(actor_type="VORTEX",center=(0,0,0),radius=2.5,intensity=0.70,
                                    winding_m=1,velocity=(0,0,0),name="ClothVortex"))
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
    pts=np.asarray(points,dtype=np.float64); n=len(axis)
    lo=float(axis[0]); hi=float(axis[-1]); h=(hi-lo)/(n-1)
    q=np.clip((pts-lo)/h,0,n-1-1e-8)
    i0=np.floor(q).astype(np.int32); f=q-i0; i1=np.minimum(i0+1,n-1)
    x0,y0,z0=i0[...,0],i0[...,1],i0[...,2]; x1,y1,z1=i1[...,0],i1[...,1],i1[...,2]
    fx,fy,fz=f[...,0][...,None],f[...,1][...,None],f[...,2][...,None]
    c000=grid[x0,y0,z0]; c100=grid[x1,y0,z0]; c010=grid[x0,y1,z0]; c110=grid[x1,y1,z0]
    c001=grid[x0,y0,z1]; c101=grid[x1,y0,z1]; c011=grid[x0,y1,z1]; c111=grid[x1,y1,z1]
    c00=c000*(1-fx)+c100*fx; c10=c010*(1-fx)+c110*fx; c01=c001*(1-fx)+c101*fx; c11=c011*(1-fx)+c111*fx
    c0=c00*(1-fy)+c10*fy; c1=c01*(1-fy)+c11*fy
    return c0*(1-fz)+c1*fz

def rotate_z(v,angle):
    c=math.cos(angle); s=math.sin(angle); out=np.empty_like(v)
    out[...,0]=c*v[...,0]-s*v[...,1]; out[...,1]=s*v[...,0]+c*v[...,1]; out[...,2]=v[...,2]
    return out

def initial_membrane():
    pos=np.zeros((NY,NX,3),dtype=np.float64)
    for j in range(NY):
        z=-HEIGHT/2+j*DY
        for i in range(NX):
            x=-WIDTH/2+i*DX
            pos[j,i]=(x,0.0,z)
    return pos

INITIAL=initial_membrane()
PINNED=np.zeros((NY,NX),dtype=bool); PINNED[-1,:]=True

CONSTRAINTS=[]
for j in range(NY):
    for i in range(NX):
        if i+1<NX: CONSTRAINTS.append(((j,i),(j,i+1),DX))
        if j+1<NY: CONSTRAINTS.append(((j,i),(j+1,i),DY))
        if i+1<NX and j+1<NY: CONSTRAINTS.append(((j,i),(j+1,i+1),math.hypot(DX,DY)))
        if i-1>=0 and j+1<NY: CONSTRAINTS.append(((j,i),(j+1,i-1),math.hypot(DX,DY)))

def source_pos(frame):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START); a=2*math.pi*1.1*t
    return np.array((2.6*math.cos(a),-1.4,1.0*math.sin(2*a)),dtype=np.float64)

def collider_pos(frame):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
    return np.array((-2.7+5.4*t,-0.7,0.4*math.sin(2*math.pi*t)),dtype=np.float64)

def pulse_gain(frame):
    x=(frame-PULSE_CENTER)/PULSE_SIGMA
    return 1.0+PULSE_GAIN*math.exp(-0.5*x*x)

def wind_force(frame,positions):
    t=(frame-FRAME_START)/(FRAME_END-FRAME_START)
    gain=WIND_GAIN*(0.55+0.45*math.sin(2*math.pi*1.5*t)**2)
    return np.broadcast_to(np.array((0.0,1.0,0.0))*gain,positions.shape)

def apply_constraints(new,col):
    for _ in range(CONSTRAINT_ITERS):
        new[PINNED]=INITIAL[PINNED]
        for (a,b,rest) in CONSTRAINTS:
            ja,ia=a; jb,ib=b
            d=new[jb,ib]-new[ja,ia]; L=np.linalg.norm(d)
            if L<1e-9: continue
            corr=d*(1.0-rest/L)
            pa=PINNED[ja,ia]; pb=PINNED[jb,ib]
            if pa and not pb: new[jb,ib]-=corr
            elif pb and not pa: new[ja,ia]+=corr
            elif not pa and not pb:
                new[ja,ia]+=0.5*corr; new[jb,ib]-=0.5*corr
        rel=new-col[None,None,:]; rr=np.linalg.norm(rel,axis=-1,keepdims=True)
        inside=rr<COLLIDER_RADIUS; proj=col[None,None,:]+rel/np.maximum(rr,1e-9)*COLLIDER_RADIUS
        new[:]=np.where(inside & (~PINNED)[...,None],proj,new)
    return new

def simulate_pair(axis,grad_grid):
    left=INITIAL.copy(); left_prev=left.copy(); right=INITIAL.copy(); right_prev=right.copy()
    nframes=FRAME_END-FRAME_START+1
    ls=np.zeros((nframes,NY,NX,3),dtype=np.float32); rs=np.zeros_like(ls)
    ls[0]=left; rs[0]=right; dt=1.0/FPS
    for oi,frame in enumerate(range(FRAME_START+1,FRAME_END+1),start=1):
        col=collider_pos(frame)
        vel=(left-left_prev)*DAMPING; new=left+vel; left_prev[:]=left
        new+=(GRAVITY[None,None,:]+wind_force(frame,new))*(dt*dt*5.0)
        left[:]=apply_constraints(new,col)
        vel=(right-right_prev)*DAMPING; new=right+vel; right_prev[:]=right
        accel=GRAVITY[None,None,:]+wind_force(frame,new)
        src=source_pos(frame); qpts=new-src[None,None,:]; qgrad=trilerp_vector(qpts,axis,grad_grid)
        t=(frame-FRAME_START)/(FRAME_END-FRAME_START); qgrad=rotate_z(qgrad,2*math.pi*FIELD_ROTATION_TURNS*t)
        mag=np.linalg.norm(qgrad,axis=-1,keepdims=True); qforce=qgrad/(1.0+0.75*mag)
        accel+=(QFG_FORCE_SCALE*pulse_gain(frame))*qforce
        new+=accel*(dt*dt*5.0)
        right[:]=apply_constraints(new,col)
        ls[oi]=left.astype(np.float32); rs[oi]=right.astype(np.float32)
    return ls,rs

LEFT_OBJ=RIGHT_OBJ=None
LEFT_STATES=RIGHT_STATES=None

def build_membrane_mesh(name,initial,material,center):
    verts=[tuple(initial[j,i]) for j in range(NY) for i in range(NX)]
    faces=[]
    for j in range(NY-1):
        for i in range(NX-1):
            a=j*NX+i; b=a+1; c=(j+1)*NX+i+1; d=(j+1)*NX+i
            faces.append((a,b,c,d))
    mesh=bpy.data.meshes.new(name+"_Mesh"); mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); obj.location=center
    mesh.materials.append(material)
    sol=obj.modifiers.new("Solidify","SOLIDIFY"); sol.thickness=0.035
    sub=obj.modifiers.new("Subdivision","SUBSURF"); sub.levels=1; sub.render_levels=1
    return obj

def update_mesh(obj,state):
    flat=state.reshape((-1,3))
    for i,p in enumerate(flat): obj.data.vertices[i].co=(float(p[0]),float(p[1]),float(p[2]))
    obj.data.update()

def qfg_cloth_v1_handler(scene):
    if LEFT_STATES is None or RIGHT_STATES is None: return
    idx=max(0,min(scene.frame_current-FRAME_START,LEFT_STATES.shape[0]-1))
    update_mesh(LEFT_OBJ,LEFT_STATES[idx]); update_mesh(RIGHT_OBJ,RIGHT_STATES[idx])

def install_handler():
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h,"__name__","")=="qfg_cloth_v1_handler":
            bpy.app.handlers.frame_change_pre.remove(h)
    bpy.app.handlers.frame_change_pre.append(qfg_cloth_v1_handler)

def setup_scene():
    sc=bpy.context.scene
    sc.frame_start=FRAME_START; sc.frame_end=FRAME_END; sc.render.fps=FPS
    sc.render.resolution_x=RES_X; sc.render.resolution_y=RES_Y; sc.render.resolution_percentage=RES_PERCENT
    sc.world.color=(0.001,0.002,0.006)
    try: ids=[x.identifier for x in sc.render.bl_rna.properties["engine"].enum_items]
    except Exception: ids=[]
    if "BLENDER_EEVEE_NEXT" in ids: sc.render.engine="BLENDER_EEVEE_NEXT"
    elif "BLENDER_EEVEE" in ids: sc.render.engine="BLENDER_EEVEE"
    try: sc.view_settings.look="AgX - Medium High Contrast"
    except Exception: pass
    add_cube("Floor",(0,0,-3.25),(9.5,7.0,0.07),MAT_BG)
    add_cube("Divider",(0,0,0),(0.018,0.12,3.8),MAT_ORANGE)
    add_cube("Support_Left",tuple(LEFT_CENTER+np.array((0,0,HEIGHT/2+0.18))),(WIDTH/2+0.25,0.10,0.10),MAT_FRAME)
    add_cube("Support_Right",tuple(RIGHT_CENTER+np.array((0,0,HEIGHT/2+0.18))),(WIDTH/2+0.25,0.10,0.10),MAT_FRAME)
    add_text("Title","QFG CLOTH / MEMBRANE",(0,0,4.15),0.48,MAT_TEXT)
    add_text("LeftLabel","CONTROL // WIND + GRAVITY",tuple(LEFT_CENTER+np.array((0,0,3.15))),0.22,MAT_TEXT)
    add_text("RightLabel","QFG // FIELD + WIND + GRAVITY",tuple(RIGHT_CENTER+np.array((0,0,3.15))),0.22,MAT_FIELD)
    add_text("Status","QFG field = numerical runtime   |   membrane = custom visualization solver",(0,0,-3.65),0.17,MAT_ORANGE)
    bpy.ops.object.camera_add(location=(0,-15.5,5.2))
    cam=bpy.context.object; cam.name="QFG_Cloth_Camera"; sc.camera=cam; cam.data.lens=56; look_at(cam,(0,0,0.1))
    keys=[(1,(0,-15.5,5.2),(0,0,0.1),56),(120,(-1,-13.5,4.4),(0,0,0.1),52),(250,(1.8,-11.5,3.6),(1.8,0,0),54),(320,(4.1,-8.8,2.8),(3.4,0,0),68),(400,(1,-12,4),(1,0,0),54),(480,(0,-15.8,5.4),(0,0,0.1),58)]
    for f,loc,tgt,lens in keys:
        cam.location=loc; look_at(cam,tgt); cam.data.lens=lens
        cam.keyframe_insert("location",frame=f); cam.keyframe_insert("rotation_euler",frame=f); cam.data.keyframe_insert("lens",frame=f)
    bpy.ops.object.light_add(type="AREA",location=(-5,-5,7)); key=bpy.context.object; key.data.energy=1200; key.data.size=5.6; key.data.color=(0.12,0.38,1.0); look_at(key,(0,0,0))
    bpy.ops.object.light_add(type="AREA",location=(5,-1,6.5)); fill=bpy.context.object; fill.data.energy=950; fill.data.size=5.0; fill.data.color=(0.55,0.10,1.0); look_at(fill,(0,0,0))
    return sc

def build_colliders():
    l=add_sphere("Collider_Left",LEFT_CENTER+collider_pos(FRAME_START),COLLIDER_RADIUS,MAT_COLLIDER)
    r=add_sphere("Collider_Right",RIGHT_CENTER+collider_pos(FRAME_START),COLLIDER_RADIUS,MAT_COLLIDER)
    for f in range(FRAME_START,FRAME_END+1,12):
        p=collider_pos(f); l.location=LEFT_CENTER+p; r.location=RIGHT_CENTER+p
        l.keyframe_insert("location",frame=f); r.keyframe_insert("location",frame=f)

def build_field_cloud(axis,density):
    parent=bpy.data.objects.new("QFG_Field_Cloud",None); bpy.context.collection.objects.link(parent)
    vmax=float(np.max(density)); threshold=float(np.quantile(density,0.945)); count=0
    for i in range(0,len(axis),2):
        for j in range(0,len(axis),2):
            for k in range(0,len(axis),2):
                val=float(density[i,j,k])
                if val<threshold or count>=160: continue
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=0.022+0.05*min(1.0,val/max(vmax,1e-9)),location=(float(axis[i]),float(axis[j]),float(axis[k])))
                o=bpy.context.object; o.parent=parent; o.data.materials.append(MAT_FIELD); count+=1
    parent.scale=(0.62,0.62,0.62)
    for f in range(FRAME_START,FRAME_END+1,12):
        parent.location=RIGHT_CENTER+source_pos(f)
        t=(f-FRAME_START)/(FRAME_END-FRAME_START); parent.rotation_euler=(0,0,2*math.pi*FIELD_ROTATION_TURNS*t)
        g=pulse_gain(f); s=0.62*(1+0.055*(g-1)); parent.scale=(s,s,s)
        parent.keyframe_insert("location",frame=f); parent.keyframe_insert("rotation_euler",frame=f); parent.keyframe_insert("scale",frame=f)

def resolve_output_dir():
    if bpy.data.filepath: base=os.path.dirname(bpy.data.filepath)
    else:
        home=os.path.expanduser("~"); docs=os.path.join(home,"Documents"); base=docs if os.path.isdir(docs) else home
    out=os.path.join(base,OUTPUT_DIR_NAME); os.makedirs(out,exist_ok=True); return out

def configure_output(sc):
    out=resolve_output_dir(); sc.render.filepath=os.path.join(out,OUTPUT_FILE); sc.render.use_file_extension=True
    img=sc.render.image_settings
    if hasattr(img,"media_type"):
        try: img.media_type="VIDEO"
        except Exception: pass
    ff=sc.render.ffmpeg
    for attr,val in (("format","MPEG4"),("codec","H264"),("constant_rate_factor","HIGH"),("ffmpeg_preset","GOOD")):
        try: setattr(ff,attr,val)
        except Exception: pass

print("\\n=== QFG CLOTH / MEMBRANE DEMO v1 ===\\n")
clear_scene()
scene=setup_scene()
world=build_qfg_world()
axis,grad_grid,density_grid=cache_field(world)
LEFT_STATES,RIGHT_STATES=simulate_pair(axis,grad_grid)
LEFT_OBJ=build_membrane_mesh("Membrane_Left",LEFT_STATES[0],MAT_LEFT,LEFT_CENTER)
RIGHT_OBJ=build_membrane_mesh("Membrane_Right",RIGHT_STATES[0],MAT_RIGHT,RIGHT_CENTER)
install_handler()
build_colliders()
build_field_cloud(axis,density_grid)
scene["demo"]="QFG Cloth / Membrane v1"
scene["scientific_status"]="QFG field numerical; membrane mechanics visualization/demo"
configure_output(scene)
out=resolve_output_dir()
blend_path=os.path.join(out,"QFG_Cloth_Membrane_v1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
scene.frame_set(FRAME_START)
qfg_cloth_v1_handler(scene)
print("Blend:",blend_path)
print("Video:",scene.render.filepath)
print("SPACE = preview | Ctrl+F12 = render")
if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
