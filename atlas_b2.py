"""B2 Atlas interaction graph, orbital-plane analysis and Bohr-envelope proxies.

This module is Blender-independent on purpose.  It turns explicitly tagged or
heuristically inferred Atlas objects into reproducible geometry descriptors.
It does *not* claim that a proxy coupling is a physical interaction energy.

Provenance policy
-----------------
SOURCE       explicit user/source tags and geometry
DERIVED      deterministic geometry calculated from SOURCE inputs
CONDITIONAL  model-dependent bridge (for example an inverse-cube J proxy)
CALIBRATED   uses a measurement or fitted scale
EXPERIMENTAL external reference
REJECTED     audit-only; never drives prediction
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Mapping, Sequence, Tuple
import math
import re
import numpy as np


@dataclass(frozen=True)
class NucleonGuess:
    nucleon_type: str
    role: str
    confidence: float
    evidence: Tuple[str, ...]
    provenance: str = "DERIVED"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InteractionNode:
    name: str
    position: Tuple[float, float, float]
    direction: Tuple[float, float, float]
    role: str
    nucleon_type: str
    provenance: str = "SOURCE"


@dataclass(frozen=True)
class InteractionEdge:
    i: int
    j: int
    name_i: str
    name_j: str
    distance: float
    direction_angle_deg: float
    cosine: float
    abs_cosine: float
    cosine_squared: float
    inverse_cube_proxy: float
    j_proxy: float
    topology: str
    kernel: str
    provenance: str


@dataclass(frozen=True)
class InteractionGraphResult:
    topology: str
    kernel: str
    names: Tuple[str, ...]
    roles: Tuple[str, ...]
    nucleon_types: Tuple[str, ...]
    edges: Tuple[InteractionEdge, ...]
    adjacency: Tuple[Tuple[int, ...], ...]
    j_proxy_matrix: Tuple[Tuple[float, ...], ...]
    total_j_proxy: float
    mean_abs_j_proxy: float
    provenance: str
    note: str

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["edges"] = [asdict(edge) for edge in self.edges]
        return data


@dataclass(frozen=True)
class OrbitalPlane:
    name: str
    normal: Tuple[float, float, float]
    tilt_to_symmetry_axis_deg: float
    provenance: str


@dataclass(frozen=True)
class OrbitalPlaneResult:
    names: Tuple[str, ...]
    planes: Tuple[OrbitalPlane, ...]
    pair_dihedral_deg: Tuple[Tuple[float, ...], ...]
    mean_pair_dihedral_deg: float
    std_pair_dihedral_deg: float
    provenance: str

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["planes"] = [asdict(plane) for plane in self.planes]
        return data


@dataclass(frozen=True)
class BohrEnvelopeResult:
    center: Tuple[float, float, float]
    axes: Tuple[float, float, float]
    rotation_matrix: Tuple[Tuple[float, float, float], ...]
    bounding_sphere_radius: float
    ellipsoid_volume: float
    point_count: int
    padding: float
    provenance: str
    note: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _tokens(name: str) -> Tuple[str, ...]:
    raw = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name))
    return tuple(t for t in re.split(r"[^A-Za-z0-9]+", raw.upper()) if t)


def infer_nucleon_from_name(name: str) -> NucleonGuess:
    """Conservative, auditable *name-only* heuristic.

    The heuristic never upgrades itself to SOURCE provenance.  It is intended
    to speed tagging of Blender scenes whose objects already carry meaningful
    names such as ``Deuteron_valence_01`` or ``He_core``.  Geometry/mesh shape
    is deliberately not interpreted as particle identity.
    """
    tokens = set(_tokens(name))
    evidence = []
    nucleon_type = "OTHER"
    type_conf = 0.0

    rules = (
        ("TRITIUM", {"TRITIUM", "TRITON", "H3"}, 0.98),
        ("DEUTERON", {"DEUTERON", "DEUTERIUM", "H2", "D2"}, 0.98),
        ("NEUTRON", {"NEUTRON"}, 0.99),
        ("PROTON", {"PROTON", "HYDROGEN"}, 0.99),
        ("HELIUM", {"HELIUM", "ALPHA", "HE4"}, 0.98),
    )
    for candidate, aliases, confidence in rules:
        match = sorted(tokens.intersection(aliases))
        if match:
            nucleon_type = candidate
            type_conf = confidence
            evidence.append(f"type token: {match[0]}")
            break

    role = "OTHER"
    role_conf = 0.0
    role_rules = (
        ("VALENCE", {"VALENCE", "FREE", "CLUB"}, 0.94),
        ("EQUATORIAL", {"EQUATORIAL", "EQUATOR", "EQ"}, 0.94),
        ("BOUND", {"BOUND", "PAIR", "PAIRED", "EB", "SGBCLP"}, 0.90),
        ("CORE", {"CORE", "CENTER", "CENTRE", "NUCLEUS", "NUCLEAR"}, 0.90),
    )
    for candidate, aliases, confidence in role_rules:
        match = sorted(tokens.intersection(aliases))
        if match:
            role = candidate
            role_conf = confidence
            evidence.append(f"role token: {match[0]}")
            break

    if nucleon_type == "OTHER" and role == "OTHER":
        confidence = 0.0
        evidence.append("no recognized name tokens")
    elif nucleon_type == "OTHER":
        confidence = role_conf * 0.75
        evidence.append("particle type unresolved")
    elif role == "OTHER":
        confidence = type_conf * 0.85
        evidence.append("Atlas role unresolved")
    else:
        confidence = min(type_conf, role_conf)

    return NucleonGuess(
        nucleon_type=nucleon_type,
        role=role,
        confidence=float(confidence),
        evidence=tuple(evidence),
    )


def _vec3(value: Sequence[float], label: str) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError(f"{label} must be a finite 3-vector")
    return arr


def _unit(value: Sequence[float], label: str) -> np.ndarray:
    arr = _vec3(value, label)
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return arr / norm


def _edge_allowed(role_i: str, role_j: str, topology: str) -> bool:
    a, b = str(role_i).upper(), str(role_j).upper()
    topology = str(topology).upper()
    if topology == "SOURCE_STAR":
        return {a, b} == {"VALENCE", "EQUATORIAL"}
    if topology == "VALENCE_ONLY":
        return a == "VALENCE" and b == "VALENCE"
    if topology == "ALL_TAGGED":
        return True
    raise ValueError(f"unknown topology {topology!r}")


def _kernel_value(kernel: str, cosine: float, inverse_cube: float) -> float:
    kernel = str(kernel).upper()
    if kernel == "TOPOLOGY_ONLY":
        return 1.0
    if kernel == "ABS_COSINE":
        return abs(cosine)
    if kernel == "COSINE_SQUARED":
        return cosine * cosine
    if kernel == "INVERSE_CUBE":
        return inverse_cube
    if kernel == "COSINE_SQUARED_INV_R3":
        return cosine * cosine * inverse_cube
    raise ValueError(f"unknown interaction kernel {kernel!r}")


def build_interaction_graph(
    nodes: Sequence[InteractionNode],
    *,
    topology: str = "SOURCE_STAR",
    kernel: str = "TOPOLOGY_ONLY",
    softening: float = 0.0,
) -> InteractionGraphResult:
    """Build a symmetric geometry/interaction-proxy graph.

    ``SOURCE_STAR`` encodes only tagged VALENCE↔EQUATORIAL connectivity.  The
    matrix is named ``j_proxy_matrix`` intentionally: no absolute interaction
    energy is inferred.  Any kernel beyond ``TOPOLOGY_ONLY`` is CONDITIONAL.
    Distances are in scene units, so inverse-cube values are unit-dependent.
    """
    if len(nodes) < 2:
        raise ValueError("at least two interaction nodes are required")
    softening = float(softening)
    if softening < 0.0 or not math.isfinite(softening):
        raise ValueError("softening must be finite and non-negative")

    positions = [_vec3(node.position, f"position {node.name}") for node in nodes]
    directions = [_unit(node.direction, f"direction {node.name}") for node in nodes]
    topology = str(topology).upper()
    kernel = str(kernel).upper()
    provenance = "DERIVED" if kernel == "TOPOLOGY_ONLY" else "CONDITIONAL"

    n = len(nodes)
    adjacency = np.zeros((n, n), dtype=np.int64)
    matrix = np.zeros((n, n), dtype=np.float64)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if not _edge_allowed(nodes[i].role, nodes[j].role, topology):
                continue
            delta = positions[j] - positions[i]
            distance = float(np.linalg.norm(delta))
            if distance <= 1e-12 and softening <= 0.0 and kernel in {"INVERSE_CUBE", "COSINE_SQUARED_INV_R3"}:
                raise ValueError(f"zero-distance edge {nodes[i].name!r}-{nodes[j].name!r}")
            cosine = float(np.clip(np.dot(directions[i], directions[j]), -1.0, 1.0))
            angle = math.degrees(math.acos(cosine))
            inverse_cube = 1.0 / max((distance * distance + softening * softening) ** 1.5, 1e-30)
            weight = float(_kernel_value(kernel, cosine, inverse_cube))
            adjacency[i, j] = adjacency[j, i] = 1
            matrix[i, j] = matrix[j, i] = weight
            edges.append(InteractionEdge(
                i=i, j=j,
                name_i=nodes[i].name, name_j=nodes[j].name,
                distance=distance,
                direction_angle_deg=angle,
                cosine=cosine,
                abs_cosine=abs(cosine),
                cosine_squared=cosine * cosine,
                inverse_cube_proxy=inverse_cube,
                j_proxy=weight,
                topology=topology,
                kernel=kernel,
                provenance=provenance,
            ))

    if not edges:
        raise ValueError(f"topology {topology} produced no edges from the supplied Atlas roles")
    values = np.asarray([abs(edge.j_proxy) for edge in edges], dtype=np.float64)
    note = (
        "Topology-only graph; no energy normalization."
        if kernel == "TOPOLOGY_ONLY"
        else "Conditional geometry proxy only; J values are not physical energies and depend on scene units/kernel choice."
    )
    return InteractionGraphResult(
        topology=topology,
        kernel=kernel,
        names=tuple(node.name for node in nodes),
        roles=tuple(node.role for node in nodes),
        nucleon_types=tuple(node.nucleon_type for node in nodes),
        edges=tuple(edges),
        adjacency=tuple(tuple(int(v) for v in row) for row in adjacency),
        j_proxy_matrix=tuple(tuple(float(v) for v in row) for row in matrix),
        total_j_proxy=float(sum(edge.j_proxy for edge in edges)),
        mean_abs_j_proxy=float(np.mean(values)),
        provenance=provenance,
        note=note,
    )


def analyze_orbital_planes(
    normals: Sequence[Sequence[float]],
    *,
    names: Sequence[str] | None = None,
    symmetry_axis: Sequence[float] = (0.0, 0.0, 1.0),
    provenance: str = "DERIVED",
) -> OrbitalPlaneResult:
    if len(normals) < 2:
        raise ValueError("at least two orbital-plane normals are required")
    unit_normals = [_unit(v, "orbital-plane normal") for v in normals]
    axis = _unit(symmetry_axis, "symmetry axis")
    if names is None:
        names = [f"Plane_{i + 1}" for i in range(len(unit_normals))]
    if len(names) != len(unit_normals):
        raise ValueError("names and normals must have equal length")

    # Plane normals are axial, not directed: n and -n define the same plane.
    tilts = [math.degrees(math.acos(float(np.clip(abs(np.dot(n, axis)), 0.0, 1.0)))) for n in unit_normals]
    matrix = np.zeros((len(unit_normals), len(unit_normals)), dtype=np.float64)
    pair_values = []
    for i in range(len(unit_normals)):
        for j in range(i + 1, len(unit_normals)):
            c = float(np.clip(abs(np.dot(unit_normals[i], unit_normals[j])), 0.0, 1.0))
            angle = math.degrees(math.acos(c))
            matrix[i, j] = matrix[j, i] = angle
            pair_values.append(angle)

    planes = tuple(
        OrbitalPlane(
            name=str(name),
            normal=tuple(float(v) for v in normal),
            tilt_to_symmetry_axis_deg=float(tilt),
            provenance=provenance,
        )
        for name, normal, tilt in zip(names, unit_normals, tilts)
    )
    values = np.asarray(pair_values, dtype=np.float64)
    return OrbitalPlaneResult(
        names=tuple(str(v) for v in names),
        planes=planes,
        pair_dihedral_deg=tuple(tuple(float(v) for v in row) for row in matrix),
        mean_pair_dihedral_deg=float(np.mean(values)),
        std_pair_dihedral_deg=float(np.std(values)),
        provenance=provenance,
    )


def estimate_integrated_bohr_envelope(
    positions: Sequence[Sequence[float]],
    *,
    radii: Sequence[float] | None = None,
    padding: float = 1.0,
) -> BohrEnvelopeResult:
    """Estimate an oriented ellipsoidal envelope around tagged structures.

    This is explicitly a *geometric proxy* for an integrated Bohr surface.  It
    is useful for visualization, overlap bookkeeping and reproducible scene
    measurements, but it is not a source-derived BSM-SG field solution.
    """
    points = np.asarray(positions, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 1:
        raise ValueError("positions must be an N x 3 array with N >= 1")
    if not np.all(np.isfinite(points)):
        raise ValueError("positions must be finite")
    padding = float(padding)
    if not math.isfinite(padding) or padding <= 0.0:
        raise ValueError("padding must be finite and positive")
    if radii is None:
        rs = np.zeros(len(points), dtype=np.float64)
    else:
        rs = np.asarray(radii, dtype=np.float64)
        if rs.shape != (len(points),) or not np.all(np.isfinite(rs)) or np.any(rs < 0.0):
            raise ValueError("radii must be finite non-negative values, one per position")

    center = np.mean(points, axis=0)
    centered = points - center
    if len(points) >= 2 and np.any(np.abs(centered) > 1e-12):
        covariance = centered.T @ centered / max(len(points), 1)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        order = np.argsort(eigenvalues)[::-1]
        rotation = eigenvectors[:, order]
    else:
        rotation = np.eye(3, dtype=np.float64)

    # Keep a proper right-handed basis for Blender quaternion conversion.
    if np.linalg.det(rotation) < 0.0:
        rotation[:, 2] *= -1.0
    local = centered @ rotation
    extents = np.max(np.abs(local) + rs[:, None], axis=0)
    fallback = max(float(np.max(rs)) if len(rs) else 0.0, 1e-4)
    extents = np.maximum(extents, fallback)
    axes = extents * padding
    sphere = max(float(np.linalg.norm(centered[i]) + rs[i]) for i in range(len(points))) * padding
    sphere = max(sphere, float(np.max(axes)))
    volume = 4.0 / 3.0 * math.pi * float(np.prod(axes))

    return BohrEnvelopeResult(
        center=tuple(float(v) for v in center),
        axes=tuple(float(v) for v in axes),
        rotation_matrix=tuple(tuple(float(v) for v in row) for row in rotation),
        bounding_sphere_radius=float(sphere),
        ellipsoid_volume=float(volume),
        point_count=int(len(points)),
        padding=padding,
        provenance="CONDITIONAL",
        note="Geometric integrated-Bohr-surface proxy; not a solved BSM-SG electromagnetic/SG surface.",
    )
