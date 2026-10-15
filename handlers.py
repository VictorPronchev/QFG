"""Timeline handlers for displaying explicitly baked QFG data.

QFG 0.4.1 makes out-of-range playback explicit.  The frame-change handler
never advances the numerical solver; it only resolves and displays cache data.
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from . import runtime
from .visualization import update_display_object, update_slice_image
from .operators import apply_body_state, apply_atlas_state, update_world_telemetry
from .debug_overlay import register_debug_overlay, unregister_debug_overlay


def _apply_cached_frame(scene, cached, display_frame: int, requested_frame: int, state: str) -> None:
    s = scene.qfg_settings
    update_display_object(scene, cached["points"], cached["weights"], s.point_radius)
    update_slice_image(cached["density_slice"])
    d = cached.get("diagnostics", {})
    s.last_time = float(d.get("time", 0.0))
    s.last_max_density = float(d.get("max_density", 0.0))
    s.last_norm = float(d.get("norm", 0.0))
    s.last_mode_variance = float(d.get("mode_variance", 0.0))
    s.last_energy = float(d.get("energy_proxy", 0.0))
    s.last_temperature = float(d.get("max_temperature", 0.0))
    s.last_gauge_energy = float(d.get("gauge_energy", 0.0))
    s.last_gravity_energy = float(d.get("gravity_energy", 0.0))
    s.last_momentum = (
        float(d.get("momentum_x", 0.0)),
        float(d.get("momentum_y", 0.0)),
        float(d.get("momentum_z", 0.0)),
    )
    body_state = cached.get("body_state")
    if body_state is not None:
        apply_body_state(scene, body_state)
    atlas_state = cached.get("atlas_state")
    if atlas_state is not None:
        apply_atlas_state(scene, atlas_state)
    profile = cached.get("profile", {})
    if profile:
        s.last_field_ms = float(profile.get("field_ms", 0.0))
        s.last_body_ms = float(profile.get("body_ms", 0.0))
        s.last_query_ms = float(profile.get("query_ms", 0.0))
        s.last_total_ms = float(profile.get("total_ms", 0.0))
        s.last_body_count = int(profile.get("body_count", 0))
        s.last_contact_count = int(profile.get("contact_count", 0))
        s.last_event_count = int(profile.get("event_count", 0))
        s.last_kinetic_energy = float(profile.get("kinetic_energy", 0.0))
        s.last_linear_kinetic_energy = float(profile.get("linear_kinetic_energy", 0.0))
        s.last_rotational_kinetic_energy = float(profile.get("rotational_kinetic_energy", 0.0))
        s.last_mean_force = float(profile.get("mean_force", 0.0))
        s.last_max_force = float(profile.get("max_force", 0.0))
        s.last_mean_torque = float(profile.get("mean_torque", 0.0))
        s.last_max_torque = float(profile.get("max_torque", 0.0))
    telemetry = cached.get("telemetry", {})
    if telemetry:
        update_world_telemetry(s, telemetry)

    runtime.debug_payload = {
        "source": "CACHE",
        "requested_frame": int(requested_frame),
        "displayed_frame": int(display_frame),
        "resolution": state,
        "body_state": body_state or {},
        "atlas_state": atlas_state or {},
        "telemetry": telemetry,
        "events": cached.get("events", []),
    }


@persistent
def qfg_frame_change_post(scene, depsgraph=None):
    if runtime.in_handler or not hasattr(scene, "qfg_settings"):
        return
    if len(runtime.cache) == 0:
        return

    requested = int(scene.frame_current)
    s = scene.qfg_settings
    display_frame, state = runtime.cache.resolve_frame(requested, s.playback_outside_mode)
    bounds = runtime.cache.bounds()

    if state in {"EMPTY", "OUTSIDE"} or display_frame is None:
        if bounds is not None:
            lo, hi = bounds
            s.status = (
                f"Outside baked range {lo}-{hi}: requested frame {requested}; "
                "cached display unchanged"
            )
            if runtime.debug_payload:
                runtime.debug_payload = dict(runtime.debug_payload)
                runtime.debug_payload["requested_frame"] = requested
                runtime.debug_payload["resolution"] = "OUTSIDE"
        return

    cached = runtime.cache.get(display_frame)
    if cached is None:
        return

    runtime.in_handler = True
    try:
        if state == "CLAMP" and display_frame != requested:
            # The nested frame-change callback sees runtime.in_handler and exits.
            scene.frame_set(display_frame)
        _apply_cached_frame(scene, cached, display_frame, requested, state)
        if bounds is None:
            s.status = f"Displaying baked QFG frame {display_frame}"
        else:
            lo, hi = bounds
            if state == "EXACT":
                s.status = f"Displaying baked QFG frame {display_frame}"
            elif state == "HOLD":
                s.status = (
                    f"Outside baked range {lo}-{hi}: requested {requested}; "
                    f"holding baked frame {display_frame}"
                )
            elif state == "CLAMP":
                s.status = f"Clamped requested frame {requested} to baked frame {display_frame}"
            else:
                s.status = f"Frame {requested} is not cached; displaying nearest baked frame {display_frame}"
    finally:
        runtime.in_handler = False


def register_handlers() -> None:
    if qfg_frame_change_post not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(qfg_frame_change_post)
    register_debug_overlay()


def unregister_handlers() -> None:
    unregister_debug_overlay()
    if qfg_frame_change_post in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(qfg_frame_change_post)
