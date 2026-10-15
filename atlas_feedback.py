"""B4 bidirectional Atlas <-> QFG feedback bridge.

This module is deliberately Blender-independent.  It samples the reduced QFG
field at tagged Atlas source locations and returns bounded translation / rotation
updates for those source frames.  The bridge is a CONDITIONAL numerical
relaxation law, not a first-principles BSM-SG force normalization.

Design goals
------------
* deterministic and regression-testable outside Blender;
* no REJECTED source may drive feedback;
* force and torque channels are explicit and separately inspectable;
* bounded per-cycle updates plus anchor restoring terms prevent runaway motion;
* positions are sampled in QFG coordinates using ``scene_scale`` while returned
  displacements remain Blender scene-space deltas.

The default law is intentionally simple::

    F = k_F c_F grad(rho) - k_anchor (x - x0)

and the alignment torque is built from a selected local target direction
(density gradient, spin texture, or a normalized hybrid)::

    tau = k_T c_T [(1-m) d x t + m n x t]
          + k_rot [(1-m) d x d0 + m n x n0]

where ``d`` is the Atlas direction, ``n`` the orbital-plane normal, and ``m``
is ``orbital_torque_mix``.  These are reduced relaxation proxies only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional, Sequence, Tuple
import math
import numpy as np

Vec3 = Tuple[float, float, float]


@dataclass(frozen=True)
class AtlasFeedbackSource:
    name: str
    position: Vec3
    direction: Vec3
    orbital_normal: Vec3
    anchor_position: Vec3
    anchor_direction: Vec3
    anchor_orbital_normal: Vec3
    force_coupling: float = 1.0
    torque_coupling: float = 1.0
    linear_mobility: float = 1.0
    angular_mobility: float = 1.0
    lock_position: bool = False
    lock_rotation: bool = False
    role: str = "OTHER"
    nucleon_type: str = "OTHER"
    provenance: str = "SOURCE"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasFeedbackConfig:
    target_mode: str = "DENSITY_GRADIENT"  # DENSITY_GRADIENT / SPIN_TEXTURE / HYBRID
    force_scale: float = 0.25
    torque_scale: float = 0.25
    anchor_strength: float = 0.10
    orientation_anchor_strength: float = 0.05
    orbital_torque_mix: float = 0.50
    spin_mix: float = 0.50
    scene_scale: float = 1.0
    dt: float = 0.002
    max_step: float = 0.02
    max_angle_deg: float = 1.0
    max_displacement: float = 0.50
    gradient_epsilon: float = 1.0e-12

    def validate(self) -> None:
        if self.target_mode.upper() not in {"DENSITY_GRADIENT", "SPIN_TEXTURE", "HYBRID"}:
            raise ValueError("target_mode must be DENSITY_GRADIENT, SPIN_TEXTURE or HYBRID")
        for label, value in (
            ("force_scale", self.force_scale), ("torque_scale", self.torque_scale),
            ("anchor_strength", self.anchor_strength),
            ("orientation_anchor_strength", self.orientation_anchor_strength),
            ("scene_scale", self.scene_scale), ("dt", self.dt),
            ("max_step", self.max_step), ("max_angle_deg", self.max_angle_deg),
            ("max_displacement", self.max_displacement),
            ("gradient_epsilon", self.gradient_epsilon),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{label} must be finite")
        if self.scene_scale <= 0.0 or self.dt <= 0.0:
            raise ValueError("scene_scale and dt must be positive")
        if self.max_step < 0.0 or self.max_angle_deg < 0.0 or self.max_displacement < 0.0:
            raise ValueError("step/angle/displacement limits must be non-negative")
        if self.gradient_epsilon <= 0.0:
            raise ValueError("gradient_epsilon must be positive")
        if not 0.0 <= float(self.orbital_torque_mix) <= 1.0:
            raise ValueError("orbital_torque_mix must be in [0, 1]")
        if not 0.0 <= float(self.spin_mix) <= 1.0:
            raise ValueError("spin_mix must be in [0, 1]")


@dataclass(frozen=True)
class AtlasFeedbackDelta:
    name: str
    sampled_density: float
    sampled_gradient: Vec3
    sampled_spin: Vec3
    target_direction: Vec3
    force: Vec3
    torque: Vec3
    displacement: Vec3
    rotation_vector: Vec3
    displacement_clipped: bool
    rotation_clipped: bool
    anchor_clipped: bool
    provenance: str = "CONDITIONAL"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasFeedbackSummary:
    source_count: int
    moved_count: int
    rotated_count: int
    clipped_count: int
    mean_force: float
    max_force: float
    mean_torque: float
    max_torque: float
    mean_step: float
    max_step: float
    force_work_proxy: float
    torque_work_proxy: float
    total_work_proxy: float
    max_anchor_displacement: float
    target_mode: str
    provenance: str
    note: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _vec3(value: Sequence[float], label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} must be a finite 3-vector")
    return arr


def _unit(value: Sequence[float], eps: float = 1.0e-12) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    norm = float(np.linalg.norm(arr))
    if norm <= eps:
        return np.zeros(3, dtype=np.float64)
    return arr / norm


def _trilinear(array: np.ndarray, coords: Tuple[float, float, float]) -> float:
    nx, ny, nz = array.shape
    x, y, z = coords
    x0 = int(math.floor(x)) % nx
    y0 = int(math.floor(y)) % ny
    z0 = int(math.floor(z)) % nz
    x1, y1, z1 = (x0 + 1) % nx, (y0 + 1) % ny, (z0 + 1) % nz
    tx, ty, tz = x - math.floor(x), y - math.floor(y), z - math.floor(z)
    c000, c100 = array[x0, y0, z0], array[x1, y0, z0]
    c010, c110 = array[x0, y1, z0], array[x1, y1, z0]
    c001, c101 = array[x0, y0, z1], array[x1, y0, z1]
    c011, c111 = array[x0, y1, z1], array[x1, y1, z1]
    c00 = c000 * (1 - tx) + c100 * tx
    c10 = c010 * (1 - tx) + c110 * tx
    c01 = c001 * (1 - tx) + c101 * tx
    c11 = c011 * (1 - tx) + c111 * tx
    c0 = c00 * (1 - ty) + c10 * ty
    c1 = c01 * (1 - ty) + c11 * ty
    return float(c0 * (1 - tz) + c1 * tz)


def _grid_coordinates(position_qfg: np.ndarray, domain_length: float, dx: float) -> Tuple[float, float, float]:
    normalized = ((position_qfg + float(domain_length) / 2.0) % float(domain_length)) / float(dx)
    return float(normalized[0]), float(normalized[1]), float(normalized[2])


def prepare_density_gradient(density: np.ndarray, dx: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return a periodic central-difference gradient on the QFG FFT grid.

    The core field engine uses periodic spatial boundaries.  B4 therefore uses
    the same topology instead of NumPy's one-sided edge gradients; otherwise a
    source close to a box face would feel an artificial boundary force.
    """
    rho = np.asarray(density, dtype=np.float64)
    if rho.ndim != 3 or not np.all(np.isfinite(rho)):
        raise ValueError("density must be a finite 3-D array")
    if min(rho.shape) < 2:
        raise ValueError("density axes must contain at least two cells")
    if not math.isfinite(float(dx)) or dx <= 0.0:
        raise ValueError("dx must be finite and positive")
    inv_2dx = 0.5 / float(dx)
    return tuple(
        (np.roll(rho, -1, axis=axis) - np.roll(rho, 1, axis=axis)) * inv_2dx
        for axis in range(3)
    )  # type: ignore


