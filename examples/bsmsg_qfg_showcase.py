# SPDX-License-Identifier: MIT
# BSM-SG / QFG CINEMATIC SHOWCASE
# Compatibility build: V8 / QFG 1.0.0-alpha + Blender 5.2 media_type VIDEO API
# Target: Blender 5.x + QFG Dynamics / qfg_lab_52.sdk
#
# Creates a ~55 second AAA-style sci-fi cinematic:
#   SHOT 01  QFG field awakening
#   SHOT 02  soliton / field reveal
#   SHOT 03  real QFGWorld two-body dynamics + collision
#   SHOT 04  BSM-SG Atlas / J_ij visual assembly
#   SHOT 05  real QFGWorld multi-body field motion
#   SHOT 06  hero orbit + plugin title
#
# IMPORTANT:
# The dynamic trajectories are generated from qfg_lab_52.sdk / QFGWorld.
# Atlas/J_ij geometry is a visualization layer built in Blender around
# the simulated structural sites; it is not a claim of measured nuclear geometry.
#
# Run from Blender: Scripting -> New/Open -> Run Script.
# By default the script builds and saves the scene but DOES NOT render the movie.
# Set AUTO_RENDER = True below when you are happy with the preview.

import bpy
import math
import random
import os
from mathutils import Vector
from pathlib import Path

# ---------------------------------------------------------------------------
# USER CONFIG
# ---------------------------------------------------------------------------

FPS = 24
FRAME_END = 1320                    # ~55 s
RENDER_X = 1920
RENDER_Y = 1080
RENDER_PERCENT = 50                 # use 100 for final
AUTO_RENDER = False
SAVE_BLEND = True

OUTPUT_DIR = "//QFG_CINEMATIC/"
OUTPUT_FILE = "BSMSG_QFG_Cinematic"
BLEND_FILE = "//BSMSG_QFG_Cinematic.blend"

QFG_GRID = 32
QFG_DT = 0.002
QFG_SUBSTEPS = 2
QFG_SEED = 1337
QFG_BACKEND = "NUMPY"

# If True, script stops if QFG SDK cannot be imported or body states cannot
# be obtained. Keep this True for a genuine QFG-driven demo.
STRICT_QFG = True

# ---------------------------------------------------------------------------
# TIMELINE / SHOTS
# ---------------------------------------------------------------------------

SHOT1 = (1, 96)
SHOT2 = (97, 288)
SHOT3 = (289, 528)
SHOT4 = (529, 816)
SHOT5 = (817, 1104)
SHOT6 = (1105, 1320)

# ---------------------------------------------------------------------------
# COLOR PALETTE
# ---------------------------------------------------------------------------

C_CYAN   = (0.015, 0.55, 1.0, 1.0)
C_BLUE   = (0.02, 0.12, 0.8, 1.0)
C_VIOLET = (0.45, 0.05, 1.0, 1.0)
C_WHITE  = (0.92, 0.97, 1.0, 1.0)
C_AMBER  = (1.0, 0.20, 0.025, 1.0)
C_DARK   = (0.003, 0.006, 0.012, 1.0)

# ---------------------------------------------------------------------------
# CLEAN SCENE
# ---------------------------------------------------------------------------

def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for db in (
        bpy.data.curves,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        # Don't aggressively remove datablocks here; Blender cleans unused
        # datablocks on save/reload and it is safer across versions.
        pass

clean_scene()

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = FRAME_END
scene.render.fps = FPS
scene.render.resolution_x = RENDER_X
scene.render.resolution_y = RENDER_Y
scene.render.resolution_percentage = RENDER_PERCENT
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUTPUT_DIR
# Blender changed the Eevee Python enum between releases.
# Some builds expose BLENDER_EEVEE_NEXT, while newer builds expose BLENDER_EEVEE.
# Select the available engine automatically.
try:
    engine_items = scene.render.bl_rna.properties["engine"].enum_items
    engine_ids = {item.identifier for item in engine_items}
except Exception:
    engine_ids = set()

if "BLENDER_EEVEE_NEXT" in engine_ids:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
elif "BLENDER_EEVEE" in engine_ids:
    scene.render.engine = "BLENDER_EEVEE"
elif "CYCLES" in engine_ids:
    scene.render.engine = "CYCLES"
else:
    raise RuntimeError(
        "No supported render engine found. Available engines: "
        + ", ".join(sorted(engine_ids))
    )

print("Cinematic render engine:", scene.render.engine)

# Try to enable motion blur where the property exists.
if hasattr(scene.render, "use_motion_blur"):
    scene.render.use_motion_blur = True

# Color management.
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass

# World background.
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.001, 0.002, 0.006, 1.0)
    bg.inputs["Strength"].default_value = 0.025

# ---------------------------------------------------------------------------
# COLLECTIONS
# ---------------------------------------------------------------------------

def new_collection(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

COL_ENV    = new_collection("00_ENV")
COL_FIELD  = new_collection("10_QFG_FIELD")
COL_DYN    = new_collection("20_QFG_DYNAMICS")
COL_ATLAS  = new_collection("30_BSM_SG_ATLAS")
COL_MULTI  = new_collection("40_QFG_MULTIBODY")
COL_TEXT   = new_collection("90_TEXT")
COL_HIDDEN = new_collection("99_HIDDEN")

def move_to_collection(obj, coll):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)

# ---------------------------------------------------------------------------
# MATERIAL HELPERS
# ---------------------------------------------------------------------------

