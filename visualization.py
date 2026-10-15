"""Blender 5.2 visualization helpers.

Field samples are stored as loose mesh vertices and rendered through a
Geometry Nodes ``Mesh to Points`` modifier.  This avoids legacy PointCloud RNA
allocation calls and keeps repeated solver updates lightweight and predictable.
"""
from __future__ import annotations

from typing import Any, Tuple
import numpy as np

try:
    import bpy  # type: ignore
except Exception:  # pragma: no cover
    bpy = None


DISPLAY_OBJECT_NAME = "QFG_Field_Points"
DISPLAY_DATA_NAME = "QFG_Field_Points_Mesh"
DISPLAY_MODIFIER_NAME = "QFG Mesh to Points"
DISPLAY_NODE_GROUP_NAME = "QFG_MeshToPoints_GN"
SLICE_IMAGE_NAME = "QFG_Density_Slice"
COLLECTION_NAME = "QFG Results"


def density_to_points(
    density: np.ndarray,
    domain_length: float,
    threshold_fraction: float,
    max_points: int,
) -> Tuple[np.ndarray, np.ndarray]:
    density = np.asarray(density, dtype=np.float32)
    if density.ndim != 3:
        raise ValueError("density must be a 3D array")
    max_value = float(np.max(density)) if density.size else 0.0
    if max_value <= 0.0:
        return np.empty((0, 3), dtype=np.float32), np.empty((0,), dtype=np.float32)
    level = max_value * float(np.clip(threshold_fraction, 0.0, 1.0))
    indices = np.argwhere(density >= level)
    if indices.size == 0:
        return np.empty((0, 3), dtype=np.float32), np.empty((0,), dtype=np.float32)

    values = density[tuple(indices.T)]
    if len(indices) > max_points:
        selected = np.argpartition(values, -max_points)[-max_points:]
        indices = indices[selected]
        values = values[selected]

    n = density.shape[0]
    voxel = float(domain_length) / n
    points = (indices.astype(np.float32) - n / 2.0 + 0.5) * voxel
    weights = values / max(max_value, 1e-12)
    return points.astype(np.float32), weights.astype(np.float32)


