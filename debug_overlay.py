"""Viewport debug overlay for QFG Dynamics 0.4.1.

The overlay is deliberately display-only: it never advances the solver.  It reads
cached/live body state and contact telemetry exposed through :mod:`runtime` and
renders lightweight 3-D vectors plus a 2-D diagnostics HUD.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Sequence, Tuple
import math

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader

from . import runtime

_DRAW_3D = None
_DRAW_2D = None


def _vec3(value: Any) -> Tuple[float, float, float]:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return (0.0, 0.0, 0.0)


def _add_segment(vertices: List[Tuple[float, float, float]], a: Sequence[float], b: Sequence[float]) -> None:
    vertices.append(_vec3(a))
    vertices.append(_vec3(b))


def _draw_segments(vertices: List[Tuple[float, float, float]], color: Tuple[float, float, float, float], width: float = 1.5) -> None:
    if not vertices:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": vertices})
    try:
        gpu.state.line_width_set(width)
    except Exception:
        pass
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _body_vectors(payload: dict, key: str, scale: float) -> List[Tuple[float, float, float]]:
    state = payload.get("body_state") or {}
    positions = state.get("positions", [])
    values = state.get(key, [])
    vertices: List[Tuple[float, float, float]] = []
    for index, position in enumerate(positions):
        if index >= len(values):
            break
        p = _vec3(position)
        v = _vec3(values[index])
        end = (p[0] + v[0] * scale, p[1] + v[1] * scale, p[2] + v[2] * scale)
        _add_segment(vertices, p, end)
    return vertices


def _contact_geometry(payload: dict, normal_scale: float, impulse_scale: float):
    telemetry = payload.get("telemetry") or {}
    contacts = telemetry.get("debug_contacts", []) or []
    crosses: List[Tuple[float, float, float]] = []
    normals: List[Tuple[float, float, float]] = []
    impulses: List[Tuple[float, float, float]] = []
    cross_size = max(0.025, 0.06 * max(normal_scale, 0.1))
    for contact in contacts:
        point = _vec3(contact.get("position", (0.0, 0.0, 0.0)))
        normal = _vec3(contact.get("normal", (0.0, 0.0, 1.0)))
        impulse = _vec3(contact.get("total_impulse", (0.0, 0.0, 0.0)))
        for axis in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            a = tuple(point[i] - axis[i] * cross_size for i in range(3))
            b = tuple(point[i] + axis[i] * cross_size for i in range(3))
            _add_segment(crosses, a, b)
        normal_end = tuple(point[i] + normal[i] * normal_scale for i in range(3))
        impulse_end = tuple(point[i] + impulse[i] * impulse_scale for i in range(3))
        _add_segment(normals, point, normal_end)
        _add_segment(impulses, point, impulse_end)
    return crosses, normals, impulses


def draw_debug_3d() -> None:
    scene = getattr(bpy.context, "scene", None)
    if scene is None or not hasattr(scene, "qfg_settings"):
        return
    s = scene.qfg_settings
    if not s.debug_overlay_enabled:
        return
    payload = runtime.debug_payload
    if not payload:
        return

    try:
        gpu.state.blend_set("ALPHA")
    except Exception:
        pass

    if s.debug_show_contacts:
        crosses, normals, impulses = _contact_geometry(
            payload, float(s.debug_contact_normal_scale), float(s.debug_impulse_scale)
        )
        _draw_segments(crosses, (1.0, 0.85, 0.15, 1.0), 2.5)
        _draw_segments(normals, (0.25, 1.0, 0.35, 0.95), 2.0)
        _draw_segments(impulses, (1.0, 0.2, 0.15, 0.95), 2.0)
    if s.debug_show_forces:
        _draw_segments(
            _body_vectors(payload, "force_total", float(s.debug_force_scale)),
            (0.15, 0.75, 1.0, 0.95), 1.8,
        )
    if s.debug_show_torques:
        _draw_segments(
            _body_vectors(payload, "torque_total", float(s.debug_torque_scale)),
            (1.0, 0.35, 0.85, 0.95), 1.8,
        )
    if s.debug_show_angular_velocity:
        _draw_segments(
            _body_vectors(payload, "angular_velocities", float(s.debug_angular_scale)),
            (0.9, 0.9, 1.0, 0.9), 1.5,
        )

    try:
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set("NONE")
    except Exception:
        pass


def _hud_lines(scene: Any, payload: dict) -> List[str]:
    s = scene.qfg_settings
    telemetry = payload.get("telemetry") or {}
    source = str(payload.get("source", "LIVE"))
    requested = payload.get("requested_frame")
    displayed = payload.get("displayed_frame")
    cache_note = ""
    if source == "CACHE":
        if requested is not None and displayed is not None and int(requested) != int(displayed):
            cache_note = f" | requested {requested}, showing {displayed}"
        else:
            cache_note = f" | frame {displayed}"
    p = _vec3(telemetry.get("momentum", (0.0, 0.0, 0.0)))
    l = _vec3(telemetry.get("angular_momentum", (0.0, 0.0, 0.0)))
    pnorm = math.sqrt(sum(v * v for v in p))
    lnorm = math.sqrt(sum(v * v for v in l))
    body_contacts = int(telemetry.get("active_body_contacts", 0))
    floor_contacts = int(telemetry.get("active_floor_contacts", 0))
    lines = [
        f"QFG Dynamics 1.0.0 | {source}{cache_note}",
        f"Bodies {s.last_body_count} | contacts body/floor {body_contacts}/{floor_contacts}",
        f"KE total {s.last_kinetic_energy:.5g} | linear {s.last_linear_kinetic_energy:.5g} | rotational {s.last_rotational_kinetic_energy:.5g}",
        f"|P| {pnorm:.5g} | |L| {lnorm:.5g}",
        f"|F| mean/max {s.last_mean_force:.5g}/{s.last_max_force:.5g}",
        f"|tau| mean/max {s.last_mean_torque:.5g}/{s.last_max_torque:.5g}",
    ]
    if getattr(s, "atlas_feedback_enabled", False):
        lines.append(
            f"B4 Atlas moved/rot {s.atlas_feedback_moved_count}/{s.atlas_feedback_rotated_count} "
            f"| clipped {s.atlas_feedback_clipped_count} | W* {s.atlas_feedback_total_work:.5g}"
        )
    if getattr(s, "atlas_constraints_enabled", False):
        lines.append(
            f"B5 nodes/pairs/groups {s.atlas_constraints_node_count}/{s.atlas_constraints_pair_count}/{s.atlas_constraints_group_count} "
            f"| cone excess {s.atlas_constraints_max_cone_excess:.4g} deg"
        )
    if getattr(s, "atlas_blind_iterations_used", 0):
        lines.append(
            f"B6 iter {s.atlas_blind_iterations_used} | angle {s.atlas_blind_final_angle:.5g} deg "
            f"| range {s.atlas_blind_window_range:.3g} | converged {s.atlas_blind_converged}"
        )
    return lines


def draw_debug_2d() -> None:
    scene = getattr(bpy.context, "scene", None)
    if scene is None or not hasattr(scene, "qfg_settings"):
        return
    s = scene.qfg_settings
    if not (s.debug_overlay_enabled and s.debug_show_hud):
        return
    payload = runtime.debug_payload
    if not payload:
        return
    region = getattr(bpy.context, "region", None)
    if region is None:
        return

    font_id = 0
    x = 18
    y = max(40, region.height - 52)
    try:
        blf.size(font_id, int(s.debug_hud_font_size))
    except TypeError:  # older API fallback
        blf.size(font_id, int(s.debug_hud_font_size), 72)
    try:
        blf.color(font_id, 0.92, 0.96, 1.0, 1.0)
    except Exception:
        pass
    for line in _hud_lines(scene, payload):
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, line)
        y -= int(s.debug_hud_font_size) + 5


def register_debug_overlay() -> None:
    global _DRAW_3D, _DRAW_2D
    if _DRAW_3D is None:
        _DRAW_3D = bpy.types.SpaceView3D.draw_handler_add(draw_debug_3d, (), "WINDOW", "POST_VIEW")
    if _DRAW_2D is None:
        _DRAW_2D = bpy.types.SpaceView3D.draw_handler_add(draw_debug_2d, (), "WINDOW", "POST_PIXEL")


def unregister_debug_overlay() -> None:
    global _DRAW_3D, _DRAW_2D
    if _DRAW_3D is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW_3D, "WINDOW")
        except Exception:
            pass
        _DRAW_3D = None
    if _DRAW_2D is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW_2D, "WINDOW")
        except Exception:
            pass
        _DRAW_2D = None
