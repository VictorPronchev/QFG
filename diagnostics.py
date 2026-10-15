"""Diagnostics, spectral metrology, caching, and export utilities."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
import csv
import json
import time
import numpy as np


DIAGNOSTIC_FIELDS = [
    "time", "max_density", "norm", "mode_variance", "mean_density",
    "max_temperature", "mean_temperature", "z_min", "z_max", "energy_proxy",
    "kinetic_energy", "vacuum_energy", "gradient_energy", "skyrme_energy",
    "gauge_energy", "gravity_energy", "center_x", "center_y", "center_z",
    "momentum_x", "momentum_y", "momentum_z",
]


def timestamped_directory(base: str | Path, prefix: str = "qfg_session") -> Path:
    root = Path(base).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    session = root / f"{prefix}_{stamp}"
    suffix = 1
    while session.exists():
        session = root / f"{prefix}_{stamp}_{suffix:02d}"
        suffix += 1
    session.mkdir(parents=True, exist_ok=False)
    return session


def write_json(path: str | Path, data: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    def encoder(value: Any) -> Any:
        if isinstance(value, np.ndarray):
            return value.tolist() if value.size <= 2000 else {
                "shape": list(value.shape), "dtype": str(value.dtype),
                "note": "Large array omitted; see NPZ/CSV export.",
            }
        if isinstance(value, np.generic):
            return value.item()
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        raise TypeError(f"Cannot serialize {type(value)!r}")

    target.write_text(json.dumps(data, indent=2, default=encoder), encoding="utf-8")
    return target


def write_rows_csv(path: str | Path, rows: Iterable[Mapping[str, Any]], fieldnames: Optional[Sequence[str]] = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if fieldnames is None:
        ordered = []
        for row in rows:
            for key in row.keys():
                if key not in ordered:
                    ordered.append(key)
        fieldnames = ordered
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return target


def write_diagnostics_csv(path: str | Path, rows: Iterable[Any]) -> Path:
    normalized = []
    for row in rows:
        if hasattr(row, "to_dict"):
            row = row.to_dict()
        elif hasattr(row, "__dataclass_fields__"):
            row = asdict(row)
        normalized.append(dict(row))
    return write_rows_csv(path, normalized, DIAGNOSTIC_FIELDS)


def save_snapshot_npz(path: str | Path, snapshot: Mapping[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {}
    for key, value in snapshot.items():
        if isinstance(value, np.ndarray):
            payload[key] = value
        elif isinstance(value, (int, float, str, bool)):
            payload[key] = np.asarray(value)
    np.savez_compressed(target, **payload)
    return target


def spectrum(signal: Sequence[float] | np.ndarray, dt: float, detrend: bool = True) -> Dict[str, np.ndarray]:
    values = np.asarray(signal, dtype=np.float64).reshape(-1)
    if len(values) < 4:
        return {"frequency": np.empty(0), "amplitude": np.empty(0), "power": np.empty(0)}
    if detrend:
        x = np.arange(len(values), dtype=np.float64)
        coeff = np.polyfit(x, values, 1)
        values = values - np.polyval(coeff, x)
    window = np.hanning(len(values))
    coherent_gain = max(float(np.sum(window)), 1e-12)
    fft = np.fft.rfft(values * window)
    amplitude = 2.0 * np.abs(fft) / coherent_gain
    if amplitude.size:
        amplitude[0] *= 0.5
        if len(values) % 2 == 0:
            amplitude[-1] *= 0.5
    frequency = np.fft.rfftfreq(len(values), d=dt)
    return {"frequency": frequency, "amplitude": amplitude, "power": amplitude ** 2}


def nearest_peak(spec: Mapping[str, np.ndarray], target_frequency: float, half_width: float) -> Dict[str, float]:
    f = np.asarray(spec["frequency"])
    a = np.asarray(spec["amplitude"])
    mask = np.abs(f - target_frequency) <= max(half_width, 0.0)
    if not np.any(mask):
        return {"target": target_frequency, "frequency": float("nan"), "amplitude": 0.0}
    local_indices = np.flatnonzero(mask)
    index = local_indices[int(np.argmax(a[mask]))]
    return {"target": float(target_frequency), "frequency": float(f[index]), "amplitude": float(a[index])}


def imd_metrics(signal: Sequence[float] | np.ndarray, dt: float, f1: float, f2: float) -> Dict[str, Any]:
    spec = spectrum(signal, dt)
    resolution = 1.0 / max(len(np.asarray(signal)) * dt, 1e-12)
    targets = {
        "f1": f1,
        "f2": f2,
        "difference": abs(f2 - f1),
        "sum": f1 + f2,
        "imd_2f1_minus_f2": abs(2.0 * f1 - f2),
        "imd_2f2_minus_f1": abs(2.0 * f2 - f1),
    }
    peaks = {name: nearest_peak(spec, freq, max(2.5 * resolution, 1e-9)) for name, freq in targets.items()}
    carrier = max(peaks["f1"]["amplitude"], peaks["f2"]["amplitude"], 1e-15)
    for name, peak in peaks.items():
        peak["relative_db"] = float(20.0 * np.log10(max(peak["amplitude"], 1e-15) / carrier))
    return {"spectrum": spec, "peaks": peaks, "resolution": resolution}


def allan_deviation(values: Sequence[float] | np.ndarray, dt: float, max_clusters: int = 40) -> Dict[str, np.ndarray]:
    """Overlapping Allan-deviation proxy for regularly sampled data."""
    y = np.asarray(values, dtype=np.float64).reshape(-1)
    if len(y) < 8:
        return {"tau": np.empty(0), "adev": np.empty(0)}
    max_m = max(1, len(y) // 4)
    m_values = np.unique(np.logspace(0, np.log10(max_m), max_clusters).astype(int))
    taus, adevs = [], []
    cumsum = np.concatenate([[0.0], np.cumsum(y)])
    for m in m_values:
        if 2 * m >= len(y):
            continue
        means = (cumsum[m:] - cumsum[:-m]) / m
        diff = means[m:] - means[:-m]
        if len(diff):
            taus.append(m * dt)
            adevs.append(np.sqrt(0.5 * np.mean(diff * diff)))
    return {"tau": np.asarray(taus), "adev": np.asarray(adevs)}


def phase_noise_proxy(complex_signal: Sequence[complex] | np.ndarray, dt: float) -> Dict[str, np.ndarray]:
    signal = np.asarray(complex_signal, dtype=np.complex128).reshape(-1)
    if len(signal) < 8:
        return {"frequency": np.empty(0), "phase_psd": np.empty(0), "phase": np.empty(0)}
    phase = np.unwrap(np.angle(signal))
    phase -= np.polyval(np.polyfit(np.arange(len(phase)), phase, 1), np.arange(len(phase)))
    spec = spectrum(phase, dt, detrend=False)
    return {"frequency": spec["frequency"], "phase_psd": spec["power"], "phase": phase}


class TimelineCache:
    """In-memory display cache; heavy solvers never run inside frame handlers."""

    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.frames: Dict[int, Dict[str, Any]] = {}
        self.source_signature: str = ""
        self.created_at: float = time.time()

    def bounds(self) -> Optional[Tuple[int, int]]:
        if not self.frames:
            return None
        keys = self.frames.keys()
        return min(keys), max(keys)

    def nearest_frame(self, frame: int) -> Optional[int]:
        if not self.frames:
            return None
        requested = int(frame)
        return min(self.frames, key=lambda value: (abs(value - requested), value))

    def resolve_frame(self, frame: int, outside_mode: str = "HOLD_LAST") -> Tuple[Optional[int], str]:
        """Resolve a requested Blender frame against the in-memory bake cache.

        Returns ``(display_frame, state)`` where state is EXACT, HOLD, CLAMP,
        MISSING, OUTSIDE, or EMPTY.  The function is pure with respect to the
        Blender scene and is therefore regression-testable without ``bpy``.
        """
        requested = int(frame)
        if requested in self.frames:
            return requested, "EXACT"
        bounds = self.bounds()
        if bounds is None:
            return None, "EMPTY"
        lo, hi = bounds
        outside = requested < lo or requested > hi
        mode = str(outside_mode).upper()
        if outside and mode == "STATUS_ONLY":
            return None, "OUTSIDE"
        nearest = self.nearest_frame(requested)
        if outside:
            return nearest, "CLAMP" if mode == "CLAMP" else "HOLD"
        return nearest, "MISSING"

    def put(
        self, frame: int, *, points: np.ndarray, weights: np.ndarray,
        density_slice: np.ndarray, diagnostics: Mapping[str, Any],
        body_state: Optional[Mapping[str, Any]] = None,
        atlas_state: Optional[Mapping[str, Any]] = None,
        events: Optional[Sequence[Mapping[str, Any]]] = None,
        profile: Optional[Mapping[str, Any]] = None,
        telemetry: Optional[Mapping[str, Any]] = None,
    ) -> None:
        payload = {
            "points": np.asarray(points, dtype=np.float32),
            "weights": np.asarray(weights, dtype=np.float32),
            "density_slice": np.asarray(density_slice, dtype=np.float32),
            "diagnostics": dict(diagnostics),
        }
        if body_state is not None:
            copied = {
                "names": list(body_state.get("names", [])),
                "collision_shapes": list(body_state.get("collision_shapes", [])),
                "phase_state": list(body_state.get("phase_state", [])),
            }
            for key in (
                "positions", "velocities", "orientations", "angular_velocities",
                "half_extents", "density", "temperature",
                "force_gravity", "force_field", "force_thermal", "force_drag",
                "force_contact", "force_total",
                "torque_external", "torque_field", "torque_drag", "torque_contact",
                "torque_total", "contact_impulse", "contact_angular_impulse",
            ):
                copied[key] = np.asarray(body_state.get(key, []), dtype=np.float32)
            payload["body_state"] = copied
        if atlas_state is not None:
            payload["atlas_state"] = {
                "names": list(atlas_state.get("names", [])),
                "positions": np.asarray(atlas_state.get("positions", []), dtype=np.float32),
                "orientations": np.asarray(atlas_state.get("orientations", []), dtype=np.float32),
                "scales": np.asarray(atlas_state.get("scales", []), dtype=np.float32),
            }
        if events is not None:
            payload["events"] = [dict(event) for event in events]
        if profile is not None:
            payload["profile"] = dict(profile)
        if telemetry is not None:
            payload["telemetry"] = dict(telemetry)
        self.frames[int(frame)] = payload

    def get(self, frame: int) -> Optional[Dict[str, Any]]:
        return self.frames.get(int(frame))

    def __len__(self) -> int:
        return len(self.frames)