def central_slice(density: np.ndarray, axis: str = "Z") -> np.ndarray:
    density = np.asarray(density, dtype=np.float32)
    axis = axis.upper()
    if axis == "X":
        result = density[density.shape[0] // 2, :, :]
    elif axis == "Y":
        result = density[:, density.shape[1] // 2, :]
    else:
        result = density[:, :, density.shape[2] // 2]
    return np.asarray(result, dtype=np.float32)


def _results_collection(scene: Any):
    collection = bpy.data.collections.get(COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(COLLECTION_NAME)
        scene.collection.children.link(collection)
    elif collection.name not in {child.name for child in scene.collection.children}:
        # A collection may survive after opening another scene in the same file.
        try:
            scene.collection.children.link(collection)
        except RuntimeError:
            pass
    return collection


def _remove_object_and_orphan_data(obj: Any) -> None:
    """Remove an incompatible old display object and its orphan data safely."""
    data = getattr(obj, "data", None)
    data_type = getattr(obj, "type", "")
    bpy.data.objects.remove(obj, do_unlink=True)
    if data is None or getattr(data, "users", 1) != 0:
        return
    try:
        if data_type == "POINTCLOUD" and hasattr(bpy.data, "pointclouds"):
            bpy.data.pointclouds.remove(data)
        elif data_type == "MESH":
            bpy.data.meshes.remove(data)
    except (ReferenceError, RuntimeError):
        pass


def _new_geometry_node_socket(node_group: Any, *, name: str, in_out: str) -> None:
    """Create a geometry interface socket across Blender API generations."""
    if hasattr(node_group, "interface"):
        node_group.interface.new_socket(
            name=name,
            in_out=in_out,
            socket_type="NodeSocketGeometry",
        )
    elif in_out == "INPUT":  # pragma: no cover - older Blender fallback
        node_group.inputs.new("NodeSocketGeometry", name)
    else:  # pragma: no cover
        node_group.outputs.new("NodeSocketGeometry", name)


def _ensure_mesh_to_points_modifier(obj: Any, point_radius: float) -> None:
    """Attach/update the Geometry Nodes viewport point renderer."""
    modifier = obj.modifiers.get(DISPLAY_MODIFIER_NAME)
    if modifier is None:
        modifier = obj.modifiers.new(DISPLAY_MODIFIER_NAME, type="NODES")

    group = modifier.node_group
    if group is None or group.bl_idname != "GeometryNodeTree":
        group = bpy.data.node_groups.new(
            f"{DISPLAY_NODE_GROUP_NAME}_{obj.name}",
            type="GeometryNodeTree",
        )
        _new_geometry_node_socket(group, name="Geometry", in_out="INPUT")
        _new_geometry_node_socket(group, name="Geometry", in_out="OUTPUT")

        nodes = group.nodes
        links = group.links
        input_node = nodes.new("NodeGroupInput")
        input_node.name = "QFG Group Input"
        input_node.location = (-240.0, 0.0)
        mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
        mesh_to_points.name = "QFG Mesh to Points"
        mesh_to_points.label = "QFG Mesh to Points"
        mesh_to_points.location = (0.0, 0.0)
        try:
            mesh_to_points.mode = "VERTICES"
        except Exception:
            pass
        output_node = nodes.new("NodeGroupOutput")
        output_node.name = "QFG Group Output"
        output_node.location = (240.0, 0.0)

        links.new(input_node.outputs["Geometry"], mesh_to_points.inputs["Mesh"])
        links.new(mesh_to_points.outputs["Points"], output_node.inputs["Geometry"])
        modifier.node_group = group

    mesh_to_points = group.nodes.get("QFG Mesh to Points")
    if mesh_to_points is not None:
        radius_input = mesh_to_points.inputs.get("Radius")
        if radius_input is not None:
            radius_input.default_value = max(float(point_radius), 1e-5)


def ensure_display_object(scene: Any):
    if bpy is None:
        raise RuntimeError("Blender bpy module is unavailable")

    obj = bpy.data.objects.get(DISPLAY_OBJECT_NAME)
    # v0.1.2 may have left a POINTCLOUD object after points.add() failed.
    # Replace it automatically, so the user does not need to clean the file.
    if obj is not None and obj.type != "MESH":
        _remove_object_and_orphan_data(obj)
        obj = None

    if obj is None:
        mesh = bpy.data.meshes.new(DISPLAY_DATA_NAME)
        obj = bpy.data.objects.new(DISPLAY_OBJECT_NAME, mesh)
        _results_collection(scene).objects.link(obj)
    elif not obj.users_collection:
        _results_collection(scene).objects.link(obj)

    obj["qfg_display_type"] = "MESH_POINTS_GN"
    obj.show_name = True
    obj.show_in_front = False
    obj.display_type = "SOLID"
    obj.hide_render = False
    return obj


def update_display_object(
    scene: Any,
    points: np.ndarray,
    weights: np.ndarray,
    point_radius: float = 0.08,
):
    """Update solver samples using a Blender-4.1-compatible mesh container."""
    obj = ensure_display_object(scene)
    points = np.asarray(points, dtype=np.float32).reshape((-1, 3))
    weights = np.asarray(weights, dtype=np.float32).reshape((-1,))
    if len(weights) != len(points):
        raise ValueError("weights and points must have the same length")

    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata(points.tolist(), [], [])
    mesh.update()

    try:
        attr = mesh.attributes.get("qfg_density")
        if attr is None or attr.domain != "POINT" or attr.data_type != "FLOAT":
            if attr is not None:
                mesh.attributes.remove(attr)
            attr = mesh.attributes.new("qfg_density", "FLOAT", "POINT")
        if len(weights):
            attr.data.foreach_set("value", weights)
    except Exception:
        # The field remains visible even if a custom attribute is unavailable.
        pass

    _ensure_mesh_to_points_modifier(obj, point_radius)
    return obj


def ensure_slice_image(width: int, height: int):
    image = bpy.data.images.get(SLICE_IMAGE_NAME)
    if image is None or image.size[0] != width or image.size[1] != height:
        if image is not None:
            bpy.data.images.remove(image)
        image = bpy.data.images.new(
            SLICE_IMAGE_NAME,
            width=width,
            height=height,
            alpha=True,
            float_buffer=True,
        )
    return image


def update_slice_image(slice_data: np.ndarray):
    data = np.asarray(slice_data, dtype=np.float32)
    data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
    maximum = float(np.max(data)) if data.size else 0.0
    normalized = data / maximum if maximum > 0 else np.zeros_like(data)
    r = np.clip(1.5 * normalized, 0.0, 1.0)
    g = np.clip(1.5 * normalized - 0.25, 0.0, 1.0)
    b = np.clip(2.0 * normalized - 1.0, 0.0, 1.0)
    a = np.ones_like(normalized)
    rgba = np.stack([r, g, b, a], axis=-1).astype(np.float32)
    image = ensure_slice_image(data.shape[1], data.shape[0])
    image.pixels.foreach_set(rgba[::-1].ravel())
    image.update()
    return image


PLOT_COLLECTION_NAME = "QFG Plots"


def _plot_collection(scene: Any):
    collection = bpy.data.collections.get(PLOT_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(PLOT_COLLECTION_NAME)
        scene.collection.children.link(collection)
    return collection


def create_curve_plot(
    scene: Any,
    name: str,
    x: np.ndarray,
    y: np.ndarray,
    *,
    location=(0.0, 0.0, 0.0),
    width: float = 8.0,
    height: float = 4.0,
    bevel_depth: float = 0.025,
):
    """Create or replace a normalized Blender curve plot."""
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    y = np.asarray(y, dtype=np.float64).reshape(-1)
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("x and y must have the same length and at least two points")
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    if len(x) < 2:
        raise ValueError("Not enough finite plot points")

    old = bpy.data.objects.get(name)
    if old is not None:
        for collection in list(old.users_collection):
            collection.objects.unlink(old)
        data = old.data
        bpy.data.objects.remove(old)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)

    xmin, xmax = float(np.min(x)), float(np.max(x))
    ymin, ymax = float(np.min(y)), float(np.max(y))
    xn = (x - xmin) / max(xmax - xmin, 1e-12) * width
    yn = (y - ymin) / max(ymax - ymin, 1e-12) * height

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel_depth
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(xn) - 1)
    coords = np.column_stack([xn, np.zeros_like(xn), yn, np.ones_like(xn)]).astype(np.float32)
    spline.points.foreach_set("co", coords.ravel())

    obj = bpy.data.objects.new(name, curve)
    obj.location = location
    obj["qfg_x_range"] = (xmin, xmax)
    obj["qfg_y_range"] = (ymin, ymax)
    obj.show_name = True
    _plot_collection(scene).objects.link(obj)
    return obj


def create_bond_curves(scene: Any, name: str, positions: np.ndarray, bonds):
    old = bpy.data.objects.get(name)
    if old is not None:
        for collection in list(old.users_collection):
            collection.objects.unlink(old)
        data = old.data
        bpy.data.objects.remove(old)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = 0.035
    curve.bevel_resolution = 2
    positions = np.asarray(positions, dtype=float)
    for i, j, _distance in bonds:
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        coords = np.array([
            [*positions[i], 1.0],
            [*positions[j], 1.0],
        ], dtype=np.float32)
        spline.points.foreach_set("co", coords.ravel())
    obj = bpy.data.objects.new(name, curve)
    _plot_collection(scene).objects.link(obj)
    return obj

HEATMAP_COLLECTION_NAME = "QFG Heatmaps"


def update_named_heatmap(name: str, data: np.ndarray):
    """Create/update a float RGBA image from a 2-D array."""
    values = np.asarray(data, dtype=np.float32)
    values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    lo = float(np.min(values)) if values.size else 0.0
    hi = float(np.max(values)) if values.size else 1.0
    normalized = (values - lo) / max(hi - lo, 1e-12)
    # Compact perceptual-ish blue/cyan/yellow map without external packages.
    r = np.clip(1.8 * normalized - 0.55, 0.0, 1.0)
    g = np.clip(1.8 * normalized, 0.0, 1.0)
    b = np.clip(1.4 - 1.8 * normalized, 0.0, 1.0)
    a = np.ones_like(normalized)
    rgba = np.stack([r, g, b, a], axis=-1).astype(np.float32)
    image = bpy.data.images.get(name)
    width, height = values.shape[1], values.shape[0]
    if image is None or image.size[0] != width or image.size[1] != height:
        if image is not None:
            bpy.data.images.remove(image)
        image = bpy.data.images.new(name, width=width, height=height, alpha=True, float_buffer=True)
    image.pixels.foreach_set(rgba[::-1].ravel())
    image["qfg_value_min"] = lo
    image["qfg_value_max"] = hi
    image.update()
    return image


def _heatmap_collection(scene: Any):
    collection = bpy.data.collections.get(HEATMAP_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(HEATMAP_COLLECTION_NAME)
        scene.collection.children.link(collection)
    return collection


def create_image_plane(scene: Any, object_name: str, image: Any, *, location=(0.0, 0.0, 0.0), size=(8.0, 8.0)):
    """Create or update a UV plane displaying a Blender image."""
    old = bpy.data.objects.get(object_name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    mesh = bpy.data.meshes.new(f"{object_name}_Mesh")
    sx, sy = size[0] / 2.0, size[1] / 2.0
    verts = [(-sx, -sy, 0.0), (sx, -sy, 0.0), (sx, sy, 0.0), (-sx, sy, 0.0)]
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    coords = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
    for loop_index, loop in enumerate(mesh.loops):
        uv.data[loop_index].uv = coords[loop.vertex_index]

    obj = bpy.data.objects.new(object_name, mesh)
    obj.location = location
    obj.show_name = True
    _heatmap_collection(scene).objects.link(obj)

    mat = bpy.data.materials.get(f"{object_name}_Material")
    if mat is None:
        mat = bpy.data.materials.new(f"{object_name}_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Closest"
    links.new(texture.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    obj.data.materials.append(mat)
    return obj


def create_orbital_plane_rings(
    scene: Any,
    name: str,
    centers: np.ndarray,
    normals: np.ndarray,
    *,
    radius: float = 1.0,
    segments: int = 64,
    bevel_depth: float = 0.02,
):
    """Create/replace wire rings that visualize orbital-plane normals.

    Each ring is centered at ``centers[i]`` and lies in the plane whose normal
    is ``normals[i]``.  This is a geometry visualization helper only.
    """
    if bpy is None:
        raise RuntimeError("Blender bpy module is unavailable")
    centers = np.asarray(centers, dtype=np.float64).reshape((-1, 3))
    normals = np.asarray(normals, dtype=np.float64).reshape((-1, 3))
    if len(centers) != len(normals) or len(centers) < 1:
        raise ValueError("centers and normals must contain the same non-zero number of 3-vectors")

    old = bpy.data.objects.get(name)
    if old is not None:
        for collection in list(old.users_collection):
            collection.objects.unlink(old)
        data = old.data
        bpy.data.objects.remove(old)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = float(bevel_depth)
    curve.bevel_resolution = 2
    angles = np.linspace(0.0, 2.0 * np.pi, max(int(segments), 8), endpoint=False)

    for center, normal in zip(centers, normals):
        norm = float(np.linalg.norm(normal))
        if norm <= 1e-12:
            continue
        n = normal / norm
        helper = np.array((1.0, 0.0, 0.0), dtype=np.float64)
        if abs(float(np.dot(n, helper))) > 0.85:
            helper = np.array((0.0, 1.0, 0.0), dtype=np.float64)
        u = np.cross(n, helper)
        u /= max(float(np.linalg.norm(u)), 1e-12)
        v = np.cross(n, u)
        points = center[None, :] + float(radius) * (
            np.cos(angles)[:, None] * u[None, :] + np.sin(angles)[:, None] * v[None, :]
        )
        spline = curve.splines.new("POLY")
        spline.points.add(len(points))
        coords = np.vstack([points, points[0]])
        coords4 = np.column_stack([coords, np.ones(len(coords))]).astype(np.float32)
        spline.points.foreach_set("co", coords4.ravel())

    obj = bpy.data.objects.new(name, curve)
    obj["qfg_visualization"] = "ORBITAL_PLANE_RINGS"
    obj.show_name = True
    _plot_collection(scene).objects.link(obj)
    return obj
