"""QFG Lab 5.2 Blender extension."""
from __future__ import annotations

bl_info = {
    "name": "QFG Dynamics 1.0.0 Alpha",
    "author": "Viktor Pronchev, Stoyan Sargoychev, and contributors",
    "version": (1, 0, 0),
    "blender": (5, 2, 0),
    "location": "3D Viewport > Sidebar > QFG 5.2",
    "description": "Field-driven dynamics, BSM-SG Atlas geometry, B2 geometry, B3 Atlas-to-field coupling, B4 bounded bidirectional feedback, B5 topology-aware constrained relaxation and B6 blind Group-15 experiment harness, topology, HRM/RF, thermal, Yb and molecular research prototypes",
    "category": "Physics",
}


def register():
    from .properties import register_properties
    from .operators import register_operators
    from .panels import register_panels
    from .handlers import register_handlers
    register_properties()
    register_operators()
    register_panels()
    register_handlers()


def unregister():
    from .handlers import unregister_handlers
    from .panels import unregister_panels
    from .operators import unregister_operators
    from .properties import unregister_properties
    from .runtime import reset_runtime
    unregister_handlers()
    unregister_panels()
    unregister_operators()
    unregister_properties()
    reset_runtime()


if __name__ == "__main__":
    register()