def input_by_names(node, names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None

def make_emission_material(name, color, strength=5.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = strength
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat, em

def make_principled_material(name, base, metallic=0.8, roughness=0.22,
                             emission=None, emission_strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        s = input_by_names(bsdf, ["Base Color"])
        if s: s.default_value = base
        s = input_by_names(bsdf, ["Metallic"])
        if s: s.default_value = metallic
        s = input_by_names(bsdf, ["Roughness"])
        if s: s.default_value = roughness
        if emission:
            s = input_by_names(bsdf, ["Emission Color", "Emission"])
            if s: s.default_value = emission
            s = input_by_names(bsdf, ["Emission Strength"])
            if s: s.default_value = emission_strength
    return mat

MAT_FIELD, EM_FIELD = make_emission_material("MAT_QFG_FIELD", C_CYAN, 4.0)
MAT_FIELD2, EM_FIELD2 = make_emission_material("MAT_QFG_FIELD_VIOLET", C_VIOLET, 5.0)
MAT_GRAPH, EM_GRAPH = make_emission_material("MAT_Jij", C_CYAN, 6.0)
MAT_FORCE, EM_FORCE = make_emission_material("MAT_FORCE", C_AMBER, 8.0)
MAT_TEXT, EM_TEXT = make_emission_material("MAT_TEXT", C_WHITE, 4.0)
MAT_FLASH, EM_FLASH = make_emission_material("MAT_FLASH", C_WHITE, 20.0)

MAT_BODY_A = make_principled_material(
    "MAT_BODY_A", (0.01, 0.05, 0.12, 1), 0.92, 0.12, C_CYAN, 1.6)
MAT_BODY_B = make_principled_material(
    "MAT_BODY_B", (0.08, 0.01, 0.12, 1), 0.92, 0.12, C_VIOLET, 1.6)
MAT_SITE = make_principled_material(
    "MAT_ATLAS_SITE", (0.015, 0.03, 0.08, 1), 0.8, 0.18, C_CYAN, 1.2)
MAT_SITE_ALT = make_principled_material(
    "MAT_ATLAS_SITE_ALT", (0.07, 0.01, 0.10, 1), 0.8, 0.18, C_VIOLET, 1.2)

# ---------------------------------------------------------------------------
# COMPOSITOR GLOW — Blender 4.x / 5.x compatible
# ---------------------------------------------------------------------------

def configure_glare_node(glare):
    """Configure Glare across Blender API generations."""
    try:
        glare.glare_type = 'FOG_GLOW'
    except Exception:
        pass

    try:
        glare.quality = 'HIGH'
    except Exception:
        pass

    # Blender 5.x moved several Glare settings to node inputs.
    try:
        if "Threshold" in glare.inputs:
            glare.inputs["Threshold"].default_value = 0.6
        elif hasattr(glare, "threshold"):
            glare.threshold = 0.6
    except Exception:
        pass

    try:
        if "Size" in glare.inputs:
            # Blender 5.x uses a normalized Size input.
            glare.inputs["Size"].default_value = 0.65
        elif hasattr(glare, "size"):
            glare.size = 7
    except Exception:
        pass

    try:
        if "Strength" in glare.inputs:
            glare.inputs["Strength"].default_value = 0.85
    except Exception:
        pass


def setup_compositor_glow(scene):
    """
    Blender <=4.x used Scene.node_tree.
    Blender 5.x replaced the scene compositor with compositor effects/node groups.
    Failure of the post effect must never abort the QFG cinematic itself.
    """
    try:
        scene.render.use_compositing = True
    except Exception:
        pass

    # -------------------------------------------------------
    # Blender 5.x compositor-effects API
    # -------------------------------------------------------
    if hasattr(scene, "compositor_effects"):
        try:
            effects = scene.compositor_effects

            # Remove effects previously created by this script only.
            for effect in list(effects):
                if effect.name.startswith("QFG Cinematic"):
                    effects.remove(effect)

            tree_name = "QFG_CINEMATIC_GLOW_TREE"
            old_tree = bpy.data.node_groups.get(tree_name)
            if old_tree is not None:
                bpy.data.node_groups.remove(old_tree, do_unlink=True)

            tree = bpy.data.node_groups.new(
                name=tree_name,
                type="CompositorNodeTree"
            )

            # Scene compositor effects receive the rendered image through the
            # first group input and return the result through the first output.
            try:
                tree.interface.new_socket(
                    name="Image",
                    in_out='INPUT',
                    socket_type='NodeSocketColor'
                )
                tree.interface.new_socket(
                    name="Image",
                    in_out='OUTPUT',
                    socket_type='NodeSocketColor'
                )
            except Exception:
                # Some Blender builds initialize default compositor sockets.
                pass

            group_in = tree.nodes.new("NodeGroupInput")
            group_out = tree.nodes.new("NodeGroupOutput")
            glare = tree.nodes.new("CompositorNodeGlare")
            glare.name = "QFG_FOG_GLOW"
            configure_glare_node(glare)

            # Locate image sockets robustly.
            in_socket = group_in.outputs.get("Image")
            glare_in = glare.inputs.get("Image")
            glare_out = glare.outputs.get("Image")
            out_socket = group_out.inputs.get("Image")

            if not all((in_socket, glare_in, glare_out, out_socket)):
                raise RuntimeError(
                    "Could not locate compositor Image sockets in Blender 5.x."
                )

            tree.links.new(in_socket, glare_in)
            tree.links.new(glare_out, out_socket)

            effect = effects.new("QFG Cinematic Glow")
            effect.node_group = tree

            if hasattr(effect, "enable_for_render"):
                effect.enable_for_render = True
            if hasattr(effect, "enable_for_preview"):
                effect.enable_for_preview = True

            print("QFG compositor: Blender 5.x Scene Compositor Effect enabled")
            return True

        except Exception as exc:
            print("WARNING: Blender 5.x compositor glow disabled:", exc)
            print("The cinematic will continue without compositor Fog Glow.")
            return False

    # -------------------------------------------------------
    # Legacy Blender compositor API
    # -------------------------------------------------------
    if hasattr(scene, "node_tree"):
        try:
            scene.use_nodes = True
            nt = scene.node_tree
            nt.nodes.clear()

            rl = nt.nodes.new("CompositorNodeRLayers")
            glare = nt.nodes.new("CompositorNodeGlare")
            configure_glare_node(glare)
            comp = nt.nodes.new("CompositorNodeComposite")

            nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
            nt.links.new(glare.outputs["Image"], comp.inputs["Image"])

            print("QFG compositor: legacy Scene.node_tree enabled")
            return True

        except Exception as exc:
            print("WARNING: legacy compositor glow disabled:", exc)
            return False

    print("WARNING: no supported compositor API found; continuing without glow.")
    return False


COMPOSITOR_GLOW_ENABLED = setup_compositor_glow(scene)

# ---------------------------------------------------------------------------
# GENERIC OBJECT HELPERS
# ---------------------------------------------------------------------------

def smooth_object(obj):
    if obj.type == 'MESH':
        for p in obj.data.polygons:
            p.use_smooth = True

def add_ico(name, loc, radius, mat, coll, subdivisions=3):
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=subdivisions, radius=radius, location=loc
    )
    obj = bpy.context.object
    obj.name = name
    move_to_collection(obj, coll)
    if mat:
        obj.data.materials.append(mat)
    smooth_object(obj)
    return obj

def add_uv(name, loc, radius, mat, coll, segments=64, rings=32):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, radius=radius, location=loc
    )
    obj = bpy.context.object
    obj.name = name
    move_to_collection(obj, coll)
    if mat:
        obj.data.materials.append(mat)
    smooth_object(obj)
    return obj

def add_curve(name, points, bevel, mat, coll):
    cu = bpy.data.curves.new(name + "_CURVE", 'CURVE')
    cu.dimensions = '3D'
    cu.resolution_u = 2
    cu.bevel_depth = bevel
    cu.bevel_resolution = 4
    spl = cu.splines.new('POLY')
    spl.points.add(len(points)-1)
    for p, co in zip(spl.points, points):
        p.co = (*co, 1.0)
    obj = bpy.data.objects.new(name, cu)
    coll.objects.link(obj)
    if mat:
        cu.materials.append(mat)
    return obj

def add_ring(name, loc, radius, mat, coll, rot=(0,0,0), bevel=0.018):
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    move_to_collection(obj, coll)
    obj.data.bevel_depth = bevel
    obj.data.bevel_resolution = 4
    obj.data.materials.append(mat)
    return obj

def iter_action_fcurves(idblock):
    """
    Return F-Curves for both legacy Blender Actions and Blender 4.4+/5.x
    layered Actions.

    Blender 5.x stores animation channels as:
        Action -> Layer -> Keyframe Strip -> Channelbag -> F-Curves
    instead of Action.fcurves.
    """
    ad = getattr(idblock, "animation_data", None)
    action = getattr(ad, "action", None) if ad else None
    if action is None:
        return []

    # -------------------------------------------------------
    # Legacy Blender API
    # -------------------------------------------------------
    legacy_fcurves = getattr(action, "fcurves", None)
    if legacy_fcurves is not None:
        try:
            return list(legacy_fcurves)
        except Exception:
            pass

    # -------------------------------------------------------
    # Blender 4.4+ / 5.x layered Action API
    # -------------------------------------------------------
    curves = []

    # Prefer the channelbag belonging to this datablock's action slot.
    active_slot = getattr(ad, "action_slot", None)

    try:
        for layer in action.layers:
            for strip in layer.strips:
                # Only keyframe strips expose animation channelbags.
                if getattr(strip, "type", None) != 'KEYFRAME':
                    continue

                # Most precise path: retrieve the channelbag for this slot.
                if active_slot is not None and hasattr(strip, "channelbag"):
                    try:
                        bag = strip.channelbag(active_slot)
                        if bag is not None:
                            curves.extend(list(bag.fcurves))
                            continue
                    except Exception:
                        pass

                # Robust fallback: iterate every channelbag on the strip.
                for bag in getattr(strip, "channelbags", ()):
                    curves.extend(list(bag.fcurves))

    except Exception as exc:
        print(
            f"WARNING: could not enumerate layered Action F-Curves for "
            f"{getattr(idblock, 'name', '<unnamed>')}: {exc}"
        )

    # Remove duplicates while preserving order.
    unique = []
    seen = set()
    for fc in curves:
        try:
            key = fc.as_pointer()
        except Exception:
            key = id(fc)
        if key not in seen:
            seen.add(key)
            unique.append(fc)

    return unique


def set_linear_keys(idblock, data_path="location"):
    """Set matching animation channels to linear interpolation."""
    for fc in iter_action_fcurves(idblock):
        if fc.data_path == data_path or data_path in fc.data_path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def set_all_linear(idblock):
    """Set every keyframe on this datablock's Action to linear interpolation."""
    for fc in iter_action_fcurves(idblock):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

def visible_scale(obj, start, end, scale=1.0, pre=2, post=2):
    obj.scale = (0,0,0)
    obj.keyframe_insert("scale", frame=max(1, start-pre))
    obj.scale = (scale,scale,scale)
    obj.keyframe_insert("scale", frame=start)
    obj.keyframe_insert("scale", frame=end)
    obj.scale = (0,0,0)
    obj.keyframe_insert("scale", frame=min(FRAME_END, end+post))
    set_all_linear(obj)

def grow_curve(obj, start, end):
    cu = obj.data
    cu.bevel_factor_mapping_start = 'RESOLUTION'
    cu.bevel_factor_mapping_end = 'RESOLUTION'
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=start)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=end)

def key_material_strength(emission_node, frame_values):
    for f, value in frame_values:
        emission_node.inputs["Strength"].default_value = value
        emission_node.inputs["Strength"].keyframe_insert("default_value", frame=f)

