"""B3 Atlas-to-QFG field bridge.

This module is deliberately Blender-independent.  It converts explicitly tagged
Atlas geometry into *conditional, dimensionless* source fields that can be
rasterized onto the reduced QFG engine grid.

Nothing in this module supplies a physical BSM-SG energy normalization.  The
scalar/vector scales are user/model inputs and are therefore CONDITIONAL unless
an external calibration is explicitly attached by a caller.

Provenance policy
-----------------
SOURCE       object identity/position/direction explicitly sourced/tagged
DERIVED      deterministic geometry built from SOURCE inputs
CONDITIONAL  field kernel, anisotropy law and source-strength bridge
CALIBRATED   caller has supplied a measured/fitted absolute scale
EXPERIMENTAL external reference
REJECTED     audit-only; never drives a field
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional, Sequence, Tuple
import math
import numpy as np


Vec3 = Tuple[float, float, float]
Mat3 = Tuple[Tuple[float, float, float], ...]


@dataclass(frozen=True)
class AtlasFieldSource:
    name: str
    position: Vec3
    direction: Vec3
    orbital_normal: Vec3
    strength: float = 1.0
    radius: float = 0.5
    anisotropy: float = 0.5
    role: str = "OTHER"
    nucleon_type: str = "OTHER"
    provenance: str = "SOURCE"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasFieldConfig:
    kernel: str = "GAUSSIAN"  # GAUSSIAN or SOFT_INV_R3
    vector_mode: str = "DIRECTOR"  # DIRECTOR or DIPOLE_PROXY
    softening: float = 0.25
    scalar_scale: float = 0.25
    vector_scale: float = 0.0
    orbital_mix: float = 0.5
    scene_scale: float = 1.0
    clip_abs: float = 100.0

    def validate(self) -> None:
        if self.kernel.upper() not in {"GAUSSIAN", "SOFT_INV_R3"}:
            raise ValueError("kernel must be GAUSSIAN or SOFT_INV_R3")
        if self.vector_mode.upper() not in {"DIRECTOR", "DIPOLE_PROXY"}:
            raise ValueError("vector_mode must be DIRECTOR or DIPOLE_PROXY")
        if not math.isfinite(self.softening) or self.softening < 0.0:
            raise ValueError("softening must be finite and non-negative")
        if not math.isfinite(self.scene_scale) or self.scene_scale <= 0.0:
            raise ValueError("scene_scale must be finite and positive")
        if not 0.0 <= float(self.orbital_mix) <= 1.0:
            raise ValueError("orbital_mix must be in [0, 1]")
        if not math.isfinite(self.clip_abs) or self.clip_abs <= 0.0:
            raise ValueError("clip_abs must be finite and positive")


@dataclass(frozen=True)
class AtlasFieldSummary:
    source_count: int
    kernel: str
    vector_mode: str
    scalar_min: float
    scalar_max: float
    scalar_mean: float
    scalar_rms: float
    vector_max: float
    vector_rms: float
    provenance: str
    note: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _vec3(value: Sequence[float], label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} must be a finite 3-vector")
    return arr


def _unit(value: Sequence[float], label: str) -> np.ndarray:
    arr = _vec3(value, label)
    norm = float(np.linalg.norm(arr))
    if norm <= 1.0e-12:
        raise ValueError(f"{label} must have non-zero length")
    return arr / norm


def director_tensor(direction: Sequence[float]) -> np.ndarray:
    """Return the traceless uniaxial tensor 3/2 uu^T - 1/2 I.

    Its radial quadratic form ranges from -1/2 (perpendicular) to +1
    (parallel).  This is a generic orientation proxy, not a source BSM-SG law.
    """
    u = _unit(direction, "direction")
    return 1.5 * np.outer(u, u) - 0.5 * np.eye(3, dtype=np.float64)


def source_anisotropy_tensor(source: AtlasFieldSource, orbital_mix: float = 0.5) -> np.ndarray:
    mix = float(orbital_mix)
    if not 0.0 <= mix <= 1.0:
        raise ValueError("orbital_mix must be in [0, 1]")
    q_dir = director_tensor(source.direction)
    q_orb = director_tensor(source.orbital_normal)
    return (1.0 - mix) * q_dir + mix * q_orb


def _profile(r2: np.ndarray, radius: float, cfg: AtlasFieldConfig) -> np.ndarray:
    radius = max(float(radius), 1.0e-9)
    if cfg.kernel.upper() == "GAUSSIAN":
        return np.exp(-0.5 * r2 / (radius * radius))
    # Dimensionless softened inverse-cube proxy: unity-order near r~radius.
    soft = max(float(cfg.softening), 1.0e-12)
    return (radius ** 3) / np.power(r2 + soft * soft, 1.5)


def evaluate_atlas_field(
    points: Sequence[Sequence[float]] | np.ndarray,
    sources: Sequence[AtlasFieldSource],
    config: Optional[AtlasFieldConfig] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Evaluate scalar/vector B3 fields at arbitrary points.

    Returns ``(scalar, vector)`` with shapes ``(M,)`` and ``(M,3)``.
    Positions/radii are scaled by ``scene_scale`` before evaluating the kernel.
    """
    cfg = config or AtlasFieldConfig()
    cfg.validate()
    p = np.asarray(points, dtype=np.float64)
    if p.ndim == 1:
        p = p[None, :]
    if p.ndim != 2 or p.shape[1] != 3 or not np.all(np.isfinite(p)):
        raise ValueError("points must have shape (M,3) with finite values")

    scalar = np.zeros(len(p), dtype=np.float64)
    vector = np.zeros((len(p), 3), dtype=np.float64)
    scale = float(cfg.scene_scale)
    ident = np.eye(3, dtype=np.float64)

    for src in sources:
        if str(src.provenance).upper() == "REJECTED":
            continue
        center = _vec3(src.position, f"position {src.name}") * scale
        direction = _unit(src.direction, f"direction {src.name}")
        normal = _unit(src.orbital_normal, f"orbital normal {src.name}")
        radius = max(float(src.radius) * scale, 1.0e-9)
        strength = float(src.strength)
        anis = float(src.anisotropy)
        if not all(math.isfinite(v) for v in (radius, strength, anis)):
            raise ValueError(f"source {src.name!r} has non-finite parameters")

        delta = p - center[None, :]
        r2 = np.einsum("ij,ij->i", delta, delta)
        profile = _profile(r2, radius, cfg)
        r = np.sqrt(np.maximum(r2, 1.0e-30))
        rhat = delta / r[:, None]
        # Exactly at the source center the anisotropy direction is undefined;
        # use zero radial anisotropy instead of an arbitrary direction.
        at_center = r2 <= 1.0e-24
        if np.any(at_center):
            rhat[at_center] = 0.0

        q = (1.0 - float(cfg.orbital_mix)) * (1.5 * np.outer(direction, direction) - 0.5 * ident)
        q += float(cfg.orbital_mix) * (1.5 * np.outer(normal, normal) - 0.5 * ident)
        angular = np.einsum("ij,jk,ik->i", rhat, q, rhat)
        angular[at_center] = 0.0
        scalar += float(cfg.scalar_scale) * strength * profile * (1.0 + anis * angular)

        if float(cfg.vector_scale) != 0.0:
            if cfg.vector_mode.upper() == "DIRECTOR":
                local_vec = np.broadcast_to(direction, delta.shape)
            else:
                cosine = np.einsum("ij,j->i", rhat, direction)
                local_vec = 3.0 * cosine[:, None] * rhat - direction[None, :]
                local_vec[at_center] = direction
            vector += float(cfg.vector_scale) * strength * profile[:, None] * local_vec

    scalar = np.clip(scalar, -cfg.clip_abs, cfg.clip_abs)
    vector = np.clip(vector, -cfg.clip_abs, cfg.clip_abs)
    return scalar.astype(np.float32), vector.astype(np.float32)


