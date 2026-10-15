"""Runtime state kept outside Blender ID properties."""
from __future__ import annotations

from typing import Any, Dict, Optional
from .diagnostics import TimelineCache

engine: Optional[Any] = None
world: Optional[Any] = None
cache = TimelineCache()
in_handler: bool = False
last_rom_result: Optional[Dict[str, Any]] = None
last_hrm_scan: Optional[Dict[str, Any]] = None
last_plasma_result: Optional[Dict[str, Any]] = None
last_cavity_shift: Optional[Dict[str, Any]] = None
last_mems_result: Optional[Dict[str, Any]] = None
last_yb_result: Optional[Dict[str, Any]] = None
last_molecular_result: Optional[Dict[str, Any]] = None
last_atlas_result: Optional[Dict[str, Any]] = None
last_atlas_graph: Optional[Dict[str, Any]] = None
last_atlas_planes: Optional[Dict[str, Any]] = None
last_bohr_envelope: Optional[Dict[str, Any]] = None
last_atlas_field: Optional[Dict[str, Any]] = None
last_atlas_feedback: Optional[Dict[str, Any]] = None
last_atlas_constraints: Optional[Dict[str, Any]] = None
last_atlas_blind_run: Optional[Dict[str, Any]] = None
debug_payload: Optional[Dict[str, Any]] = None


def reset_runtime() -> None:
    global engine, world, last_rom_result, last_hrm_scan, last_plasma_result
    global last_cavity_shift, last_mems_result, last_yb_result, last_molecular_result, last_atlas_result
    global last_atlas_graph, last_atlas_planes, last_bohr_envelope, last_atlas_field, last_atlas_feedback, last_atlas_constraints, last_atlas_blind_run, debug_payload
    engine = None
    world = None
    cache.clear()
    last_rom_result = None
    last_hrm_scan = None
    last_plasma_result = None
    last_cavity_shift = None
    last_mems_result = None
    last_yb_result = None
    last_molecular_result = None
    last_atlas_result = None
    last_atlas_graph = None
    last_atlas_planes = None
    last_bohr_envelope = None
    last_atlas_field = None
    last_atlas_feedback = None
    last_atlas_constraints = None
    last_atlas_blind_run = None
    debug_payload = None