# ---------------------------------------------------------------------------
# CAMERA + FOCUS
# ---------------------------------------------------------------------------

bpy.ops.object.camera_add(location=(0, -13, 5))
cam = bpy.context.object
cam.name = "QFG_CINEMATIC_CAMERA"
move_to_collection(cam, COL_ENV)
scene.camera = cam
cam.data.lens = 55
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 1.7

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,0))
focus = bpy.context.object
focus.name = "CAM_FOCUS"
move_to_collection(focus, COL_ENV)
cam.data.dof.focus_object = focus

def look_at(obj, target):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def camera_key(frame, loc, target, lens=55):
    cam.location = loc
    look_at(cam, target)
    cam.data.lens = lens
    cam.keyframe_insert("location", frame=frame)
    cam.keyframe_insert("rotation_euler", frame=frame)
    cam.data.keyframe_insert("lens", frame=frame)

    focus.location = target
    focus.keyframe_insert("location", frame=frame)

# Cinematic camera path.
camera_key(1,    (0.0, -16.0, 5.5), (0,0,0), 65)
camera_key(96,   (0.0, -9.5, 2.0),  (0,0,0), 52)

camera_key(97,   (-7.0, -8.0, 3.8), (0,0,0), 58)
camera_key(288,  (6.0, -6.0, 2.3),  (0,0,0), 68)

camera_key(289,  (0.0, -14.0, 3.0), (0,0,0), 58)
camera_key(528,  (0.0, -9.0, 1.3),  (0,0,0), 72)

camera_key(529,  (7.5, -8.0, 5.0),  (0,0,0), 64)
camera_key(816,  (-6.8,-7.0, 3.0),  (0,0,0), 58)

camera_key(817,  (0.0,-12.0, 6.5),  (0,0,0), 60)
camera_key(1104, (7.5,-6.0, 2.3),   (0,0,0), 70)

camera_key(1105, (7.2,-7.2, 4.0),   (0,0,0), 72)
camera_key(1320, (-7.5,-6.5, 3.2),  (0,0,0), 58)

set_all_linear(cam)
set_all_linear(focus)

# ---------------------------------------------------------------------------
# LIGHTING
# ---------------------------------------------------------------------------

def add_area(name, loc, energy, size, color):
    bpy.ops.object.light_add(type='AREA', location=loc)
    l = bpy.context.object
    l.name = name
    move_to_collection(l, COL_ENV)
    l.data.energy = energy
    l.data.shape = 'DISK'
    l.data.size = size
    l.data.color = color[:3]
    look_at(l, (0,0,0))
    return l

def add_point(name, loc, energy, color):
    bpy.ops.object.light_add(type='POINT', location=loc)
    l = bpy.context.object
    l.name = name
    move_to_collection(l, COL_ENV)
    l.data.energy = energy
    l.data.color = color[:3]
    l.data.shadow_soft_size = 1.5
    return l

key_l = add_area("KEY_CYAN", (-5,-4,7), 1150, 5.0, C_CYAN)
rim_l = add_area("RIM_VIOLET", (6,2,4), 900, 4.0, C_VIOLET)
fill_l = add_area("FILL_WHITE", (0,-2,8), 550, 3.0, C_WHITE)

# A subtle central light.
core_l = add_point("FIELD_CORE_LIGHT", (0,0,0), 250, C_CYAN)

# ---------------------------------------------------------------------------
# CAMERA-ATTACHED TITLES
# ---------------------------------------------------------------------------

def add_camera_text(name, body, start, end, loc=(-3.0, 1.4, -6.0), size=0.34):
    cu = bpy.data.curves.new(name + "_FONT", 'FONT')
    cu.body = body
    cu.align_x = 'LEFT'
    cu.align_y = 'CENTER'
    cu.size = size
    cu.extrude = 0.002
    obj = bpy.data.objects.new(name, cu)
    COL_TEXT.objects.link(obj)
    obj.parent = cam
    obj.location = loc
    obj.rotation_euler = (0,0,0)
    cu.materials.append(MAT_TEXT)
    visible_scale(obj, start, end, 1.0, pre=6, post=6)
    return obj

add_camera_text("TXT_01", "QFG // FIELD AWAKENING", 18, 88, (-3.6,1.65,-6.0), 0.30)
add_camera_text("TXT_02", "SOLITON FIELD // COHERENT STRUCTURE", 120, 266, (-3.9,1.65,-6.0), 0.26)
add_camera_text("TXT_03", "QFG DYNAMICS // REAL-TIME BODY COUPLING", 312, 500, (-4.2,1.65,-6.0), 0.25)
add_camera_text("TXT_04", "BSM-SG ATLAS // J_ij INTERACTION GRAPH", 555, 790, (-4.0,1.65,-6.0), 0.25)
add_camera_text("TXT_05", "QFG WORLD // MULTI-BODY FIELD FEEDBACK", 838, 1080, (-4.2,1.65,-6.0), 0.24)
add_camera_text("TXT_06", "BSM-SG / QFG\nUNIFIED FIELD SIMULATION", 1140, 1305, (-3.8,1.55,-6.0), 0.34)

# ---------------------------------------------------------------------------
# QFG SDK ADAPTER
# ---------------------------------------------------------------------------

QFG_AVAILABLE = False
QFG_IMPORT_ERROR = None
QFG_PACKAGE_ROOT = None
QFG_SDK_MODULE = None

def load_qfg_sdk():
    """
    Locate QFG Lab 5.2 both as a legacy add-on and as a Blender 5.x Extension.

    Legacy install:
        qfg_lab_52.sdk

    Blender Extensions are namespaced, typically:
        bl_ext.user_default.qfg_lab_52.sdk

    The repository namespace is deliberately NOT hard-coded; we inspect the
    enabled add-ons and already-loaded modules first.
    """
    import importlib
    import sys

    candidates = []

    # 1) Enabled Blender add-ons/extensions are the strongest source of truth.
    try:
        addon_keys = list(bpy.context.preferences.addons.keys())
    except Exception:
        addon_keys = []

    print("QFG SDK discovery: enabled add-on keys containing 'qfg':")
    for key in addon_keys:
        if "qfg" in key.lower() or "bsm" in key.lower():
            print("   ", key)

        kl = key.lower()
        if (
            kl.endswith("qfg_lab_52")
            or ".qfg_lab_52" in kl
            or "qfg_dynamics" in kl
        ):
            candidates.append(key)

    # 2) Already imported extension modules.
    for modname in list(sys.modules.keys()):
        ml = modname.lower()
        if (
            ml.endswith("qfg_lab_52")
            or ".qfg_lab_52" in ml
        ):
            root = modname
            if ".sdk" in root:
                root = root.split(".sdk", 1)[0]
            candidates.append(root)

    # 3) Known packaging forms as fallbacks.
    candidates.extend([
        "qfg_lab_52",
        "bl_ext.user_default.qfg_lab_52",
        "bl_ext.blender_org.qfg_lab_52",
    ])

    # Normalize and keep ordering.
    roots = []
    seen = set()
    for c in candidates:
        c = str(c).strip(".")
        if not c:
            continue

        # An enabled key may itself point to a submodule. Walk back to the
        # qfg_lab_52 package when possible.
        parts = c.split(".")
        if "qfg_lab_52" in parts:
            idx = parts.index("qfg_lab_52")
            c = ".".join(parts[:idx+1])

        if c not in seen:
            seen.add(c)
            roots.append(c)

    errors = []

    for root in roots:
        sdk_name = root + ".sdk"
        try:
            sdk = importlib.import_module(sdk_name)

            required = (
                "create_world",
                "EngineConfig",
                "WorldConfig",
                "ActorSpec",
                "BodySpec",
            )
            missing = [name for name in required if not hasattr(sdk, name)]
            if missing:
                errors.append(
                    f"{sdk_name}: imported but missing {', '.join(missing)}"
                )
                continue

            print("QFG SDK FOUND:", sdk_name)
            try:
                print("QFG SDK file:", sdk.__file__)
            except Exception:
                pass

            return root, sdk, errors

        except Exception as exc:
            errors.append(f"{sdk_name}: {type(exc).__name__}: {exc}")

    return None, None, errors


QFG_PACKAGE_ROOT, QFG_SDK_MODULE, _qfg_import_errors = load_qfg_sdk()

if QFG_SDK_MODULE is not None:
    create_world = QFG_SDK_MODULE.create_world
    EngineConfig = QFG_SDK_MODULE.EngineConfig
    WorldConfig = QFG_SDK_MODULE.WorldConfig
    ActorSpec = QFG_SDK_MODULE.ActorSpec
    BodySpec = QFG_SDK_MODULE.BodySpec
    QFG_AVAILABLE = True
