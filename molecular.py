"""Molecular Creator bridge with transparent QFG-inspired proxy functionals.

This is not a Kohn-Sham or ab-initio implementation. It provides scene
extraction, bond inference, explicit proxy terms inspired by the QFG-DFT notes,
property proxies, target-objective evaluation, and a small derivative-free
geometry optimizer suitable for interactive Blender experiments.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple
import math
import numpy as np


@dataclass
class AtomSpec:
    name: str
    atomic_number: int
    position: Tuple[float, float, float]
    charge: float = 0.0
    covalent_radius: float = 0.7


@dataclass
class MolecularProxyConfig:
    coulomb_scale: float = 0.05
    overlap_scale: float = 0.2
    gradient_scale: float = 0.05       # beta-like term
    kinetic_scale: float = 0.05        # gamma-like term
    topology_scale: float = 0.05       # eta-like term
    softening: float = 0.15
    bond_tolerance: float = 1.25
    bond_stiffness: float = 0.4
    charge_scale: float = 0.05


@dataclass
class MolecularTarget:
    target_energy: float = 0.0
    target_band_gap: float = 2.0
    target_wavelength_nm: float = 550.0
    target_oscillator_strength: float = 1.0
    energy_weight: float = 1.0
    band_gap_weight: float = 1.0
    wavelength_weight: float = 0.2
    oscillator_weight: float = 0.2
    synthesis_weight: float = 0.05


@dataclass
class OptimizationConfig:
    iterations: int = 120
    initial_step: float = 0.15
    cooling: float = 0.97
    seed: int = 1234
    pin_first_atom: bool = True


def infer_bonds(atoms: Sequence[AtomSpec], tolerance: float = 1.25) -> List[Tuple[int, int, float]]:
    bonds: List[Tuple[int, int, float]] = []
    for i in range(len(atoms)):
        pi = np.asarray(atoms[i].position, dtype=float)
        for j in range(i + 1, len(atoms)):
            pj = np.asarray(atoms[j].position, dtype=float)
            distance = float(np.linalg.norm(pi - pj))
            cutoff = tolerance * (atoms[i].covalent_radius + atoms[j].covalent_radius)
            if distance <= cutoff:
                bonds.append((i, j, distance))
    return bonds


def _pair_terms(atoms: Sequence[AtomSpec], cfg: MolecularProxyConfig) -> Dict[str, float]:
    nuclear = 0.0
    overlap = 0.0
    gradient = 0.0
    kinetic = 0.0
    topology = 0.0
    charge = 0.0
    bonds = infer_bonds(atoms, cfg.bond_tolerance)
    bonded = {(min(i, j), max(i, j)): r for i, j, r in bonds}

    for i in range(len(atoms)):
        pi = np.asarray(atoms[i].position, dtype=float)
        for j in range(i + 1, len(atoms)):
            pj = np.asarray(atoms[j].position, dtype=float)
            r = float(np.linalg.norm(pi - pj))
            safe_r = math.sqrt(r * r + cfg.softening * cfg.softening)
            sigma = max(atoms[i].covalent_radius + atoms[j].covalent_radius, 1e-6)
            z_product = atoms[i].atomic_number * atoms[j].atomic_number
            nuclear += cfg.coulomb_scale * z_product / safe_r
            overlap_factor = math.exp(-(r / sigma) ** 2)
            overlap += cfg.overlap_scale * overlap_factor
            gradient += cfg.gradient_scale * (r / sigma) ** 2 * overlap_factor
            kinetic += cfg.kinetic_scale * z_product ** 0.25 * overlap_factor / max(sigma, 1e-6)
            charge += cfg.charge_scale * atoms[i].charge * atoms[j].charge / safe_r
            if (i, j) in bonded:
                topology += cfg.topology_scale * (r / sigma - 1.0) ** 2
                topology += cfg.bond_stiffness * (r - 0.85 * sigma) ** 2

    return {
        "nuclear_proxy": float(nuclear),
        "coherence_overlap_proxy": float(overlap),
        "gradient_beta_proxy": float(gradient),
        "kinetic_gamma_proxy": float(kinetic),
        "topology_eta_proxy": float(topology),
        "charge_proxy": float(charge),
        "bond_count": float(len(bonds)),
    }


def proxy_energy(atoms: Sequence[AtomSpec], cfg: MolecularProxyConfig) -> Dict[str, float]:
    terms = _pair_terms(atoms, cfg)
    total = (
        terms["nuclear_proxy"]
        - terms["coherence_overlap_proxy"]
        + terms["gradient_beta_proxy"]
        + terms["kinetic_gamma_proxy"]
        + terms["topology_eta_proxy"]
        + terms["charge_proxy"]
    )
    properties = predict_properties(atoms, cfg, total_energy=total)
    return {
        "proxy_total": float(total),
        **terms,
        **properties,
        "atom_count": float(len(atoms)),
    }


def predict_properties(atoms: Sequence[AtomSpec], cfg: MolecularProxyConfig, total_energy: float | None = None) -> Dict[str, float]:
    if total_energy is None:
        total_energy = float(sum(_pair_terms(atoms, cfg).values()))
    bonds = infer_bonds(atoms, cfg.bond_tolerance)
    z_sum = max(sum(atom.atomic_number for atom in atoms), 1)
    electron_count = z_sum - sum(atom.charge for atom in atoms)
    mean_bond = float(np.mean([r for _, _, r in bonds])) if bonds else 0.0
    aromatic_proxy = 0.0
    if len(atoms) >= 5 and bonds:
        degree = np.zeros(len(atoms), dtype=int)
        for i, j, _ in bonds:
            degree[i] += 1
            degree[j] += 1
        aromatic_proxy = float(np.mean(np.clip(degree - 1, 0, 2)))
    coherence = math.exp(-abs(total_energy) / max(z_sum, 1.0)) * (1.0 + 0.15 * aromatic_proxy)
    band_gap = max(0.05, 8.0 / math.sqrt(max(electron_count, 1.0)) + 0.3 / max(mean_bond, 0.3) - 0.5 * aromatic_proxy)
    wavelength = 1239.841984 / band_gap
    oscillator = max(0.0, coherence * len(bonds) / max(len(atoms), 1))
    stability = -float(total_energy) / max(len(atoms), 1)
    synthesis_complexity = float(len(atoms) + 0.5 * len(bonds) + 0.2 * len({a.atomic_number for a in atoms}))
    return {
        "band_gap_proxy_ev": float(band_gap),
        "wavelength_proxy_nm": float(wavelength),
        "oscillator_strength_proxy": float(oscillator),
        "coherence_proxy": float(coherence),
        "stability_proxy": float(stability),
        "synthesis_complexity_proxy": synthesis_complexity,
        "mean_bond_length": mean_bond,
        "aromaticity_proxy": aromatic_proxy,
    }


def target_objective(atoms: Sequence[AtomSpec], cfg: MolecularProxyConfig, target: MolecularTarget) -> Dict[str, float]:
    result = proxy_energy(atoms, cfg)
    objective = target.energy_weight * (result["proxy_total"] - target.target_energy) ** 2
    objective += target.band_gap_weight * (result["band_gap_proxy_ev"] - target.target_band_gap) ** 2
    objective += target.wavelength_weight * ((result["wavelength_proxy_nm"] - target.target_wavelength_nm) / 100.0) ** 2
    objective += target.oscillator_weight * (result["oscillator_strength_proxy"] - target.target_oscillator_strength) ** 2
    objective += target.synthesis_weight * result["synthesis_complexity_proxy"]
    return {**result, "target_objective": float(objective)}


def optimize_geometry(
    atoms: Sequence[AtomSpec],
    cfg: MolecularProxyConfig,
    target: MolecularTarget,
    opt: OptimizationConfig,
) -> Dict[str, object]:
    if not atoms:
        raise ValueError("At least one atom is required")
    rng = np.random.default_rng(opt.seed)
    positions = np.asarray([atom.position for atom in atoms], dtype=float)
    best_positions = positions.copy()

    def make_atoms(pos: np.ndarray) -> List[AtomSpec]:
        return [AtomSpec(
            name=atom.name,
            atomic_number=atom.atomic_number,
            position=tuple(float(v) for v in pos[i]),
            charge=atom.charge,
            covalent_radius=atom.covalent_radius,
        ) for i, atom in enumerate(atoms)]

    best_result = target_objective(make_atoms(best_positions), cfg, target)
    history = [best_result["target_objective"]]
    step = opt.initial_step
    start_index = 1 if opt.pin_first_atom else 0
    for _ in range(opt.iterations):
        candidate = best_positions.copy()
        atom_index = int(rng.integers(start_index, len(atoms))) if len(atoms) > start_index else 0
        candidate[atom_index] += rng.normal(scale=step, size=3)
        result = target_objective(make_atoms(candidate), cfg, target)
        if result["target_objective"] < best_result["target_objective"]:
            best_positions = candidate
            best_result = result
        step *= opt.cooling
        history.append(best_result["target_objective"])
    return {
        "positions": best_positions,
        "atoms": make_atoms(best_positions),
        "result": best_result,
        "objective_history": np.asarray(history, dtype=float),
    }


def molecule_preset(name: str) -> List[AtomSpec]:
    key = name.upper()
    if key == "H2":
        return [
            AtomSpec("H1", 1, (-0.37, 0.0, 0.0), covalent_radius=0.31),
            AtomSpec("H2", 1, (0.37, 0.0, 0.0), covalent_radius=0.31),
        ]
    if key == "H2O":
        angle = np.deg2rad(104.5 / 2.0)
        r = 0.96
        return [
            AtomSpec("O", 8, (0.0, 0.0, 0.0), covalent_radius=0.66),
            AtomSpec("H1", 1, (r * np.sin(angle), r * np.cos(angle), 0.0), covalent_radius=0.31),
            AtomSpec("H2", 1, (-r * np.sin(angle), r * np.cos(angle), 0.0), covalent_radius=0.31),
        ]
    if key in {"BENZENE", "C6H6"}:
        atoms: List[AtomSpec] = []
        for i in range(6):
            angle = 2.0 * np.pi * i / 6.0
            atoms.append(AtomSpec(f"C{i+1}", 6, (1.39 * np.cos(angle), 1.39 * np.sin(angle), 0.0), covalent_radius=0.76))
        for i in range(6):
            angle = 2.0 * np.pi * i / 6.0
            atoms.append(AtomSpec(f"H{i+1}", 1, (2.48 * np.cos(angle), 2.48 * np.sin(angle), 0.0), covalent_radius=0.31))
        return atoms
    raise ValueError(f"Unknown molecular preset: {name}")