def sample_feedback_field(
    position_scene: Sequence[float],
    *,
    density: np.ndarray,
    density_gradient: Tuple[np.ndarray, np.ndarray, np.ndarray],
    domain_length: float,
    dx: float,
    scene_scale: float = 1.0,
    spin_texture: Optional[Sequence[np.ndarray]] = None,
) -> Tuple[float, np.ndarray, np.ndarray]:
    pos_qfg = _vec3(position_scene, "position") * float(scene_scale)
    coords = _grid_coordinates(pos_qfg, domain_length, dx)
    sampled_density = _trilinear(np.asarray(density, dtype=np.float64), coords)
    grad = np.asarray([_trilinear(np.asarray(c, dtype=np.float64), coords) for c in density_gradient], dtype=np.float64)
    if spin_texture is None:
        spin = np.zeros(3, dtype=np.float64)
    else:
        if len(spin_texture) != 3:
            raise ValueError("spin_texture must contain three arrays")
        spin = np.asarray([_trilinear(np.asarray(c, dtype=np.float64), coords) for c in spin_texture], dtype=np.float64)
    return sampled_density, grad, spin


def _target_direction(gradient: np.ndarray, spin: np.ndarray, cfg: AtlasFeedbackConfig) -> np.ndarray:
    g = _unit(gradient, cfg.gradient_epsilon)
    s = _unit(spin, cfg.gradient_epsilon)
    mode = cfg.target_mode.upper()
    if mode == "DENSITY_GRADIENT":
        return g
    if mode == "SPIN_TEXTURE":
        return s if np.linalg.norm(s) > 0.0 else g
    # Hybrid: normalized weighted sum, with graceful fallback.
    mixed = (1.0 - float(cfg.spin_mix)) * g + float(cfg.spin_mix) * s
    result = _unit(mixed, cfg.gradient_epsilon)
    if np.linalg.norm(result) <= 0.0:
        return g if np.linalg.norm(g) > 0.0 else s
    return result