else:
    QFG_IMPORT_ERROR = "\n".join(_qfg_import_errors)

if STRICT_QFG and not QFG_AVAILABLE:
    enabled_qfg = []
    try:
        enabled_qfg = [
            k for k in bpy.context.preferences.addons.keys()
            if "qfg" in k.lower() or "bsm" in k.lower()
        ]
    except Exception:
        pass

    raise RuntimeError(
        "QFG Dynamics appears to be enabled, but the cinematic could not "
        "resolve its SDK module.\n\n"
        "Enabled QFG/BSM add-on keys:\n  "
        + ("\n  ".join(enabled_qfg) if enabled_qfg else "<none detected>")
        + "\n\nSDK import attempts:\n  "
        + ("\n  ".join(_qfg_import_errors) if _qfg_import_errors else "<none>")
        + "\n\nThis is a package-namespace/API discovery error, not evidence "
          "that the plug-in is disabled."
    )

def xyz_from(value):
    if value is None:
        return None

    if isinstance(value, Vector):
        return Vector(value)

    if isinstance(value, (tuple, list)) and len(value) >= 3:
        try:
            return Vector((float(value[0]), float(value[1]), float(value[2])))
        except Exception:
            pass

    if isinstance(value, dict):
        # direct xyz
        if all(k in value for k in ("x","y","z")):
            return Vector((float(value["x"]), float(value["y"]), float(value["z"])))
        # nested state variants
        for key in ("position", "pos", "location", "value", "vector", "field",
                    "force", "gradient"):
            if key in value:
                v = xyz_from(value[key])
                if v is not None:
                    return v

    for attr in ("position", "pos", "location", "value", "vector", "field",
                 "force", "gradient"):
        if hasattr(value, attr):
            v = xyz_from(getattr(value, attr))
            if v is not None:
                return v

    if all(hasattr(value, k) for k in ("x","y","z")):
        try:
            return Vector((float(value.x), float(value.y), float(value.z)))
        except Exception:
            pass

    return None

def _safe_vars(obj):
    try:
        return vars(obj)
    except Exception:
        return {}


def _body_name_candidates(obj):
    """Collect likely body identifiers/names from arbitrary SDK objects."""
    out = set()
    if obj is None:
        return out

    if isinstance(obj, str):
        out.add(obj)
        return out

    if isinstance(obj, dict):
        for key in ("name", "id", "body_id", "body_name", "uid", "key"):
            if key in obj:
                try:
                    out.add(str(obj[key]))
                except Exception:
                    pass
        for key in ("spec", "body", "state"):
            if key in obj:
                out |= _body_name_candidates(obj[key])
        return out

    for key in ("name", "id", "body_id", "body_name", "uid", "key"):
        if hasattr(obj, key):
            try:
                out.add(str(getattr(obj, key)))
            except Exception:
                pass

    for key in ("spec", "body", "state"):
        if hasattr(obj, key):
            try:
                out |= _body_name_candidates(getattr(obj, key))
            except Exception:
                pass

    return out


def _find_named_body(container, handle, name, depth=0, seen=None):
    """
    Search nested SDK containers for the requested body.
    Supports dict/list/tuple/dataclass-like objects and Blender-independent
    Python objects used by QFG Dynamics 1.0.0-alpha.
    """
    if container is None or depth > 5:
        return None

    if seen is None:
        seen = set()

    try:
        oid = id(container)
        if oid in seen:
            return None
        seen.add(oid)
    except Exception:
        pass

    wanted = {str(name)}
    if handle is not None:
        try:
            wanted.add(str(handle))
        except Exception:
            pass

    # The object itself may be the requested body/state.
    names = _body_name_candidates(container)
    if names & wanted:
        p = xyz_from(container)
        if p is not None:
            return container

    # Dict: direct key lookup, then nested scan.
    if isinstance(container, dict):
        for key in (name, handle, str(name), str(handle) if handle is not None else None):
            if key is None:
                continue
            try:
                if key in container:
                    item = container[key]
                    if xyz_from(item) is not None:
                        return item
            except Exception:
                pass

        for key, value in container.items():
            try:
                if str(key) in wanted and xyz_from(value) is not None:
                    return value
            except Exception:
                pass

        for value in container.values():
            found = _find_named_body(value, handle, name, depth+1, seen)
            if found is not None:
                return found
        return None

    # List/tuple/set.
    if isinstance(container, (list, tuple, set)):
        for value in container:
            found = _find_named_body(value, handle, name, depth+1, seen)
            if found is not None:
                return found
        return None

    # Generic dataclass / SDK object.
    attrs = _safe_vars(container)
    if attrs:
        # Common nested state fields first.
        for key in (
            "state", "body_state", "snapshot", "spec", "body",
            "transform", "kinematics", "dynamic_state"
        ):
            if key in attrs:
                found = _find_named_body(attrs[key], handle, name, depth+1, seen)
                if found is not None:
                    return found

        # Then inspect all non-private attributes.
        for key, value in attrs.items():
            if str(key).startswith("_"):
                continue
            if isinstance(value, (str, int, float, bool, bytes)):
                continue
            found = _find_named_body(value, handle, name, depth+1, seen)
            if found is not None:
                return found

    return None


def container_lookup(container, handle, name):
    """Backwards-compatible wrapper used by the cinematic adapter."""
    return _find_named_body(container, handle, name)


_BODY_SNAPSHOT_MODE_LOGGED = False


def _call_body_snapshot(world, handle, name):
    """
    QFG Dynamics 1.0.0-alpha exposes QFGWorld.body_snapshot.
    Different alpha builds may accept body handle, name, index, or no argument.
    Probe those forms safely and return the requested snapshot/state.
    """
    global _BODY_SNAPSHOT_MODE_LOGGED

    fn = getattr(world, "body_snapshot", None)
    if not callable(fn):
        return None

    attempts = []

    # Most likely signatures first.
    for label, args in (
        ("handle", (handle,)),
        ("name", (name,)),
    ):
        if args[0] is None:
            continue
        try:
            value = fn(*args)
            attempts.append((label, value))
            p = xyz_from(value)
            if p is not None:
                if not _BODY_SNAPSHOT_MODE_LOGGED:
                    print(f"QFG body state source: world.body_snapshot({label})")
                    _BODY_SNAPSHOT_MODE_LOGGED = True
                return value

            found = _find_named_body(value, handle, name)
            if found is not None and xyz_from(found) is not None:
                if not _BODY_SNAPSHOT_MODE_LOGGED:
                    print(f"QFG body state source: world.body_snapshot({label}) nested result")
                    _BODY_SNAPSHOT_MODE_LOGGED = True
                return found
        except (TypeError, KeyError, IndexError, ValueError, AttributeError):
            pass
        except Exception:
            # Alpha SDK can throw implementation-specific lookup exceptions.
            pass

    # Some builds expose body_snapshot() as an all-body snapshot.
    try:
        value = fn()
        found = _find_named_body(value, handle, name)
        if found is not None and xyz_from(found) is not None:
            if not _BODY_SNAPSHOT_MODE_LOGGED:
                print("QFG body state source: world.body_snapshot() aggregate")
                _BODY_SNAPSHOT_MODE_LOGGED = True
            return found
    except Exception:
        pass

    return None


def _resolve_world_bodies(world):
    """Return world.bodies whether it is a property or a zero-arg method."""
    bodies = getattr(world, "bodies", None)
    if callable(bodies):
        try:
            bodies = bodies()
        except Exception:
            return None
    return bodies


