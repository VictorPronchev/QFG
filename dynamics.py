"""QFG Dynamics 0.4.1 rigid-body runtime foundation.

Version 0.4.0 extended the reduced QFG body runtime from translation-only
spherical proxies to a small deterministic 6-DoF rigid-body layer:

- quaternion orientation and angular velocity;
- shape-dependent inertia for spheres and oriented boxes (OBBs);
- external / field-alignment / drag / contact torque telemetry;
- impulses applied at contact points, so friction and off-centre impacts spin bodies;
- shape-aware Sphere/Sphere, Sphere/Box and Box/Box SAT contacts;
- shape-aware floor contacts;
- deterministic state hashing including rotational state.

This remains a research/runtime prototype, not validated engineering software
and not a replacement for PhysX, Chaos, Bullet or another production solver.
The API is deliberately backend-neutral so a future C++/CUDA implementation can
replace the numerical body layer without changing Blender content scripts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import hashlib
import math
import time
import numpy as np

from .core import ActorSpec, Diagnostics, EngineConfig, QFGEngine3D

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]  # w, x, y, z


def _zero3() -> np.ndarray:
    return np.zeros(3, dtype=np.float64)


def _identity_quat() -> np.ndarray:
    return np.asarray((1.0, 0.0, 0.0, 0.0), dtype=np.float64)


def _normalize(v: np.ndarray, fallback: Sequence[float] = (1.0, 0.0, 0.0)) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n <= 1.0e-15:
        return np.asarray(fallback, dtype=np.float64)
    return np.asarray(v, dtype=np.float64) / n


def _quat_normalize(q: Sequence[float]) -> np.ndarray:
    qn = np.asarray(q, dtype=np.float64)
    n = float(np.linalg.norm(qn))
    if n <= 1.0e-15:
        return _identity_quat()
    qn = qn / n
    # q and -q represent the same orientation. Canonicalize for deterministic hashes.
    if qn[0] < 0.0:
        qn = -qn
    return qn


def _quat_mul(a: Sequence[float], b: Sequence[float]) -> np.ndarray:
    aw, ax, ay, az = np.asarray(a, dtype=np.float64)
    bw, bx, by, bz = np.asarray(b, dtype=np.float64)
    return np.asarray((
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    ), dtype=np.float64)


def _quat_to_matrix(q: Sequence[float]) -> np.ndarray:
    w, x, y, z = _quat_normalize(q)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return np.asarray((
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
    ), dtype=np.float64)


def _integrate_quaternion(q: np.ndarray, angular_velocity_world: np.ndarray, dt: float) -> np.ndarray:
    # q maps local -> world, angular velocity is expressed in world coordinates.
    omega = np.asarray((0.0, *angular_velocity_world), dtype=np.float64)
    qdot = 0.5 * _quat_mul(omega, q)
    return _quat_normalize(q + qdot * dt)


@dataclass
class WorldConfig:
    """Configuration for the coupled QFG field/rigid-body runtime."""

    substeps: int = 2
    gravity: Vec3 = (0.0, 0.0, -0.35)
    floor_height: float = -3.75
    body_collisions: bool = True
    deterministic: bool = True
    seed: int = 1337
    max_body_speed: float = 24.0
    max_angular_speed: float = 80.0
    field_force_scale: float = 1.0
    thermal_force_scale: float = 1.0
    field_torque_scale: float = 1.0
    field_event_threshold: float = 0.35
    contact_event_threshold: float = 1.0e-4
    penetration_slop: float = 1.0e-4
    position_correction: float = 0.82
    friction_epsilon: float = 1.0e-10

    def validate(self) -> None:
        if self.substeps < 1:
            raise ValueError("substeps must be at least 1")
        if self.max_body_speed <= 0:
            raise ValueError("max_body_speed must be positive")
        if self.max_angular_speed <= 0:
            raise ValueError("max_angular_speed must be positive")
        if self.contact_event_threshold < 0:
            raise ValueError("contact_event_threshold must be non-negative")
        if self.penetration_slop < 0:
            raise ValueError("penetration_slop must be non-negative")
        if not 0.0 <= self.position_correction <= 1.0:
            raise ValueError("position_correction must be in [0, 1]")
        if self.friction_epsilon <= 0:
            raise ValueError("friction_epsilon must be positive")


@dataclass
class BodySpec:
    """Reduced 6-DoF rigid body coupled to the QFG field.

    ``radius`` remains part of the public API for backwards compatibility and
    defines SPHERE geometry. BOX geometry uses ``half_extents``.
    """

    name: str
    position: Vec3 = (0.0, 0.0, 0.0)
    velocity: Vec3 = (0.0, 0.0, 0.0)
    orientation: Quat = (1.0, 0.0, 0.0, 0.0)
    angular_velocity: Vec3 = (0.0, 0.0, 0.0)
    mass: float = 1.0
    radius: float = 0.25
    collision_shape: str = "SPHERE"
    half_extents: Vec3 = (0.25, 0.25, 0.25)
    field_coupling: float = 1.0
    thermal_coupling: float = 0.0
    field_torque_coupling: float = 0.0
    external_torque: Vec3 = (0.0, 0.0, 0.0)
    linear_drag: float = 0.08
    angular_drag: float = 0.08
    restitution: float = 0.35
    friction: float = 0.25
    kinematic: bool = False
    phase_transition_temperature: float = 1.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.mass <= 0:
            raise ValueError(f"Body {self.name!r}: mass must be positive")
        shape = self.collision_shape.upper()
        if shape not in {"SPHERE", "BOX"}:
            raise ValueError(f"Body {self.name!r}: collision_shape must be SPHERE or BOX")
        self.collision_shape = shape
        if self.radius <= 0:
            raise ValueError(f"Body {self.name!r}: radius must be positive")
        if any(float(v) <= 0.0 for v in self.half_extents):
            raise ValueError(f"Body {self.name!r}: half_extents must be positive")
        if self.linear_drag < 0 or self.angular_drag < 0:
            raise ValueError(f"Body {self.name!r}: drag values must be non-negative")
        if not 0.0 <= self.restitution <= 1.0:
            raise ValueError(f"Body {self.name!r}: restitution must be in [0, 1]")
        if self.friction < 0:
            raise ValueError(f"Body {self.name!r}: friction must be non-negative")
        _quat_normalize(self.orientation)


@dataclass
class BodyState:
    spec: BodySpec
    position: np.ndarray
    velocity: np.ndarray
    orientation: np.ndarray
    angular_velocity: np.ndarray
    sampled_density: float = 0.0
    sampled_temperature: float = 0.0
    phase_state: str = "SOLID"
    force_gravity: np.ndarray = field(default_factory=_zero3)
    force_field: np.ndarray = field(default_factory=_zero3)
    force_thermal: np.ndarray = field(default_factory=_zero3)
    force_drag: np.ndarray = field(default_factory=_zero3)
    force_contact: np.ndarray = field(default_factory=_zero3)
    force_total: np.ndarray = field(default_factory=_zero3)
    torque_external: np.ndarray = field(default_factory=_zero3)
    torque_field: np.ndarray = field(default_factory=_zero3)
    torque_drag: np.ndarray = field(default_factory=_zero3)
    torque_contact: np.ndarray = field(default_factory=_zero3)
    torque_total: np.ndarray = field(default_factory=_zero3)
    contact_impulse: np.ndarray = field(default_factory=_zero3)
    contact_angular_impulse: np.ndarray = field(default_factory=_zero3)

    @classmethod
    def from_spec(cls, spec: BodySpec) -> "BodyState":
        spec.validate()
        return cls(
            spec=spec,
            position=np.asarray(spec.position, dtype=np.float64).copy(),
            velocity=np.asarray(spec.velocity, dtype=np.float64).copy(),
            orientation=_quat_normalize(spec.orientation),
            angular_velocity=np.asarray(spec.angular_velocity, dtype=np.float64).copy(),
        )

    def rotation_matrix(self) -> np.ndarray:
        return _quat_to_matrix(self.orientation)

    def local_inertia_diag(self) -> np.ndarray:
        m = float(self.spec.mass)
        if self.spec.collision_shape == "SPHERE":
            value = 0.4 * m * float(self.spec.radius) ** 2
            return np.asarray((value, value, value), dtype=np.float64)
        hx, hy, hz = (float(v) for v in self.spec.half_extents)
        return np.asarray((
            (m / 3.0) * (hy * hy + hz * hz),
            (m / 3.0) * (hx * hx + hz * hz),
            (m / 3.0) * (hx * hx + hy * hy),
        ), dtype=np.float64)

    def inertia_world(self) -> np.ndarray:
        r = self.rotation_matrix()
        return r @ np.diag(self.local_inertia_diag()) @ r.T

    def inverse_inertia_world(self) -> np.ndarray:
        if self.spec.kinematic:
            return np.zeros((3, 3), dtype=np.float64)
        diag = self.local_inertia_diag()
        inv = np.where(diag > 1.0e-15, 1.0 / diag, 0.0)
        r = self.rotation_matrix()
        return r @ np.diag(inv) @ r.T


@dataclass
class Contact:
    normal: np.ndarray  # unit vector from body A toward body B
    penetration: float
    point: np.ndarray
    feature: str = ""


@dataclass
class DynamicsEvent:
    kind: str
    time: float
    body_a: str = ""
    body_b: str = ""
    position: Vec3 = (0.0, 0.0, 0.0)
    value: float = 0.0
    impulse: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProfileSample:
    field_ms: float = 0.0
    body_ms: float = 0.0
    query_ms: float = 0.0
    total_ms: float = 0.0
    body_count: int = 0
    contact_count: int = 0
    event_count: int = 0
    kinetic_energy: float = 0.0
    linear_kinetic_energy: float = 0.0
    rotational_kinetic_energy: float = 0.0
    mean_force: float = 0.0
    max_force: float = 0.0
    mean_torque: float = 0.0
    max_torque: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WorldStepResult:
    diagnostics: Diagnostics
    profile: ProfileSample
    events: List[DynamicsEvent]
    telemetry: Dict[str, Any] = field(default_factory=dict)


class QFGWorld:
    """Field-driven rigid-body runtime with a stable Python SDK surface."""

    def __init__(self, engine_config: EngineConfig, world_config: Optional[WorldConfig] = None):
        self.engine_config = engine_config
        self.world_config = world_config or WorldConfig()
        self.world_config.validate()
        self.engine = QFGEngine3D(engine_config)
        self.bodies: List[BodyState] = []
        self.events: List[DynamicsEvent] = []
        self.event_history: List[DynamicsEvent] = []
        self.profile_history: List[ProfileSample] = []
        self._active_contacts: Set[Tuple[int, int]] = set()
        self._active_floor_contacts: Set[int] = set()
        self._field_inside: Set[int] = set()
        self._debug_contacts: List[Dict[str, Any]] = []
        self._rng = np.random.default_rng(self.world_config.seed)
        self._cached_density: Optional[np.ndarray] = None
        self._cached_temperature: Optional[np.ndarray] = None
        self._cached_density_gradient: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None
        self._cached_temperature_gradient: Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]] = None
        self._last_query_refresh_ms = 0.0

    @property
    def time(self) -> float:
        return self.engine.time

    @property
    def step_index(self) -> int:
        return self.engine.step_index

    def add_field_actor(self, actor: ActorSpec) -> None:
        self.engine.add_actor(actor)

    def add_body(self, body: BodySpec) -> None:
        self.bodies.append(BodyState.from_spec(body))

    def clear_bodies(self) -> None:
        self.bodies.clear()
        self._active_contacts.clear()
        self._active_floor_contacts.clear()
        self._field_inside.clear()
        self._debug_contacts.clear()

    # ------------------------------------------------------------------
    # Field query cache
    # ------------------------------------------------------------------
    def _refresh_query_cache(self) -> None:
        start = time.perf_counter()
        density = np.asarray(self.engine.density(), dtype=np.float64)
        temperature = np.asarray(self.engine.temperature_numpy(), dtype=np.float64)
        self._cached_density = density
        self._cached_temperature = temperature
        edge_order = 2 if min(density.shape) >= 3 else 1
        self._cached_density_gradient = tuple(
            np.asarray(v, dtype=np.float64)
            for v in np.gradient(density, self.engine.dx, edge_order=edge_order)
        )
        self._cached_temperature_gradient = tuple(
            np.asarray(v, dtype=np.float64)
            for v in np.gradient(temperature, self.engine.dx, edge_order=edge_order)
        )
        self._last_query_refresh_ms = (time.perf_counter() - start) * 1000.0

    def _grid_coordinates(self, position: Sequence[float]) -> Tuple[float, float, float]:
        p = np.asarray(position, dtype=np.float64)
        normalized = ((p + self.engine.L / 2.0) % self.engine.L) / self.engine.dx
        return float(normalized[0]), float(normalized[1]), float(normalized[2])

    @staticmethod
    def _trilinear(array: np.ndarray, coords: Tuple[float, float, float]) -> float:
        nx, ny, nz = array.shape
        x, y, z = coords
        x0 = int(math.floor(x)) % nx
        y0 = int(math.floor(y)) % ny
        z0 = int(math.floor(z)) % nz
        x1 = (x0 + 1) % nx
        y1 = (y0 + 1) % ny
        z1 = (z0 + 1) % nz
        tx, ty, tz = x - math.floor(x), y - math.floor(y), z - math.floor(z)
        c000 = array[x0, y0, z0]
        c100 = array[x1, y0, z0]
        c010 = array[x0, y1, z0]
        c110 = array[x1, y1, z0]
        c001 = array[x0, y0, z1]
        c101 = array[x1, y0, z1]
        c011 = array[x0, y1, z1]
        c111 = array[x1, y1, z1]
        c00 = c000 * (1 - tx) + c100 * tx
        c10 = c010 * (1 - tx) + c110 * tx
        c01 = c001 * (1 - tx) + c101 * tx
        c11 = c011 * (1 - tx) + c111 * tx
        c0 = c00 * (1 - ty) + c10 * ty
        c1 = c01 * (1 - ty) + c11 * ty
        return float(c0 * (1 - tz) + c1 * tz)

    def sample_density(self, position: Sequence[float]) -> float:
        if self._cached_density is None:
            self._refresh_query_cache()
        return self._trilinear(self._cached_density, self._grid_coordinates(position))

    def sample_temperature(self, position: Sequence[float]) -> float:
        if self._cached_temperature is None:
            self._refresh_query_cache()
        return self._trilinear(self._cached_temperature, self._grid_coordinates(position))

    def sample_density_gradient(self, position: Sequence[float]) -> np.ndarray:
        if self._cached_density_gradient is None:
            self._refresh_query_cache()
        coords = self._grid_coordinates(position)
        return np.asarray([
            self._trilinear(component, coords)
            for component in self._cached_density_gradient
        ], dtype=np.float64)

    def sample_temperature_gradient(self, position: Sequence[float]) -> np.ndarray:
        if self._cached_temperature_gradient is None:
            self._refresh_query_cache()
        coords = self._grid_coordinates(position)
        return np.asarray([
            self._trilinear(component, coords)
            for component in self._cached_temperature_gradient
        ], dtype=np.float64)

    def sample_field(self, position: Sequence[float]) -> Dict[str, Any]:
        return {
            "density": self.sample_density(position),
            "temperature": self.sample_temperature(position),
            "density_gradient": self.sample_density_gradient(position),
            "temperature_gradient": self.sample_temperature_gradient(position),
        }

    # ------------------------------------------------------------------
    # Geometry / collision detection
    # ------------------------------------------------------------------
    @staticmethod
    def _support_point(body: BodyState, direction: Sequence[float]) -> np.ndarray:
        d = _normalize(np.asarray(direction, dtype=np.float64))
        if body.spec.collision_shape == "SPHERE":
            return body.position + d * body.spec.radius
        r = body.rotation_matrix()
        h = np.asarray(body.spec.half_extents, dtype=np.float64)
        local_d = r.T @ d
        local = np.zeros(3, dtype=np.float64)
        local[local_d > 1.0e-15] = h[local_d > 1.0e-15]
        local[local_d < -1.0e-15] = -h[local_d < -1.0e-15]
        # Zero components select the centre of the supporting face/edge. This
        # avoids inventing a torque for a perfectly centred floor impact.
        return body.position + r @ local

    @staticmethod
    def _projected_radius(body: BodyState, axis: np.ndarray) -> float:
        n = _normalize(axis)
        if body.spec.collision_shape == "SPHERE":
            return float(body.spec.radius)
        r = body.rotation_matrix()
        h = np.asarray(body.spec.half_extents, dtype=np.float64)
        return float(np.sum(h * np.abs(r.T @ n)))

    def _sphere_sphere_contact(self, a: BodyState, b: BodyState) -> Optional[Contact]:
        delta = b.position - a.position
        distance = float(np.linalg.norm(delta))
        target = float(a.spec.radius + b.spec.radius)
        if distance >= target:
            return None
        normal = _normalize(delta)
        penetration = target - distance
        pa = a.position + normal * a.spec.radius
        pb = b.position - normal * b.spec.radius
        return Contact(normal, penetration, 0.5 * (pa + pb), "SPHERE_SPHERE")

    def _sphere_box_contact(self, sphere: BodyState, box: BodyState) -> Optional[Contact]:
        rbox = box.rotation_matrix()
        h = np.asarray(box.spec.half_extents, dtype=np.float64)
        local = rbox.T @ (sphere.position - box.position)
        closest_local = np.clip(local, -h, h)
        closest_world = box.position + rbox @ closest_local
        delta = closest_world - sphere.position  # sphere -> box
        distance = float(np.linalg.norm(delta))
        radius = float(sphere.spec.radius)
        if distance > radius:
            return None
        if distance > 1.0e-12:
            normal = delta / distance
            penetration = radius - distance
            point = closest_world
        else:
            # Sphere centre is inside the OBB. Pick the nearest face but orient
            # the solver normal so moving A -= normal ejects the sphere outward.
            face_distance = h - np.abs(local)
            axis_index = int(np.argmin(face_distance))
            sign = 1.0 if local[axis_index] >= 0.0 else -1.0
            outward = rbox[:, axis_index] * sign
            normal = -outward
            penetration = radius + float(face_distance[axis_index])
            face_local = local.copy()
            face_local[axis_index] = sign * h[axis_index]
            point = box.position + rbox @ face_local
        return Contact(_normalize(normal), max(0.0, penetration), point, "SPHERE_BOX")

    def _box_box_contact(self, a: BodyState, b: BodyState) -> Optional[Contact]:
        ra = a.rotation_matrix()
        rb = b.rotation_matrix()
        axes_a = [ra[:, i] for i in range(3)]
        axes_b = [rb[:, i] for i in range(3)]
        candidates: List[np.ndarray] = [*axes_a, *axes_b]
        for ua in axes_a:
            for ub in axes_b:
                cross = np.cross(ua, ub)
                if float(np.linalg.norm(cross)) > 1.0e-9:
                    candidates.append(_normalize(cross))

        center_delta = b.position - a.position
        best_axis: Optional[np.ndarray] = None
        best_overlap = float("inf")
        for axis in candidates:
            n = _normalize(axis)
            ra_proj = self._projected_radius(a, n)
            rb_proj = self._projected_radius(b, n)
            separation = abs(float(np.dot(center_delta, n)))
            overlap = ra_proj + rb_proj - separation
            if overlap <= 0.0:
                return None
            if overlap < best_overlap:
                best_overlap = overlap
                best_axis = n

        assert best_axis is not None
        if float(np.dot(center_delta, best_axis)) < 0.0:
            best_axis = -best_axis
        pa = self._support_point(a, best_axis)
        pb = self._support_point(b, -best_axis)
        point = 0.5 * (pa + pb)
        return Contact(best_axis, float(best_overlap), point, "BOX_BOX_SAT")

    def _detect_contact(self, a: BodyState, b: BodyState) -> Optional[Contact]:
        sa, sb = a.spec.collision_shape, b.spec.collision_shape
        if sa == "SPHERE" and sb == "SPHERE":
            return self._sphere_sphere_contact(a, b)
        if sa == "SPHERE" and sb == "BOX":
            return self._sphere_box_contact(a, b)
        if sa == "BOX" and sb == "SPHERE":
            contact = self._sphere_box_contact(b, a)
            if contact is None:
                return None
            return Contact(-contact.normal, contact.penetration, contact.point, "BOX_SPHERE")
        return self._box_box_contact(a, b)

    # ------------------------------------------------------------------
    # Impulse solver / 6-DoF integration
    # ------------------------------------------------------------------
    def _emit(self, event: DynamicsEvent) -> None:
        self.events.append(event)
        self.event_history.append(event)

    @staticmethod
    def _point_velocity(body: BodyState, point: np.ndarray) -> np.ndarray:
        r = point - body.position
        return body.velocity + np.cross(body.angular_velocity, r)

    @staticmethod
    def _impulse_denominator(body: BodyState, r: np.ndarray, axis: np.ndarray) -> float:
        if body.spec.kinematic:
            return 0.0
        inv_mass = 1.0 / body.spec.mass
        inv_i = body.inverse_inertia_world()
        angular = np.cross(inv_i @ np.cross(r, axis), r)
        return float(inv_mass + np.dot(axis, angular))

    @staticmethod
    def _apply_impulse_at_point(body: BodyState, impulse: np.ndarray, point: np.ndarray) -> None:
        if body.spec.kinematic:
            return
        body.velocity += impulse / body.spec.mass
        r = point - body.position
        angular_impulse = np.cross(r, impulse)
        body.angular_velocity += body.inverse_inertia_world() @ angular_impulse
        body.contact_impulse += impulse
        body.contact_angular_impulse += angular_impulse

    def _resolve_contact(
        self, a: BodyState, b: BodyState, contact: Contact, dt: float
    ) -> Tuple[float, float, np.ndarray, np.ndarray]:
        n = contact.normal
        inv_a = 0.0 if a.spec.kinematic else 1.0 / a.spec.mass
        inv_b = 0.0 if b.spec.kinematic else 1.0 / b.spec.mass
        inv_total = inv_a + inv_b
        if inv_total <= 0.0:
            zero = np.zeros(3, dtype=np.float64)
            return 0.0, 0.0, zero, zero

        correction_depth = max(contact.penetration - self.world_config.penetration_slop, 0.0)
        if correction_depth > 0.0:
            correction = n * (correction_depth * self.world_config.position_correction / inv_total)
            if not a.spec.kinematic:
                a.position -= correction * inv_a
            if not b.spec.kinematic:
                b.position += correction * inv_b

        point = contact.point
        ra = point - a.position
        rb = point - b.position
        relative = self._point_velocity(b, point) - self._point_velocity(a, point)
        normal_velocity = float(np.dot(relative, n))
        normal_scalar = 0.0
        normal_impulse = np.zeros(3, dtype=np.float64)
        if normal_velocity < 0.0:
            denom = (
                self._impulse_denominator(a, ra, n)
                + self._impulse_denominator(b, rb, n)
            )
            if denom > 1.0e-15:
                restitution = min(a.spec.restitution, b.spec.restitution)
                normal_scalar = -(1.0 + restitution) * normal_velocity / denom
                normal_impulse = n * normal_scalar
                self._apply_impulse_at_point(a, -normal_impulse, point)
                self._apply_impulse_at_point(b, normal_impulse, point)

        relative_after = self._point_velocity(b, point) - self._point_velocity(a, point)
        tangent_velocity = relative_after - float(np.dot(relative_after, n)) * n
        tangent_speed = float(np.linalg.norm(tangent_velocity))
        friction_scalar = 0.0
        friction_impulse = np.zeros(3, dtype=np.float64)
        if tangent_speed > self.world_config.friction_epsilon and normal_scalar > 0.0:
            tangent = tangent_velocity / tangent_speed
            denom_t = (
                self._impulse_denominator(a, ra, tangent)
                + self._impulse_denominator(b, rb, tangent)
            )
            if denom_t > 1.0e-15:
                jt = -float(np.dot(relative_after, tangent)) / denom_t
                mu = math.sqrt(max(0.0, a.spec.friction) * max(0.0, b.spec.friction))
                limit = mu * abs(normal_scalar)
                friction_scalar = float(np.clip(jt, -limit, limit))
                friction_impulse = tangent * friction_scalar
                self._apply_impulse_at_point(a, -friction_impulse, point)
                self._apply_impulse_at_point(b, friction_impulse, point)

        if dt > 0.0:
            total = normal_impulse + friction_impulse
            if not a.spec.kinematic:
                a.force_contact += -total / dt
                a.torque_contact += np.cross(point - a.position, -total) / dt
            if not b.spec.kinematic:
                b.force_contact += total / dt
                b.torque_contact += np.cross(point - b.position, total) / dt
        return (
            float(normal_scalar), abs(float(friction_scalar)),
            normal_impulse.copy(), friction_impulse.copy(),
        )

    def _solve_floor_contact(self, index: int, body: BodyState, dt: float) -> bool:
        floor_height = float(self.world_config.floor_height)
        support = self._support_point(body, (0.0, 0.0, -1.0))
        penetration = floor_height - float(support[2])
        point_velocity = self._point_velocity(body, support)
        touching = penetration >= -self.world_config.penetration_slop and point_velocity[2] <= 0.0
        if not touching:
            return False

        if penetration > 0.0 and not body.spec.kinematic:
            body.position[2] += penetration * self.world_config.position_correction
            support = self._support_point(body, (0.0, 0.0, -1.0))

        n = np.asarray((0.0, 0.0, 1.0), dtype=np.float64)
        r = support - body.position
        point_velocity = self._point_velocity(body, support)
        normal_speed = max(0.0, -float(np.dot(point_velocity, n)))
        normal_scalar = 0.0
        normal_impulse = np.zeros(3, dtype=np.float64)
        if normal_speed > 0.0 and not body.spec.kinematic:
            denom = self._impulse_denominator(body, r, n)
            if denom > 1.0e-15:
                normal_scalar = (1.0 + body.spec.restitution) * normal_speed / denom
                normal_impulse = n * normal_scalar
                self._apply_impulse_at_point(body, normal_impulse, support)

        tangent_velocity = self._point_velocity(body, support)
        tangent_velocity = tangent_velocity - float(np.dot(tangent_velocity, n)) * n
        tangent_speed = float(np.linalg.norm(tangent_velocity))
        friction_scalar = 0.0
        friction_impulse = np.zeros(3, dtype=np.float64)
        if tangent_speed > self.world_config.friction_epsilon and normal_scalar > 0.0:
            tangent = tangent_velocity / tangent_speed
            denom_t = self._impulse_denominator(body, support - body.position, tangent)
            if denom_t > 1.0e-15:
                jt = -float(np.dot(tangent_velocity, tangent)) / denom_t
                limit = body.spec.friction * normal_scalar
                friction_scalar = float(np.clip(jt, -limit, limit))
                friction_impulse = tangent * friction_scalar
                self._apply_impulse_at_point(body, friction_impulse, support)

        total = normal_impulse + friction_impulse
        if dt > 0.0 and not body.spec.kinematic:
            body.force_contact += total / dt
            body.torque_contact += np.cross(support - body.position, total) / dt

        self._debug_contacts.append({
            "kind": "FLOOR",
            "body_a": body.spec.name,
            "body_b": "WORLD_FLOOR",
            "position": tuple(float(v) for v in support),
            "normal": (0.0, 0.0, 1.0),
            "penetration": float(max(penetration, 0.0)),
            "normal_impulse": tuple(float(v) for v in normal_impulse),
            "friction_impulse": tuple(float(v) for v in friction_impulse),
            "total_impulse": tuple(float(v) for v in total),
            "feature": f"{body.spec.collision_shape}_FLOOR",
        })

        if index not in self._active_floor_contacts and (
            normal_speed > self.world_config.contact_event_threshold
            or max(penetration, 0.0) > self.world_config.contact_event_threshold
        ):
            self._emit(DynamicsEvent(
                kind="contact_begin", time=self.time,
                body_a=body.spec.name, body_b="WORLD_FLOOR",
                position=tuple(float(v) for v in support),
                value=float(max(penetration, 0.0)), impulse=float(abs(normal_scalar)),
                details={
                    "normal": (0.0, 0.0, 1.0),
                    "normal_impulse": float(normal_scalar),
                    "friction_impulse": abs(float(friction_scalar)),
                    "relative_normal_speed": float(normal_speed),
                    "shape": body.spec.collision_shape,
                },
            ))
        return True

    def _integrate_bodies(self, dt: float) -> int:
        # Debug contacts intentionally represent the final integration substep.
        # They are display telemetry only and never participate in the solver.
        self._debug_contacts = []
        gravity = np.asarray(self.world_config.gravity, dtype=np.float64)
        max_speed = float(self.world_config.max_body_speed)
        max_angular = float(self.world_config.max_angular_speed)
        field_scale = float(self.world_config.field_force_scale)
        thermal_scale = float(self.world_config.thermal_force_scale)
        field_torque_scale = float(self.world_config.field_torque_scale)
        floor_contacts: Set[int] = set()

        for index, body in enumerate(self.bodies):
            for vector in (
                body.force_gravity, body.force_field, body.force_thermal, body.force_drag,
                body.force_contact, body.force_total, body.torque_external, body.torque_field,
                body.torque_drag, body.torque_contact, body.torque_total,
                body.contact_impulse, body.contact_angular_impulse,
            ):
                vector.fill(0.0)

            sample = self.sample_field(body.position)
            body.sampled_density = float(sample["density"])
            body.sampled_temperature = float(sample["temperature"])

            if not body.spec.kinematic:
                gradient = np.asarray(sample["density_gradient"], dtype=np.float64)
                body.force_gravity = gravity * body.spec.mass
                body.force_field = field_scale * body.spec.field_coupling * gradient
                body.force_thermal = (
                    thermal_scale * body.spec.thermal_coupling
                    * np.asarray(sample["temperature_gradient"], dtype=np.float64)
                )
                body.force_drag = -body.spec.linear_drag * body.spec.mass * body.velocity
                external_force = body.force_gravity + body.force_field + body.force_thermal
                body.velocity += (external_force / body.spec.mass) * dt
                body.velocity *= math.exp(-body.spec.linear_drag * dt)
                speed = float(np.linalg.norm(body.velocity))
                if speed > max_speed:
                    body.velocity *= max_speed / max(speed, 1.0e-12)
                body.position += body.velocity * dt

                body.torque_external = np.asarray(body.spec.external_torque, dtype=np.float64)
                if abs(body.spec.field_torque_coupling) > 0.0:
                    axis_world = body.rotation_matrix()[:, 2]
                    body.torque_field = (
                        field_torque_scale * body.spec.field_torque_coupling
                        * np.cross(axis_world, gradient)
                    )
                inertia_world = body.inertia_world()
                angular_momentum = inertia_world @ body.angular_velocity
                body.torque_drag = -body.spec.angular_drag * angular_momentum
                applied_torque = body.torque_external + body.torque_field
                # Euler rigid-body equation in world coordinates.
                alpha = body.inverse_inertia_world() @ (
                    applied_torque - np.cross(body.angular_velocity, angular_momentum)
                )
                body.angular_velocity += alpha * dt
                body.angular_velocity *= math.exp(-body.spec.angular_drag * dt)
                omega = float(np.linalg.norm(body.angular_velocity))
                if omega > max_angular:
                    body.angular_velocity *= max_angular / max(omega, 1.0e-12)
                body.orientation = _integrate_quaternion(body.orientation, body.angular_velocity, dt)

            if self._solve_floor_contact(index, body, dt):
                floor_contacts.add(index)

            inside = body.sampled_density >= self.world_config.field_event_threshold
            if inside and index not in self._field_inside:
                self._field_inside.add(index)
                self._emit(DynamicsEvent(
                    kind="field_enter", time=self.time, body_a=body.spec.name,
                    position=tuple(float(v) for v in body.position), value=body.sampled_density,
                ))
            elif not inside and index in self._field_inside:
                self._field_inside.remove(index)
                self._emit(DynamicsEvent(
                    kind="field_exit", time=self.time, body_a=body.spec.name,
                    position=tuple(float(v) for v in body.position), value=body.sampled_density,
                ))

            new_phase = "SOFTENED" if (
                body.sampled_temperature >= body.spec.phase_transition_temperature
            ) else "SOLID"
            if new_phase != body.phase_state:
                old_phase = body.phase_state
                body.phase_state = new_phase
                self._emit(DynamicsEvent(
                    kind="phase_transition", time=self.time, body_a=body.spec.name,
                    position=tuple(float(v) for v in body.position), value=body.sampled_temperature,
                    details={"from": old_phase, "to": new_phase},
                ))

        for index in self._active_floor_contacts - floor_contacts:
            body = self.bodies[index]
            self._emit(DynamicsEvent(
                kind="contact_end", time=self.time,
                body_a=body.spec.name, body_b="WORLD_FLOOR",
                position=tuple(float(v) for v in body.position),
            ))
        self._active_floor_contacts = floor_contacts

        body_contact_count = self._solve_body_contacts(dt) if self.world_config.body_collisions else 0
        for body in self.bodies:
            body.force_total = (
                body.force_gravity + body.force_field + body.force_thermal
                + body.force_drag + body.force_contact
            )
            body.torque_total = (
                body.torque_external + body.torque_field + body.torque_drag + body.torque_contact
            )
        return len(floor_contacts) + body_contact_count

    def _solve_body_contacts(self, dt: float = 1.0) -> int:
        contacts: Set[Tuple[int, int]] = set()
        count = 0
        for i in range(len(self.bodies)):
            a = self.bodies[i]
            for j in range(i + 1, len(self.bodies)):
                b = self.bodies[j]
                contact = self._detect_contact(a, b)
                if contact is None:
                    continue
                count += 1
                contacts.add((i, j))
                relative_before = self._point_velocity(b, contact.point) - self._point_velocity(a, contact.point)
                normal_speed = float(-min(np.dot(relative_before, contact.normal), 0.0))
                normal_impulse, friction_impulse, normal_vector, friction_vector = self._resolve_contact(
                    a, b, contact, dt
                )
                total_vector = normal_vector + friction_vector
                self._debug_contacts.append({
                    "kind": "BODY",
                    "body_a": a.spec.name,
                    "body_b": b.spec.name,
                    "position": tuple(float(v) for v in contact.point),
                    "normal": tuple(float(v) for v in contact.normal),
                    "penetration": float(contact.penetration),
                    "normal_impulse": tuple(float(v) for v in normal_vector),
                    "friction_impulse": tuple(float(v) for v in friction_vector),
                    "total_impulse": tuple(float(v) for v in total_vector),
                    "normal_impulse_magnitude": float(normal_impulse),
                    "friction_impulse_magnitude": float(friction_impulse),
                    "feature": contact.feature,
                })
                if (i, j) not in self._active_contacts:
                    self._emit(DynamicsEvent(
                        kind="contact_begin", time=self.time,
                        body_a=a.spec.name, body_b=b.spec.name,
                        position=tuple(float(v) for v in contact.point),
                        value=float(contact.penetration), impulse=abs(float(normal_impulse)),
                        details={
                            "normal": tuple(float(v) for v in contact.normal),
                            "normal_impulse": float(normal_impulse),
                            "friction_impulse": float(friction_impulse),
                            "relative_normal_speed": normal_speed,
                            "feature": contact.feature,
                            "shape_a": a.spec.collision_shape,
                            "shape_b": b.spec.collision_shape,
                        },
                    ))

        for pair in self._active_contacts - contacts:
            a, b = self.bodies[pair[0]], self.bodies[pair[1]]
            self._emit(DynamicsEvent(
                kind="contact_end", time=self.time,
                body_a=a.spec.name, body_b=b.spec.name,
                position=tuple(float(v) for v in 0.5 * (a.position + b.position)),
            ))
        self._active_contacts = contacts
        return count

    # ------------------------------------------------------------------
    # Telemetry / stepping / serialization
    # ------------------------------------------------------------------
    def telemetry(self) -> Dict[str, Any]:
        if not self.bodies:
            return {
                "kinetic_energy": 0.0, "linear_kinetic_energy": 0.0,
                "rotational_kinetic_energy": 0.0,
                "momentum": (0.0, 0.0, 0.0), "angular_momentum": (0.0, 0.0, 0.0),
                "mean_force": 0.0, "max_force": 0.0,
                "mean_torque": 0.0, "max_torque": 0.0,
                "active_body_contacts": len(self._active_contacts),
                "active_floor_contacts": len(self._active_floor_contacts),
                "debug_contacts": [],
            }
        dynamic = [body for body in self.bodies if not body.spec.kinematic]
        linear_ke = sum(
            0.5 * body.spec.mass * float(np.dot(body.velocity, body.velocity)) for body in dynamic
        )
        rotational_ke = sum(
            0.5 * float(np.dot(body.angular_velocity, body.inertia_world() @ body.angular_velocity))
            for body in dynamic
        )
        momentum = np.sum([body.spec.mass * body.velocity for body in dynamic], axis=0) if dynamic else np.zeros(3)
        angular_momentum = np.sum([
            np.cross(body.position, body.spec.mass * body.velocity)
            + body.inertia_world() @ body.angular_velocity
            for body in dynamic
        ], axis=0) if dynamic else np.zeros(3)
        force_norms = np.asarray([float(np.linalg.norm(body.force_total)) for body in self.bodies], dtype=np.float64)
        torque_norms = np.asarray([float(np.linalg.norm(body.torque_total)) for body in self.bodies], dtype=np.float64)
        return {
            "kinetic_energy": float(linear_ke + rotational_ke),
            "linear_kinetic_energy": float(linear_ke),
            "rotational_kinetic_energy": float(rotational_ke),
            "momentum": tuple(float(v) for v in momentum),
            "angular_momentum": tuple(float(v) for v in angular_momentum),
            "mean_force": float(np.mean(force_norms)),
            "max_force": float(np.max(force_norms)),
            "mean_torque": float(np.mean(torque_norms)),
            "max_torque": float(np.max(torque_norms)),
            "active_body_contacts": len(self._active_contacts),
            "active_floor_contacts": len(self._active_floor_contacts),
            "debug_contacts": [dict(contact) for contact in self._debug_contacts],
        }

    def step(self, count: int = 1) -> WorldStepResult:
        if count < 1:
            raise ValueError("count must be at least 1")
        final_diagnostics: Optional[Diagnostics] = None
        aggregate = ProfileSample(body_count=len(self.bodies))
        self.events = []
        total_start = time.perf_counter()
        for _ in range(count):
            for _substep in range(self.world_config.substeps):
                field_start = time.perf_counter()
                final_diagnostics = self.engine.step(1)
                aggregate.field_ms += (time.perf_counter() - field_start) * 1000.0
                self._cached_density = None
                self._cached_temperature = None
                self._cached_density_gradient = None
                self._cached_temperature_gradient = None
                self._refresh_query_cache()
                aggregate.query_ms += self._last_query_refresh_ms
                body_start = time.perf_counter()
                aggregate.contact_count += self._integrate_bodies(self.engine.config.dt)
                aggregate.body_ms += (time.perf_counter() - body_start) * 1000.0

        telemetry = self.telemetry()
        aggregate.kinetic_energy = float(telemetry["kinetic_energy"])
        aggregate.linear_kinetic_energy = float(telemetry["linear_kinetic_energy"])
        aggregate.rotational_kinetic_energy = float(telemetry["rotational_kinetic_energy"])
        aggregate.mean_force = float(telemetry["mean_force"])
        aggregate.max_force = float(telemetry["max_force"])
        aggregate.mean_torque = float(telemetry["mean_torque"])
        aggregate.max_torque = float(telemetry["max_torque"])
        aggregate.total_ms = (time.perf_counter() - total_start) * 1000.0
        aggregate.event_count = len(self.events)
        self.profile_history.append(aggregate)
        assert final_diagnostics is not None
        return WorldStepResult(final_diagnostics, aggregate, list(self.events), telemetry)

    def body_snapshot(self) -> Dict[str, Any]:
        return {
            "names": [body.spec.name for body in self.bodies],
            "positions": np.asarray([body.position for body in self.bodies], dtype=np.float32),
            "velocities": np.asarray([body.velocity for body in self.bodies], dtype=np.float32),
            "orientations": np.asarray([body.orientation for body in self.bodies], dtype=np.float32),
            "angular_velocities": np.asarray([body.angular_velocity for body in self.bodies], dtype=np.float32),
            "collision_shapes": [body.spec.collision_shape for body in self.bodies],
            "half_extents": np.asarray([body.spec.half_extents for body in self.bodies], dtype=np.float32),
            "density": np.asarray([body.sampled_density for body in self.bodies], dtype=np.float32),
            "temperature": np.asarray([body.sampled_temperature for body in self.bodies], dtype=np.float32),
            "phase_state": [body.phase_state for body in self.bodies],
            "force_gravity": np.asarray([body.force_gravity for body in self.bodies], dtype=np.float32),
            "force_field": np.asarray([body.force_field for body in self.bodies], dtype=np.float32),
            "force_thermal": np.asarray([body.force_thermal for body in self.bodies], dtype=np.float32),
            "force_drag": np.asarray([body.force_drag for body in self.bodies], dtype=np.float32),
            "force_contact": np.asarray([body.force_contact for body in self.bodies], dtype=np.float32),
            "force_total": np.asarray([body.force_total for body in self.bodies], dtype=np.float32),
            "torque_external": np.asarray([body.torque_external for body in self.bodies], dtype=np.float32),
            "torque_field": np.asarray([body.torque_field for body in self.bodies], dtype=np.float32),
            "torque_drag": np.asarray([body.torque_drag for body in self.bodies], dtype=np.float32),
            "torque_contact": np.asarray([body.torque_contact for body in self.bodies], dtype=np.float32),
            "torque_total": np.asarray([body.torque_total for body in self.bodies], dtype=np.float32),
            "contact_impulse": np.asarray([body.contact_impulse for body in self.bodies], dtype=np.float32),
            "contact_angular_impulse": np.asarray([body.contact_angular_impulse for body in self.bodies], dtype=np.float32),
        }

    def snapshot_hash(self) -> str:
        """Stable SHA-256 hash of the translational + rotational runtime state."""
        digest = hashlib.sha256()
        digest.update(str(self.step_index).encode("ascii"))
        digest.update(np.float64(self.time).tobytes())
        for body in self.bodies:
            digest.update(body.spec.name.encode("utf-8"))
            digest.update(body.spec.collision_shape.encode("ascii"))
            digest.update(np.asarray(body.position, dtype="<f8").tobytes())
            digest.update(np.asarray(body.velocity, dtype="<f8").tobytes())
            digest.update(np.asarray(_quat_normalize(body.orientation), dtype="<f8").tobytes())
            digest.update(np.asarray(body.angular_velocity, dtype="<f8").tobytes())
            digest.update(np.float64(body.sampled_density).tobytes())
            digest.update(np.float64(body.sampled_temperature).tobytes())
            digest.update(body.phase_state.encode("ascii"))
        return digest.hexdigest()

    def snapshot(self) -> Dict[str, Any]:
        payload = self.engine.snapshot()
        payload.update({
            "world_config": asdict(self.world_config),
            "bodies": [asdict(body.spec) for body in self.bodies],
            "body_state": self.body_snapshot(),
            "events": [event.to_dict() for event in self.event_history],
            "profile": [sample.to_dict() for sample in self.profile_history],
            "telemetry": self.telemetry(),
            "state_hash": self.snapshot_hash(),
        })
        return payload


__all__ = [
    "WorldConfig", "BodySpec", "BodyState", "Contact", "DynamicsEvent",
    "ProfileSample", "WorldStepResult", "QFGWorld",
]
