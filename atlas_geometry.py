"""Atlas Direct geometry extraction and blind-holdout helpers.

This module is deliberately independent of Blender.  It accepts 3-D valence
vectors, computes their geometry, and optionally compares a *frozen* prediction
with an external reference value.  It does not infer BSM-SG ontology from data
and it does not fit molecular angles.

Scientific provenance vocabulary used by the Blender bridge:
SOURCE       - explicitly tagged source geometry/data.
DERIVED      - deterministic calculation from source-tagged geometry.
CONDITIONAL  - model-dependent bridge/hypothesis.
CALIBRATED   - quantity fixed using a reference/measurement.
EXPERIMENTAL - external measurement/reference.
REJECTED     - retained only for audit/history; must not drive predictions.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Sequence, Tuple
import math
import numpy as np


PROVENANCE_LEVELS = (
    "SOURCE", "DERIVED", "CONDITIONAL", "CALIBRATED", "EXPERIMENTAL", "REJECTED",
)


# Offline holdout registry.  These values are shown only after an explicit
# Blender "Reveal reference" action.  The registry is not consulted by the
# geometry calculation or freeze step.
GROUP15_REFERENCE_ANGLES: Mapping[str, Mapping[str, object]] = {
    "N": {
        "molecule": "NH3",
        "angle_deg": 106.7,
        "label": "H-N-H equilibrium angle",
        "source": "NIST CCCBDB experimental geometry",
    },
    "P": {
        "molecule": "PH3",
        "angle_deg": 93.3,
        "label": "H-P-H equilibrium angle",
        "source": "NIST CCCBDB experimental geometry",
    },
    "AS": {
        "molecule": "AsH3",
        "angle_deg": 92.083,
        "label": "H-As-H equilibrium angle",
        "source": "NIST CCCBDB experimental geometry",
    },
    "SB": {
        "molecule": "SbH3",
        "angle_deg": 91.5566,
        "label": "H-Sb-H equilibrium angle",
        "source": "NIST CCCBDB experimental geometry",
    },
}


@dataclass(frozen=True)
class PairAngle:
    i: int
    j: int
    name_i: str
    name_j: str
    angle_deg: float


@dataclass(frozen=True)
class AtlasGeometryResult:
    element: str
    names: Tuple[str, ...]
    vectors: Tuple[Tuple[float, float, float], ...]
    unit_vectors: Tuple[Tuple[float, float, float], ...]
    norms: Tuple[float, ...]
    pair_angles: Tuple[PairAngle, ...]
    mean_pair_angle_deg: float
    std_pair_angle_deg: float
    min_pair_angle_deg: float
    max_pair_angle_deg: float
    symmetry_axis: Tuple[float, float, float]
    mean_polar_tilt_deg: float
    std_polar_tilt_deg: float
    c3v_height_ratio: float | None
    provenance: str = "DERIVED"

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["pair_angles"] = [asdict(item) for item in self.pair_angles]
        return data


def _as_vectors(vectors: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError("vectors must be an N x 3 array")
    if len(arr) < 2:
        raise ValueError("at least two valence vectors are required")
    if not np.all(np.isfinite(arr)):
        raise ValueError("vectors must contain only finite values")
    norms = np.linalg.norm(arr, axis=1)
    if np.any(norms <= 1e-12):
        raise ValueError("valence vectors must have non-zero length")
    return arr


def angle_degrees(a: Sequence[float], b: Sequence[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = float(np.linalg.norm(va))
    nb = float(np.linalg.norm(vb))
    if na <= 1e-12 or nb <= 1e-12:
        raise ValueError("angle vectors must have non-zero length")
    cosine = float(np.dot(va, vb) / (na * nb))
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def c3v_height_ratio_from_pair_angle(angle_deg: float) -> float | None:
    """Return |h|/r for three equivalent C3v arms from their pair angle.

    For azimuth separation 120 degrees,
        cos(theta) = 3/2 cos(alpha)^2 - 1/2,
    with |h|/r = |cos(alpha)|.
    Returns None outside the geometrically allowed C3v equal-arm range.
    """
    x = (math.cos(math.radians(float(angle_deg))) + 0.5) / 1.5
    if x < -1e-12 or x > 1.0 + 1e-12:
        return None
    return math.sqrt(max(0.0, min(1.0, x)))


def analyze_valence_vectors(
    vectors: Sequence[Sequence[float]],
    *,
    names: Sequence[str] | None = None,
    element: str = "CUSTOM",
    provenance: str = "DERIVED",
) -> AtlasGeometryResult:
    arr = _as_vectors(vectors)
    if provenance not in PROVENANCE_LEVELS:
        raise ValueError(f"unknown provenance {provenance!r}")
    if names is None:
        names = [f"V{i + 1}" for i in range(len(arr))]
    if len(names) != len(arr):
        raise ValueError("names and vectors must have equal length")

    norms = np.linalg.norm(arr, axis=1)
    unit = arr / norms[:, None]

    pair_angles = []
    values = []
    for i in range(len(unit)):
        for j in range(i + 1, len(unit)):
            angle = angle_degrees(unit[i], unit[j])
            pair_angles.append(PairAngle(i, j, str(names[i]), str(names[j]), angle))
            values.append(angle)
    angle_values = np.asarray(values, dtype=np.float64)

    # For an equivalent three-arm pyramid, the vector sum points along the C3
    # symmetry axis.  The same definition remains a useful descriptive axis for
    # imperfect source geometry; if vectors cancel, PCA supplies a deterministic
    # fallback axis.
    axis_raw = np.sum(unit, axis=0)
    if float(np.linalg.norm(axis_raw)) <= 1e-10:
        covariance = unit.T @ unit
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        axis_raw = eigenvectors[:, int(np.argmax(eigenvalues))]
    axis = axis_raw / max(float(np.linalg.norm(axis_raw)), 1e-12)

    # Orient the axis toward the majority of vectors for stable positive tilts.
    if float(np.sum(unit @ axis)) < 0.0:
        axis = -axis
    polar = np.degrees(np.arccos(np.clip(unit @ axis, -1.0, 1.0)))

    mean_angle = float(np.mean(angle_values))
    height_ratio = c3v_height_ratio_from_pair_angle(mean_angle) if len(unit) == 3 else None

    return AtlasGeometryResult(
        element=str(element).upper(),
        names=tuple(str(v) for v in names),
        vectors=tuple(tuple(float(x) for x in row) for row in arr),
        unit_vectors=tuple(tuple(float(x) for x in row) for row in unit),
        norms=tuple(float(x) for x in norms),
        pair_angles=tuple(pair_angles),
        mean_pair_angle_deg=mean_angle,
        std_pair_angle_deg=float(np.std(angle_values)),
        min_pair_angle_deg=float(np.min(angle_values)),
        max_pair_angle_deg=float(np.max(angle_values)),
        symmetry_axis=tuple(float(x) for x in axis),
        mean_polar_tilt_deg=float(np.mean(polar)),
        std_polar_tilt_deg=float(np.std(polar)),
        c3v_height_ratio=None if height_ratio is None else float(height_ratio),
        provenance=provenance,
    )


def reference_for_element(element: str) -> Dict[str, object] | None:
    item = GROUP15_REFERENCE_ANGLES.get(str(element).upper())
    return None if item is None else dict(item)


def compare_frozen_prediction(angle_deg: float, element: str, prediction_provenance: str = "DERIVED") -> Dict[str, object]:
    """Compare a previously frozen angle with a registry reference.

    This routine has no role in prediction.  Call it only after freezing.
    """
    reference = reference_for_element(element)
    if reference is None:
        raise KeyError(f"no built-in holdout reference for element {element!r}")
    observed = float(reference["angle_deg"])
    residual = float(angle_deg) - observed
    return {
        "element": str(element).upper(),
        "molecule": reference["molecule"],
        "prediction_deg": float(angle_deg),
        "reference_deg": observed,
        "residual_deg": residual,
        "absolute_residual_deg": abs(residual),
        "relative_residual_percent": abs(residual) / max(abs(observed), 1e-12) * 100.0,
        "reference_label": reference["label"],
        "reference_source": reference["source"],
        "prediction_provenance": str(prediction_provenance).upper(),
        "reference_provenance": "EXPERIMENTAL",
    }


def three_arm_vectors_from_pair_angle(angle_deg: float, radius: float = 1.0) -> np.ndarray:
    """Construct an ideal C3v three-arm geometry; useful for tests/examples."""
    h_ratio = c3v_height_ratio_from_pair_angle(angle_deg)
    if h_ratio is None:
        raise ValueError("angle is incompatible with equal-arm C3v geometry")
    z = float(radius) * h_ratio
    rho = float(radius) * math.sqrt(max(0.0, 1.0 - h_ratio * h_ratio))
    return np.asarray([
        (rho, 0.0, z),
        (-0.5 * rho, math.sqrt(3.0) * 0.5 * rho, z),
        (-0.5 * rho, -math.sqrt(3.0) * 0.5 * rho, z),
    ], dtype=np.float64)