def extract_body_position(world, result, handle, name):
    """
    Resolve a QFG body position across SDK generations.

    Priority for QFG Dynamics 1.0.0-alpha:
      1. world.body_snapshot(...)
      2. world.bodies
      3. world.snapshot(...)
      4. step-result state containers
      5. returned body handle itself
      6. legacy get_body/get_body_state APIs
    """

    # -------------------------------------------------------
    # 1. Current 1.0.0-alpha API: body_snapshot
    # -------------------------------------------------------
    snap = _call_body_snapshot(world, handle, name)
    p = xyz_from(snap)
    if p is not None:
        return p

    # -------------------------------------------------------
    # 2. Current 1.0.0-alpha body collection
    # -------------------------------------------------------
    bodies = _resolve_world_bodies(world)
    found = _find_named_body(bodies, handle, name)
    p = xyz_from(found)
    if p is not None:
        global _BODY_SNAPSHOT_MODE_LOGGED
        if not _BODY_SNAPSHOT_MODE_LOGGED:
            print("QFG body state source: world.bodies")
            _BODY_SNAPSHOT_MODE_LOGGED = True
        return p

    # If there are only a few bodies and add_body returned an integer index/id,
    # support list-like indexing explicitly.
    if bodies is not None and isinstance(handle, int):
        try:
            item = bodies[handle]
            p = xyz_from(item)
            if p is not None:
                if not _BODY_SNAPSHOT_MODE_LOGGED:
                    print("QFG body state source: world.bodies[index]")
                    _BODY_SNAPSHOT_MODE_LOGGED = True
                return p
        except Exception:
            pass

    # -------------------------------------------------------
    # 3. Whole-world snapshot API, present in some alpha builds
    # -------------------------------------------------------
    snapshot_fn = getattr(world, "snapshot", None)
    if callable(snapshot_fn):
        try:
            snapshot = snapshot_fn()
            found = _find_named_body(snapshot, handle, name)
            p = xyz_from(found)
            if p is not None:
                if not _BODY_SNAPSHOT_MODE_LOGGED:
                    print("QFG body state source: world.snapshot()")
                    _BODY_SNAPSHOT_MODE_LOGGED = True
                return p
        except Exception:
            pass

    # -------------------------------------------------------
    # 4. Step result containers
    # -------------------------------------------------------
    if result is not None:
        # Result itself may be or contain a snapshot.
        found = _find_named_body(result, handle, name)
        p = xyz_from(found)
        if p is not None:
            if not _BODY_SNAPSHOT_MODE_LOGGED:
                print("QFG body state source: world.step() result")
                _BODY_SNAPSHOT_MODE_LOGGED = True
            return p

        for attr in (
            "body_states", "states", "bodies", "body_results",
            "snapshot", "body_snapshot"
        ):
            if hasattr(result, attr):
                value = getattr(result, attr)
                if callable(value):
                    try:
                        value = value()
                    except Exception:
                        continue
                found = _find_named_body(value, handle, name)
                p = xyz_from(found)
                if p is not None:
                    if not _BODY_SNAPSHOT_MODE_LOGGED:
                        print(f"QFG body state source: step_result.{attr}")
                        _BODY_SNAPSHOT_MODE_LOGGED = True
                    return p

    # -------------------------------------------------------
    # 5. add_body() may return a mutable Body object.
    # -------------------------------------------------------
    p = xyz_from(handle)
    if p is not None:
        if not _BODY_SNAPSHOT_MODE_LOGGED:
            print("QFG body state source: add_body() returned object")
            _BODY_SNAPSHOT_MODE_LOGGED = True
        return p

    # -------------------------------------------------------
    # 6. Legacy SDK getter methods
    # -------------------------------------------------------
    for getter_name in ("get_body", "body", "get_body_state"):
        getter = getattr(world, getter_name, None)
        if callable(getter):
            for key in (handle, name):
                if key is None:
                    continue
                try:
                    item = getter(key)
                    p = xyz_from(item)
                    if p is not None:
                        if not _BODY_SNAPSHOT_MODE_LOGGED:
                            print(f"QFG body state source: world.{getter_name}()")
                            _BODY_SNAPSHOT_MODE_LOGGED = True
                        return p
                except Exception:
                    pass

    return None


def qfg_body_debug_dump(world, handle, name):
    """Compact diagnostic only used if state extraction still fails."""
    import inspect

    lines = []
    lines.append(f"body name={name!r}, handle={handle!r}, handle_type={type(handle)!r}")

    fn = getattr(world, "body_snapshot", None)
    if callable(fn):
        try:
            lines.append(f"body_snapshot signature: {inspect.signature(fn)}")
        except Exception:
            lines.append("body_snapshot signature: <unavailable>")

    bodies = _resolve_world_bodies(world)
    lines.append(f"world.bodies type: {type(bodies)!r}")
    try:
        lines.append(f"world.bodies repr: {repr(bodies)[:1200]}")
    except Exception:
        pass

    if bodies is not None:
        try:
            if isinstance(bodies, dict):
                lines.append(f"world.bodies keys: {list(bodies.keys())[:20]!r}")
            else:
                first = list(bodies)[:3]
                lines.append(f"first bodies: {repr(first)[:1200]}")
                for idx, item in enumerate(first):
                    lines.append(
                        f"body[{idx}] type={type(item)!r} attrs="
                        f"{[a for a in dir(item) if not a.startswith('_')][:60]!r}"
                    )
                    lines.append(f"body[{idx}] vars={repr(_safe_vars(item))[:1200]}")
        except Exception as exc:
            lines.append(f"world.bodies inspection error: {exc!r}")

    return "\n".join(lines)

def qfg_sample_density(world, pos):
    fn = getattr(world, "sample_density", None)
    if not callable(fn):
        return None
    try:
        v = fn(tuple(pos))
        if isinstance(v, (int,float)):
            return float(v)
        if isinstance(v, dict):
            for k in ("density","value"):
                if k in v:
                    return float(v[k])
        for k in ("density","value"):
            if hasattr(v,k):
                return float(getattr(v,k))
    except Exception:
        pass
    return None

def qfg_sample_field(world, pos):
    fn = getattr(world, "sample_field", None)
    if not callable(fn):
        return Vector((0,0,0))
    try:
        v = fn(tuple(pos))
        out = xyz_from(v)
        if out is not None:
            return out
    except Exception:
        pass
    return Vector((0,0,0))

def build_qfg_world(seed=QFG_SEED):
    if not QFG_AVAILABLE:
        return None
    ec = EngineConfig(grid_size=QFG_GRID, dt=QFG_DT, backend=QFG_BACKEND)
    wc = WorldConfig(
        substeps=QFG_SUBSTEPS,
        deterministic=True,
        seed=seed,
    )
    world = create_world(ec, wc)
    world.add_field_actor(
        ActorSpec(center=(0,0,0), radius=2.6, intensity=1.35)
    )
    return world

# ---------------------------------------------------------------------------
# SHOT 1/2: QFG FIELD CLOUD — SAMPLED FROM QFG WORLD
# ---------------------------------------------------------------------------

world_field = build_qfg_world(QFG_SEED)

def build_density_cloud(world, sample_count=850, keep=180):
    random.seed(20260929)
    samples = []

    # Sample deterministic positions in the QFG field.
    for _ in range(sample_count):
        p = Vector((
            random.uniform(-4.0,4.0),
            random.uniform(-4.0,4.0),
            random.uniform(-3.0,3.0),
        ))
        d = qfg_sample_density(world, p) if world else None
        if d is None:
            # Visual fallback only if density query is absent in a build.
            # The cinematic still uses QFGWorld dynamics later.
            r = p.length
            d = math.exp(-(r*r)/(2.2*2.2))
        samples.append((d,p))

    samples.sort(key=lambda x: x[0], reverse=True)
    chosen = samples[:keep]

    # One combined mesh: tiny tetra/icosphere-like diamonds around each sample.
    verts = []
    faces = []
    for d,p in chosen:
        s = 0.025 + 0.065 * max(0.0, min(1.0, float(d)))
        base = len(verts)
        verts.extend([
            tuple(p + Vector(( s, 0, 0))),
            tuple(p + Vector((-s, 0, 0))),
            tuple(p + Vector((0, s, 0))),
            tuple(p + Vector((0,-s, 0))),
            tuple(p + Vector((0, 0, s))),
            tuple(p + Vector((0, 0,-s))),
        ])
        faces.extend([
            (base+0,base+2,base+4), (base+2,base+1,base+4),
            (base+1,base+3,base+4), (base+3,base+0,base+4),
            (base+2,base+0,base+5), (base+1,base+2,base+5),
            (base+3,base+1,base+5), (base+0,base+3,base+5),
        ])

    me = bpy.data.meshes.new("QFG_FIELD_CLOUD_MESH")
    me.from_pydata(verts, [], faces)
    me.update()

    obj = bpy.data.objects.new("QFG_FIELD_CLOUD", me)
    COL_FIELD.objects.link(obj)
    me.materials.append(MAT_FIELD)
    return obj

field_cloud = build_density_cloud(world_field)
visible_scale(field_cloud, 1, FRAME_END, 1.0, pre=0, post=0)

field_cloud.rotation_euler = (0,0,0)
field_cloud.keyframe_insert("rotation_euler", frame=1)
field_cloud.rotation_euler = (math.radians(18), math.radians(-12), math.radians(85))
field_cloud.keyframe_insert("rotation_euler", frame=FRAME_END)

