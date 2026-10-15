"""Reduced-order resonator model for RF/HRM experiments."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Tuple
import numpy as np


@dataclass
class ROMConfig:
    detuning_min: float = -3.0
    detuning_max: float = 3.0
    points: int = 241
    drive_amplitude: float = 0.5
    linear_loss: float = 0.15
    nonlinear_loss: float = 0.02
    duffing: float = 0.8
    external_coupling: float = 0.2
    dt: float = 0.002
    settle_steps: int = 2500
    second_tone_ratio: float = 0.0
    second_tone_offset: float = 0.2


def _integrate_at_detuning(cfg: ROMConfig, detuning: float, initial: complex) -> complex:
    a = complex(initial)
    root_k = np.sqrt(max(cfg.external_coupling, 0.0))
    for i in range(cfg.settle_steps):
        t = i * cfg.dt
        power = abs(a) ** 2
        drive = cfg.drive_amplitude
        if cfg.second_tone_ratio:
            drive += cfg.drive_amplitude * cfg.second_tone_ratio * np.exp(-1j * cfg.second_tone_offset * t)
        da = (
            (1j * (detuning - cfg.duffing * power)
             - (cfg.linear_loss + cfg.nonlinear_loss * power)) * a
            + root_k * drive
        )
        a += cfg.dt * da
    return a


def sweep(cfg: ROMConfig, reverse: bool = False) -> Dict[str, np.ndarray]:
    detunings = np.linspace(cfg.detuning_min, cfg.detuning_max, cfg.points)
    if reverse:
        detunings = detunings[::-1]
    amplitudes = np.zeros(cfg.points, dtype=np.complex128)
    a = 0j
    for index, detuning in enumerate(detunings):
        a = _integrate_at_detuning(cfg, float(detuning), a)
        amplitudes[index] = a
    transmission = 1.0 - np.sqrt(max(cfg.external_coupling, 0.0)) * amplitudes / max(cfg.drive_amplitude, 1e-12)
    return {
        "detuning": detunings,
        "amplitude": np.abs(amplitudes),
        "phase": np.angle(amplitudes),
        "s21_magnitude": np.abs(transmission),
        "s21_db": 20.0 * np.log10(np.maximum(np.abs(transmission), 1e-12)),
    }


def hysteresis(cfg: ROMConfig) -> Dict[str, np.ndarray]:
    forward = sweep(cfg, reverse=False)
    reverse = sweep(cfg, reverse=True)
    order = np.argsort(reverse["detuning"])
    return {
        "detuning": forward["detuning"],
        "forward_db": forward["s21_db"],
        "reverse_db": reverse["s21_db"][order],
        "forward_amplitude": forward["amplitude"],
        "reverse_amplitude": reverse["amplitude"][order],
    }
