"""Reduced experiment models derived from the QFG experimental program.

These models generate comparison curves and candidate signatures. They are not
substitutes for calibrated RF, plasma, optical, MEMS, or metrology software.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
import numpy as np

from .diagnostics import allan_deviation, imd_metrics, phase_noise_proxy


@dataclass
class HRMScanConfig:
    f1_min: float = 4.0
    f1_max: float = 6.0
    f2_min: float = 4.0
    f2_max: float = 7.0
    points: int = 13
    duration: float = 2.0
    dt: float = 0.002
    nx: int = 128
    length: float = 20.0
    rho0: float = 1.0
    lambda_cohesion: float = 1.0
    damping: float = 0.05
    a1: float = 0.3
    a2: float = 0.3
    alpha: float = 1.0e-6
    zeta_em: float = 0.0015
    noise_amplitude: float = 0.0
    seed: int = 1234


def _hrm_1d_run(cfg: HRMScanConfig, f1: float, f2: float) -> Dict[str, Any]:
    x = np.linspace(-cfg.length / 2, cfg.length / 2, cfg.nx, endpoint=False)
    dx = x[1] - x[0]
    k = 2.0 * np.pi * np.fft.fftfreq(cfg.nx, d=dx)
    psi = np.exp(-x * x).astype(np.complex128)
    kinetic = np.exp(-1j * k * k * cfg.dt)
    times = np.arange(0.0, cfg.duration, cfg.dt)
    rng = np.random.default_rng(cfg.seed)
    modevar = np.empty(len(times))
    observable = np.empty(len(times), dtype=np.complex128)

    for i, t in enumerate(times):
        psi = np.fft.ifft(np.fft.fft(psi) * kinetic)
        rho = np.abs(psi) ** 2
        z = np.maximum(1.0 + cfg.alpha * (rho - cfg.rho0), 1e-9)
        drive = cfg.a1 * np.sin(2 * np.pi * f1 * t) + cfg.a2 * np.sin(2 * np.pi * f2 * t)
        potential = -2.0 * cfg.lambda_cohesion * (rho - cfg.rho0)
        potential += cfg.zeta_em * drive / np.sqrt(z)
        psi *= np.exp((1j * potential - cfg.damping) * cfg.dt)
        if cfg.noise_amplitude > 0:
            psi += cfg.noise_amplitude * np.sqrt(cfg.dt) * (
                rng.normal(size=cfg.nx) + 1j * rng.normal(size=cfg.nx)
            )
        modevar[i] = np.var(rho)
        observable[i] = np.mean(psi)

    tail = max(8, len(times) // 4)
    return {
        "time": times,
        "modevar": modevar,
        "observable": observable,
        "steady_modevar": float(np.mean(modevar[-tail:])),
        "modevar_jitter": float(np.std(modevar[-tail:])),
        "imd": imd_metrics(np.real(observable), cfg.dt, f1, f2),
        "phase_noise": phase_noise_proxy(observable, cfg.dt),
        "allan": allan_deviation(np.unwrap(np.angle(observable + 1e-15)), cfg.dt),
    }


def hrm_scan(cfg: HRMScanConfig) -> Dict[str, Any]:
    f1_values = np.linspace(cfg.f1_min, cfg.f1_max, cfg.points)
    f2_values = np.linspace(cfg.f2_min, cfg.f2_max, cfg.points)
    modevar = np.empty((cfg.points, cfg.points), dtype=np.float64)
    jitter = np.empty_like(modevar)
    difference_imd_db = np.empty_like(modevar)
    for i, f1 in enumerate(f1_values):
        for j, f2 in enumerate(f2_values):
            run = _hrm_1d_run(cfg, float(f1), float(f2))
            modevar[i, j] = run["steady_modevar"]
            jitter[i, j] = run["modevar_jitter"]
            difference_imd_db[i, j] = run["imd"]["peaks"]["difference"]["relative_db"]
    best = np.unravel_index(int(np.argmin(modevar)), modevar.shape)
    return {
        "f1": f1_values,
        "f2": f2_values,
        "modevar": modevar,
        "jitter": jitter,
        "difference_imd_db": difference_imd_db,
        "best_f1": float(f1_values[best[0]]),
        "best_f2": float(f2_values[best[1]]),
        "best_difference": float(abs(f2_values[best[1]] - f1_values[best[0]])),
        "best_modevar": float(modevar[best]),
    }


@dataclass
class PlasmaConfig:
    duration: float = 5.0
    dt: float = 0.001
    f1: float = 5.0
    f2: float = 6.2
    a1: float = 0.3
    a2: float = 0.3
    ionization_gain: float = 0.8
    recombination: float = 0.25
    diffusion: float = 0.05
    boundary_factor: float = 1.0
    nonlinearity: float = 0.4


def simulate_glow_plasma(cfg: PlasmaConfig) -> Dict[str, np.ndarray]:
    """Zero-dimensional glow/plasma envelope proxy with dual-frequency drive."""
    t = np.arange(0.0, cfg.duration, cfg.dt)
    density = np.zeros_like(t)
    light = np.zeros_like(t)
    phase = np.zeros_like(t)
    n = 0.02
    phi = 0.0
    for i, time_value in enumerate(t):
        drive = cfg.a1 * np.sin(2 * np.pi * cfg.f1 * time_value)
        drive += cfg.a2 * np.sin(2 * np.pi * cfg.f2 * time_value)
        source = cfg.ionization_gain * max(drive * drive - 0.05 * cfg.boundary_factor, 0.0)
        dn = source - cfg.recombination * n * n - cfg.diffusion * cfg.boundary_factor * n
        n = max(n + cfg.dt * dn, 0.0)
        phi += cfg.dt * (cfg.nonlinearity * n + drive)
        density[i] = n
        phase[i] = phi
        light[i] = n * (1.0 + 0.2 * np.cos(phi))
    return {
        "time": t,
        "density": density,
        "light": light,
        "phase": phase,
        "mode_variance": np.asarray(np.var(light[-max(8, len(light)//4):])),
        "imd": imd_metrics(light, cfg.dt, cfg.f1, cfg.f2),
    }


@dataclass
class CavityShiftConfig:
    powers: int = 100
    power_max: float = 10.0
    base_frequency: float = 1.0
    alpha: float = 1.0e-6
    density_per_power: float = 0.01
    thermal_coefficient: float = 1.0e-4
    q_factor: float = 1.0e5
    temperature_rise_per_power: float = 0.02


def cavity_shift_sweep(cfg: CavityShiftConfig) -> Dict[str, np.ndarray]:
    power = np.linspace(0.0, cfg.power_max, cfg.powers)
    density_offset = cfg.density_per_power * power * np.log10(max(cfg.q_factor, 1.0))
    z = 1.0 + cfg.alpha * density_offset
    qfg_frequency = cfg.base_frequency / np.sqrt(np.maximum(z, 1e-12))
    temperature = cfg.temperature_rise_per_power * power
    thermal_frequency = cfg.base_frequency * (1.0 - cfg.thermal_coefficient * temperature)
    combined = qfg_frequency + thermal_frequency - cfg.base_frequency
    return {
        "power": power,
        "density_offset": density_offset,
        "temperature": temperature,
        "qfg_shift": qfg_frequency - cfg.base_frequency,
        "thermal_shift": thermal_frequency - cfg.base_frequency,
        "combined_shift": combined,
    }


@dataclass
class MEMSConfig:
    geometry_min: float = 0.5
    geometry_max: float = 2.0
    points: int = 120
    base_q: float = 1000.0
    material_loss: float = 1.0e-3
    qfg_geometry_scale: float = 0.05
    resonance_center: float = 1.0
    resonance_width: float = 0.12


def mems_geometry_sweep(cfg: MEMSConfig) -> Dict[str, np.ndarray]:
    geometry = np.linspace(cfg.geometry_min, cfg.geometry_max, cfg.points)
    geometric_lock = np.exp(-0.5 * ((geometry - cfg.resonance_center) / max(cfg.resonance_width, 1e-9)) ** 2)
    inverse_q = cfg.material_loss + 1.0 / max(cfg.base_q, 1e-12) - cfg.qfg_geometry_scale * geometric_lock / max(cfg.base_q, 1.0)
    q_factor = 1.0 / np.maximum(inverse_q, 1e-12)
    return {"geometry": geometry, "q_factor": q_factor, "locking_proxy": geometric_lock}


def validation_program_summary() -> Dict[str, Dict[str, str]]:
    return {
        "rf_cavity_hrm": {
            "tests": "Z(rho), two-tone locking, sidebands, non-thermal drift",
            "outputs": "S21, IMD, modeVar, Allan/phase-noise proxies",
        },
        "glow_plasma": {
            "tests": "dual-frequency coupling and dielectric-boundary sensitivity",
            "outputs": "light envelope, threshold, stability and sidebands",
        },
        "optical_cavity": {
            "tests": "linewidth/phase-locking comparison",
            "outputs": "frequency shift versus power and Q",
        },
        "mems": {
            "tests": "geometry-dependent Q-factor",
            "outputs": "Q versus geometry proxy",
        },
        "yb": {
            "tests": "Rabi/Ramsey/AC-Stark candidate shifts",
            "outputs": "population traces and Q-factor sweeps",
        },
    }
