"""B5 constraint-aware Atlas/QFG relaxation.

Pure numerical geometry projection used after the B4 field-feedback proposal.
The module preserves reviewed Atlas topology while still allowing collective
valence motion.  It is intentionally dimensionless/geometry-only and carries
CONDITIONAL provenance for the projection law.

Supported constraint families
-----------------------------
* captured pair distances (explicit/manual, parent-child, or B2 source-star);
* radial shell preservation around the Atlas nuclear centre;
* per-node angular cones around captured valence directions;
* symmetry groups that preserve a captured azimuth pattern while allowing the
  *collective polar tilt* to relax.  For a three-arm C3 group this means the
  H-X-H-like pair angle is free to evolve rather than being frozen at capture.

The solver is an iterative bounded projection, not a claim of an absolute
BSM-SG force law.  It is designed to keep B4 proposals inside a declared
geometric admissible set and to be deterministic/regression-testable without
Blender.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple
import math
import numpy as np

Vec3 = Tuple[float, float, float]


@dataclass(frozen=True)
class AtlasConstraintNode:
    name: str
    position: Vec3
    anchor_position: Vec3
    movable: bool = True
    preserve_radius: bool = True
    max_cone_deg: float = 0.0  # <=0 disables the cone
    symmetry_group: str = ""
    role: str = "OTHER"
    provenance: str = "SOURCE"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasDistanceConstraint:
    a: str
    b: str
    target_distance: float
    stiffness: float = 1.0
    provenance: str = "SOURCE"
    note: str = ""

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasSymmetryConstraint:
    name: str
    members: Tuple[str, ...]
    axis: Vec3
    azimuth_directions: Tuple[Tuple[str, Vec3], ...]
    provenance: str = "DERIVED"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasConstraintConfig:
    iterations: int = 8
    distance_stiffness: float = 1.0
    shell_stiffness: float = 1.0
    cone_stiffness: float = 1.0
    symmetry_stiffness: float = 0.75
    shell_tolerance: float = 0.0
    convergence_tolerance: float = 1.0e-6
    max_correction: float = 0.025
    preserve_movable_centroid: bool = False
    epsilon: float = 1.0e-12

    def validate(self) -> None:
        if int(self.iterations) < 1:
            raise ValueError("iterations must be >= 1")
        for label, value in (
            ("distance_stiffness", self.distance_stiffness),
            ("shell_stiffness", self.shell_stiffness),
            ("cone_stiffness", self.cone_stiffness),
            ("symmetry_stiffness", self.symmetry_stiffness),
            ("shell_tolerance", self.shell_tolerance),
            ("convergence_tolerance", self.convergence_tolerance),
            ("max_correction", self.max_correction),
            ("epsilon", self.epsilon),
        ):
            if not math.isfinite(float(value)):
                raise ValueError(f"{label} must be finite")
        if self.shell_tolerance < 0.0 or self.convergence_tolerance < 0.0 or self.max_correction < 0.0:
            raise ValueError("tolerances/max_correction must be non-negative")
        if self.epsilon <= 0.0:
            raise ValueError("epsilon must be positive")
        for label, value in (
            ("distance_stiffness", self.distance_stiffness),
            ("shell_stiffness", self.shell_stiffness),
            ("cone_stiffness", self.cone_stiffness),
            ("symmetry_stiffness", self.symmetry_stiffness),
        ):
            if float(value) < 0.0:
                raise ValueError(f"{label} must be non-negative")


@dataclass(frozen=True)
class AtlasConstraintDelta:
    name: str
    proposed_position: Vec3
    constrained_position: Vec3
    correction: Vec3
    correction_norm: float
    shell_error: float
    cone_excess_deg: float
    provenance: str = "CONDITIONAL"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AtlasConstraintSummary:
    node_count: int
    movable_count: int
    pair_constraint_count: int
    symmetry_group_count: int
    iterations_performed: int
    converged: bool
    max_pair_error_before: float
    max_pair_error_after: float
    max_shell_error_before: float
    max_shell_error_after: float
    max_cone_excess_before_deg: float
    max_cone_excess_after_deg: float
    max_correction_norm: float
    rms_correction_norm: float
    mean_symmetry_pair_angle_before_deg: float
    mean_symmetry_pair_angle_after_deg: float
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
    n = float(np.linalg.norm(arr))
    if n <= eps:
        return np.zeros(3, dtype=np.float64)
    return arr / n


def _angle_deg(a: Sequence[float], b: Sequence[float], eps: float = 1.0e-12) -> float:
    ua, ub = _unit(a, eps), _unit(b, eps)
    if np.linalg.norm(ua) <= eps or np.linalg.norm(ub) <= eps:
        return 0.0
    return math.degrees(math.acos(float(np.clip(np.dot(ua, ub), -1.0, 1.0))))


def _bounded(delta: np.ndarray, max_norm: float, eps: float) -> np.ndarray:
    if max_norm <= 0.0:
        return delta
    n = float(np.linalg.norm(delta))
    if n <= max_norm or n <= eps:
        return delta
    return delta * (max_norm / n)


def _slerp_unit(a: np.ndarray, b: np.ndarray, t: float, eps: float) -> np.ndarray:
    ua, ub = _unit(a, eps), _unit(b, eps)
    dot = float(np.clip(np.dot(ua, ub), -1.0, 1.0))
    omega = math.acos(dot)
    if omega <= eps:
        return ua
    if abs(math.pi - omega) <= 1.0e-8:
        # Deterministic orthogonal fallback for antipodal vectors.
        trial = np.array((1.0, 0.0, 0.0), dtype=np.float64)
        if abs(float(np.dot(trial, ua))) > 0.9:
            trial = np.array((0.0, 1.0, 0.0), dtype=np.float64)
        tangent = _unit(trial - np.dot(trial, ua) * ua, eps)
        return _unit(math.cos(math.pi * t) * ua + math.sin(math.pi * t) * tangent, eps)
    so = math.sin(omega)
    return _unit(math.sin((1.0 - t) * omega) / so * ua + math.sin(t * omega) / so * ub, eps)


def build_symmetry_constraints(
    nodes: Sequence[AtlasConstraintNode], center: Sequence[float], eps: float = 1.0e-12,
) -> Tuple[AtlasSymmetryConstraint, ...]:
    """Build group frames from captured anchor positions.

    The symmetry axis is the normalized sum of anchor directions.  The captured
    transverse direction of each member becomes its azimuth reference.  During
    projection the common polar tilt may change, so this does *not* freeze the
    pair angle of a C3 group.
    """
    c = _vec3(center, "center")
    groups: Dict[str, list[AtlasConstraintNode]] = {}
    for node in nodes:
        name = str(node.symmetry_group).strip()
        if name:
            groups.setdefault(name, []).append(node)
    out = []
    for group_name in sorted(groups):
        members = sorted(groups[group_name], key=lambda n: n.name)
        if len(members) < 2:
            continue
        dirs = [_unit(_vec3(n.anchor_position, n.name + " anchor") - c, eps) for n in members]
        axis = _unit(np.sum(dirs, axis=0), eps)
        if np.linalg.norm(axis) <= eps:
            # PCA fallback: normal to the dominant anchor plane.
            m = np.asarray(dirs, dtype=np.float64)
            cov = m.T @ m
            vals, vecs = np.linalg.eigh(cov)
            axis = _unit(vecs[:, int(np.argmin(vals))], eps)
        # Orient deterministically toward the summed direction if available.
        summed = np.sum(dirs, axis=0)
        if np.linalg.norm(summed) > eps and float(np.dot(axis, summed)) < 0.0:
            axis = -axis
        azimuths = []
        fallback_basis = None
        for node, direction in zip(members, dirs):
            transverse = direction - float(np.dot(direction, axis)) * axis
            tangent = _unit(transverse, eps)
            if np.linalg.norm(tangent) <= eps:
                if fallback_basis is None:
                    trial = np.array((1.0, 0.0, 0.0), dtype=np.float64)
                    if abs(float(np.dot(trial, axis))) > 0.9:
                        trial = np.array((0.0, 1.0, 0.0), dtype=np.float64)
                    fallback_basis = _unit(trial - float(np.dot(trial, axis)) * axis, eps)
                tangent = fallback_basis
            azimuths.append((node.name, tuple(float(v) for v in tangent)))
        out.append(AtlasSymmetryConstraint(
            name=group_name,
            members=tuple(n.name for n in members),
            axis=tuple(float(v) for v in axis),
            azimuth_directions=tuple(azimuths),
        ))
    return tuple(out)


def _pair_error(positions: Mapping[str, np.ndarray], pairs: Sequence[AtlasDistanceConstraint]) -> float:
    errors = []
    for edge in pairs:
        if edge.a not in positions or edge.b not in positions:
            continue
        d = float(np.linalg.norm(positions[edge.b] - positions[edge.a]))
        errors.append(abs(d - float(edge.target_distance)))
    return max(errors, default=0.0)


def _shell_error(
    positions: Mapping[str, np.ndarray], nodes: Mapping[str, AtlasConstraintNode], center: np.ndarray,
) -> float:
    errors = []
    for name, node in nodes.items():
        if not node.preserve_radius or name not in positions:
            continue
        target = float(np.linalg.norm(_vec3(node.anchor_position, name + " anchor") - center))
        current = float(np.linalg.norm(positions[name] - center))
        errors.append(abs(current - target))
    return max(errors, default=0.0)


def _cone_excess(
    positions: Mapping[str, np.ndarray], nodes: Mapping[str, AtlasConstraintNode], center: np.ndarray, eps: float,
) -> float:
    excess = []
    for name, node in nodes.items():
        if node.max_cone_deg <= 0.0 or name not in positions:
            continue
        a = _vec3(node.anchor_position, name + " anchor") - center
        b = positions[name] - center
        excess.append(max(0.0, _angle_deg(a, b, eps) - float(node.max_cone_deg)))
    return max(excess, default=0.0)


def _symmetry_pair_mean(
    positions: Mapping[str, np.ndarray], groups: Sequence[AtlasSymmetryConstraint], center: np.ndarray, eps: float,
) -> float:
    values = []
    for group in groups:
        members = [name for name in group.members if name in positions]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                values.append(_angle_deg(positions[members[i]] - center, positions[members[j]] - center, eps))
    return float(np.mean(values)) if values else 0.0


def project_atlas_constraints(
    nodes: Sequence[AtlasConstraintNode],
    proposed_positions: Mapping[str, Sequence[float]],
    *,
    center: Sequence[float],
    distance_constraints: Sequence[AtlasDistanceConstraint] = (),
    symmetry_constraints: Optional[Sequence[AtlasSymmetryConstraint]] = None,
    config: Optional[AtlasConstraintConfig] = None,
) -> Tuple[Tuple[AtlasConstraintDelta, ...], AtlasConstraintSummary]:
    """Project proposed Atlas positions into the captured B5 admissible set."""
    cfg = config or AtlasConstraintConfig()
    cfg.validate()
    c = _vec3(center, "center")
    node_map = {n.name: n for n in nodes if str(n.provenance).upper() != "REJECTED"}
    positions: Dict[str, np.ndarray] = {}
    proposed: Dict[str, np.ndarray] = {}
    for name, node in node_map.items():
        p = _vec3(proposed_positions.get(name, node.position), name + " proposed")
        positions[name] = p.copy()
        proposed[name] = p.copy()
    pairs = tuple(
        edge for edge in distance_constraints
        if str(edge.provenance).upper() != "REJECTED"
        and edge.a in node_map and edge.b in node_map
        and edge.a != edge.b and float(edge.target_distance) >= 0.0
    )
    groups = tuple(symmetry_constraints) if symmetry_constraints is not None else build_symmetry_constraints(tuple(node_map.values()), c, cfg.epsilon)

    pair_before = _pair_error(positions, pairs)
    shell_before = _shell_error(positions, node_map, c)
    cone_before = _cone_excess(positions, node_map, c, cfg.epsilon)
    symmetry_before = _symmetry_pair_mean(positions, groups, c, cfg.epsilon)
    movable_names = [name for name, node in node_map.items() if node.movable]
    initial_centroid = np.mean([positions[n] for n in movable_names], axis=0) if movable_names else np.zeros(3)

    performed = 0
    converged = False
    for iteration in range(int(cfg.iterations)):
        max_applied = 0.0

        # Pair-distance projection.
        for edge in pairs:
            pa, pb = positions[edge.a], positions[edge.b]
            delta = pb - pa
            dist = float(np.linalg.norm(delta))
            if dist <= cfg.epsilon:
                continue
            error = dist - float(edge.target_distance)
            if abs(error) <= cfg.convergence_tolerance:
                continue
            unit = delta / dist
            strength = float(cfg.distance_stiffness) * float(edge.stiffness)
            correction = _bounded(0.5 * strength * error * unit, cfg.max_correction, cfg.epsilon)
            ma, mb = node_map[edge.a].movable, node_map[edge.b].movable
            if ma and mb:
                positions[edge.a] += correction
                positions[edge.b] -= correction
                max_applied = max(max_applied, float(np.linalg.norm(correction)))
            elif ma:
                full = _bounded(2.0 * correction, cfg.max_correction, cfg.epsilon)
                positions[edge.a] += full
                max_applied = max(max_applied, float(np.linalg.norm(full)))
            elif mb:
                full = _bounded(2.0 * correction, cfg.max_correction, cfg.epsilon)
                positions[edge.b] -= full
                max_applied = max(max_applied, float(np.linalg.norm(full)))

        # Radial shell preservation.  Tolerance defines a real admissible band.
        for name, node in node_map.items():
            if not node.movable or not node.preserve_radius:
                continue
            current_vec = positions[name] - c
            r = float(np.linalg.norm(current_vec))
            target_r = float(np.linalg.norm(_vec3(node.anchor_position, name + " anchor") - c))
            if r <= cfg.epsilon or target_r <= cfg.epsilon:
                continue
            error = r - target_r
            excess = max(0.0, abs(error) - float(cfg.shell_tolerance))
            if excess <= cfg.convergence_tolerance:
                continue
            signed_excess = math.copysign(excess, error)
            corr = -float(cfg.shell_stiffness) * signed_excess * (current_vec / r)
            corr = _bounded(corr, cfg.max_correction, cfg.epsilon)
            positions[name] += corr
            max_applied = max(max_applied, float(np.linalg.norm(corr)))

        # Per-node angular freedom cone around the captured radial direction.
        for name, node in node_map.items():
            if not node.movable or float(node.max_cone_deg) <= 0.0:
                continue
            anchor = _unit(_vec3(node.anchor_position, name + " anchor") - c, cfg.epsilon)
            current_vec = positions[name] - c
            r = float(np.linalg.norm(current_vec))
            current = _unit(current_vec, cfg.epsilon)
            if r <= cfg.epsilon or np.linalg.norm(anchor) <= cfg.epsilon or np.linalg.norm(current) <= cfg.epsilon:
                continue
            angle = _angle_deg(anchor, current, cfg.epsilon)
            max_angle = float(node.max_cone_deg)
            if angle <= max_angle + cfg.convergence_tolerance:
                continue
            desired = _slerp_unit(anchor, current, max_angle / max(angle, cfg.epsilon), cfg.epsilon)
            target_pos = c + r * desired
            corr = float(cfg.cone_stiffness) * (target_pos - positions[name])
            corr = _bounded(corr, cfg.max_correction, cfg.epsilon)
            positions[name] += corr
            max_applied = max(max_applied, float(np.linalg.norm(corr)))

        # Symmetry projection: preserve captured azimuth pattern, but use the
        # *current mean polar tilt*.  This lets a C3 pyramid open/close.
        for group in groups:
            members = [n for n in group.members if n in positions and node_map[n].movable]
            if len(members) < 2:
                continue
            axis = _unit(group.axis, cfg.epsilon)
            if np.linalg.norm(axis) <= cfg.epsilon:
                continue
            current_alpha = []
            for name in members:
                u = _unit(positions[name] - c, cfg.epsilon)
                if np.linalg.norm(u) > cfg.epsilon:
                    current_alpha.append(math.acos(float(np.clip(np.dot(u, axis), -1.0, 1.0))))
            if not current_alpha:
                continue
            alpha = float(np.mean(current_alpha))
            azimuth_map = {name: _unit(vec, cfg.epsilon) for name, vec in group.azimuth_directions}
            for name in members:
                tangent = azimuth_map.get(name)
                if tangent is None or np.linalg.norm(tangent) <= cfg.epsilon:
                    continue
                r = float(np.linalg.norm(positions[name] - c))
                if r <= cfg.epsilon:
                    continue
                desired_dir = _unit(math.cos(alpha) * axis + math.sin(alpha) * tangent, cfg.epsilon)
                target_pos = c + r * desired_dir
                corr = float(cfg.symmetry_stiffness) * (target_pos - positions[name])
                corr = _bounded(corr, cfg.max_correction, cfg.epsilon)
                positions[name] += corr
                max_applied = max(max_applied, float(np.linalg.norm(corr)))

        if cfg.preserve_movable_centroid and movable_names:
            centroid = np.mean([positions[n] for n in movable_names], axis=0)
            shift = initial_centroid - centroid
            shift = _bounded(shift, cfg.max_correction, cfg.epsilon)
            for name in movable_names:
                positions[name] += shift
            max_applied = max(max_applied, float(np.linalg.norm(shift)))

        performed = iteration + 1
        pair_now = _pair_error(positions, pairs)
        shell_now = max(0.0, _shell_error(positions, node_map, c) - float(cfg.shell_tolerance))
        cone_now = _cone_excess(positions, node_map, c, cfg.epsilon)
        if max(pair_now, shell_now, math.radians(cone_now), max_applied) <= float(cfg.convergence_tolerance):
            converged = True
            break

    deltas = []
    correction_norms = []
    for name in sorted(node_map):
        corr = positions[name] - proposed[name]
        corr_norm = float(np.linalg.norm(corr))
        correction_norms.append(corr_norm)
        node = node_map[name]
        shell_error = 0.0
        if node.preserve_radius:
            shell_error = abs(
                float(np.linalg.norm(positions[name] - c))
                - float(np.linalg.norm(_vec3(node.anchor_position, name + " anchor") - c))
            )
        cone_excess = 0.0
        if node.max_cone_deg > 0.0:
            cone_excess = max(
                0.0,
                _angle_deg(_vec3(node.anchor_position, name + " anchor") - c, positions[name] - c, cfg.epsilon)
                - float(node.max_cone_deg),
            )
        deltas.append(AtlasConstraintDelta(
            name=name,
            proposed_position=tuple(float(v) for v in proposed[name]),
            constrained_position=tuple(float(v) for v in positions[name]),
            correction=tuple(float(v) for v in corr),
            correction_norm=corr_norm,
            shell_error=float(shell_error),
            cone_excess_deg=float(cone_excess),
        ))

    pair_after = _pair_error(positions, pairs)
    shell_after = _shell_error(positions, node_map, c)
    cone_after = _cone_excess(positions, node_map, c, cfg.epsilon)
    symmetry_after = _symmetry_pair_mean(positions, groups, c, cfg.epsilon)
    summary = AtlasConstraintSummary(
        node_count=len(node_map),
        movable_count=sum(bool(n.movable) for n in node_map.values()),
        pair_constraint_count=len(pairs),
        symmetry_group_count=len(groups),
        iterations_performed=performed,
        converged=bool(converged),
        max_pair_error_before=float(pair_before),
        max_pair_error_after=float(pair_after),
        max_shell_error_before=float(shell_before),
        max_shell_error_after=float(shell_after),
        max_cone_excess_before_deg=float(cone_before),
        max_cone_excess_after_deg=float(cone_after),
        max_correction_norm=max(correction_norms, default=0.0),
        rms_correction_norm=float(np.sqrt(np.mean(np.square(correction_norms)))) if correction_norms else 0.0,
        mean_symmetry_pair_angle_before_deg=float(symmetry_before),
        mean_symmetry_pair_angle_after_deg=float(symmetry_after),
        provenance="CONDITIONAL",
        note=(
            "B5 is a bounded geometry-projection layer. Captured topology may be SOURCE/DERIVED, "
            "but projection stiffnesses, tolerances and iterative relaxation are CONDITIONAL and "
            "must not be interpreted as absolute BSM-SG forces or energies."
        ),
    )
    return tuple(deltas), summary


__all__ = [
    "AtlasConstraintNode", "AtlasDistanceConstraint", "AtlasSymmetryConstraint",
    "AtlasConstraintConfig", "AtlasConstraintDelta", "AtlasConstraintSummary",
    "build_symmetry_constraints", "project_atlas_constraints",
]
