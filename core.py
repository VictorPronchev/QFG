"""Numerical core for QFG Lab 5.2.

The implementation is a research workbench built from the mathematical ideas in
QFG notes: a complex scalar or two-component order parameter, density-dependent
Z(rho), reduced spin texture, a Skyrme/Faddeev-inspired stabilizer, HRM dual
pumping, thermal feedback, a weak-field Poisson gravity proxy, and a reduced
U(1)-like gauge response.

It is not a validated fundamental-physics solver and it does not replace
established QFT, GR, DFT, plasma, or quantum-control software.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import math
import numpy as np

try:  # Optional acceleration. NumPy is the portable default.
    import torch  # type: ignore
except Exception:  # pragma: no cover
    torch = None

ArrayLike = Any


@dataclass
class EngineConfig:
    grid_size: int = 32
    domain_length: float = 16.0
    dt: float = 0.002
    rho0: float = 1.0
    lambda_cohesion: float = 1.0
    kappa_stability: float = 0.0019
    alpha_dielectric: float = 1.0e-6
    zeta_em: float = 0.0015
    damping: float = 0.02
    delta_anisotropy: float = 0.0
    field_mode: str = "SCALAR"  # SCALAR or SPINOR
    backend: str = "AUTO"       # AUTO, NUMPY, TORCH_CPU, TORCH_CUDA

    # Thermal / phase-change proxy
    thermal_enabled: bool = True
    heat_conduction: float = 0.05
    collision_heating: float = 0.01
    critical_temperature: float = 1.5
    temperature_cap: float = 5.0

    # Harmonic resonance modulation
    hrm_enabled: bool = False
    drive_a1: float = 0.3
    drive_a2: float = 0.3
    drive_f1: float = 5.0
    drive_f2: float = 6.2
    drive_profile: str = "UNIFORM"  # UNIFORM, GAUSSIAN, STANDING_X, RADIAL
    drive_width: float = 2.0

    # Reduced topological/orientation sector
    topology_enabled: bool = True
    spin_exchange: float = 0.0
    skyrme_potential_scale: float = 0.0
    external_b: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    # Reduced U(1)-like gauge response
    gauge_enabled: bool = False
    gauge_coupling: float = 0.05
    gauge_damping: float = 0.10
    gauge_wave_speed: float = 1.0
    gauge_backreaction: float = 0.02

    # Weak-field gravity proxy: nabla^2 Phi = 4 pi G_eff (epsilon - <epsilon>)
    gravity_enabled: bool = False
    gravity_strength: float = 1.0e-4
    gravity_backreaction: float = 1.0

    # Optional stochastic robustness testing
    noise_enabled: bool = False
    noise_amplitude: float = 0.0
    noise_seed: int = 12345

    min_z: float = 1.0e-6

    def validate(self) -> None:
        if self.grid_size < 8:
            raise ValueError("grid_size must be at least 8")
        if self.domain_length <= 0:
            raise ValueError("domain_length must be positive")
        if self.dt <= 0:
            raise ValueError("dt must be positive")
        if self.rho0 <= 0:
            raise ValueError("rho0 must be positive")
        if self.critical_temperature <= 0:
            raise ValueError("critical_temperature must be positive")
        if self.field_mode not in {"SCALAR", "SPINOR"}:
            raise ValueError("field_mode must be SCALAR or SPINOR")
        if self.drive_profile not in {"UNIFORM", "GAUSSIAN", "STANDING_X", "RADIAL"}:
            raise ValueError("unknown drive_profile")


@dataclass
class ActorSpec:
    actor_type: str = "GAUSSIAN"  # GAUSSIAN, HOPF_RING, VORTEX, PLANE_WAVE, BOUNDARY
    center: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    radius: float = 1.0
    intensity: float = 1.0
    spin_theta: float = 0.0
    spin_phi: float = 0.0
    winding_m: int = 1
    winding_n: int = 1
    ring_radius: float = 2.0
    boundary_shape: str = "SPHERE"  # SPHERE or BOX
    boundary_size: Tuple[float, float, float] = (2.0, 2.0, 2.0)
    boundary_potential: float = 0.0
    boundary_damping: float = 0.0
    name: str = "QFG Actor"


@dataclass
class Diagnostics:
    time: float
    max_density: float
    norm: float
    mode_variance: float
    mean_density: float
    max_temperature: float
    mean_temperature: float
    z_min: float
    z_max: float
    energy_proxy: float
    kinetic_energy: float
    vacuum_energy: float
    gradient_energy: float
    skyrme_energy: float
    gauge_energy: float
    gravity_energy: float
    atlas_scalar_energy: float
    center_x: float
    center_y: float
    center_z: float
    momentum_x: float
    momentum_y: float
    momentum_z: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


class QFGEngine3D:
    """Reduced 3-D QFG workbench using periodic spectral boundaries.

    Time evolution uses Strang splitting for the order parameter. The gauge and
    thermal sectors use explicit updates. Those sectors are intentionally
    reduced models, useful for numerical experiments and Blender visualization.
    """

    def __init__(self, config: EngineConfig):
        config.validate()
        self.config = config
        self.backend_name, self.device = self._select_backend(config.backend)
        self.is_torch = self.backend_name.startswith("TORCH")
        self.N = int(config.grid_size)
        self.L = float(config.domain_length)
        self.dx = self.L / self.N
        self.time = 0.0
        self.step_index = 0
        self.history: List[Diagnostics] = []
        self.actors: List[ActorSpec] = []
        self.rng = np.random.default_rng(config.noise_seed)

        space = np.linspace(-self.L / 2, self.L / 2, self.N, endpoint=False, dtype=np.float32)
        X, Y, Z = np.meshgrid(space, space, space, indexing="ij")
        k = (2.0 * np.pi * np.fft.fftfreq(self.N, d=self.dx)).astype(np.float32)
        KX, KY, KZ = np.meshgrid(k, k, k, indexing="ij")
        k2 = (KX * KX + KY * KY + KZ * KZ).astype(np.float32)

        self.space = space
        self.X = self._from_numpy(X)
        self.Y = self._from_numpy(Y)
        self.Z = self._from_numpy(Z)
        self.KX = self._from_numpy(KX)
        self.KY = self._from_numpy(KY)
        self.KZ = self._from_numpy(KZ)
        self.K2 = self._from_numpy(k2)

        if self.is_torch:
            self.kinetic_operator = torch.exp(-1j * self.K2.to(torch.complex64) * (config.dt / 2.0))
        else:
            self.kinetic_operator = np.exp(-1j * k2.astype(np.complex64) * (config.dt / 2.0)).astype(np.complex64)

        field_shape = (2, self.N, self.N, self.N) if config.field_mode == "SPINOR" else (self.N, self.N, self.N)
        self.psi = self._zeros(field_shape, complex_values=True)
        scalar_shape = (self.N, self.N, self.N)
        self.temperature = self._zeros(scalar_shape)
        self.static_potential = self._zeros(scalar_shape)
        # B3 Atlas field bridge. These arrays are populated explicitly from
        # tagged Atlas geometry and remain dimensionless/CONDITIONAL until a
        # caller supplies an independently justified normalization.
        self.atlas_potential = self._zeros(scalar_shape)
        self.atlas_vector_field = self._zeros((3, *scalar_shape))
        self.atlas_field_metadata: Dict[str, Any] = {}
        self.static_damping = self._zeros(scalar_shape)
        self.last_z = self._ones(scalar_shape)
        self.gravity_potential = self._zeros(scalar_shape)
        self.gauge_a = self._zeros((3, *scalar_shape))
        self.gauge_e = self._zeros((3, *scalar_shape))
        self.last_current = self._zeros((3, *scalar_shape))
        self.drive_mask = self._build_drive_mask()

    # ------------------------------------------------------------------
    # Backend helpers
    # ------------------------------------------------------------------
    @staticmethod
    def torch_available() -> bool:
        return torch is not None

    @staticmethod
    def cuda_available() -> bool:
        return bool(torch is not None and torch.cuda.is_available())

    def _select_backend(self, requested: str) -> Tuple[str, str]:
        requested = requested.upper()
        if requested == "NUMPY":
            return "NUMPY", "cpu"
        if requested == "TORCH_CUDA":
            if torch is None:
                raise RuntimeError("PyTorch is not installed in Blender's Python environment")
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA requested but torch.cuda.is_available() is false")
            return "TORCH_CUDA", "cuda"
        if requested == "TORCH_CPU":
            if torch is None:
                raise RuntimeError("PyTorch is not installed in Blender's Python environment")
            return "TORCH_CPU", "cpu"
        if requested == "AUTO":
            if torch is not None and torch.cuda.is_available():
                return "TORCH_CUDA", "cuda"
            return "NUMPY", "cpu"
        raise ValueError(f"Unknown backend: {requested}")

    def _from_numpy(self, arr: np.ndarray) -> ArrayLike:
        if self.is_torch:
            return torch.as_tensor(arr, dtype=torch.float32, device=self.device)
        return np.asarray(arr, dtype=np.float32)

    def _zeros(self, shape: Sequence[int], complex_values: bool = False) -> ArrayLike:
        if self.is_torch:
            return torch.zeros(tuple(shape), dtype=torch.complex64 if complex_values else torch.float32, device=self.device)
        return np.zeros(tuple(shape), dtype=np.complex64 if complex_values else np.float32)

    def _ones(self, shape: Sequence[int]) -> ArrayLike:
        if self.is_torch:
            return torch.ones(tuple(shape), dtype=torch.float32, device=self.device)
        return np.ones(tuple(shape), dtype=np.float32)

    def _fftn(self, arr: ArrayLike) -> ArrayLike:
        return torch.fft.fftn(arr, dim=(-3, -2, -1)) if self.is_torch else np.fft.fftn(arr, axes=(-3, -2, -1))

    def _ifftn(self, arr: ArrayLike) -> ArrayLike:
        return torch.fft.ifftn(arr, dim=(-3, -2, -1)) if self.is_torch else np.fft.ifftn(arr, axes=(-3, -2, -1))

    def _abs2(self, arr: ArrayLike) -> ArrayLike:
        return torch.abs(arr) ** 2 if self.is_torch else np.abs(arr) ** 2

    def _to_numpy(self, arr: ArrayLike) -> np.ndarray:
        return arr.detach().cpu().numpy() if self.is_torch else np.asarray(arr)

    def _real_scalar(self, value: ArrayLike) -> float:
        return float(value.detach().cpu().item()) if self.is_torch else float(np.asarray(value).item())

    def _clamp(self, arr: ArrayLike, low: float, high: Optional[float] = None) -> ArrayLike:
        return torch.clamp(arr, min=low, max=high) if self.is_torch else np.clip(arr, low, high)

    def _complex_exp(self, phase: ArrayLike) -> ArrayLike:
        if self.is_torch:
            return torch.exp(1j * phase.to(torch.complex64))
        return np.exp(1j * phase).astype(np.complex64)

    def _sqrt(self, arr: ArrayLike) -> ArrayLike:
        return torch.sqrt(arr) if self.is_torch else np.sqrt(arr)

    def _sum_axis0(self, arr: ArrayLike) -> ArrayLike:
        return arr.sum(dim=0) if self.is_torch else arr.sum(axis=0)

    def _mean(self, arr: ArrayLike) -> ArrayLike:
        return torch.mean(arr) if self.is_torch else np.mean(arr)

    # ------------------------------------------------------------------
    # Field construction
    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.psi[...] = 0
        self.temperature[...] = 0
        self.static_potential[...] = 0
        self.atlas_potential[...] = 0
        self.atlas_vector_field[...] = 0
        self.atlas_field_metadata = {}
        self.static_damping[...] = 0
        self.last_z[...] = 1
        self.gravity_potential[...] = 0
        self.gauge_a[...] = 0
        self.gauge_e[...] = 0
        self.last_current[...] = 0
        self.time = 0.0
        self.step_index = 0
        self.history.clear()
        self.actors.clear()

    def add_actor(self, actor: ActorSpec) -> None:
        actor_type = actor.actor_type.upper()
        if actor.radius <= 0 and actor_type != "PLANE_WAVE":
            raise ValueError(f"Actor {actor.name!r} has non-positive radius")
        if actor_type == "GAUSSIAN":
            self._spawn_gaussian(actor)
        elif actor_type == "HOPF_RING":
            self._spawn_hopf_ring(actor)
        elif actor_type == "VORTEX":
            self._spawn_vortex(actor)
        elif actor_type == "PLANE_WAVE":
            self._spawn_plane_wave(actor)
        elif actor_type == "BOUNDARY":
            self._add_boundary(actor)
        else:
            raise ValueError(f"Unsupported actor_type: {actor.actor_type}")
        self.actors.append(actor)

    def set_atlas_field(
        self,
        scalar_potential: np.ndarray,
        vector_field: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Install a B3 Atlas field bundle on the current grid.

        The arrays are expected to be already normalized by the caller.  This
        method intentionally performs no physical-unit interpretation.
        """
        scalar = np.asarray(scalar_potential, dtype=np.float32)
        expected = (self.N, self.N, self.N)
        if scalar.shape != expected or not np.all(np.isfinite(scalar)):
            raise ValueError(f"Atlas scalar potential must have shape {expected} and finite values")
        if vector_field is None:
            vector = np.zeros((3, *expected), dtype=np.float32)
        else:
            vector = np.asarray(vector_field, dtype=np.float32)
            if vector.shape != (3, *expected) or not np.all(np.isfinite(vector)):
                raise ValueError(f"Atlas vector field must have shape {(3, *expected)} and finite values")
        self.atlas_potential = self._from_numpy(scalar)
        self.atlas_vector_field = self._from_numpy(vector)
        self.atlas_field_metadata = dict(metadata or {})

    def clear_atlas_field(self) -> None:
        self.atlas_potential[...] = 0
        self.atlas_vector_field[...] = 0
        self.atlas_field_metadata = {}

    def atlas_field_numpy(self) -> Tuple[np.ndarray, np.ndarray]:
        return (
            self._to_numpy(self.atlas_potential).astype(np.float32, copy=False),
            self._to_numpy(self.atlas_vector_field).astype(np.float32, copy=False),
        )

    def _phase_kick(self, velocity: Tuple[float, float, float]) -> ArrayLike:
        phase = velocity[0] * self.X + velocity[1] * self.Y + velocity[2] * self.Z
        return self._complex_exp(phase)

    def _spinor_orientation(self, theta: float, phi: float) -> Tuple[complex, complex]:
        return complex(math.cos(theta / 2.0), 0.0), math.sin(theta / 2.0) * complex(math.cos(phi), math.sin(phi))

    def _spawn_gaussian(self, actor: ActorSpec) -> None:
        cx, cy, cz = actor.center
        r2 = (self.X - cx) ** 2 + (self.Y - cy) ** 2 + (self.Z - cz) ** 2
        if self.is_torch:
            envelope = actor.intensity * torch.exp(-r2 / max(2.0 * actor.radius ** 2, 1e-12))
        else:
            envelope = actor.intensity * np.exp(-r2 / max(2.0 * actor.radius ** 2, 1e-12))
        node = envelope.to(torch.complex64) if self.is_torch else envelope.astype(np.complex64)
        node = node * self._phase_kick(actor.velocity)
        if self.config.field_mode == "SCALAR":
            self.psi += node
        else:
            c0, c1 = self._spinor_orientation(actor.spin_theta, actor.spin_phi)
            self.psi[0] += node * c0
            self.psi[1] += node * c1

    def _spawn_hopf_ring(self, actor: ActorSpec) -> None:
        cx, cy, cz = actor.center
        x = self.X - cx
        y = self.Y - cy
        z = self.Z - cz
        radial = self._sqrt(x * x + y * y)
        tube2 = (radial - actor.ring_radius) ** 2 + z * z
        if self.is_torch:
            envelope = actor.intensity * torch.exp(-tube2 / max(2.0 * actor.radius ** 2, 1e-12))
            theta_xy = torch.atan2(y, x)
            theta_tube = torch.atan2(z, radial - actor.ring_radius)
        else:
            envelope = actor.intensity * np.exp(-tube2 / max(2.0 * actor.radius ** 2, 1e-12))
            theta_xy = np.arctan2(y, x)
            theta_tube = np.arctan2(z, radial - actor.ring_radius)
        phase = actor.winding_m * theta_xy + actor.winding_n * theta_tube
        base = (envelope.to(torch.complex64) if self.is_torch else envelope.astype(np.complex64)) * self._complex_exp(phase)
        base *= self._phase_kick(actor.velocity)
        if self.config.field_mode == "SCALAR":
            self.psi += base
        else:
            # Stereographic-like two-component ring texture.
            if self.is_torch:
                beta = torch.atan2(torch.sqrt(tube2), torch.full_like(tube2, max(actor.radius, 1e-6)))
                self.psi[0] += base * torch.cos(beta / 2.0)
                self.psi[1] += base * torch.sin(beta / 2.0) * self._complex_exp(theta_xy)
            else:
                beta = np.arctan2(np.sqrt(tube2), max(actor.radius, 1e-6))
                self.psi[0] += base * np.cos(beta / 2.0)
                self.psi[1] += base * np.sin(beta / 2.0) * self._complex_exp(theta_xy)

    def _spawn_vortex(self, actor: ActorSpec) -> None:
        cx, cy, cz = actor.center
        x = self.X - cx
        y = self.Y - cy
        z = self.Z - cz
        rxy2 = x * x + y * y
        r2 = rxy2 + z * z
        if self.is_torch:
            angle = torch.atan2(y, x)
            envelope = actor.intensity * torch.sqrt(rxy2 + 1e-12) * torch.exp(-r2 / max(2.0 * actor.radius ** 2, 1e-12))
        else:
            angle = np.arctan2(y, x)
            envelope = actor.intensity * np.sqrt(rxy2 + 1e-12) * np.exp(-r2 / max(2.0 * actor.radius ** 2, 1e-12))
        node = (envelope.to(torch.complex64) if self.is_torch else envelope.astype(np.complex64)) * self._complex_exp(actor.winding_m * angle)
        node *= self._phase_kick(actor.velocity)
        if self.config.field_mode == "SCALAR":
            self.psi += node
        else:
            self.psi[0] += node
            self.psi[1] += 0.35 * node * self._complex_exp(actor.winding_n * angle)

    def _spawn_plane_wave(self, actor: ActorSpec) -> None:
        wave = actor.intensity * self._phase_kick(actor.velocity)
        if self.config.field_mode == "SCALAR":
            self.psi += wave
        else:
            c0, c1 = self._spinor_orientation(actor.spin_theta, actor.spin_phi)
            self.psi[0] += wave * c0
            self.psi[1] += wave * c1

    def _add_boundary(self, actor: ActorSpec) -> None:
        cx, cy, cz = actor.center
        if actor.boundary_shape.upper() == "BOX":
            sx, sy, sz = actor.boundary_size
            mask = (
                (abs(self.X - cx) <= max(sx / 2.0, self.dx))
                & (abs(self.Y - cy) <= max(sy / 2.0, self.dx))
                & (abs(self.Z - cz) <= max(sz / 2.0, self.dx))
            )
        else:
            r2 = (self.X - cx) ** 2 + (self.Y - cy) ** 2 + (self.Z - cz) ** 2
            mask = r2 <= actor.radius ** 2
        mask_f = mask.to(torch.float32) if self.is_torch else mask.astype(np.float32)
        self.static_potential += mask_f * float(actor.boundary_potential)
        self.static_damping += mask_f * max(0.0, float(actor.boundary_damping))

    def _build_drive_mask(self) -> ArrayLike:
        cfg = self.config
        if cfg.drive_profile == "UNIFORM":
            return self._ones((self.N, self.N, self.N))
        if cfg.drive_profile == "GAUSSIAN":
            r2 = self.X * self.X + self.Y * self.Y + self.Z * self.Z
            if self.is_torch:
                return torch.exp(-r2 / max(2.0 * cfg.drive_width ** 2, 1e-12))
            return np.exp(-r2 / max(2.0 * cfg.drive_width ** 2, 1e-12)).astype(np.float32)
        if cfg.drive_profile == "STANDING_X":
            if self.is_torch:
                return torch.cos(2.0 * math.pi * self.X / self.L) ** 2
            return (np.cos(2.0 * math.pi * self.X / self.L) ** 2).astype(np.float32)
        radial = self._sqrt(self.X * self.X + self.Y * self.Y)
        if self.is_torch:
            return torch.exp(-((radial - cfg.drive_width) ** 2 + self.Z ** 2) / max(0.5 * cfg.drive_width ** 2, 1e-12))
        return np.exp(-((radial - cfg.drive_width) ** 2 + self.Z ** 2) / max(0.5 * cfg.drive_width ** 2, 1e-12)).astype(np.float32)

    # ------------------------------------------------------------------
    # Differential operators and derived fields
    # ------------------------------------------------------------------
    def _kinetic_half_step(self, psi: ArrayLike) -> ArrayLike:
        return self._ifftn(self._fftn(psi) * self.kinetic_operator)

    def _laplacian_real(self, field: ArrayLike) -> ArrayLike:
        if self.is_torch:
            return self._ifftn(-self.K2.to(torch.complex64) * self._fftn(field.to(torch.complex64))).real
        return self._ifftn(-self.K2.astype(np.complex64) * self._fftn(field.astype(np.complex64))).real.astype(np.float32)

    def _spectral_derivative(self, field: ArrayLike, axis: int) -> ArrayLike:
        k = (self.KX, self.KY, self.KZ)[axis]
        if self.is_torch:
            return self._ifftn(1j * k.to(torch.complex64) * self._fftn(field.to(torch.complex64))).real
        return self._ifftn(1j * k.astype(np.complex64) * self._fftn(field.astype(np.complex64))).real.astype(np.float32)

    def density_backend(self, psi: Optional[ArrayLike] = None) -> ArrayLike:
        field = self.psi if psi is None else psi
        density = self._abs2(field)
        return self._sum_axis0(density) if self.config.field_mode == "SPINOR" else density

    def density(self) -> np.ndarray:
        return self._to_numpy(self.density_backend()).astype(np.float32, copy=False)

    def temperature_numpy(self) -> np.ndarray:
        return self._to_numpy(self.temperature).astype(np.float32, copy=False)

    def gauge_magnitude(self) -> np.ndarray:
        mag = self._sqrt(self._sum_axis0(self.gauge_a * self.gauge_a))
        return self._to_numpy(mag).astype(np.float32, copy=False)

    def gravity_numpy(self) -> np.ndarray:
        return self._to_numpy(self.gravity_potential).astype(np.float32, copy=False)

    def _spin_texture_backend(self, spinor: ArrayLike) -> Tuple[ArrayLike, ArrayLike, ArrayLike]:
        a, b = spinor[0], spinor[1]
        rho = self._abs2(a) + self._abs2(b) + 1e-12
        if self.is_torch:
            cross = torch.conj(a) * b
            return 2.0 * torch.real(cross) / rho, 2.0 * torch.imag(cross) / rho, (torch.abs(a) ** 2 - torch.abs(b) ** 2) / rho
        cross = np.conj(a) * b
        return 2.0 * np.real(cross) / rho, 2.0 * np.imag(cross) / rho, (np.abs(a) ** 2 - np.abs(b) ** 2) / rho

    def spin_texture(self) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        if self.config.field_mode != "SPINOR":
            return None
        return tuple(self._to_numpy(v).astype(np.float32, copy=False) for v in self._spin_texture_backend(self.psi))  # type: ignore

    def _current_density(self, field: ArrayLike) -> ArrayLike:
        components = field if self.config.field_mode == "SPINOR" else field[None, ...]
        current = self._zeros((3, self.N, self.N, self.N))
        for axis in range(3):
            total = self._zeros((self.N, self.N, self.N))
            k = (self.KX, self.KY, self.KZ)[axis]
            for component in components:
                if self.is_torch:
                    deriv = self._ifftn(1j * k.to(torch.complex64) * self._fftn(component))
                    total += torch.imag(torch.conj(component) * deriv)
                else:
                    deriv = self._ifftn(1j * k.astype(np.complex64) * self._fftn(component))
                    total += np.imag(np.conj(component) * deriv).astype(np.float32)
            current[axis] = total
        return current

    def _skyrme_density_backend(self, texture: Tuple[ArrayLike, ArrayLike, ArrayLike]) -> ArrayLike:
        n = texture
        grads = [[self._spectral_derivative(n[a], i) for i in range(3)] for a in range(3)]
        # |d_i n x d_j n|^2 summed over pairs.
        density = self._zeros((self.N, self.N, self.N))
        for i, j in ((0, 1), (1, 2), (2, 0)):
            ax, ay, az = grads[0][i], grads[1][i], grads[2][i]
            bx, by, bz = grads[0][j], grads[1][j], grads[2][j]
            cx = ay * bz - az * by
            cy = az * bx - ax * bz
            cz = ax * by - ay * bx
            density += cx * cx + cy * cy + cz * cz
        return density

    # ------------------------------------------------------------------
    # Evolution
    # ------------------------------------------------------------------
    def step(self, count: int = 1) -> Diagnostics:
        if count < 1:
            raise ValueError("count must be at least one")
        diag: Optional[Diagnostics] = None
        for _ in range(count):
            self._step_once()
            diag = self.compute_diagnostics()
            self.history.append(diag)
        assert diag is not None
        return diag

    def _step_once(self) -> None:
        cfg = self.config
        psi_mid = self._kinetic_half_step(self.psi)
        rho = self.density_backend(psi_mid)

        # Thermal feedback.
        if cfg.thermal_enabled:
            self.temperature += cfg.heat_conduction * self._laplacian_real(self.temperature) * cfg.dt
            self.temperature += cfg.collision_heating * (rho - cfg.rho0) ** 2 * cfg.dt
            self.temperature = self._clamp(self.temperature, 0.0, cfg.temperature_cap)

        dynamic_lambda = (
            cfg.lambda_cohesion * torch.exp(-self.temperature / cfg.critical_temperature)
            if self.is_torch else
            cfg.lambda_cohesion * np.exp(-self.temperature / cfg.critical_temperature)
        )

        lap_rho = self._laplacian_real(rho)
        v_base = -2.0 * dynamic_lambda * (rho - cfg.rho0) + cfg.kappa_stability * lap_rho
        z_rho = self._clamp(1.0 + cfg.alpha_dielectric * (rho - cfg.rho0), cfg.min_z, None)
        self.last_z = z_rho

        drive = 0.0
        if cfg.hrm_enabled:
            drive = cfg.drive_a1 * math.sin(2.0 * math.pi * cfg.drive_f1 * self.time)
            drive += cfg.drive_a2 * math.sin(2.0 * math.pi * cfg.drive_f2 * self.time)

        v_total = v_base + self.static_potential + self.atlas_potential
        v_total += (drive * self.drive_mask / self._sqrt(z_rho)) * cfg.zeta_em

        texture = None
        skyrme_density = self._zeros((self.N, self.N, self.N))
        if cfg.field_mode == "SPINOR":
            texture = self._spin_texture_backend(psi_mid)
            if cfg.topology_enabled:
                skyrme_density = self._skyrme_density_backend(texture)
                v_total += cfg.skyrme_potential_scale * skyrme_density

        # Weak-field gravity proxy from a local energy-density estimate.
        if cfg.gravity_enabled:
            source = cfg.lambda_cohesion * (rho - cfg.rho0) ** 2 + 0.5 * lap_rho * lap_rho
            source = source - self._mean(source)
            source_k = self._fftn(source)
            if self.is_torch:
                denom = self.K2.clone()
                denom[0, 0, 0] = 1.0
                phi_k = -(4.0 * math.pi * cfg.gravity_strength) * source_k / denom.to(torch.complex64)
                phi_k[0, 0, 0] = 0.0
            else:
                denom = np.array(self.K2, copy=True)
                denom[0, 0, 0] = 1.0
                phi_k = -(4.0 * math.pi * cfg.gravity_strength) * source_k / denom.astype(np.complex64)
                phi_k[0, 0, 0] = 0.0
            self.gravity_potential = self._ifftn(phi_k).real
            v_total += cfg.gravity_backreaction * self.gravity_potential

        # Reduced gauge dynamics and backreaction.
        current = self._current_density(psi_mid)
        self.last_current = current
        if cfg.gauge_enabled:
            lap_a = self._zeros(self.gauge_a.shape)
            for axis in range(3):
                lap_a[axis] = self._laplacian_real(self.gauge_a[axis])
            self.gauge_e += cfg.dt * (
                cfg.gauge_wave_speed ** 2 * lap_a
                + cfg.gauge_coupling * current
                - cfg.gauge_damping * self.gauge_e
            )
            self.gauge_a += cfg.dt * self.gauge_e
            a2 = self._sum_axis0(self.gauge_a * self.gauge_a)
            a_dot_j = self._sum_axis0(self.gauge_a * current)
            v_total += cfg.gauge_backreaction * (0.5 * cfg.gauge_coupling ** 2 * a2 - cfg.gauge_coupling * a_dot_j / (rho + 1e-9))

        # Optional complex noise for robustness tests.
        if cfg.noise_enabled and cfg.noise_amplitude > 0:
            noise_np = (
                self.rng.standard_normal((self.N, self.N, self.N), dtype=np.float32)
                + 1j * self.rng.standard_normal((self.N, self.N, self.N), dtype=np.float32)
            )
            if self.is_torch:
                noise = torch.as_tensor(noise_np, dtype=torch.complex64, device=self.device)
            else:
                noise = noise_np.astype(np.complex64)
        else:
            noise = 0.0

        damping_total = cfg.damping + self.static_damping
        if cfg.field_mode == "SCALAR":
            if self.is_torch:
                op = torch.exp((1j * v_total.to(torch.complex64) - damping_total) * cfg.dt)
            else:
                op = np.exp((1j * v_total - damping_total) * cfg.dt).astype(np.complex64)
            psi_pot = psi_mid * op + cfg.noise_amplitude * math.sqrt(cfg.dt) * noise
        else:
            assert texture is not None
            nx, ny, nz = texture
            bx, by, bz = cfg.external_b
            external_projection = cfg.spin_exchange * (bx * nx + by * ny + bz * nz)
            atlas_projection = (
                self.atlas_vector_field[0] * nx
                + self.atlas_vector_field[1] * ny
                + self.atlas_vector_field[2] * nz
            )
            h0 = v_total - cfg.delta_anisotropy * nz - external_projection - atlas_projection
            h1 = v_total + cfg.delta_anisotropy * nz + external_projection + atlas_projection
            if self.is_torch:
                op0 = torch.exp((1j * h0.to(torch.complex64) - damping_total) * cfg.dt)
                op1 = torch.exp((1j * h1.to(torch.complex64) - damping_total) * cfg.dt)
            else:
                op0 = np.exp((1j * h0 - damping_total) * cfg.dt).astype(np.complex64)
                op1 = np.exp((1j * h1 - damping_total) * cfg.dt).astype(np.complex64)
            psi_pot = self._zeros(psi_mid.shape, complex_values=True)
            psi_pot[0] = psi_mid[0] * op0 + cfg.noise_amplitude * math.sqrt(cfg.dt) * noise
            psi_pot[1] = psi_mid[1] * op1 + cfg.noise_amplitude * math.sqrt(cfg.dt) * noise

        self.psi = self._kinetic_half_step(psi_pot)
        self.time += cfg.dt
        self.step_index += 1

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    def _component_energies(self) -> Dict[str, float]:
        cfg = self.config
        rho = self.density_backend()
        psi_k = self._fftn(self.psi)
        if self.is_torch:
            spectral_power = torch.abs(psi_k) ** 2
            if cfg.field_mode == "SPINOR":
                spectral_power = spectral_power.sum(dim=0)
            kinetic = self._real_scalar(torch.sum(self.K2 * spectral_power)) / (self.N ** 3)
            vacuum = self._real_scalar(torch.sum(cfg.lambda_cohesion * (rho - cfg.rho0) ** 2))
            grad_rho = self._real_scalar(torch.sum(self._laplacian_real(rho) ** 2)) * abs(cfg.kappa_stability)
            gauge = 0.5 * self._real_scalar(torch.sum(self.gauge_e ** 2 + cfg.gauge_wave_speed ** 2 * self.gauge_a ** 2))
            gravity = 0.5 * self._real_scalar(torch.sum(rho * self.gravity_potential))
            atlas = self._real_scalar(torch.sum(rho * self.atlas_potential))
        else:
            spectral_power = np.abs(psi_k) ** 2
            if cfg.field_mode == "SPINOR":
                spectral_power = spectral_power.sum(axis=0)
            kinetic = float(np.sum(self.K2 * spectral_power) / (self.N ** 3))
            vacuum = float(np.sum(cfg.lambda_cohesion * (rho - cfg.rho0) ** 2))
            grad_rho = float(np.sum(self._laplacian_real(rho) ** 2)) * abs(cfg.kappa_stability)
            gauge = 0.5 * float(np.sum(self.gauge_e ** 2 + cfg.gauge_wave_speed ** 2 * self.gauge_a ** 2))
            gravity = 0.5 * float(np.sum(rho * self.gravity_potential))
            atlas = float(np.sum(rho * self.atlas_potential))
        skyrme = 0.0
        if cfg.field_mode == "SPINOR" and cfg.topology_enabled:
            texture = self._spin_texture_backend(self.psi)
            skyrme_density = self._skyrme_density_backend(texture)
            if self.is_torch:
                skyrme = 0.25 * cfg.kappa_stability * self._real_scalar(torch.sum(skyrme_density))
            else:
                skyrme = 0.25 * cfg.kappa_stability * float(np.sum(skyrme_density))
        scale = self.dx ** 3
        return {
            "kinetic": kinetic * scale,
            "vacuum": vacuum * scale,
            "gradient": grad_rho * scale,
            "skyrme": skyrme * scale,
            "gauge": gauge * scale,
            "gravity": gravity * scale,
            "atlas_scalar": atlas * scale,
        }

    def _center_and_momentum(self, rho: ArrayLike) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        norm_raw = self._real_scalar(self._sum_backend(rho))
        denom = max(norm_raw, 1e-12)
        coords = []
        for coord in (self.X, self.Y, self.Z):
            coords.append(self._real_scalar(self._sum_backend(coord * rho)) / denom)
        current = self.last_current
        momentum = []
        for axis in range(3):
            momentum.append(self._real_scalar(self._sum_backend(current[axis])) * self.dx ** 3)
        return (coords[0], coords[1], coords[2]), (momentum[0], momentum[1], momentum[2])

    def _sum_backend(self, arr: ArrayLike) -> ArrayLike:
        return torch.sum(arr) if self.is_torch else np.sum(arr)

    def compute_diagnostics(self) -> Diagnostics:
        rho = self.density_backend()
        if self.is_torch:
            max_density = self._real_scalar(torch.max(rho))
            mean_density = self._real_scalar(torch.mean(rho))
            mode_var = self._real_scalar(torch.var(rho, unbiased=False))
            norm = self._real_scalar(torch.sum(rho)) * self.dx ** 3
            max_temp = self._real_scalar(torch.max(self.temperature))
            mean_temp = self._real_scalar(torch.mean(self.temperature))
            z_min = self._real_scalar(torch.min(self.last_z))
            z_max = self._real_scalar(torch.max(self.last_z))
        else:
            max_density = float(np.max(rho))
            mean_density = float(np.mean(rho))
            mode_var = float(np.var(rho))
            norm = float(np.sum(rho) * self.dx ** 3)
            max_temp = float(np.max(self.temperature))
            mean_temp = float(np.mean(self.temperature))
            z_min = float(np.min(self.last_z))
            z_max = float(np.max(self.last_z))
        energies = self._component_energies()
        center, momentum = self._center_and_momentum(rho)
        energy_proxy = sum(energies.values()) + float(np.sum(self.temperature_numpy()) * self.dx ** 3)
        return Diagnostics(
            time=float(self.time),
            max_density=max_density,
            norm=norm,
            mode_variance=mode_var,
            mean_density=mean_density,
            max_temperature=max_temp,
            mean_temperature=mean_temp,
            z_min=z_min,
            z_max=z_max,
            energy_proxy=float(energy_proxy),
            kinetic_energy=float(energies["kinetic"]),
            vacuum_energy=float(energies["vacuum"]),
            gradient_energy=float(energies["gradient"]),
            skyrme_energy=float(energies["skyrme"]),
            gauge_energy=float(energies["gauge"]),
            gravity_energy=float(energies["gravity"]),
            atlas_scalar_energy=float(energies["atlas_scalar"]),
            center_x=float(center[0]),
            center_y=float(center[1]),
            center_z=float(center[2]),
            momentum_x=float(momentum[0]),
            momentum_y=float(momentum[1]),
            momentum_z=float(momentum[2]),
        )

    def topological_diagnostics(self) -> Dict[str, float]:
        """Return Skyrme and Coulomb-gauge helicity/Hopf comparison proxies."""
        texture = self.spin_texture()
        if texture is None:
            return {"skyrme_energy_proxy": 0.0, "hopf_proxy": 0.0, "orientation_variance": 0.0}
        nx, ny, nz = (np.asarray(v, dtype=np.float64) for v in texture)
        n = np.stack([nx, ny, nz], axis=0)
        grads = [[np.gradient(n[a], self.dx, axis=i, edge_order=1) for i in range(3)] for a in range(3)]
        dnx = np.stack([grads[a][0] for a in range(3)], axis=0)
        dny = np.stack([grads[a][1] for a in range(3)], axis=0)
        dnz = np.stack([grads[a][2] for a in range(3)], axis=0)
        bx = 0.5 * np.sum(n * np.cross(dny, dnz, axisa=0, axisb=0, axisc=0), axis=0)
        by = 0.5 * np.sum(n * np.cross(dnz, dnx, axisa=0, axisb=0, axisc=0), axis=0)
        bz = 0.5 * np.sum(n * np.cross(dnx, dny, axisa=0, axisb=0, axisc=0), axis=0)
        skyrme = float(np.sum(bx * bx + by * by + bz * bz) * self.dx ** 3)

        bx_k, by_k, bz_k = np.fft.fftn(bx), np.fft.fftn(by), np.fft.fftn(bz)
        kx = self._to_numpy(self.KX).astype(np.float64)
        ky = self._to_numpy(self.KY).astype(np.float64)
        kz = self._to_numpy(self.KZ).astype(np.float64)
        k2 = kx * kx + ky * ky + kz * kz
        k2[0, 0, 0] = 1.0
        ax_k = 1j * (ky * bz_k - kz * by_k) / k2
        ay_k = 1j * (kz * bx_k - kx * bz_k) / k2
        az_k = 1j * (kx * by_k - ky * bx_k) / k2
        ax_k[0, 0, 0] = ay_k[0, 0, 0] = az_k[0, 0, 0] = 0.0
        ax = np.fft.ifftn(ax_k).real
        ay = np.fft.ifftn(ay_k).real
        az = np.fft.ifftn(az_k).real
        hopf = float(np.sum(ax * bx + ay * by + az * bz) * self.dx ** 3 / (32.0 * np.pi ** 2))
        orientation_variance = float(np.mean(np.var(n.reshape(3, -1), axis=1)))
        return {
            "skyrme_energy_proxy": skyrme,
            "hopf_proxy": hopf,
            "orientation_variance": orientation_variance,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "step_index": self.step_index,
            "backend": self.backend_name,
            "device": self.device,
            "config": asdict(self.config),
            "density": self.density(),
            "temperature": self.temperature_numpy(),
            "gauge_magnitude": self.gauge_magnitude(),
            "gravity_potential": self.gravity_numpy(),
            "atlas_potential": self._to_numpy(self.atlas_potential).astype(np.float32, copy=False),
            "atlas_vector_field": self._to_numpy(self.atlas_vector_field).astype(np.float32, copy=False),
            "diagnostics": self.compute_diagnostics().to_dict(),
            "topology": self.topological_diagnostics(),
        }
