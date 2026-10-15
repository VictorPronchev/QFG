"""Reduced Yb control and spectroscopy planning models.

The functions model two-level Bloch dynamics, Ramsey interference, ODMR-like
frequency sweeps, cavity-Q comparisons, and a two-ion phase proxy. They do not
represent a complete Yb:YAG crystal, ion trap, optical-pumping cycle, or master-
equation simulation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import numpy as np


@dataclass
class YbConfig:
    duration: float = 20.0
    dt: float = 0.005
    rabi_frequency: float = 1.0
    detuning: float = 0.0
    dephasing: float = 0.02
    relaxation: float = 0.01
    q_factor: float = 1.0e4
    cavity_power: float = 1.0
    alpha: float = 1.0e-6
    density_offset: float = 0.0
    qfg_correction_scale: float = 1.0
    texture_coupling: float = 0.0
    texture_divergence: float = 0.0
    ac_stark_scale: float = 0.0
    initial_ground: bool = True


def qfg_shift(cfg: YbConfig) -> float:
    z_correction = cfg.alpha * cfg.density_offset
    cavity_factor = np.log10(max(cfg.q_factor, 1.0)) * cfg.cavity_power
    texture = cfg.texture_coupling * cfg.texture_divergence ** 2
    ac_stark = cfg.ac_stark_scale * cfg.cavity_power
    return float(cfg.qfg_correction_scale * z_correction * cavity_factor + texture + ac_stark)


def simulate_rabi(cfg: YbConfig) -> Dict[str, np.ndarray]:
    times = np.arange(0.0, cfg.duration, cfg.dt)
    u = 0.0
    v = 0.0
    w = -1.0 if cfg.initial_ground else 1.0
    result = np.empty((len(times), 3), dtype=np.float64)
    z_rho = max(1.0 + cfg.alpha * cfg.density_offset, 1e-12)
    shift = qfg_shift(cfg)
    omega = cfg.rabi_frequency * np.sqrt(z_rho)
    delta = cfg.detuning + shift
    for i, _ in enumerate(times):
        du = -delta * v - cfg.dephasing * u
        dv = delta * u - omega * w - cfg.dephasing * v
        dw = omega * v - cfg.relaxation * (w + 1.0)
        u += cfg.dt * du
        v += cfg.dt * dv
        w += cfg.dt * dw
        result[i] = (u, v, w)
    return {
        "time": times,
        "u": result[:, 0],
        "v": result[:, 1],
        "w": result[:, 2],
        "excited_population": 0.5 * (result[:, 2] + 1.0),
        "effective_rabi_frequency": np.asarray(omega),
        "qfg_shift": np.asarray(shift),
        "effective_detuning": np.asarray(delta),
    }


def simulate_ramsey(cfg: YbConfig, free_time_max: float = 20.0, points: int = 300) -> Dict[str, np.ndarray]:
    free_times = np.linspace(0.0, free_time_max, points)
    shift = qfg_shift(cfg)
    delta = cfg.detuning + shift
    contrast = np.exp(-cfg.dephasing * free_times)
    population = 0.5 * (1.0 + contrast * np.cos(delta * free_times))
    return {
        "free_time": free_times,
        "excited_population": population,
        "contrast": contrast,
        "qfg_shift": np.asarray(shift),
        "effective_detuning": np.asarray(delta),
    }


def simulate_odmr_sweep(
    cfg: YbConfig,
    frequency_min: float = -5.0,
    frequency_max: float = 5.0,
    points: int = 401,
    contrast: float = 0.08,
    linewidth: float = 0.25,
) -> Dict[str, np.ndarray]:
    frequency = np.linspace(frequency_min, frequency_max, points)
    center = cfg.detuning + qfg_shift(cfg)
    gamma = max(linewidth, 1e-9)
    lorentzian = gamma ** 2 / ((frequency - center) ** 2 + gamma ** 2)
    fluorescence = 1.0 - contrast * lorentzian
    return {
        "frequency": frequency,
        "fluorescence": fluorescence,
        "contrast": contrast * lorentzian,
        "center": np.asarray(center),
        "qfg_shift": np.asarray(qfg_shift(cfg)),
    }


def q_factor_sweep(
    cfg: YbConfig,
    q_min: float = 1.0e2,
    q_max: float = 1.0e7,
    points: int = 120,
) -> Dict[str, np.ndarray]:
    q_values = np.logspace(np.log10(q_min), np.log10(q_max), points)
    shifts = np.empty_like(q_values)
    rabi = np.empty_like(q_values)
    for i, q in enumerate(q_values):
        local = YbConfig(**{**cfg.__dict__, "q_factor": float(q)})
        shifts[i] = qfg_shift(local)
        rabi[i] = local.rabi_frequency * np.sqrt(max(1.0 + local.alpha * local.density_offset, 1e-12))
    return {"q_factor": q_values, "shift": shifts, "effective_rabi_frequency": rabi}


def two_ion_phase_proxy(
    cfg: YbConfig,
    phase_points: int = 181,
    gate_time: float = 1.0,
    coupling: float = 0.1,
) -> Dict[str, np.ndarray]:
    modulation_phase = np.linspace(-np.pi, np.pi, phase_points)
    shift = qfg_shift(cfg)
    ideal_phase = coupling * gate_time * np.cos(modulation_phase)
    accumulated_phase = ideal_phase + shift * gate_time * (1.0 + 0.1 * np.cos(2.0 * modulation_phase))
    offset = accumulated_phase - ideal_phase
    return {
        "modulation_phase": modulation_phase,
        "ideal_phase": ideal_phase,
        "accumulated_phase": accumulated_phase,
        "phase_offset": offset,
        "qfg_shift": np.asarray(shift),
    }