def _clip_vector(vector: np.ndarray, max_norm: float) -> Tuple[np.ndarray, bool]:
    if max_norm <= 0.0:
        return np.zeros(3, dtype=np.float64), bool(np.linalg.norm(vector) > 0.0)
    norm = float(np.linalg.norm(vector))
    if norm <= max_norm:
        return vector, False
    return vector * (max_norm / max(norm, 1.0e-30)), True


def evaluate_feedback(
    sources: Sequence[AtlasFeedbackSource],
    *,
    density: np.ndarray,
    domain_length: float,
    dx: float,
    config: Optional[AtlasFeedbackConfig] = None,
    spin_texture: Optional[Sequence[np.ndarray]] = None,
) -> Tuple[Tuple[AtlasFeedbackDelta, ...], AtlasFeedbackSummary]:
    cfg = config or AtlasFeedbackConfig()
    cfg.validate()
    gradient_fields = prepare_density_gradient(density, dx)
    deltas = []

    for src in sources:
        if str(src.provenance).upper() == "REJECTED":
            continue
        pos = _vec3(src.position, f"{src.name} position")
        anchor_pos = _vec3(src.anchor_position, f"{src.name} anchor position")
        direction = _unit(src.direction, cfg.gradient_epsilon)
        normal = _unit(src.orbital_normal, cfg.gradient_epsilon)
        anchor_dir = _unit(src.anchor_direction, cfg.gradient_epsilon)
        anchor_normal = _unit(src.anchor_orbital_normal, cfg.gradient_epsilon)
        if np.linalg.norm(direction) <= 0.0 or np.linalg.norm(normal) <= 0.0:
            raise ValueError(f"{src.name}: direction and orbital normal must be non-zero")

        rho, grad, spin = sample_feedback_field(
            pos, density=density, density_gradient=gradient_fields,
            domain_length=domain_length, dx=dx, scene_scale=cfg.scene_scale,
            spin_texture=spin_texture,
        )
        target = _target_direction(grad, spin, cfg)

        force = float(cfg.force_scale) * float(src.force_coupling) * grad
        force -= float(cfg.anchor_strength) * (pos - anchor_pos)
        if src.lock_position:
            displacement = np.zeros(3, dtype=np.float64)
            disp_clipped = False
            anchor_clipped = False
        else:
            displacement = float(src.linear_mobility) * force * float(cfg.dt)
            displacement, disp_clipped = _clip_vector(displacement, float(cfg.max_step))
            proposed = pos + displacement
            offset = proposed - anchor_pos
            anchor_clipped = False
            if cfg.max_displacement > 0.0:
                offset_norm = float(np.linalg.norm(offset))
                if offset_norm > float(cfg.max_displacement):
                    proposed = anchor_pos + offset * (float(cfg.max_displacement) / max(offset_norm, 1.0e-30))
                    displacement = proposed - pos
                    anchor_clipped = True

        mix = float(cfg.orbital_torque_mix)
        torque = np.zeros(3, dtype=np.float64)
        if np.linalg.norm(target) > 0.0:
            align = (1.0 - mix) * np.cross(direction, target) + mix * np.cross(normal, target)
            torque += float(cfg.torque_scale) * float(src.torque_coupling) * align
        anchor_align = (1.0 - mix) * np.cross(direction, anchor_dir) + mix * np.cross(normal, anchor_normal)
        torque += float(cfg.orientation_anchor_strength) * anchor_align

        if src.lock_rotation:
            rotation_vector = np.zeros(3, dtype=np.float64)
            rot_clipped = False
        else:
            rotation_vector = float(src.angular_mobility) * torque * float(cfg.dt)
            rotation_vector, rot_clipped = _clip_vector(rotation_vector, math.radians(float(cfg.max_angle_deg)))

        deltas.append(AtlasFeedbackDelta(
            name=src.name,
            sampled_density=float(rho),
            sampled_gradient=tuple(float(v) for v in grad),
            sampled_spin=tuple(float(v) for v in spin),
            target_direction=tuple(float(v) for v in target),
            force=tuple(float(v) for v in force),
            torque=tuple(float(v) for v in torque),
            displacement=tuple(float(v) for v in displacement),
            rotation_vector=tuple(float(v) for v in rotation_vector),
            displacement_clipped=bool(disp_clipped),
            rotation_clipped=bool(rot_clipped),
            anchor_clipped=bool(anchor_clipped),
        ))

    if deltas:
        forces = np.asarray([d.force for d in deltas], dtype=np.float64)
        torques = np.asarray([d.torque for d in deltas], dtype=np.float64)
        steps = np.asarray([d.displacement for d in deltas], dtype=np.float64)
        force_norm = np.linalg.norm(forces, axis=1)
        torque_norm = np.linalg.norm(torques, axis=1)
        step_norm = np.linalg.norm(steps, axis=1)
        anchors = {s.name: np.asarray(s.anchor_position, dtype=np.float64) for s in sources}
        pos_map = {s.name: np.asarray(s.position, dtype=np.float64) for s in sources}
        anchor_disp = [float(np.linalg.norm(pos_map[d.name] + np.asarray(d.displacement) - anchors[d.name])) for d in deltas]
        force_work = float(sum(np.dot(np.asarray(d.force, dtype=np.float64), np.asarray(d.displacement, dtype=np.float64)) for d in deltas))
        torque_work = float(sum(np.dot(np.asarray(d.torque, dtype=np.float64), np.asarray(d.rotation_vector, dtype=np.float64)) for d in deltas))
        clipped = sum(bool(d.displacement_clipped or d.rotation_clipped or d.anchor_clipped) for d in deltas)
        moved = sum(float(np.linalg.norm(d.displacement)) > 1.0e-15 for d in deltas)
        rotated = sum(float(np.linalg.norm(d.rotation_vector)) > 1.0e-15 for d in deltas)
        summary = AtlasFeedbackSummary(
            source_count=len(deltas), moved_count=int(moved), rotated_count=int(rotated), clipped_count=int(clipped),
            mean_force=float(np.mean(force_norm)), max_force=float(np.max(force_norm)),
            mean_torque=float(np.mean(torque_norm)), max_torque=float(np.max(torque_norm)),
            mean_step=float(np.mean(step_norm)), max_step=float(np.max(step_norm)),
            force_work_proxy=force_work, torque_work_proxy=torque_work,
            total_work_proxy=force_work + torque_work,
            max_anchor_displacement=float(max(anchor_disp)), target_mode=cfg.target_mode.upper(),
            provenance="CONDITIONAL",
            note=(
                "B4 bidirectional feedback is a bounded dimensionless relaxation bridge. "
                "Force/torque normalization, mobilities and anchor terms are CONDITIONAL; "
                "they are not claimed as first-principles BSM-SG dynamics."
            ),
        )
    else:
        summary = AtlasFeedbackSummary(
            source_count=0, moved_count=0, rotated_count=0, clipped_count=0,
            mean_force=0.0, max_force=0.0, mean_torque=0.0, max_torque=0.0,
            mean_step=0.0, max_step=0.0, force_work_proxy=0.0, torque_work_proxy=0.0,
            total_work_proxy=0.0, max_anchor_displacement=0.0,
            target_mode=cfg.target_mode.upper(), provenance="DERIVED",
            note="No non-rejected B4 feedback sources were evaluated.",
        )
    return tuple(deltas), summary


def rodrigues_rotate(vector: Sequence[float], rotation_vector: Sequence[float]) -> np.ndarray:
    """Rotate a vector by an axis-angle rotation vector (radians)."""
    v = _vec3(vector, "vector")
    rv = _vec3(rotation_vector, "rotation_vector")
    angle = float(np.linalg.norm(rv))
    if angle <= 1.0e-15:
        return v.copy()
    axis = rv / angle
    return (
        v * math.cos(angle)
        + np.cross(axis, v) * math.sin(angle)
        + axis * float(np.dot(axis, v)) * (1.0 - math.cos(angle))
    )


__all__ = [
    "AtlasFeedbackSource", "AtlasFeedbackConfig", "AtlasFeedbackDelta", "AtlasFeedbackSummary",
    "prepare_density_gradient", "sample_feedback_field", "evaluate_feedback", "rodrigues_rotate",
]