# Central coherent core.
field_core = add_ico("QFG_FIELD_CORE", (0,0,0), 0.18, MAT_FIELD, COL_FIELD, 4)
visible_scale(field_core, 25, FRAME_END, 1.0, pre=10, post=0)

# Concentric/tilted soliton rings.
soliton_rings = []
for i, (r, tilt) in enumerate([
    (0.75, (math.radians(63), 0, 0)),
    (1.05, (0, math.radians(70), math.radians(20))),
    (1.42, (math.radians(35), math.radians(50), math.radians(10))),
    (1.85, (math.radians(78), math.radians(25), math.radians(40))),
]):
    ring = add_ring(f"SOLITON_RING_{i:02d}", (0,0,0), r,
                    MAT_FIELD if i%2==0 else MAT_FIELD2, COL_FIELD,
                    rot=tilt, bevel=0.015 + i*0.003)
    visible_scale(ring, 105+i*12, FRAME_END, 1.0, pre=8, post=0)
    ring.rotation_euler = tilt
    ring.keyframe_insert("rotation_euler", frame=105+i*12)
    ring.rotation_euler = (
        tilt[0] + math.radians(140 if i%2==0 else -120),
        tilt[1] + math.radians(70),
        tilt[2] + math.radians(170),
    )
    ring.keyframe_insert("rotation_euler", frame=FRAME_END)
    set_all_linear(ring)
    soliton_rings.append(ring)

# Animate field emission intensity.
key_material_strength(EM_FIELD, [
    (1, 0.3), (35, 3.0), (120, 7.0), (250, 4.0),
    (500, 5.5), (820, 4.0), (1150, 6.0), (1320, 3.0)
])
key_material_strength(EM_FIELD2, [
    (1, 0.1), (110, 2.0), (180, 7.5), (290, 4.0),
    (820, 5.0), (1320, 3.0)
])

# ---------------------------------------------------------------------------
# SHOT 3: REAL QFG TWO-BODY DYNAMICS
# ---------------------------------------------------------------------------

def simulate_two_body():
    world = build_qfg_world(QFG_SEED + 1)
    if world is None:
        return None

    a = world.add_body(BodySpec(
        name="Cinematic_A",
        position=(-4.2,0.0,0.0),
        velocity=(4.2,0.20,0.0),
        mass=1.0,
        radius=0.48,
        field_coupling=8.0,
    ))
    b = world.add_body(BodySpec(
        name="Cinematic_B",
        position=(4.2,0.0,0.0),
        velocity=(-4.2,-0.20,0.0),
        mass=1.0,
        radius=0.48,
        field_coupling=8.0,
    ))

    pa = [Vector((-4.2,0,0))]
    pb = [Vector((4.2,0,0))]
    fa = [qfg_sample_field(world, pa[0])]
    fb = [qfg_sample_field(world, pb[0])]

    last_result = None
    for _ in range(239):
        last_result = world.step()
        p1 = extract_body_position(world, last_result, a, "Cinematic_A")
        p2 = extract_body_position(world, last_result, b, "Cinematic_B")

        if p1 is None or p2 is None:
            raise RuntimeError(
                "QFGWorld is stepping, but a body state still could not be resolved.\n\n"
                "A:\n" + qfg_body_debug_dump(world, a, "Cinematic_A") +
                "\n\nB:\n" + qfg_body_debug_dump(world, b, "Cinematic_B")
            )

        pa.append(Vector(p1))
        pb.append(Vector(p2))
        fa.append(qfg_sample_field(world, p1))
        fb.append(qfg_sample_field(world, p2))

    return world, pa, pb, fa, fb

two_body = simulate_two_body()

world_dyn, path_a, path_b, field_a, field_b = two_body

body_a = add_uv("QFG_BODY_A", path_a[0], 0.48, MAT_BODY_A, COL_DYN)
body_b = add_uv("QFG_BODY_B", path_b[0], 0.48, MAT_BODY_B, COL_DYN)

visible_scale(body_a, SHOT3[0], SHOT3[1], 1.0, pre=5, post=8)
visible_scale(body_b, SHOT3[0], SHOT3[1], 1.0, pre=5, post=8)

# Key real QFG positions.
for i, (pa,pb) in enumerate(zip(path_a, path_b)):
    f = SHOT3[0] + i
    body_a.location = pa
    body_b.location = pb
    body_a.keyframe_insert("location", frame=f)
    body_b.keyframe_insert("location", frame=f)

set_linear_keys(body_a)
set_linear_keys(body_b)

trail_a = add_curve("TRAIL_A", path_a, 0.025, MAT_FIELD, COL_DYN)
trail_b = add_curve("TRAIL_B", path_b, 0.025, MAT_FIELD2, COL_DYN)
grow_curve(trail_a, SHOT3[0], SHOT3[1]-8)
grow_curve(trail_b, SHOT3[0], SHOT3[1]-8)
visible_scale(trail_a, SHOT3[0], SHOT3[1], 1.0, pre=1, post=8)
visible_scale(trail_b, SHOT3[0], SHOT3[1], 1.0, pre=1, post=8)

# Collision flash at closest approach.
closest_i = min(
    range(len(path_a)),
    key=lambda i: (path_a[i]-path_b[i]).length
)
impact_frame = SHOT3[0] + closest_i
impact_pos = (path_a[closest_i] + path_b[closest_i]) * 0.5

flash = add_ico("QFG_IMPACT_FLASH", impact_pos, 0.13, MAT_FLASH, COL_DYN, 3)
flash.scale = (0,0,0)
flash.keyframe_insert("scale", frame=impact_frame-2)
flash.scale = (6.0,6.0,6.0)
flash.keyframe_insert("scale", frame=impact_frame+1)
flash.scale = (0,0,0)
flash.keyframe_insert("scale", frame=impact_frame+7)

impact_light = add_point("QFG_IMPACT_LIGHT", impact_pos, 0, C_WHITE)
impact_light.data.energy = 0
impact_light.data.keyframe_insert("energy", frame=impact_frame-2)
impact_light.data.energy = 5000
impact_light.data.keyframe_insert("energy", frame=impact_frame+1)
impact_light.data.energy = 0
impact_light.data.keyframe_insert("energy", frame=impact_frame+8)

scene.timeline_markers.new("QFG IMPACT", frame=impact_frame)

# ---------------------------------------------------------------------------
# FORCE ARROWS — driven by sample_field() from QFG world
# ---------------------------------------------------------------------------

def make_arrow(name, mat, coll):
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)

    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.035, depth=0.8)
    shaft = bpy.context.object
    shaft.name = name + "_SHAFT"
    move_to_collection(shaft, coll)
    shaft.data.materials.append(mat)
    shaft.parent = root
    shaft.location = (0,0,0.40)

    bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=0.10, radius2=0.0, depth=0.28)
    cone = bpy.context.object
    cone.name = name + "_HEAD"
    move_to_collection(cone, coll)
    cone.data.materials.append(mat)
    cone.parent = root
    cone.location = (0,0,0.94)
    return root

def orient_arrow(root, origin, vec, max_len=1.6):
    v = Vector(vec)
    L = min(max_len, max(0.001, v.length * 0.55))
    root.location = origin
    if v.length > 1e-8:
        root.rotation_euler = v.to_track_quat('Z','Y').to_euler()
    root.scale = (1,1,L)

arrow_a = make_arrow("QFG_FIELD_VECTOR_A", MAT_FORCE, COL_DYN)
arrow_b = make_arrow("QFG_FIELD_VECTOR_B", MAT_FORCE, COL_DYN)
visible_scale(arrow_a, SHOT3[0]+8, SHOT3[1]-8, 1.0, pre=4, post=4)
visible_scale(arrow_b, SHOT3[0]+8, SHOT3[1]-8, 1.0, pre=4, post=4)

for i in range(0, len(path_a), 8):
    f = SHOT3[0] + i
    orient_arrow(arrow_a, path_a[i], field_a[i])
    orient_arrow(arrow_b, path_b[i], field_b[i])
    arrow_a.keyframe_insert("location", frame=f)
    arrow_a.keyframe_insert("rotation_euler", frame=f)
    arrow_a.keyframe_insert("scale", frame=f)
    arrow_b.keyframe_insert("location", frame=f)
    arrow_b.keyframe_insert("rotation_euler", frame=f)
    arrow_b.keyframe_insert("scale", frame=f)

set_all_linear(arrow_a)
set_all_linear(arrow_b)

# ---------------------------------------------------------------------------
# SHOT 4: BSM-SG ATLAS / J_ij VISUAL ASSEMBLY
# ---------------------------------------------------------------------------

random.seed(12345)

