"""B6 blind Atlas/QFG relaxation protocol helpers.

This module is deliberately independent of Blender and deliberately does not
import the experimental holdout registry.  It decides only whether a sequence
of *predicted* Atlas geometries has numerically settled.

Scientific status
-----------------
The B6 run protocol is CONDITIONAL because B3/B4/B5 field, feedback and
projection laws are reduced research models.  The holdout discipline itself is
strict: convergence is determined without consulting any experimental target.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Sequence
import hashlib
import json
import math
import numpy as np


@dataclass(frozen=True)
class BlindRelaxationConfig:
    max_iterations: int = 160
    min_iterations: int = 12
    convergence_window: int = 8
    angle_window_tolerance_deg: float = 0.02
    angle_slope_tolerance_deg_per_iter: float = 0.003
    spread_tolerance_deg: float = 0.02
    correction_tolerance: float = 0.0  # <=0 disables this gate

    def validate(self) -> None:
        if int(self.max_iterations) < 1:
            raise ValueError("max_iterations must be >= 1")
        if int(self.min_iterations) < 1:
            raise ValueError("min_iterations must be >= 1")
        if int(self.convergence_window) < 2:
            raise ValueError("convergence_window must be >= 2")
        if self.min_iterations > self.max_iterations:
            raise ValueError("min_iterations cannot exceed max_iterations")
        if self.convergence_window > self.max_iterations:
            raise ValueError("convergence_window cannot exceed max_iterations")
        for name, value in (
            ("angle_window_tolerance_deg", self.angle_window_tolerance_deg),
            ("angle_slope_tolerance_deg_per_iter", self.angle_slope_tolerance_deg_per_iter),
            ("spread_tolerance_deg", self.spread_tolerance_deg),
            ("correction_tolerance", self.correction_tolerance),
        ):
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class BlindRelaxationSample:
    iteration: int
    qfg_time: float
    mean_pair_angle_deg: float
    std_pair_angle_deg: float
    min_pair_angle_deg: float
    max_pair_angle_deg: float
    c3v_height_ratio: float | None = None
    max_constraint_correction: float = 0.0
    feedback_work_proxy: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class BlindConvergenceSummary:
    sample_count: int
    converged: bool
    reason: str
    final_angle_deg: float
    final_spread_deg: float
    final_height_ratio: float | None
    window_angle_range_deg: float
    window_angle_slope_deg_per_iter: float
    window_max_spread_deg: float
    window_max_constraint_correction: float
    provenance: str = "CONDITIONAL"

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def _finite_sample(sample: BlindRelaxationSample) -> None:
    for name in (
        "qfg_time", "mean_pair_angle_deg", "std_pair_angle_deg",
        "min_pair_angle_deg", "max_pair_angle_deg",
        "max_constraint_correction", "feedback_work_proxy",
    ):
        if not math.isfinite(float(getattr(sample, name))):
            raise ValueError(f"sample {name} must be finite")
    if sample.c3v_height_ratio is not None and not math.isfinite(float(sample.c3v_height_ratio)):
        raise ValueError("sample c3v_height_ratio must be finite or None")


def evaluate_blind_convergence(
    samples: Sequence[BlindRelaxationSample], config: BlindRelaxationConfig,
) -> BlindConvergenceSummary:
    """Evaluate convergence using predicted geometry only.

    No external/experimental reference enters this function.  Convergence
    requires a sufficiently long run, a narrow recent angle range, small recent
    linear drift and small C3 pair-angle spread.  An optional B5 correction gate
    can additionally require the projection correction to be small.
    """
    config.validate()
    for sample in samples:
        _finite_sample(sample)
    if not samples:
        return BlindConvergenceSummary(
            sample_count=0, converged=False, reason="no samples", final_angle_deg=0.0,
            final_spread_deg=0.0, final_height_ratio=None, window_angle_range_deg=math.inf,
            window_angle_slope_deg_per_iter=math.inf, window_max_spread_deg=math.inf,
            window_max_constraint_correction=math.inf,
        )

    final = samples[-1]
    window_n = min(len(samples), int(config.convergence_window))
    tail = samples[-window_n:]
    angles = np.asarray([s.mean_pair_angle_deg for s in tail], dtype=np.float64)
    spreads = np.asarray([s.std_pair_angle_deg for s in tail], dtype=np.float64)
    corrections = np.asarray([s.max_constraint_correction for s in tail], dtype=np.float64)
    angle_range = float(np.max(angles) - np.min(angles)) if len(angles) else math.inf
    max_spread = float(np.max(np.abs(spreads))) if len(spreads) else math.inf
    max_correction = float(np.max(np.abs(corrections))) if len(corrections) else math.inf
    if len(angles) >= 2:
        x = np.arange(len(angles), dtype=np.float64)
        slope = float(np.polyfit(x, angles, 1)[0])
    else:
        slope = math.inf

    enough = len(samples) >= max(int(config.min_iterations), int(config.convergence_window))
    range_ok = angle_range <= float(config.angle_window_tolerance_deg)
    slope_ok = abs(slope) <= float(config.angle_slope_tolerance_deg_per_iter)
    spread_ok = max_spread <= float(config.spread_tolerance_deg)
    correction_ok = (
        float(config.correction_tolerance) <= 0.0
        or max_correction <= float(config.correction_tolerance)
    )
    converged = bool(enough and range_ok and slope_ok and spread_ok and correction_ok)

    if converged:
        reason = "blind geometry convergence gates satisfied"
    elif not enough:
        reason = "minimum blind samples not reached"
    else:
        failed = []
        if not range_ok:
            failed.append("angle window")
        if not slope_ok:
            failed.append("angle drift")
        if not spread_ok:
            failed.append("C3 spread")
        if not correction_ok:
            failed.append("constraint correction")
        reason = "waiting for " + ", ".join(failed)

    return BlindConvergenceSummary(
        sample_count=len(samples), converged=converged, reason=reason,
        final_angle_deg=float(final.mean_pair_angle_deg),
        final_spread_deg=float(final.std_pair_angle_deg),
        final_height_ratio=None if final.c3v_height_ratio is None else float(final.c3v_height_ratio),
        window_angle_range_deg=angle_range,
        window_angle_slope_deg_per_iter=slope,
        window_max_spread_deg=max_spread,
        window_max_constraint_correction=max_correction,
    )


def protocol_fingerprint(payload: Dict[str, object]) -> str:
    """Stable SHA-256 fingerprint for a blind protocol/source snapshot."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
