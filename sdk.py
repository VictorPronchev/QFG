"""Public QFG Dynamics Python SDK.

Content scripts should import this module instead of reaching into Blender
operators or private runtime globals.  The same surface can later be backed by
a compiled C++/CUDA runtime.
"""
from __future__ import annotations

from typing import Optional

from .core import ActorSpec, EngineConfig
from .dynamics import BodySpec, QFGWorld, WorldConfig


def create_world(
    engine_config: Optional[EngineConfig] = None,
    world_config: Optional[WorldConfig] = None,
) -> QFGWorld:
    return QFGWorld(engine_config or EngineConfig(), world_config or WorldConfig())


__all__ = [
    "ActorSpec",
    "EngineConfig",
    "BodySpec",
    "WorldConfig",
    "QFGWorld",
    "create_world",
]