atlas_targets = [
    Vector(( 1.15, 1.15, 1.15)),
    Vector((-1.15,-1.15, 1.15)),
    Vector((-1.15, 1.15,-1.15)),
    Vector(( 1.15,-1.15,-1.15)),
]

# Outer twisted shell.
for i in range(8):
    a = math.radians(i*45 + 22.5)
    z = 0.75 if i%2==0 else -0.75
    atlas_targets.append(Vector((2.15*math.cos(a), 2.15*math.sin(a), z)))

atlas_sites = []
atlas_starts = []

for i, target in enumerate(atlas_targets):
    start = Vector((
        random.uniform(-5.0,5.0),
        random.uniform(-3.5,3.5),
        random.uniform(-3.0,3.0),
    ))
    atlas_starts.append(start)

    obj = add_ico(
        f"ATLAS_SITE_{i:02d}", start, 0.16,
        MAT_SITE if i%2==0 else MAT_SITE_ALT,
        COL_ATLAS, 3
    )
    atlas_sites.append(obj)

    obj.scale = (0,0,0)
    obj.keyframe_insert("scale", frame=SHOT4[0]-3)
    obj.scale = (1,1,1)
    obj.keyframe_insert("scale", frame=SHOT4[0]+25+i*3)

    obj.location = start
    obj.keyframe_insert("location", frame=SHOT4[0]+18)
    obj.location = target
    obj.keyframe_insert("location", frame=SHOT4[0]+150+i*2)

    # A tiny settling overshoot for cinematic feel.
    settle = target * 0.96
    obj.location = settle
    obj.keyframe_insert("location", frame=SHOT4[0]+178+i)
    obj.location = target
    obj.keyframe_insert("location", frame=SHOT4[0]+205+i)

    obj.scale = (1,1,1)
    obj.keyframe_insert("scale", frame=SHOT4[1]-5)
    obj.scale = (0,0,0)
    obj.keyframe_insert("scale", frame=SHOT4[1]+5)
    set_all_linear(obj)

# Build nearest-neighbour graph based on target distances.
pairs = []
for i in range(len(atlas_targets)):
    distances = sorted(
        [((atlas_targets[i] - atlas_targets[j]).length, j)
         for j in range(len(atlas_targets)) if j != i],
        key=lambda x: x[0]
    )
    for _, j in distances[:3]:
        p = tuple(sorted((i,j)))
        if p not in pairs:
            pairs.append(p)

atlas_edges = []
for k,(i,j) in enumerate(pairs):
    edge = add_curve(
        f"Jij_{i:02d}_{j:02d}",
        [atlas_targets[i], atlas_targets[j]],
        0.012,
        MAT_GRAPH,
        COL_ATLAS
    )
    start = SHOT4[0] + 150 + (k % 14)*5
    end = min(SHOT4[1]-20, start+35)
    grow_curve(edge, start, end)
    visible_scale(edge, start-1, SHOT4[1], 1.0, pre=1, post=4)
    atlas_edges.append(edge)

# Orbital / orientation rings.
for i in range(4):
    t = atlas_targets[i]
    ring = add_ring(
        f"ATLAS_ORBIT_{i:02d}", t, 0.55 + i*0.06,
        MAT_FIELD2 if i%2 else MAT_FIELD, COL_ATLAS,
        rot=(math.radians(30+i*17), math.radians(60-i*8), math.radians(i*35)),
        bevel=0.010
    )
    visible_scale(ring, SHOT4[0]+215+i*8, SHOT4[1], 1.0, pre=5, post=4)
    ring.rotation_euler = (
        math.radians(30+i*17),
        math.radians(60-i*8),
        math.radians(i*35)
    )
    ring.keyframe_insert("rotation_euler", frame=SHOT4[0]+215+i*8)
    ring.rotation_euler.z += math.radians(150 if i%2==0 else -150)
    ring.keyframe_insert("rotation_euler", frame=SHOT4[1])
    set_all_linear(ring)

# Bohr-like envelope visualization: three large rings.
for i,rot in enumerate([
    (0,0,0),
    (math.radians(65),0,math.radians(25)),
    (math.radians(30),math.radians(70),math.radians(-20)),
]):
    ring = add_ring(
        f"ATLAS_ENVELOPE_{i}", (0,0,0), 2.75, MAT_FIELD, COL_ATLAS,
        rot=rot, bevel=0.006
    )
    visible_scale(ring, SHOT4[0]+245+i*8, SHOT4[1], 1.0, pre=6, post=4)

scene.timeline_markers.new("ATLAS REVEAL", frame=SHOT4[0]+150)

# ---------------------------------------------------------------------------
# SHOT 5: REAL QFG MULTI-BODY FIELD MOTION
# ---------------------------------------------------------------------------

def simulate_multibody(count=6, steps=288):
    world = build_qfg_world(QFG_SEED + 7)
    handles = []
    names = []
    initial = []

    for i in range(count):
        ang = 2*math.pi*i/count
        r = 3.1 + (0.25 if i%2 else -0.15)
        p = Vector((r*math.cos(ang), r*math.sin(ang), 0.55*math.sin(ang*2)))
        # tangential initial velocity
        tangent = Vector((-math.sin(ang), math.cos(ang), 0.12*math.cos(ang*3)))
        tangent.normalize()
        vel = tangent * (1.35 + 0.12*i)

        name = f"Multi_{i:02d}"
        h = world.add_body(BodySpec(
            name=name,
            position=tuple(p),
            velocity=tuple(vel),
            mass=1.0 + 0.08*i,
            radius=0.20,
            field_coupling=10.0 + i*0.6,
        ))
        handles.append(h)
        names.append(name)
        initial.append(p)

    paths = [[initial[i]] for i in range(count)]

    for _ in range(steps-1):
        res = world.step()
        for i,(h,name) in enumerate(zip(handles,names)):
            p = extract_body_position(world,res,h,name)
            if p is None:
                raise RuntimeError(
                    "Could not resolve multi-body QFG state.\n\n"
                    + qfg_body_debug_dump(world, h, name)
                )
            paths[i].append(Vector(p))
    return world, paths

world_multi, multi_paths = simulate_multibody()

multi_objs = []
multi_trails = []

for i,path in enumerate(multi_paths):
    obj = add_ico(
        f"QFG_MULTI_BODY_{i:02d}", path[0], 0.20,
        MAT_SITE if i%2==0 else MAT_SITE_ALT, COL_MULTI, 3
    )
    multi_objs.append(obj)
    visible_scale(obj, SHOT5[0], SHOT5[1], 1.0, pre=5, post=8)

    # map simulation samples across shot frames
    for n,p in enumerate(path):
        f = SHOT5[0] + int(n * (SHOT5[1]-SHOT5[0])/(len(path)-1))
        obj.location = p
        obj.keyframe_insert("location", frame=f)
    set_linear_keys(obj)

    tr = add_curve(
        f"MULTI_TRAIL_{i:02d}", path,
        0.010 if i%2 else 0.014,
        MAT_FIELD if i%2==0 else MAT_FIELD2, COL_MULTI
    )
    grow_curve(tr, SHOT5[0]+10+i*2, SHOT5[1]-15)
    visible_scale(tr, SHOT5[0], SHOT5[1], 1.0, pre=1, post=8)
    multi_trails.append(tr)

# Add final interaction graph using final multi-body positions.
multi_final = [p[-1] for p in multi_paths]
multi_pairs = []
for i in range(len(multi_final)):
    dlist = sorted(
        [((multi_final[i] - multi_final[j]).length,j)
         for j in range(len(multi_final)) if j!=i]
    )
    for _,j in dlist[:2]:
        p = tuple(sorted((i,j)))
        if p not in multi_pairs:
            multi_pairs.append(p)

for k,(i,j) in enumerate(multi_pairs):
    edge = add_curve(
        f"MULTI_Jij_{i}_{j}", [multi_final[i], multi_final[j]],
        0.009, MAT_GRAPH, COL_MULTI
    )
    s = SHOT5[1]-95 + k*4
    grow_curve(edge, s, min(SHOT5[1]-15, s+30))
    visible_scale(edge, s-1, SHOT5[1], 1.0, pre=1, post=8)

scene.timeline_markers.new("MULTI-BODY FIELD", frame=SHOT5[0]+15)

# ---------------------------------------------------------------------------
# SHOT 6: HERO STRUCTURE
# ---------------------------------------------------------------------------

# Final hero structure: re-use Atlas target geometry with larger polished core.
hero_sites = []
for i,t in enumerate(atlas_targets):
    obj = add_ico(
        f"HERO_SITE_{i:02d}", t, 0.18 if i<4 else 0.13,
        MAT_SITE if i%2==0 else MAT_SITE_ALT,
        COL_ATLAS, 4
    )
    visible_scale(obj, SHOT6[0]+10+i*2, FRAME_END, 1.0, pre=8, post=0)
    hero_sites.append(obj)

