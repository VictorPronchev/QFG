"""Blender property definitions for QFG Lab 5.2."""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty,
    IntProperty, PointerProperty, StringProperty,
)


class QFGSceneProperties(bpy.types.PropertyGroup):
    # Core engine
    backend: EnumProperty(
        name="Backend",
        items=[
            ("AUTO", "Auto", "PyTorch CUDA when available; otherwise NumPy"),
            ("NUMPY", "NumPy CPU", "Portable CPU backend"),
            ("TORCH_CPU", "PyTorch CPU", "Installed PyTorch CPU backend"),
            ("TORCH_CUDA", "PyTorch CUDA", "Installed CUDA-enabled PyTorch backend"),
        ], default="AUTO",
    )
    field_mode: EnumProperty(
        name="Field",
        items=[
            ("SCALAR", "Scalar prototype", "One complex order parameter"),
            ("SPINOR", "Spinor prototype", "Two-component reduced spinor field"),
        ], default="SCALAR",
    )
    grid_size: EnumProperty(
        name="Grid",
        items=[
            ("24", "24³ Preview", "Fast viewport preview"),
            ("32", "32³ Standard", "Recommended starting point"),
            ("48", "48³ Detailed", "Moderate cost"),
            ("64", "64³ High", "Heavy inside Blender"),
            ("96", "96³ Extreme", "Very heavy; CUDA recommended"),
            ("128", "128³ Research", "Potentially several GB during analysis"),
        ], default="32",
    )
    domain_length: FloatProperty(name="Domain length", default=16.0, min=1.0, max=512.0)
    dt: FloatProperty(name="dt", default=0.002, min=1e-7, max=0.1, precision=7)
    steps_per_action: IntProperty(name="Steps per action", default=10, min=1, max=100000)
    steps_per_frame: IntProperty(name="Steps per frame", default=5, min=1, max=10000)

    rho0: FloatProperty(name="Vacuum density ρ₀", default=1.0, min=1e-8)
    lambda_cohesion: FloatProperty(name="λ cohesion", default=1.0, min=0.0)
    kappa_stability: FloatProperty(name="κ stability", default=0.0019, min=-10.0, max=10.0, precision=7)
    alpha_dielectric: FloatProperty(name="α in Z(ρ)", default=1e-6, min=-1.0, max=1.0, precision=9)
    zeta_em: FloatProperty(name="ζEM", default=0.0015, min=-10.0, max=10.0, precision=7)
    damping: FloatProperty(name="Damping", default=0.02, min=0.0, max=10.0, precision=6)
    delta_anisotropy: FloatProperty(name="Δ anisotropy", default=0.0, min=-10.0, max=10.0, precision=6)

    # Topological/orientation sector
    topology_enabled: BoolProperty(name="Topology / Skyrme sector", default=True)
    spin_exchange: FloatProperty(name="Spin exchange", default=0.0, min=-10.0, max=10.0)
    skyrme_potential_scale: FloatProperty(name="Skyrme backreaction", default=0.0, min=-10.0, max=10.0, precision=7)
    external_b: FloatVectorProperty(name="External B proxy", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")

    # Thermal
    thermal_enabled: BoolProperty(name="Thermal module", default=True)
    heat_conduction: FloatProperty(name="Heat conduction", default=0.05, min=0.0, max=10.0)
    collision_heating: FloatProperty(name="Collision heating", default=0.01, min=0.0, max=10.0)
    critical_temperature: FloatProperty(name="Critical temperature", default=1.5, min=1e-6)
    temperature_cap: FloatProperty(name="Temperature cap", default=5.0, min=0.0)

    # HRM
    hrm_enabled: BoolProperty(name="HRM dual drive", default=False)
    drive_a1: FloatProperty(name="A₁", default=0.3)
    drive_a2: FloatProperty(name="A₂", default=0.3)
    drive_f1: FloatProperty(name="f₁", default=5.0, min=0.0)
    drive_f2: FloatProperty(name="f₂", default=6.2, min=0.0)
    drive_profile: EnumProperty(
        name="Drive profile",
        items=[
            ("UNIFORM", "Uniform", "Uniform phase drive"),
            ("GAUSSIAN", "Gaussian", "Localized central drive"),
            ("STANDING_X", "Standing X", "Standing-wave profile along X"),
            ("RADIAL", "Radial ring", "Ring-shaped drive profile"),
        ], default="UNIFORM",
    )
    drive_width: FloatProperty(name="Drive width/radius", default=2.0, min=0.01)

    # Gauge and gravity
    gauge_enabled: BoolProperty(name="Reduced U(1) gauge field", default=False)
    gauge_coupling: FloatProperty(name="Gauge coupling q", default=0.05, min=0.0, max=10.0)
    gauge_damping: FloatProperty(name="Gauge damping", default=0.10, min=0.0, max=10.0)
    gauge_wave_speed: FloatProperty(name="Gauge wave speed", default=1.0, min=0.001, max=100.0)
    gauge_backreaction: FloatProperty(name="Gauge backreaction", default=0.02, min=-10.0, max=10.0)
    gravity_enabled: BoolProperty(name="Weak-field gravity proxy", default=False)
    gravity_strength: FloatProperty(name="Effective G", default=1e-4, min=0.0, precision=9)
    gravity_backreaction: FloatProperty(name="Gravity backreaction", default=1.0, min=-100.0, max=100.0)

    # Noise/robustness
    noise_enabled: BoolProperty(name="Noise robustness test", default=False)
    noise_amplitude: FloatProperty(name="Noise amplitude", default=0.0, min=0.0, max=10.0, precision=7)
    noise_seed: IntProperty(name="Noise seed", default=12345, min=0)

    # QFG Dynamics runtime foundation
    dynamics_enabled: BoolProperty(
        name="QFG Dynamics bodies",
        description="Couple reduced dynamic bodies to the QFG field",
        default=False,
    )
    dynamics_substeps: IntProperty(name="Dynamics substeps", default=2, min=1, max=32)
    dynamics_gravity: FloatVectorProperty(
        name="World gravity", size=3, default=(0.0, 0.0, -0.35), subtype="ACCELERATION",
    )
    dynamics_floor_height: FloatProperty(name="Floor height", default=-3.75)
    dynamics_body_collisions: BoolProperty(name="Body collisions", default=True)
    dynamics_deterministic: BoolProperty(name="Deterministic replay", default=True)
    dynamics_seed: IntProperty(name="World seed", default=1337, min=0)
    dynamics_max_speed: FloatProperty(name="Maximum body speed", default=24.0, min=0.01)
    dynamics_max_angular_speed: FloatProperty(name="Maximum angular speed", default=80.0, min=0.01)
    dynamics_field_force_scale: FloatProperty(name="Global field force", default=1.0)
    dynamics_thermal_force_scale: FloatProperty(name="Global thermal force", default=1.0)
    dynamics_field_torque_scale: FloatProperty(name="Global field torque", default=1.0)
    dynamics_field_event_threshold: FloatProperty(name="Field event threshold", default=0.35, min=0.0)
    dynamics_contact_event_threshold: FloatProperty(name="Contact event threshold", default=1e-4, min=0.0, precision=7)
    dynamics_penetration_slop: FloatProperty(name="Penetration slop", default=1e-4, min=0.0, precision=7)
    dynamics_position_correction: FloatProperty(name="Position correction", default=0.82, min=0.0, max=1.0)
    last_field_ms: FloatProperty(name="Field step ms", default=0.0, precision=5)
    last_body_ms: FloatProperty(name="Body step ms", default=0.0, precision=5)
    last_query_ms: FloatProperty(name="Field query ms", default=0.0, precision=5)
    last_total_ms: FloatProperty(name="World total ms", default=0.0, precision=5)
    last_body_count: IntProperty(name="Dynamic bodies", default=0)
    last_contact_count: IntProperty(name="Contacts", default=0)
    last_event_count: IntProperty(name="Events", default=0)
    last_kinetic_energy: FloatProperty(name="Body kinetic energy", default=0.0, precision=7)
    last_linear_kinetic_energy: FloatProperty(name="Linear kinetic energy", default=0.0, precision=7)
    last_rotational_kinetic_energy: FloatProperty(name="Rotational kinetic energy", default=0.0, precision=7)
    last_mean_force: FloatProperty(name="Mean body force", default=0.0, precision=7)
    last_max_force: FloatProperty(name="Maximum body force", default=0.0, precision=7)
    last_mean_torque: FloatProperty(name="Mean body torque", default=0.0, precision=7)
    last_max_torque: FloatProperty(name="Maximum body torque", default=0.0, precision=7)
    last_body_momentum: FloatVectorProperty(name="Body momentum", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    last_body_angular_momentum: FloatVectorProperty(name="Body angular momentum", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    last_active_body_contacts: IntProperty(name="Active body contacts", default=0)
    last_active_floor_contacts: IntProperty(name="Active floor contacts", default=0)

    # Native cinematic showcase
    showcase_mode: EnumProperty(
        name="Showcase",
        items=[
            ("COLLISION", "Collision", "Field-coupled collision showcase"),
            ("HOPF", "Hopf", "Reduced spinor topology showcase"),
            ("VORTEX", "Vortex", "Spinor winding showcase"),
            ("HRM_CAVITY", "HRM cavity", "Dual-drive cavity showcase"),
            ("THERMAL", "Thermal", "Thermal feedback showcase"),
            ("GAUGE_GRAVITY", "Gauge + gravity", "Reduced coupled sectors showcase"),
            ("PLASMA_BOUNDARY", "Plasma boundary", "Driven boundary showcase"),
        ],
        default="COLLISION",
    )
    showcase_quality: EnumProperty(
        name="Quality",
        items=[
            ("PREVIEW", "Preview", "32³, 720p, faster bake"),
            ("FINAL", "Final", "64³, 1080p, heavier bake"),
        ],
        default="PREVIEW",
    )
    showcase_body_count: IntProperty(name="Hero bodies", default=48, min=4, max=256)
    showcase_still_frame: IntProperty(name="Hero still frame", default=56, min=1, max=10000)

    # Visualization and bake
    threshold_fraction: FloatProperty(name="Density threshold", default=0.25, min=0.001, max=1.0)
    max_points: IntProperty(name="Maximum points", default=12000, min=100, max=500000)
    point_radius: FloatProperty(name="Point radius", default=0.08, min=0.001, max=2.0)
    slice_axis: EnumProperty(name="Slice axis", items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")], default="Z")
    bake_start: IntProperty(name="Bake start", default=1, min=-100000, max=100000)
    bake_end: IntProperty(name="Bake end", default=120, min=-100000, max=100000)
    playback_outside_mode: EnumProperty(
        name="Outside baked range",
        items=[
            ("HOLD_LAST", "Hold nearest baked frame", "Keep the requested Blender frame but display the nearest cached state"),
            ("CLAMP", "Clamp timeline", "Move the Blender timeline to the nearest cached frame"),
            ("STATUS_ONLY", "Status only", "Do not change the displayed cached state; report that the frame is outside the cache"),
        ],
        default="HOLD_LAST",
    )
    output_directory: StringProperty(name="Output directory", subtype="DIR_PATH", default="//qfg_results")

    # Viewport debug / 6-DoF diagnostics overlay
    debug_overlay_enabled: BoolProperty(name="6-DoF debug overlay", default=True)
    debug_show_hud: BoolProperty(name="Diagnostics HUD", default=True)
    debug_show_contacts: BoolProperty(name="Contact points / normals / impulses", default=True)
    debug_show_forces: BoolProperty(name="Total force vectors", default=False)
    debug_show_torques: BoolProperty(name="Total torque vectors", default=False)
    debug_show_angular_velocity: BoolProperty(name="Angular velocity vectors", default=False)
    debug_force_scale: FloatProperty(name="Force scale", default=0.15, min=0.0, max=1000.0)
    debug_torque_scale: FloatProperty(name="Torque scale", default=0.25, min=0.0, max=1000.0)
    debug_angular_scale: FloatProperty(name="Angular velocity scale", default=0.10, min=0.0, max=1000.0)
    debug_contact_normal_scale: FloatProperty(name="Contact normal scale", default=0.50, min=0.0, max=1000.0)
    debug_impulse_scale: FloatProperty(name="Contact impulse scale", default=0.25, min=0.0, max=1000.0)
    debug_hud_font_size: IntProperty(name="HUD font size", default=13, min=8, max=40)

    # Runtime/read-only
    status: StringProperty(name="Status", default="Not initialized")
    backend_status: StringProperty(name="Backend status", default="Unknown")
    last_time: FloatProperty(name="Time", default=0.0, precision=7)
    last_max_density: FloatProperty(name="Max density", default=0.0, precision=7)
    last_norm: FloatProperty(name="Norm", default=0.0, precision=7)
    last_mode_variance: FloatProperty(name="Mode variance", default=0.0, precision=9)
    last_energy: FloatProperty(name="Energy proxy", default=0.0, precision=7)
    last_temperature: FloatProperty(name="Max temperature", default=0.0, precision=7)
    last_gauge_energy: FloatProperty(name="Gauge energy", default=0.0, precision=7)
    last_gravity_energy: FloatProperty(name="Gravity energy", default=0.0, precision=7)
    last_atlas_energy: FloatProperty(name="Atlas scalar energy", default=0.0, precision=7)
    last_momentum: FloatVectorProperty(name="Momentum", size=3, default=(0.0, 0.0, 0.0))
    hopf_proxy: FloatProperty(name="Hopf proxy", default=0.0, precision=9)
    skyrme_proxy: FloatProperty(name="Skyrme proxy", default=0.0, precision=9)
    orientation_variance: FloatProperty(name="Orientation variance", default=0.0, precision=9)

    # RF ROM
    rom_detuning_min: FloatProperty(name="Detuning min", default=-3.0)
    rom_detuning_max: FloatProperty(name="Detuning max", default=3.0)
    rom_points: IntProperty(name="Sweep points", default=241, min=21, max=4001)
    rom_drive: FloatProperty(name="Drive", default=0.5, min=0.0)
    rom_linear_loss: FloatProperty(name="Linear loss", default=0.15, min=0.0)
    rom_nonlinear_loss: FloatProperty(name="Nonlinear loss", default=0.02, min=0.0)
    rom_duffing: FloatProperty(name="Duffing K", default=0.8)
    rom_external_coupling: FloatProperty(name="External coupling", default=0.2, min=0.0)
    rom_dt: FloatProperty(name="ROM dt", default=0.002, min=1e-6, max=0.1, precision=7)
    rom_settle_steps: IntProperty(name="Settle steps", default=2500, min=10, max=200000)
    rom_second_tone_ratio: FloatProperty(name="Second-tone ratio", default=0.25, min=0.0)
    rom_second_tone_offset: FloatProperty(name="Tone offset", default=0.2)

    # HRM scan
    scan_f1_min: FloatProperty(name="f₁ min", default=4.0)
    scan_f1_max: FloatProperty(name="f₁ max", default=6.0)
    scan_f2_min: FloatProperty(name="f₂ min", default=4.0)
    scan_f2_max: FloatProperty(name="f₂ max", default=7.0)
    scan_points: IntProperty(name="Scan points/axis", default=9, min=3, max=31)
    scan_duration: FloatProperty(name="Run duration", default=1.2, min=0.05, max=100.0)
    scan_dt: FloatProperty(name="Scan dt", default=0.003, min=1e-5, max=0.1)
    scan_nx: IntProperty(name="1-D grid", default=96, min=32, max=1024)
    scan_best: StringProperty(name="Best HRM point", default="Not run")

    # Plasma/cavity/MEMS proxies
    plasma_boundary_factor: FloatProperty(name="Boundary factor", default=1.0, min=0.0, max=10.0)
    plasma_ionization: FloatProperty(name="Ionization gain", default=0.8, min=0.0)
    plasma_recombination: FloatProperty(name="Recombination", default=0.25, min=0.0)
    cavity_q_factor: FloatProperty(name="Cavity Q", default=1e5, min=1.0)
    cavity_power_max: FloatProperty(name="Power max", default=10.0, min=0.0)
    cavity_density_per_power: FloatProperty(name="ρ offset / power", default=0.01)
    cavity_thermal_coefficient: FloatProperty(name="Thermal coefficient", default=1e-4)
    mems_base_q: FloatProperty(name="MEMS base Q", default=1000.0, min=1.0)
    mems_geometry_scale: FloatProperty(name="Geometry-lock scale", default=0.05)

    # Yb module
    yb_duration: FloatProperty(name="Duration", default=20.0, min=0.01)
    yb_dt: FloatProperty(name="Yb dt", default=0.005, min=1e-6, max=1.0, precision=7)
    yb_rabi_frequency: FloatProperty(name="Rabi frequency", default=1.0, min=0.0)
    yb_detuning: FloatProperty(name="Detuning", default=0.0)
    yb_dephasing: FloatProperty(name="Dephasing", default=0.02, min=0.0)
    yb_relaxation: FloatProperty(name="Relaxation", default=0.01, min=0.0)
    yb_q_factor: FloatProperty(name="Yb cavity Q", default=1e4, min=1.0)
    yb_cavity_power: FloatProperty(name="Cavity power (relative)", default=1.0, min=0.0)
    yb_density_offset: FloatProperty(name="ρ−ρ₀", default=0.0)
    yb_correction_scale: FloatProperty(name="QFG correction scale", default=1.0)
    yb_texture_coupling: FloatProperty(name="Texture ξ", default=0.0)
    yb_texture_divergence: FloatProperty(name="∇·n proxy", default=0.0)
    yb_ac_stark_scale: FloatProperty(name="AC-Stark proxy", default=0.0)
    yb_ramsey_free_time: FloatProperty(name="Ramsey max free time", default=20.0, min=0.01)
    yb_odmr_min: FloatProperty(name="ODMR min", default=-5.0)
    yb_odmr_max: FloatProperty(name="ODMR max", default=5.0)
    yb_odmr_points: IntProperty(name="ODMR points", default=401, min=51, max=4001)

    # Atlas Direct / BSM-SG source geometry bridge
    atlas_element: EnumProperty(
        name="Group-15 holdout",
        items=[
            ("N", "N / NH₃", "Nitrogen holdout reference"),
            ("P", "P / PH₃", "Phosphorus holdout reference"),
            ("AS", "As / AsH₃", "Arsenic holdout reference"),
            ("SB", "Sb / SbH₃", "Antimony holdout reference"),
            ("CUSTOM", "Custom", "No built-in experimental reference"),
        ],
        default="N",
    )
    atlas_center_mode: EnumProperty(
        name="Nuclear center",
        items=[
            ("CORE_CENTROID", "Tagged core centroid", "Centroid of Atlas nucleons tagged CORE; extraction stops if no core is tagged"),
            ("CENTER_OBJECT", "Center object", "Use the selected center object origin"),
            ("WORLD_ORIGIN", "World origin", "Use (0,0,0)"),
        ],
        default="CORE_CENTROID",
    )
    atlas_center_object: PointerProperty(name="Center object", type=bpy.types.Object)
    atlas_tag_nucleon_type: EnumProperty(
        name="Tag nucleon",
        items=[
            ("PROTON", "Proton", "Proton source object"),
            ("NEUTRON", "Neutron", "Neutron source object"),
            ("DEUTERON", "Deuteron", "Proton + neutron structural unit"),
            ("TRITIUM", "Tritium", "Proton + two-neutron structural unit"),
            ("HELIUM", "Helium", "Helium structural unit"),
            ("OTHER", "Other", "Other source structure"),
        ],
        default="DEUTERON",
    )
    atlas_vector_scale: FloatProperty(name="Vector display scale", default=2.0, min=0.01, max=1000.0)
    atlas_status: StringProperty(name="Atlas status", default="No Atlas geometry extracted")
    atlas_mean_angle: FloatProperty(name="Mean valence angle", default=0.0, precision=6)
    atlas_angle_spread: FloatProperty(name="Angle spread σ", default=0.0, precision=6)
    atlas_min_angle: FloatProperty(name="Min angle", default=0.0, precision=6)
    atlas_max_angle: FloatProperty(name="Max angle", default=0.0, precision=6)
    atlas_height_ratio: FloatProperty(name="C3v h/r", default=0.0, precision=7)
    atlas_frozen: BoolProperty(name="Blind prediction frozen", default=False)
    atlas_frozen_angle: FloatProperty(name="Frozen angle", default=0.0, precision=6)
    atlas_frozen_spread: FloatProperty(name="Frozen σ", default=0.0, precision=6)
    atlas_frozen_element: StringProperty(name="Frozen element", default="")
    atlas_reference_revealed: BoolProperty(name="Reference revealed", default=False)
    atlas_reference_angle: FloatProperty(name="Reference angle", default=0.0, precision=6)
    atlas_residual_angle: FloatProperty(name="Residual", default=0.0, precision=6)
    atlas_residual_percent: FloatProperty(name="Residual %", default=0.0, precision=5)

    # B2 Atlas interaction graph / orbital planes / integrated envelope
    atlas_graph_topology: EnumProperty(
        name="Interaction topology",
        items=[
            ("SOURCE_STAR", "Source star", "Connect tagged VALENCE to tagged EQUATORIAL objects only"),
            ("VALENCE_ONLY", "Valence pairs", "Diagnostic pair graph between tagged valence objects"),
            ("ALL_TAGGED", "All tagged", "Diagnostic complete graph of all Atlas objects"),
        ],
        default="SOURCE_STAR",
    )
    atlas_graph_kernel: EnumProperty(
        name="J proxy kernel",
        items=[
            ("TOPOLOGY_ONLY", "Topology only", "Unit edge weight; DERIVED connectivity only"),
            ("ABS_COSINE", "|cos χ|", "Conditional orbital/direction overlap proxy"),
            ("COSINE_SQUARED", "cos² χ", "Conditional spin-even overlap proxy"),
            ("INVERSE_CUBE", "1/r³", "Conditional inverse-cube SG-like geometry proxy; scene-unit dependent"),
            ("COSINE_SQUARED_INV_R3", "cos² χ / r³", "Conditional overlap × inverse-cube proxy"),
        ],
        default="TOPOLOGY_ONLY",
    )
    atlas_graph_softening: FloatProperty(name="Graph softening", default=0.0, min=0.0, precision=6)
    atlas_graph_status: StringProperty(name="Interaction graph status", default="No B2 graph built")
    atlas_graph_edge_count: IntProperty(name="Graph edges", default=0, min=0)
    atlas_graph_total_proxy: FloatProperty(name="Σ J proxy", default=0.0, precision=7)
    atlas_graph_mean_proxy: FloatProperty(name="Mean |J proxy|", default=0.0, precision=7)

    atlas_plane_scale: FloatProperty(name="Orbital-plane display radius", default=1.25, min=0.01, max=1000.0)
    atlas_plane_status: StringProperty(name="Orbital plane status", default="No orbital planes extracted")
    atlas_plane_mean_dihedral: FloatProperty(name="Mean plane dihedral", default=0.0, precision=6)
    atlas_plane_spread: FloatProperty(name="Plane dihedral σ", default=0.0, precision=6)

    atlas_bohr_radius_mode: EnumProperty(
        name="Envelope source radius",
        items=[
            ("OBJECT_BOUNDS", "Object bounds", "Use half of the largest world-space object dimension"),
            ("FIXED", "Fixed radius", "Use one scene-unit radius for every tagged Atlas object"),
            ("POINTS_ONLY", "Centers only", "Ignore object radii and envelope object origins only"),
        ],
        default="OBJECT_BOUNDS",
    )
    atlas_bohr_fixed_radius: FloatProperty(name="Fixed source radius", default=0.25, min=0.0, precision=5)
    atlas_bohr_padding: FloatProperty(name="Envelope padding", default=1.05, min=0.01, max=100.0, precision=5)
    atlas_bohr_status: StringProperty(name="Bohr envelope status", default="No integrated envelope built")
    atlas_bohr_volume: FloatProperty(name="Envelope volume", default=0.0, min=0.0, precision=7)
    atlas_bohr_sphere_radius: FloatProperty(name="Bounding radius", default=0.0, min=0.0, precision=7)

    # B3 Atlas -> QFG field bridge
    atlas_field_enabled: BoolProperty(
        name="Atlas field bridge",
        description="Allow tagged Atlas structures to populate the reduced QFG field; CONDITIONAL bridge",
        default=False,
    )
    atlas_field_auto_apply: BoolProperty(
        name="Apply on engine initialize",
        description="Rebuild and install the Atlas field whenever the QFG engine is initialized/reset",
        default=True,
    )
    atlas_field_live_update: BoolProperty(
        name="Refresh before manual steps",
        description="Re-rasterize B3 from current Atlas object transforms before each Run QFG Steps action; expensive on large grids",
        default=False,
    )
    atlas_field_source_scope: EnumProperty(
        name="Field source scope",
        items=[
            ("SOURCE_ONLY", "SOURCE only", "Use only explicit SOURCE-tagged Atlas objects"),
            ("SOURCE_DERIVED", "SOURCE + DERIVED", "Allow reviewed DERIVED auto-tags; excludes CONDITIONAL/CALIBRATED/EXPERIMENTAL/REJECTED"),
            ("ALL_NON_REJECTED", "All non-rejected", "Diagnostic mode; use every enabled Atlas object except REJECTED"),
        ],
        default="SOURCE_ONLY",
    )
    atlas_field_role_scope: EnumProperty(
        name="Field roles",
        items=[
            ("VALENCE_EQ", "Valence + equatorial", "Use VALENCE and EQUATORIAL Atlas sources"),
            ("VALENCE", "Valence only", "Use only VALENCE Atlas sources"),
            ("ALL", "All Atlas roles", "Use all tagged Atlas structures"),
        ],
        default="VALENCE_EQ",
    )
    atlas_field_kernel: EnumProperty(
        name="Field kernel",
        items=[
            ("GAUSSIAN", "Gaussian", "Localized finite source; numerically robust"),
            ("SOFT_INV_R3", "Soft 1/r³ proxy", "Conditional softened inverse-cube source; scene-unit dependent"),
        ],
        default="GAUSSIAN",
    )
    atlas_field_vector_mode: EnumProperty(
        name="Vector field",
        items=[
            ("DIRECTOR", "Director", "Local field follows the Atlas source direction"),
            ("DIPOLE_PROXY", "Dipole proxy", "Use 3(d·r^)r^-d orientation pattern"),
        ],
        default="DIRECTOR",
    )
    atlas_field_softening: FloatProperty(name="Field softening", default=0.25, min=0.0, precision=6)
    atlas_field_scalar_scale: FloatProperty(name="Scalar potential scale", default=0.25, min=-100.0, max=100.0, precision=6)
    atlas_field_vector_scale: FloatProperty(name="Vector/spin scale", default=0.0, min=-100.0, max=100.0, precision=6)
    atlas_field_orbital_mix: FloatProperty(
        name="Orbital-normal mix",
        description="0 = valence/director tensor only, 1 = orbital-plane-normal tensor only",
        default=0.5, min=0.0, max=1.0, precision=4,
    )
    atlas_field_scene_scale: FloatProperty(
        name="Atlas -> QFG length scale", default=1.0, min=1e-6, max=1e6, precision=6,
    )
    atlas_field_clip_abs: FloatProperty(name="Field safety clip", default=100.0, min=1e-6, max=1e9, precision=5)
    atlas_field_status: StringProperty(name="Atlas field status", default="No B3 field built")
    atlas_field_source_count: IntProperty(name="B3 field sources", default=0, min=0)
    atlas_field_scalar_min: FloatProperty(name="Atlas V min", default=0.0, precision=7)
    atlas_field_scalar_max: FloatProperty(name="Atlas V max", default=0.0, precision=7)
    atlas_field_scalar_rms: FloatProperty(name="Atlas V RMS", default=0.0, precision=7)
    atlas_field_vector_max: FloatProperty(name="Atlas |B| max", default=0.0, precision=7)
    atlas_field_vector_rms: FloatProperty(name="Atlas |B| RMS", default=0.0, precision=7)


    # B4 QFG -> Atlas bidirectional feedback / bounded relaxation
    atlas_feedback_enabled: BoolProperty(
        name="B4 bidirectional feedback",
        description="Allow the live QFG field to move/rotate tagged Atlas sources through a bounded CONDITIONAL relaxation bridge",
        default=False,
    )
    atlas_feedback_auto_capture: BoolProperty(
        name="Auto-capture anchors",
        description="Capture current Atlas positions/orientations as B4 anchors when feedback first runs",
        default=True,
    )
    atlas_feedback_rerasterize: BoolProperty(
        name="Rebuild B3 after feedback",
        description="Re-rasterize the Atlas->QFG field after B4 moves the source geometry",
        default=True,
    )
    atlas_feedback_target_mode: EnumProperty(
        name="Torque target",
        items=[
            ("DENSITY_GRADIENT", "Density gradient", "Align Atlas frames to the local QFG density-gradient direction"),
            ("SPIN_TEXTURE", "Spin texture", "Use local QFG spin texture when available; fall back to density gradient"),
            ("HYBRID", "Hybrid", "Normalized blend of density-gradient and spin-texture directions"),
        ],
        default="DENSITY_GRADIENT",
    )
    atlas_feedback_force_scale: FloatProperty(
        name="B4 force scale", default=0.25, min=-1000.0, max=1000.0, precision=6,
        description="Dimensionless force-proxy normalization; CONDITIONAL",
    )
    atlas_feedback_torque_scale: FloatProperty(
        name="B4 torque scale", default=0.25, min=-1000.0, max=1000.0, precision=6,
        description="Dimensionless alignment-torque normalization; CONDITIONAL",
    )
    atlas_feedback_anchor_strength: FloatProperty(
        name="Position anchor", default=0.10, min=0.0, max=1000.0, precision=6,
        description="Restoring strength toward the captured Atlas anchor position; numerical stabilizer",
    )
    atlas_feedback_orientation_anchor: FloatProperty(
        name="Orientation anchor", default=0.05, min=0.0, max=1000.0, precision=6,
        description="Restoring alignment toward the captured Atlas source frame; numerical stabilizer",
    )
    atlas_feedback_orbital_mix: FloatProperty(
        name="Torque orbital mix", default=0.5, min=0.0, max=1.0, precision=4,
        description="0 = valence direction torque only, 1 = orbital-normal torque only",
    )
    atlas_feedback_spin_mix: FloatProperty(
        name="Hybrid spin mix", default=0.5, min=0.0, max=1.0, precision=4,
        description="In HYBRID mode, weight of the spin-texture direction",
    )
    atlas_feedback_max_step: FloatProperty(
        name="Max translation / cycle", default=0.02, min=0.0, max=1000.0, precision=6,
        description="Scene-space safety clamp for one B4 feedback update",
    )
    atlas_feedback_max_angle: FloatProperty(
        name="Max rotation / cycle", default=1.0, min=0.0, max=180.0, precision=5,
        description="Maximum axis-angle rotation in degrees per B4 update",
    )
    atlas_feedback_max_displacement: FloatProperty(
        name="Max anchor displacement", default=0.5, min=0.0, max=10000.0, precision=6,
        description="Maximum scene-space distance from the captured anchor; 0 disables the radius limit",
    )
    atlas_feedback_status: StringProperty(name="B4 feedback status", default="No B4 feedback evaluated")
    atlas_feedback_source_count: IntProperty(name="B4 feedback sources", default=0, min=0)
    atlas_feedback_moved_count: IntProperty(name="B4 moved sources", default=0, min=0)
    atlas_feedback_rotated_count: IntProperty(name="B4 rotated sources", default=0, min=0)
    atlas_feedback_clipped_count: IntProperty(name="B4 clipped updates", default=0, min=0)
    atlas_feedback_mean_force: FloatProperty(name="B4 mean |F|", default=0.0, precision=7)
    atlas_feedback_max_force: FloatProperty(name="B4 max |F|", default=0.0, precision=7)
    atlas_feedback_mean_torque: FloatProperty(name="B4 mean |τ|", default=0.0, precision=7)
    atlas_feedback_max_torque: FloatProperty(name="B4 max |τ|", default=0.0, precision=7)
    atlas_feedback_force_work: FloatProperty(name="B4 force work proxy", default=0.0, precision=7)
    atlas_feedback_torque_work: FloatProperty(name="B4 torque work proxy", default=0.0, precision=7)
    atlas_feedback_total_work: FloatProperty(name="B4 total work proxy", default=0.0, precision=7)
    atlas_feedback_max_anchor_displacement: FloatProperty(name="B4 max anchor displacement", default=0.0, min=0.0, precision=7)

    # B5 constraint-aware molecular / Atlas relaxation
    atlas_constraints_enabled: BoolProperty(
        name="B5 geometry constraints",
        description="Project B4 proposals back into captured BSM-SG/Atlas topology and angular admissibility constraints",
        default=False,
    )
    atlas_constraints_auto_capture: BoolProperty(
        name="Auto-capture B5 constraints",
        description="Capture the current reviewed Atlas topology the first time B5 is required",
        default=True,
    )
    atlas_constraints_pair_mode: EnumProperty(
        name="Connectivity capture",
        items=[
            ("MANUAL_NEIGHBORS", "Manual neighbours", "Use comma-separated neighbour names on Atlas objects; intended for reviewed/source connectivity"),
            ("PARENT_CHILD", "Parent-child", "Capture Atlas parent/child relations as DERIVED distance constraints"),
            ("SOURCE_STAR", "B2 source star", "Use VALENCE↔EQUATORIAL source-star edges; DERIVED/conditional structural bridge"),
            ("NONE", "No pair distances", "Use only shell, cone and symmetry constraints"),
        ],
        default="MANUAL_NEIGHBORS",
    )
    atlas_constraints_distance_stiffness: FloatProperty(
        name="Pair-distance stiffness", default=1.0, min=0.0, max=10.0, precision=5,
        description="Conditional iterative projection strength for captured pair distances",
    )
    atlas_constraints_shell_stiffness: FloatProperty(
        name="Shell stiffness", default=1.0, min=0.0, max=10.0, precision=5,
        description="Conditional projection strength for captured radial shell distance",
    )
    atlas_constraints_cone_stiffness: FloatProperty(
        name="Angular-cone stiffness", default=1.0, min=0.0, max=10.0, precision=5,
        description="Projection strength when a valence nucleon exceeds its declared angular freedom cone",
    )
    atlas_constraints_symmetry_stiffness: FloatProperty(
        name="Symmetry stiffness", default=0.75, min=0.0, max=10.0, precision=5,
        description="Preserve captured group azimuth pattern while allowing collective polar tilt to relax",
    )
    atlas_constraints_shell_tolerance: FloatProperty(
        name="Shell tolerance", default=0.0, min=0.0, max=1000.0, precision=6,
        description="Allowed radial deviation in scene units before B5 shell projection acts",
    )
    atlas_constraints_iterations: IntProperty(name="B5 projection iterations", default=8, min=1, max=200)
    atlas_constraints_tolerance: FloatProperty(
        name="B5 convergence tolerance", default=1e-6, min=0.0, max=1.0, precision=8,
    )
    atlas_constraints_max_correction: FloatProperty(
        name="Max B5 correction / iter", default=0.025, min=0.0, max=1000.0, precision=6,
        description="Safety clamp on each constraint correction; 0 disables this clamp",
    )
    atlas_constraints_preserve_centroid: BoolProperty(
        name="Preserve movable centroid", default=False,
        description="Remove net translation introduced by constraint projection; useful for isolated symmetric groups",
    )
    atlas_constraints_status: StringProperty(name="B5 constraint status", default="No B5 constraints captured")
    atlas_constraints_node_count: IntProperty(name="B5 nodes", default=0, min=0)
    atlas_constraints_pair_count: IntProperty(name="B5 pair constraints", default=0, min=0)
    atlas_constraints_group_count: IntProperty(name="B5 symmetry groups", default=0, min=0)
    atlas_constraints_iterations_used: IntProperty(name="B5 iterations used", default=0, min=0)
    atlas_constraints_max_pair_error: FloatProperty(name="B5 max pair error", default=0.0, min=0.0, precision=7)
    atlas_constraints_max_shell_error: FloatProperty(name="B5 max shell error", default=0.0, min=0.0, precision=7)
    atlas_constraints_max_cone_excess: FloatProperty(name="B5 max cone excess", default=0.0, min=0.0, precision=7)
    atlas_constraints_max_correction_used: FloatProperty(name="B5 max correction", default=0.0, min=0.0, precision=7)
    atlas_constraints_pair_angle_before: FloatProperty(name="B5 symmetry angle before", default=0.0, precision=6)
    atlas_constraints_pair_angle_after: FloatProperty(name="B5 symmetry angle after", default=0.0, precision=6)

    # B6 blind end-to-end relaxation harness.  These are numerical protocol
    # controls, not physical constants.  The convergence detector never reads
    # the experimental holdout registry.
    atlas_blind_auto_initialize: BoolProperty(
        name="Auto-initialize QFG", default=True,
        description="Reinitialize the QFG engine at the start of a B6 blind run after source geometry/constraints are prepared",
    )
    atlas_blind_reset_to_anchors: BoolProperty(
        name="Reset to B4 anchors", default=True,
        description="Restore the captured source geometry before beginning the blind relaxation",
    )
    atlas_blind_recapture_constraints: BoolProperty(
        name="Recapture B5 constraints", default=True,
        description="Capture the current reviewed B5 admissible geometry before the blind run",
    )
    atlas_blind_steps_per_iteration: IntProperty(name="QFG steps / B6 iteration", default=1, min=1, max=10000)
    atlas_blind_max_iterations: IntProperty(name="B6 max iterations", default=160, min=1, max=100000)
    atlas_blind_min_iterations: IntProperty(name="B6 min iterations", default=12, min=1, max=100000)
    atlas_blind_window: IntProperty(name="Convergence window", default=8, min=2, max=10000)
    atlas_blind_angle_tolerance: FloatProperty(
        name="Angle window tolerance", default=0.02, min=0.0, max=180.0, precision=6,
        description="Maximum recent peak-to-peak mean valence-angle variation required for convergence",
    )
    atlas_blind_slope_tolerance: FloatProperty(
        name="Angle drift tolerance / iter", default=0.003, min=0.0, max=180.0, precision=7,
        description="Maximum absolute recent linear drift of the predicted angle",
    )
    atlas_blind_spread_tolerance: FloatProperty(
        name="C3 spread tolerance", default=0.02, min=0.0, max=180.0, precision=6,
        description="Maximum pair-angle standard deviation permitted in the convergence window",
    )
    atlas_blind_correction_tolerance: FloatProperty(
        name="B5 correction tolerance", default=0.0, min=0.0, max=1000.0, precision=7,
        description="Optional maximum B5 correction in the convergence window; 0 disables this gate",
    )
    atlas_blind_freeze_on_convergence: BoolProperty(
        name="Freeze prediction on convergence", default=True,
        description="Automatically freeze the final B6 prediction while keeping the experimental reference hidden",
    )
    atlas_blind_status: StringProperty(name="B6 blind-run status", default="No B6 blind run")
    atlas_blind_running: BoolProperty(name="B6 running", default=False)
    atlas_blind_converged: BoolProperty(name="B6 converged", default=False)
    atlas_blind_iterations_used: IntProperty(name="B6 iterations used", default=0, min=0)
    atlas_blind_final_angle: FloatProperty(name="B6 final angle", default=0.0, precision=6)
    atlas_blind_final_spread: FloatProperty(name="B6 final spread", default=0.0, min=0.0, precision=6)
    atlas_blind_window_range: FloatProperty(name="B6 angle window range", default=0.0, min=0.0, precision=7)
    atlas_blind_window_slope: FloatProperty(name="B6 angle slope", default=0.0, precision=8)
    atlas_blind_protocol_hash: StringProperty(name="B6 protocol hash", default="")

    # Molecular bridge
    mol_coulomb_scale: FloatProperty(name="Coulomb proxy", default=0.05, min=0.0)
    mol_overlap_scale: FloatProperty(name="Coherence overlap", default=0.2, min=0.0)
    mol_gradient_scale: FloatProperty(name="β gradient proxy", default=0.05, min=0.0)
    mol_kinetic_scale: FloatProperty(name="γ kinetic proxy", default=0.05, min=0.0)
    mol_topology_scale: FloatProperty(name="η topology proxy", default=0.05, min=0.0)
    mol_softening: FloatProperty(name="Softening", default=0.15, min=1e-6)
    mol_bond_tolerance: FloatProperty(name="Bond tolerance", default=1.25, min=0.1, max=5.0)
    mol_bond_stiffness: FloatProperty(name="Bond stiffness", default=0.4, min=0.0)
    mol_target_energy: FloatProperty(name="Target energy", default=0.0)
    mol_target_band_gap: FloatProperty(name="Target band gap (eV)", default=2.0, min=0.0)
    mol_target_wavelength: FloatProperty(name="Target λmax (nm)", default=550.0, min=1.0)
    mol_target_oscillator: FloatProperty(name="Target oscillator", default=1.0, min=0.0)
    mol_opt_iterations: IntProperty(name="Optimizer iterations", default=120, min=1, max=10000)
    mol_opt_step: FloatProperty(name="Optimizer step", default=0.15, min=1e-5, max=10.0)
    molecular_status: StringProperty(name="Molecular result", default="No evaluation")


class QFGObjectProperties(bpy.types.PropertyGroup):
    enabled: BoolProperty(name="QFG actor", default=False)
    actor_type: EnumProperty(
        name="Actor type",
        items=[
            ("GAUSSIAN", "Gaussian node", "Localized complex field node"),
            ("HOPF_RING", "Hopf ring ansatz", "Ring-like spinor/topological ansatz"),
            ("VORTEX", "Vortex node", "Phase-winding vortex ansatz"),
            ("PLANE_WAVE", "Plane wave", "Uniform complex wave"),
            ("BOUNDARY", "Boundary", "Static potential/damping region"),
            ("MOLECULE_ATOM", "Molecular atom", "Atom for Molecular Creator"),
            ("ATLAS_NUCLEON", "Atlas nucleon", "BSM-SG/Atlas geometry source object"),
            ("YB_PROBE", "Yb probe", "Scene marker for Yb module"),
            ("DETECTOR", "Detector marker", "Measurement point/region marker"),
            ("DYNAMIC_BODY", "QFG dynamic body", "Reduced field-coupled body for QFG Dynamics"),
        ], default="GAUSSIAN",
    )
    velocity: FloatVectorProperty(name="Phase kick / wave vector", size=3, default=(0.0, 0.0, 0.0), subtype="VELOCITY")
    radius: FloatProperty(name="Field radius", default=1.0, min=0.01)
    intensity: FloatProperty(name="Intensity", default=1.0, min=0.0)
    spin_theta: FloatProperty(name="Spin θ", default=0.0, subtype="ANGLE")
    spin_phi: FloatProperty(name="Spin φ", default=0.0, subtype="ANGLE")
    winding_m: IntProperty(name="Winding m", default=1, min=-32, max=32)
    winding_n: IntProperty(name="Winding n", default=1, min=-32, max=32)
    ring_radius: FloatProperty(name="Ring radius", default=2.0, min=0.01)
    boundary_shape: EnumProperty(name="Boundary shape", items=[("SPHERE", "Sphere", ""), ("BOX", "Box", "")], default="SPHERE")
    boundary_potential: FloatProperty(name="Boundary potential", default=0.0)
    boundary_damping: FloatProperty(name="Boundary damping", default=0.0, min=0.0)
    atomic_number: IntProperty(name="Atomic number", default=6, min=1, max=118)
    atomic_charge: FloatProperty(name="Charge", default=0.0)
    covalent_radius: FloatProperty(name="Covalent radius", default=0.7, min=0.05, max=5.0)
    atlas_nucleon_type: EnumProperty(
        name="Nucleon type",
        items=[
            ("PROTON", "Proton", "Proton"),
            ("NEUTRON", "Neutron", "Neutron"),
            ("DEUTERON", "Deuteron", "Proton + neutron structural unit"),
            ("TRITIUM", "Tritium", "Proton + two-neutron structural unit"),
            ("HELIUM", "Helium", "Helium structural unit"),
            ("OTHER", "Other", "Other source structure"),
        ],
        default="DEUTERON",
    )
    atlas_role: EnumProperty(
        name="Atlas role",
        items=[
            ("CORE", "Core", "Contributes to nuclear-center estimate"),
            ("VALENCE", "Free valence", "Free valence direction used by Atlas Direct"),
            ("BOUND", "Bound", "Bound/excluded from principal valence"),
            ("EQUATORIAL", "Equatorial", "Equatorial source structure"),
            ("OTHER", "Other", "Other Atlas role"),
        ],
        default="OTHER",
    )
    atlas_direction_mode: EnumProperty(
        name="Valence direction",
        items=[
            ("RADIAL", "Center → object", "Use vector from nuclear center to object origin"),
            ("LOCAL_X", "+Local X", "Use object local +X axis"),
            ("LOCAL_Y", "+Local Y", "Use object local +Y axis"),
            ("LOCAL_Z", "+Local Z", "Use object local +Z axis"),
            ("NEG_X", "−Local X", "Use object local -X axis"),
            ("NEG_Y", "−Local Y", "Use object local -Y axis"),
            ("NEG_Z", "−Local Z", "Use object local -Z axis"),
        ],
        default="RADIAL",
    )
    atlas_provenance: EnumProperty(
        name="Provenance",
        items=[
            ("SOURCE", "SOURCE", "Explicit BSM-SG/Atlas source geometry"),
            ("DERIVED", "DERIVED", "Deterministic result from source geometry"),
            ("CONDITIONAL", "CONDITIONAL", "Model-dependent bridge"),
            ("CALIBRATED", "CALIBRATED", "Uses a reference/measurement"),
            ("EXPERIMENTAL", "EXPERIMENTAL", "External measurement/reference"),
            ("REJECTED", "REJECTED", "Audit-only rejected assumption"),
        ],
        default="SOURCE",
    )
    atlas_source_note: StringProperty(name="Source note", default="BSM-SG Atlas")
    atlas_inference_confidence: FloatProperty(name="Auto-tag confidence", default=0.0, min=0.0, max=1.0, precision=3)
    atlas_inference_note: StringProperty(name="Auto-tag evidence", default="")
    atlas_field_enabled: BoolProperty(
        name="B3 field source",
        description="Include this Atlas object in the conditional Atlas-to-QFG field bridge",
        default=True,
    )
    atlas_field_strength: FloatProperty(
        name="B3 source strength",
        description="Dimensionless conditional source weight; not an absolute BSM-SG energy",
        default=1.0, min=-100.0, max=100.0, precision=6,
    )
    atlas_field_radius: FloatProperty(
        name="B3 source radius",
        description="Source kernel radius in Blender scene units before Atlas->QFG scaling",
        default=0.5, min=1e-6, max=1e6, precision=6,
    )
    atlas_field_anisotropy: FloatProperty(
        name="B3 anisotropy",
        description="Dimensionless director/orbital anisotropy amplitude; CONDITIONAL",
        default=0.5, min=0.0, max=1.0, precision=5,
    )
    atlas_orbital_normal_mode: EnumProperty(
        name="Orbital plane normal",
        items=[
            ("LOCAL_X", "+Local X", "Use object local +X as the plane normal"),
            ("LOCAL_Y", "+Local Y", "Use object local +Y as the plane normal"),
            ("LOCAL_Z", "+Local Z", "Use object local +Z as the plane normal"),
            ("NEG_X", "−Local X", "Use object local -X as the plane normal"),
            ("NEG_Y", "−Local Y", "Use object local -Y as the plane normal"),
            ("NEG_Z", "−Local Z", "Use object local -Z as the plane normal"),
            ("VALENCE_VECTOR", "Valence vector (conditional)", "Use Atlas valence direction as plane normal; convenience bridge, not SOURCE"),
        ],
        default="LOCAL_Z",
    )

    atlas_feedback_enabled: BoolProperty(
        name="B4 feedback source",
        description="Allow this Atlas object to receive conditional QFG force/torque feedback",
        default=True,
    )
    atlas_feedback_force_coupling: FloatProperty(
        name="B4 force coupling", default=1.0, min=-1000.0, max=1000.0, precision=6,
    )
    atlas_feedback_torque_coupling: FloatProperty(
        name="B4 torque coupling", default=1.0, min=-1000.0, max=1000.0, precision=6,
    )
    atlas_feedback_linear_mobility: FloatProperty(
        name="B4 linear mobility", default=1.0, min=0.0, max=1000.0, precision=6,
    )
    atlas_feedback_angular_mobility: FloatProperty(
        name="B4 angular mobility", default=1.0, min=0.0, max=1000.0, precision=6,
    )
    atlas_feedback_lock_position: BoolProperty(name="Lock B4 position", default=False)
    atlas_feedback_lock_rotation: BoolProperty(name="Lock B4 rotation", default=False)

    # B5 per-object admissibility declarations.  These are geometry constraints,
    # not absolute force/energy parameters.
    atlas_constraint_enabled: BoolProperty(
        name="B5 constrained", default=True,
        description="Include this Atlas object in the B5 constraint snapshot/projection",
    )
    atlas_constraint_fixed: BoolProperty(
        name="B5 fixed node", default=False,
        description="Keep this node fixed while allowing connected constrained nodes to move",
    )
    atlas_constraint_preserve_radius: BoolProperty(
        name="Preserve shell radius", default=True,
        description="Preserve the captured distance from the Atlas nuclear centre, within the scene B5 tolerance",
    )
    atlas_constraint_max_cone_deg: FloatProperty(
        name="Angular freedom cone", default=0.0, min=0.0, max=180.0, precision=5,
        description="Maximum angular departure in degrees from the captured radial direction; 0 disables the cone",
    )
    atlas_constraint_neighbors: StringProperty(
        name="B5 neighbours", default="",
        description="Comma-separated Atlas object names for explicit/manual captured connectivity",
    )
    atlas_constraint_symmetry_group: StringProperty(
        name="B5 symmetry group", default="",
        description="Objects sharing a group preserve captured azimuth pattern but may change collective polar tilt",
    )

    body_mass: FloatProperty(name="Body mass", default=1.0, min=1e-6)
    collision_shape: EnumProperty(
        name="Collision shape",
        items=[
            ("SPHERE", "Sphere", "Spherical rigid-body collision shape"),
            ("BOX", "Box (OBB)", "Oriented box rigid-body collision shape"),
        ],
        default="SPHERE",
    )
    collision_radius: FloatProperty(name="Collision radius", default=0.25, min=0.001)
    collision_half_extents: FloatVectorProperty(
        name="Box half extents", size=3, default=(0.25, 0.25, 0.25), min=0.001, subtype="XYZ",
    )
    angular_velocity: FloatVectorProperty(
        name="Angular velocity", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ",
    )
    field_coupling: FloatProperty(name="Field coupling", default=1.0)
    thermal_coupling: FloatProperty(name="Thermal coupling", default=0.0)
    field_torque_coupling: FloatProperty(name="Field torque coupling", default=0.0)
    external_torque: FloatVectorProperty(name="External torque", size=3, default=(0.0, 0.0, 0.0), subtype="XYZ")
    linear_drag: FloatProperty(name="Linear drag", default=0.08, min=0.0)
    angular_drag: FloatProperty(name="Angular drag", default=0.08, min=0.0)
    restitution: FloatProperty(name="Restitution", default=0.35, min=0.0, max=1.0)
    friction: FloatProperty(name="Friction", default=0.25, min=0.0, max=1.0)
    kinematic_body: BoolProperty(name="Kinematic", default=False)
    phase_transition_temperature: FloatProperty(name="Softening temperature", default=1.5, min=0.0)


CLASSES = (QFGSceneProperties, QFGObjectProperties)


def register_properties() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.qfg_settings = PointerProperty(type=QFGSceneProperties)
    bpy.types.Object.qfg_actor = PointerProperty(type=QFGObjectProperties)


def unregister_properties() -> None:
    if hasattr(bpy.types.Scene, "qfg_settings"):
        del bpy.types.Scene.qfg_settings
    if hasattr(bpy.types.Object, "qfg_actor"):
        del bpy.types.Object.qfg_actor
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