def rasterize_atlas_field(
    space: Sequence[float] | np.ndarray,
    sources: Sequence[AtlasFieldSource],
    config: Optional[AtlasFieldConfig] = None,
) -> Tuple[np.ndarray, np.ndarray, AtlasFieldSummary]:
    """Rasterize a B3 field bundle on a cubic QFG grid defined by ``space``."""
    axis = np.asarray(space, dtype=np.float64)
    if axis.ndim != 1 or len(axis) < 2 or not np.all(np.isfinite(axis)):
        raise ValueError("space must be a finite 1-D axis with at least two samples")
    X, Y, Z = np.meshgrid(axis, axis, axis, indexing="ij")
    points = np.column_stack((X.ravel(), Y.ravel(), Z.ravel()))
    scalar_flat, vector_flat = evaluate_atlas_field(points, sources, config)
    n = len(axis)
    scalar = scalar_flat.reshape((n, n, n))
    vector = vector_flat.reshape((n, n, n, 3)).transpose(3, 0, 1, 2)
    mag = np.sqrt(np.sum(vector.astype(np.float64) ** 2, axis=0))
    cfg = config or AtlasFieldConfig()
    accepted = [s for s in sources if str(s.provenance).upper() != "REJECTED"]
    provenance = "CONDITIONAL" if accepted else "DERIVED"
    summary = AtlasFieldSummary(
        source_count=len(accepted),
        kernel=cfg.kernel.upper(),
        vector_mode=cfg.vector_mode.upper(),
        scalar_min=float(np.min(scalar)) if scalar.size else 0.0,
        scalar_max=float(np.max(scalar)) if scalar.size else 0.0,
        scalar_mean=float(np.mean(scalar)) if scalar.size else 0.0,
        scalar_rms=float(np.sqrt(np.mean(scalar.astype(np.float64) ** 2))) if scalar.size else 0.0,
        vector_max=float(np.max(mag)) if mag.size else 0.0,
        vector_rms=float(np.sqrt(np.mean(mag ** 2))) if mag.size else 0.0,
        provenance=provenance,
        note=(
            "Dimensionless Atlas-to-QFG field bridge. Kernel, anisotropy law and "
            "source strengths are CONDITIONAL; no absolute BSM-SG energy normalization is claimed."
        ),
    )
    return scalar, vector, summary