for k,(i,j) in enumerate(pairs):
    edge = add_curve(
        f"HERO_Jij_{i:02d}_{j:02d}",
        [atlas_targets[i], atlas_targets[j]],
        0.010, MAT_GRAPH, COL_ATLAS
    )
    s = SHOT6[0]+55+(k%16)*3
    grow_curve(edge, s, min(FRAME_END-50,s+35))
    visible_scale(edge, s-1, FRAME_END, 1.0, pre=1, post=0)

hero_core = add_ico("HERO_QFG_CORE", (0,0,0), 0.32, MAT_FIELD, COL_ATLAS, 4)
visible_scale(hero_core, SHOT6[0]+25, FRAME_END, 1.0, pre=10, post=0)

# Hero rings
for i,rot in enumerate([
    (math.radians(75),0,0),
    (0,math.radians(75),math.radians(30)),
    (math.radians(35),math.radians(55),math.radians(-35)),
]):
    ring = add_ring(
        f"HERO_FIELD_RING_{i}", (0,0,0), 3.0+i*0.22,
        MAT_FIELD if i!=1 else MAT_FIELD2, COL_ATLAS,
        rot=rot, bevel=0.008+i*0.002
    )
    visible_scale(ring, SHOT6[0]+30+i*10, FRAME_END, 1.0, pre=8, post=0)
    ring.rotation_euler = rot
    ring.keyframe_insert("rotation_euler", frame=SHOT6[0]+30+i*10)
    ring.rotation_euler = (
        rot[0] + math.radians(80*(i+1)),
        rot[1] + math.radians(-55*(i+1)),
        rot[2] + math.radians(180 if i%2==0 else -160),
    )
    ring.keyframe_insert("rotation_euler", frame=FRAME_END)
    set_all_linear(ring)

scene.timeline_markers.new("HERO REVEAL", frame=SHOT6[0]+45)

# ---------------------------------------------------------------------------
# FLOOR / ENVIRONMENT — minimal dark reflective pedestal
# ---------------------------------------------------------------------------

floor_mat = make_principled_material(
    "MAT_FLOOR", (0.002,0.004,0.008,1), 0.75, 0.18
)

bpy.ops.mesh.primitive_plane_add(size=40, location=(0,0,-3.15))
floor = bpy.context.object
floor.name = "CINEMATIC_FLOOR"
move_to_collection(floor, COL_ENV)
floor.data.materials.append(floor_mat)

# Subtle emissive rings on floor.
for i in range(3):
    ring = add_ring(
        f"FLOOR_RING_{i}", (0,0,-3.10), 3.0+i*2.0,
        MAT_FIELD if i%2==0 else MAT_FIELD2,
        COL_ENV, rot=(0,0,0), bevel=0.008
    )
    visible_scale(ring, 1, FRAME_END, 1.0, pre=0, post=0)

# ---------------------------------------------------------------------------
# VOLUMETRIC HAZE CUBE
# ---------------------------------------------------------------------------

try:
    bpy.ops.mesh.primitive_cube_add(size=22, location=(0,0,2.5))
    fog = bpy.context.object
    fog.name = "QFG_VOLUMETRIC_HAZE"
    move_to_collection(fog, COL_ENV)

    fog_mat = bpy.data.materials.new("MAT_QFG_HAZE")
    fog_mat.use_nodes = True
    fog_mat.node_tree.nodes.clear()
    out = fog_mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
    vol = fog_mat.node_tree.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.006
    if "Anisotropy" in vol.inputs:
        vol.inputs["Anisotropy"].default_value = 0.25
    fog_mat.node_tree.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    fog.data.materials.append(fog_mat)
except Exception as e:
    print("Volumetric haze skipped:", e)

# ---------------------------------------------------------------------------
# TIMELINE MARKERS / SOUND-DESIGN CUES
# ---------------------------------------------------------------------------

for name, frame in [
    ("FIELD WAKE", 24),
    ("SOLITON RISE", 130),
    ("DYNAMICS START", SHOT3[0]),
    ("ATLAS BUILD", SHOT4[0]),
    ("FIELD FEEDBACK", SHOT5[0]),
    ("FINAL TITLE", 1140),
]:
    if name not in [m.name for m in scene.timeline_markers]:
        scene.timeline_markers.new(name, frame=frame)

# ---------------------------------------------------------------------------
# SHOT VISIBILITY — hide major groups outside their ranges using object scales
# ---------------------------------------------------------------------------

# Field cloud and core are a persistent unifying visual.
# Bodies, Atlas and multi-body objects already have scale visibility keyframes.

# ---------------------------------------------------------------------------
# QFG TECHNICAL HUD — visible in the hero shot
# ---------------------------------------------------------------------------

hud_body = (
    f"QFGWorld // deterministic seed {QFG_SEED}\n"
    f"grid {QFG_GRID}^3 // dt {QFG_DT:.4f} // substeps {QFG_SUBSTEPS}\n"
    "BSM-SG Atlas // J_ij // field feedback"
)
add_camera_text("TXT_HUD", hud_body, 1170, 1300, (1.45,-1.45,-6.0), 0.16)

# ---------------------------------------------------------------------------
# FINAL CAMERA / RENDER SETTINGS
# ---------------------------------------------------------------------------

scene.frame_set(1)

# ---------------------------------------------------------------------------
# OUTPUT FORMAT — Blender 5.2 compatible
# ---------------------------------------------------------------------------
#
# Blender 5.2 separates Media Type from image file format:
#   image_settings.media_type = 'VIDEO'
# instead of the legacy:
#   image_settings.file_format = 'FFMPEG'
#
# Keep a fallback for older Blender versions.

def configure_cinematic_output(scene):
    img = scene.render.image_settings

    if hasattr(img, "media_type"):
        # Blender 5.2+
        img.media_type = 'VIDEO'
        print("Render output API: Blender 5.x media_type=VIDEO")
    else:
        # Legacy Blender
        img.file_format = 'FFMPEG'
        print("Render output API: legacy file_format=FFMPEG")

    ff = scene.render.ffmpeg
    if ff is None:
        raise RuntimeError(
            "Blender reports VIDEO output but FFmpeg settings are unavailable."
        )

    # Use guarded enum assignment because supported formats/codecs can differ
    # depending on Blender build / platform.
    try:
        ff.format = 'MPEG4'
    except Exception as exc:
        print("WARNING: MPEG4 container unavailable, keeping Blender default:", exc)

    try:
        ff.codec = 'H264'
    except Exception as exc:
        print("WARNING: H264 codec unavailable, keeping Blender default:", exc)

    try:
        ff.constant_rate_factor = 'HIGH'
    except Exception as exc:
        print("WARNING: HIGH CRF preset unavailable, keeping Blender default:", exc)

    try:
        ff.ffmpeg_preset = 'GOOD'
    except Exception as exc:
        print("WARNING: GOOD FFmpeg preset unavailable, keeping Blender default:", exc)

    # Let Blender append the extension appropriate to the selected container.
    scene.render.use_file_extension = True
    scene.render.filepath = os.path.join(
        bpy.path.abspath(OUTPUT_DIR),
        OUTPUT_FILE
    )

    print("Cinematic output path:", scene.render.filepath)
    print("Cinematic media type:", getattr(img, "media_type", "<legacy>"))
    print("Cinematic FFmpeg container:", getattr(ff, "format", "<unknown>"))
    print("Cinematic FFmpeg codec:", getattr(ff, "codec", "<unknown>"))


configure_cinematic_output(scene)

# Ensure output directory exists.
Path(bpy.path.abspath(OUTPUT_DIR)).mkdir(parents=True, exist_ok=True)

# Save the generated scene.
if SAVE_BLEND:
    bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(BLEND_FILE))

print("="*72)
print("BSM-SG / QFG CINEMATIC SHOWCASE BUILT")
print(f"Frames: 1-{FRAME_END} @ {FPS} fps")
print(f"Impact frame: {impact_frame}")
print(
    "Dynamic paths: generated by "
    + ((QFG_PACKAGE_ROOT + ".sdk") if QFG_PACKAGE_ROOT else "<unresolved QFG SDK>")
    + " / QFGWorld"
)
print("Atlas/J_ij: Blender visualization layer around structural sites")
print(f"Output: {scene.render.filepath}")
print("="*72)

if AUTO_RENDER:
    bpy.ops.render.render(animation=True)
