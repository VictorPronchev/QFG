"""User interface panels for QFG Lab 5.2."""
from __future__ import annotations

import bpy


class QFG_PT_Main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "QFG Dynamics 1.0.0 Alpha"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        box = layout.box()
        box.label(text="Field-driven multi-physics runtime", icon="EXPERIMENTAL")
        box.label(text=s.status)
        row = layout.row(align=True)
        row.operator("qfg.initialize", icon="PLAY")
        row.operator("qfg.step", icon="FRAME_NEXT")
        row = layout.row(align=True)
        row.operator("qfg.reset", icon="FILE_REFRESH")
        row.operator("qfg.clear_results", icon="TRASH")
        layout.operator("qfg.run_validation_suite", icon="MOD_PHYSICS")


class QFG_PT_Presets(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Starting Scenes"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Native Hero Showcase", icon="RENDER_STILL")
        box.prop(context.scene.qfg_settings, "showcase_mode")
        box.prop(context.scene.qfg_settings, "showcase_quality")
        if context.scene.qfg_settings.showcase_mode == "COLLISION":
            box.prop(context.scene.qfg_settings, "showcase_body_count")
        row = box.row(align=True)
        op = row.operator("qfg.create_hero_showcase", text="Build", icon="OUTLINER_COLLECTION")
        op.bake_after_build = False
        op.render_after_bake = False
        op = row.operator("qfg.create_hero_showcase", text="Build + Bake", icon="MOD_PHYSICS")
        op.bake_after_build = True
        op.render_after_bake = False
        row = box.row(align=True)
        row.prop(context.scene.qfg_settings, "showcase_still_frame")
        row.operator("qfg.render_hero_still", text="Render Still", icon="RENDER_STILL")
        layout.separator()
        for preset, label in (
            ("COLLISION", "Two-node collision"),
            ("HOPF", "Hopf-ring prototype"),
            ("VORTEX", "Vortex prototype"),
            ("HRM_CAVITY", "HRM cavity"),
            ("THERMAL", "Thermal collision"),
            ("GAUGE_GRAVITY", "Gauge + gravity"),
            ("PLASMA_BOUNDARY", "Plasma boundary"),
        ):
            op = layout.operator("qfg.create_preset", text=label)
            op.preset = preset



class QFG_PT_Core(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Numerical Core"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "backend")
        row = layout.row(align=True)
        row.operator("qfg.check_backend", icon="CHECKMARK")
        row.operator("qfg.copy_torch_command", icon="COPYDOWN")
        layout.label(text=s.backend_status)
        layout.prop(s, "field_mode")
        layout.prop(s, "grid_size")
        layout.prop(s, "domain_length")
        layout.prop(s, "dt")
        row = layout.row(align=True)
        row.prop(s, "steps_per_action")
        row.prop(s, "steps_per_frame")


class QFG_PT_Dynamics(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Dynamics Runtime"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "dynamics_enabled")
        if not s.dynamics_enabled:
            layout.label(text="Enable for field-coupled bodies")
            return
        row = layout.row(align=True)
        row.prop(s, "dynamics_substeps")
        row.prop(s, "dynamics_seed")
        layout.prop(s, "dynamics_deterministic")
        layout.prop(s, "dynamics_gravity")
        layout.prop(s, "dynamics_floor_height")
        layout.prop(s, "dynamics_body_collisions")
        row = layout.row(align=True)
        row.prop(s, "dynamics_max_speed")
        row.prop(s, "dynamics_max_angular_speed")
        layout.prop(s, "dynamics_field_force_scale")
        layout.prop(s, "dynamics_thermal_force_scale")
        layout.prop(s, "dynamics_field_torque_scale")
        layout.prop(s, "dynamics_field_event_threshold")
        row = layout.row(align=True)
        row.prop(s, "dynamics_contact_event_threshold")
        row.prop(s, "dynamics_penetration_slop")
        layout.prop(s, "dynamics_position_correction")
        box = layout.box()
        box.label(text="Runtime profiler")
        box.label(text=f"Bodies: {s.last_body_count} | Contacts: {s.last_contact_count}")
        box.label(text=f"Events: {s.last_event_count}")
        box.label(text=f"Field: {s.last_field_ms:.3f} ms")
        box.label(text=f"Queries: {s.last_query_ms:.3f} ms")
        box.label(text=f"Bodies: {s.last_body_ms:.3f} ms")
        box.label(text=f"Total: {s.last_total_ms:.3f} ms")
        telemetry = layout.box()
        telemetry.label(text="6-DoF telemetry")
        telemetry.label(text=f"Kinetic total: {s.last_kinetic_energy:.6g}")
        telemetry.label(text=f"Linear / rotational: {s.last_linear_kinetic_energy:.6g} / {s.last_rotational_kinetic_energy:.6g}")
        telemetry.label(text=f"Mean / max |F|: {s.last_mean_force:.6g} / {s.last_max_force:.6g}")
        telemetry.label(text=f"Mean / max |τ|: {s.last_mean_torque:.6g} / {s.last_max_torque:.6g}")


class QFG_PT_Field(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Field and Topology"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        for prop in ("rho0", "lambda_cohesion", "kappa_stability", "alpha_dielectric", "zeta_em", "damping", "delta_anisotropy"):
            layout.prop(s, prop)
        layout.prop(s, "topology_enabled")
        if s.topology_enabled:
            layout.prop(s, "spin_exchange")
            layout.prop(s, "skyrme_potential_scale")
            layout.prop(s, "external_b")
            layout.operator("qfg.compute_topology", icon="MOD_WIREFRAME")
            col = layout.column(align=True)
            col.label(text=f"Hopf proxy: {s.hopf_proxy:.6g}")
            col.label(text=f"Skyrme proxy: {s.skyrme_proxy:.6g}")
            col.label(text=f"Orientation var: {s.orientation_variance:.6g}")


class QFG_PT_ThermalHRM(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Thermal and HRM"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "thermal_enabled")
        if s.thermal_enabled:
            for prop in ("heat_conduction", "collision_heating", "critical_temperature", "temperature_cap"):
                layout.prop(s, prop)
        layout.separator()
        layout.prop(s, "hrm_enabled")
        if s.hrm_enabled:
            row = layout.row(align=True)
            row.prop(s, "drive_a1")
            row.prop(s, "drive_a2")
            row = layout.row(align=True)
            row.prop(s, "drive_f1")
            row.prop(s, "drive_f2")
            layout.prop(s, "drive_profile")
            layout.prop(s, "drive_width")


class QFG_PT_GaugeGravity(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Gauge, Gravity and Noise"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "gauge_enabled")
        if s.gauge_enabled:
            for prop in ("gauge_coupling", "gauge_damping", "gauge_wave_speed", "gauge_backreaction"):
                layout.prop(s, prop)
        layout.prop(s, "gravity_enabled")
        if s.gravity_enabled:
            layout.prop(s, "gravity_strength")
            layout.prop(s, "gravity_backreaction")
        layout.prop(s, "noise_enabled")
        if s.noise_enabled:
            layout.prop(s, "noise_amplitude")
            layout.prop(s, "noise_seed")


class QFG_PT_Visualization(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Visualization and Timeline"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "threshold_fraction")
        layout.prop(s, "max_points")
        layout.prop(s, "point_radius")
        layout.prop(s, "slice_axis")
        layout.operator("qfg.update_visualization", icon="HIDE_OFF")
        row = layout.row(align=True)
        row.prop(s, "bake_start")
        row.prop(s, "bake_end")
        layout.operator("qfg.bake_timeline", icon="REC")
        layout.operator("qfg.clear_cache", icon="X")
        layout.prop(s, "playback_outside_mode")


class QFG_PT_Debug(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "6-DoF Debug Overlay"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        layout.prop(s, "debug_overlay_enabled")
        if not s.debug_overlay_enabled:
            return
        layout.prop(s, "debug_show_hud")
        layout.prop(s, "debug_show_contacts")
        layout.prop(s, "debug_show_forces")
        layout.prop(s, "debug_show_torques")
        layout.prop(s, "debug_show_angular_velocity")
        box = layout.box()
        box.label(text="Vector scales")
        if s.debug_show_contacts:
            row = box.row(align=True)
            row.prop(s, "debug_contact_normal_scale")
            row.prop(s, "debug_impulse_scale")
        if s.debug_show_forces:
            box.prop(s, "debug_force_scale")
        if s.debug_show_torques:
            box.prop(s, "debug_torque_scale")
        if s.debug_show_angular_velocity:
            box.prop(s, "debug_angular_scale")
        if s.debug_show_hud:
            box.prop(s, "debug_hud_font_size")
        telemetry = layout.box()
        telemetry.label(text="Current rigid-body state")
        telemetry.label(text=f"Active body / floor contacts: {s.last_active_body_contacts} / {s.last_active_floor_contacts}")
        telemetry.label(text=f"P body: ({s.last_body_momentum[0]:.3g}, {s.last_body_momentum[1]:.3g}, {s.last_body_momentum[2]:.3g})")
        telemetry.label(text=f"L body: ({s.last_body_angular_momentum[0]:.3g}, {s.last_body_angular_momentum[1]:.3g}, {s.last_body_angular_momentum[2]:.3g})")


class QFG_PT_Diagnostics(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Diagnostics and Export"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        col = layout.column(align=True)
        col.label(text=f"t: {s.last_time:.6g}")
        col.label(text=f"Max density: {s.last_max_density:.6g}")
        col.label(text=f"Norm: {s.last_norm:.6g}")
        col.label(text=f"modeVar: {s.last_mode_variance:.6g}")
        col.label(text=f"Energy proxy: {s.last_energy:.6g}")
        col.label(text=f"Max T: {s.last_temperature:.6g}")
        col.label(text=f"Gauge E: {s.last_gauge_energy:.6g}")
        col.label(text=f"Gravity E: {s.last_gravity_energy:.6g}")
        col.label(text=f"Atlas scalar E: {s.last_atlas_energy:.6g}")
        col.label(text=f"Field P: ({s.last_momentum[0]:.3g}, {s.last_momentum[1]:.3g}, {s.last_momentum[2]:.3g})")
        col.label(text=f"Body P: ({s.last_body_momentum[0]:.3g}, {s.last_body_momentum[1]:.3g}, {s.last_body_momentum[2]:.3g})")
        col.label(text=f"Body L: ({s.last_body_angular_momentum[0]:.3g}, {s.last_body_angular_momentum[1]:.3g}, {s.last_body_angular_momentum[2]:.3g})")
        layout.prop(s, "output_directory")
        layout.operator("qfg.export_session", icon="EXPORT")


class QFG_PT_RF(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "RF / HRM / Plasma"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        box = layout.box()
        box.label(text="Nonlinear RF resonator")
        for prop in ("rom_detuning_min", "rom_detuning_max", "rom_points", "rom_drive", "rom_linear_loss", "rom_nonlinear_loss", "rom_duffing", "rom_external_coupling", "rom_second_tone_ratio"):
            box.prop(s, prop)
        box.operator("qfg.run_rom", icon="FCURVE")

        box = layout.box()
        box.label(text="HRM scan")
        row = box.row(align=True)
        row.prop(s, "scan_f1_min")
        row.prop(s, "scan_f1_max")
        row = box.row(align=True)
        row.prop(s, "scan_f2_min")
        row.prop(s, "scan_f2_max")
        box.prop(s, "scan_points")
        box.prop(s, "scan_duration")
        box.prop(s, "scan_dt")
        box.prop(s, "scan_nx")
        box.operator("qfg.run_hrm_scan", icon="IMAGE_DATA")
        box.label(text=s.scan_best)

        box = layout.box()
        box.label(text="Glow-plasma boundary proxy")
        box.prop(s, "plasma_boundary_factor")
        box.prop(s, "plasma_ionization")
        box.prop(s, "plasma_recombination")
        box.operator("qfg.run_plasma", icon="LIGHT")


class QFG_PT_CavityMEMS(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Cavity and MEMS"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        box = layout.box()
        box.label(text="Cavity shift: QFG vs thermal")
        box.prop(s, "cavity_q_factor")
        box.prop(s, "cavity_power_max")
        box.prop(s, "cavity_density_per_power")
        box.prop(s, "cavity_thermal_coefficient")
        box.operator("qfg.run_cavity_shift", icon="OUTLINER_OB_SPEAKER")
        box = layout.box()
        box.label(text="MEMS geometry/Q proxy")
        box.prop(s, "mems_base_q")
        box.prop(s, "mems_geometry_scale")
        box.operator("qfg.run_mems", icon="MOD_WAVE")


class QFG_PT_Yb(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Yb Quantum-Control Suite"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        for prop in ("yb_duration", "yb_dt", "yb_rabi_frequency", "yb_detuning", "yb_dephasing", "yb_relaxation", "yb_q_factor", "yb_cavity_power", "yb_density_offset", "yb_correction_scale", "yb_texture_coupling", "yb_texture_divergence", "yb_ac_stark_scale", "yb_ramsey_free_time"):
            layout.prop(s, prop)
        row = layout.row(align=True)
        row.prop(s, "yb_odmr_min")
        row.prop(s, "yb_odmr_max")
        layout.prop(s, "yb_odmr_points")
        layout.operator("qfg.run_yb", icon="PARTICLES")
        layout.label(text="Outputs: Rabi, Ramsey, ODMR, Q sweep, two-ion phase")


class QFG_PT_AtlasDirect(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Atlas Direct / BSM-SG Geometry"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout

        box = layout.box()
        box.label(text="SOURCE geometry", icon="OUTLINER_OB_MESH")
        box.prop(s, "atlas_element")
        box.prop(s, "atlas_center_mode")
        if s.atlas_center_mode == "CENTER_OBJECT":
            box.prop(s, "atlas_center_object")
        box.prop(s, "atlas_tag_nucleon_type")
        box.operator("qfg.auto_detect_atlas_selected", icon="VIEWZOOM")
        box.label(text="Auto-detect is DERIVED name heuristics; review tags manually")
        row = box.row(align=True)
        op = row.operator("qfg.tag_atlas_selected", text="Tag Core")
        op.role = "CORE"
        op = row.operator("qfg.tag_atlas_selected", text="Tag Valence")
        op.role = "VALENCE"
        row = box.row(align=True)
        op = row.operator("qfg.tag_atlas_selected", text="Tag Bound")
        op.role = "BOUND"
        op = row.operator("qfg.tag_atlas_selected", text="Tag Equatorial")
        op.role = "EQUATORIAL"

        calc = layout.box()
        calc.label(text="DERIVED geometry", icon="DRIVER_DISTANCE")
        calc.prop(s, "atlas_vector_scale")
        calc.operator("qfg.extract_atlas_geometry", icon="ORIENTATION_GLOBAL")
        if s.atlas_mean_angle:
            calc.label(text=f"Mean pair angle: {s.atlas_mean_angle:.4f}°")
            calc.label(text=f"Spread σ: {s.atlas_angle_spread:.4f}°")
            calc.label(text=f"Range: {s.atlas_min_angle:.4f}° … {s.atlas_max_angle:.4f}°")
            calc.label(text=f"C3v h/r proxy: {s.atlas_height_ratio:.6f}")

        b2 = layout.box()
        b2.label(text="B2 interaction / orbital / Bohr proxies", icon="NODETREE")
        b2.prop(s, "atlas_graph_topology")
        b2.prop(s, "atlas_graph_kernel")
        if s.atlas_graph_kernel in {"INVERSE_CUBE", "COSINE_SQUARED_INV_R3"}:
            b2.prop(s, "atlas_graph_softening")
        b2.operator("qfg.build_atlas_interaction_graph", icon="NODETREE")
        if s.atlas_graph_edge_count:
            b2.label(text=f"Edges: {s.atlas_graph_edge_count}")
            b2.label(text=f"ΣJ proxy: {s.atlas_graph_total_proxy:.6g}")
            b2.label(text=f"Mean |J| proxy: {s.atlas_graph_mean_proxy:.6g}")
        b2.label(text=s.atlas_graph_status)

        b2.separator()
        b2.prop(s, "atlas_plane_scale")
        b2.operator("qfg.extract_atlas_orbital_planes", icon="ORIENTATION_GIMBAL")
        if s.atlas_plane_mean_dihedral or s.atlas_plane_spread:
            b2.label(text=f"Mean plane dihedral: {s.atlas_plane_mean_dihedral:.4f}°")
            b2.label(text=f"Plane σ: {s.atlas_plane_spread:.4f}°")
        b2.label(text=s.atlas_plane_status)

        b2.separator()
        b2.prop(s, "atlas_bohr_radius_mode")
        if s.atlas_bohr_radius_mode == "FIXED":
            b2.prop(s, "atlas_bohr_fixed_radius")
        b2.prop(s, "atlas_bohr_padding")
        b2.operator("qfg.build_integrated_bohr_envelope", icon="MESH_UVSPHERE")
        if s.atlas_bohr_volume:
            b2.label(text=f"Envelope volume proxy: {s.atlas_bohr_volume:.6g}")
            b2.label(text=f"Bounding radius: {s.atlas_bohr_sphere_radius:.6g}")
        b2.label(text=s.atlas_bohr_status)
        b2.label(text="J and Bohr envelope are proxies unless independently normalized")

        b3 = layout.box()
        b3.label(text="B3 Atlas → QFG field bridge", icon="FORCE_FORCE")
        b3.prop(s, "atlas_field_enabled")
        b3.prop(s, "atlas_field_auto_apply")
        b3.prop(s, "atlas_field_live_update")
        b3.prop(s, "atlas_field_source_scope")
        b3.prop(s, "atlas_field_role_scope")
        b3.prop(s, "atlas_field_kernel")
        if s.atlas_field_kernel == "SOFT_INV_R3":
            b3.prop(s, "atlas_field_softening")
        b3.prop(s, "atlas_field_scene_scale")
        b3.prop(s, "atlas_field_scalar_scale")
        b3.prop(s, "atlas_field_vector_scale")
        if abs(s.atlas_field_vector_scale) > 0.0:
            b3.prop(s, "atlas_field_vector_mode")
        b3.prop(s, "atlas_field_orbital_mix")
        b3.prop(s, "atlas_field_clip_abs")
        row = b3.row(align=True)
        row.operator("qfg.apply_atlas_field", icon="FORCE_FORCE")
        row.operator("qfg.clear_atlas_field", icon="X")
        if s.atlas_field_source_count:
            b3.label(text=f"Sources: {s.atlas_field_source_count}")
            b3.label(text=f"V range: {s.atlas_field_scalar_min:.4g} … {s.atlas_field_scalar_max:.4g}")
            b3.label(text=f"V RMS: {s.atlas_field_scalar_rms:.4g}")
            b3.label(text=f"|B| max/RMS: {s.atlas_field_vector_max:.4g} / {s.atlas_field_vector_rms:.4g}")
        b3.label(text=s.atlas_field_status)
        b3.label(text="CONDITIONAL: geometry feeds dynamics; absolute energy scale remains open")

        b4 = layout.box()
        b4.label(text="B4 QFG → Atlas feedback", icon="CONSTRAINT")
        b4.prop(s, "atlas_feedback_enabled")
        b4.prop(s, "atlas_feedback_auto_capture")
        b4.prop(s, "atlas_feedback_rerasterize")
        b4.prop(s, "atlas_feedback_target_mode")
        if s.atlas_feedback_target_mode == "HYBRID":
            b4.prop(s, "atlas_feedback_spin_mix")
        b4.prop(s, "atlas_feedback_force_scale")
        b4.prop(s, "atlas_feedback_torque_scale")
        b4.prop(s, "atlas_feedback_anchor_strength")
        b4.prop(s, "atlas_feedback_orientation_anchor")
        b4.prop(s, "atlas_feedback_orbital_mix")
        b4.prop(s, "atlas_feedback_max_step")
        b4.prop(s, "atlas_feedback_max_angle")
        b4.prop(s, "atlas_feedback_max_displacement")
        row = b4.row(align=True)
        row.operator("qfg.capture_atlas_feedback_anchors", icon="PINNED")
        row.operator("qfg.reset_atlas_feedback_anchors", icon="LOOP_BACK")
        b4.operator("qfg.apply_atlas_feedback", icon="CONSTRAINT")
        if s.atlas_feedback_source_count:
            b4.label(text=f"Sources/moved/rotated: {s.atlas_feedback_source_count} / {s.atlas_feedback_moved_count} / {s.atlas_feedback_rotated_count}")
            b4.label(text=f"|F| mean/max: {s.atlas_feedback_mean_force:.4g} / {s.atlas_feedback_max_force:.4g}")
            b4.label(text=f"|τ| mean/max: {s.atlas_feedback_mean_torque:.4g} / {s.atlas_feedback_max_torque:.4g}")
            b4.label(text=f"Work proxy F/τ/total: {s.atlas_feedback_force_work:.4g} / {s.atlas_feedback_torque_work:.4g} / {s.atlas_feedback_total_work:.4g}")
            b4.label(text=f"Max anchor displacement: {s.atlas_feedback_max_anchor_displacement:.4g}")
            if s.atlas_feedback_clipped_count:
                b4.label(text=f"Safety-clipped updates: {s.atlas_feedback_clipped_count}", icon="ERROR")
        b4.label(text=s.atlas_feedback_status)
        b4.label(text="CONDITIONAL bounded relaxation; not absolute BSM-SG force normalization")

        b5 = layout.box()
        b5.label(text="B5 topology / angular constraints", icon="MODIFIER")
        b5.prop(s, "atlas_constraints_enabled")
        b5.prop(s, "atlas_constraints_auto_capture")
        b5.prop(s, "atlas_constraints_pair_mode")
        b5.prop(s, "atlas_constraints_distance_stiffness")
        b5.prop(s, "atlas_constraints_shell_stiffness")
        b5.prop(s, "atlas_constraints_cone_stiffness")
        b5.prop(s, "atlas_constraints_symmetry_stiffness")
        b5.prop(s, "atlas_constraints_shell_tolerance")
        b5.prop(s, "atlas_constraints_iterations")
        b5.prop(s, "atlas_constraints_tolerance")
        b5.prop(s, "atlas_constraints_max_correction")
        b5.prop(s, "atlas_constraints_preserve_centroid")
        row = b5.row(align=True)
        row.operator("qfg.capture_atlas_constraints", icon="PINNED")
        row.operator("qfg.clear_atlas_constraints", icon="X")
        b5.operator("qfg.apply_atlas_constraints", icon="MODIFIER")
        if s.atlas_constraints_node_count:
            b5.label(text=f"Nodes/pairs/groups: {s.atlas_constraints_node_count} / {s.atlas_constraints_pair_count} / {s.atlas_constraints_group_count}")
            b5.label(text=f"Iterations: {s.atlas_constraints_iterations_used}; max correction: {s.atlas_constraints_max_correction_used:.4g}")
            b5.label(text=f"Pair/shell error: {s.atlas_constraints_max_pair_error:.4g} / {s.atlas_constraints_max_shell_error:.4g}")
            b5.label(text=f"Cone excess: {s.atlas_constraints_max_cone_excess:.4g}°")
            if s.atlas_constraints_group_count:
                b5.label(text=f"Symmetry pair angle: {s.atlas_constraints_pair_angle_before:.4f}° → {s.atlas_constraints_pair_angle_after:.4f}°")
        b5.label(text=s.atlas_constraints_status)
        b5.label(text="C3 groups preserve azimuth while collective polar tilt remains free")
        b5.label(text="CONDITIONAL projection law; recapture after changing source topology")

        b6 = layout.box()
        b6.label(text="B6 blind Group-15 relaxation", icon="EXPERIMENTAL")
        b6.prop(s, "atlas_blind_auto_initialize")
        b6.prop(s, "atlas_blind_reset_to_anchors")
        b6.prop(s, "atlas_blind_recapture_constraints")
        b6.prop(s, "atlas_blind_steps_per_iteration")
        row = b6.row(align=True)
        row.prop(s, "atlas_blind_min_iterations")
        row.prop(s, "atlas_blind_max_iterations")
        b6.prop(s, "atlas_blind_window")
        b6.prop(s, "atlas_blind_angle_tolerance")
        b6.prop(s, "atlas_blind_slope_tolerance")
        b6.prop(s, "atlas_blind_spread_tolerance")
        b6.prop(s, "atlas_blind_correction_tolerance")
        b6.prop(s, "atlas_blind_freeze_on_convergence")
        row = b6.row(align=True)
        row.operator("qfg.run_blind_atlas_relaxation", icon="PLAY")
        row.operator("qfg.reset_blind_atlas_run", icon="LOOP_BACK")
        if s.atlas_blind_iterations_used:
            b6.label(text=f"Iterations: {s.atlas_blind_iterations_used}; converged={s.atlas_blind_converged}")
            b6.label(text=f"Final angle / σ: {s.atlas_blind_final_angle:.5f}° / {s.atlas_blind_final_spread:.4g}°")
            b6.label(text=f"Window range: {s.atlas_blind_window_range:.4g}°")
            b6.label(text=f"Drift: {s.atlas_blind_window_slope:+.3g}°/iter")
        if s.atlas_blind_protocol_hash:
            b6.label(text=f"Protocol SHA-256: {s.atlas_blind_protocol_hash[:16]}…")
        b6.label(text=s.atlas_blind_status)
        b6.label(text="CONDITIONAL dynamics; convergence detector never reads experiment")

        blind = layout.box()
        blind.label(text="Blind holdout", icon="HIDE_ON")
        if not s.atlas_frozen:
            blind.operator("qfg.freeze_atlas_prediction", icon="LOCKED")
            blind.label(text="Experimental reference remains hidden")
        else:
            blind.label(text=f"FROZEN {s.atlas_frozen_element}: {s.atlas_frozen_angle:.4f}°")
            blind.label(text=f"Frozen σ: {s.atlas_frozen_spread:.4f}°")
            if not s.atlas_reference_revealed:
                blind.operator("qfg.reveal_atlas_reference", icon="HIDE_OFF")
            else:
                blind.label(text=f"EXPERIMENTAL: {s.atlas_reference_angle:.4f}°")
                blind.label(text=f"Residual: {s.atlas_residual_angle:+.4f}° ({s.atlas_residual_percent:.3f}%)")
            blind.operator("qfg.reset_atlas_holdout", icon="LOOP_BACK")

        layout.operator("qfg.export_atlas_report", icon="EXPORT")
        layout.label(text=s.atlas_status)
        layout.label(text="SOURCE → DERIVED → freeze → EXPERIMENTAL")


class QFG_PT_Molecular(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "QFG 5.2"
    bl_label = "Molecular Creator"
    bl_parent_id = "QFG_PT_Main"

    def draw(self, context):
        s = context.scene.qfg_settings
        layout = self.layout
        row = layout.row(align=True)
        for molecule, label in (("H2", "H₂"), ("H2O", "H₂O"), ("BENZENE", "C₆H₆")):
            op = row.operator("qfg.create_molecule", text=label)
            op.molecule = molecule
        for prop in ("mol_coulomb_scale", "mol_overlap_scale", "mol_gradient_scale", "mol_kinetic_scale", "mol_topology_scale", "mol_bond_stiffness", "mol_bond_tolerance"):
            layout.prop(s, prop)
        layout.operator("qfg.evaluate_molecule", icon="VIEWZOOM")
        box = layout.box()
        box.label(text="Target-driven optimizer")
        box.prop(s, "mol_target_energy")
        box.prop(s, "mol_target_band_gap")
        box.prop(s, "mol_target_wavelength")
        box.prop(s, "mol_target_oscillator")
        box.prop(s, "mol_opt_iterations")
        box.prop(s, "mol_opt_step")
        box.operator("qfg.optimize_molecule", icon="MODIFIER")
        layout.label(text=s.molecular_status)
        layout.label(text="Proxy only — not a Kohn–Sham/QFG-DFT solve")


class QFG_PT_Object(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_label = "QFG Actor 5.2"

    def draw(self, context):
        obj = context.object
        if obj is None:
            return
        p = obj.qfg_actor
        layout = self.layout
        layout.prop(p, "enabled", toggle=True, icon="PHYSICS")
        if not p.enabled:
            return
        layout.prop(p, "actor_type")
        if p.actor_type in {"GAUSSIAN", "HOPF_RING", "VORTEX", "PLANE_WAVE"}:
            layout.prop(p, "velocity")
            layout.prop(p, "radius")
            layout.prop(p, "intensity")
            layout.prop(p, "spin_theta")
            layout.prop(p, "spin_phi")
        if p.actor_type in {"HOPF_RING", "VORTEX"}:
            layout.prop(p, "winding_m")
            layout.prop(p, "winding_n")
        if p.actor_type == "HOPF_RING":
            layout.prop(p, "ring_radius")
        if p.actor_type == "BOUNDARY":
            layout.prop(p, "boundary_shape")
            layout.prop(p, "boundary_potential")
            layout.prop(p, "boundary_damping")
        if p.actor_type == "MOLECULE_ATOM":
            layout.prop(p, "atomic_number")
            layout.prop(p, "atomic_charge")
            layout.prop(p, "covalent_radius")
        if p.actor_type == "ATLAS_NUCLEON":
            layout.prop(p, "atlas_nucleon_type")
            layout.prop(p, "atlas_role")
            layout.prop(p, "atlas_direction_mode")
            layout.prop(p, "atlas_orbital_normal_mode")
            layout.separator()
            layout.prop(p, "atlas_field_enabled")
            if p.atlas_field_enabled:
                layout.prop(p, "atlas_field_strength")
                layout.prop(p, "atlas_field_radius")
                layout.prop(p, "atlas_field_anisotropy")
            layout.separator()
            layout.prop(p, "atlas_feedback_enabled")
            if p.atlas_feedback_enabled:
                layout.prop(p, "atlas_feedback_force_coupling")
                layout.prop(p, "atlas_feedback_torque_coupling")
                layout.prop(p, "atlas_feedback_linear_mobility")
                layout.prop(p, "atlas_feedback_angular_mobility")
                row = layout.row(align=True)
                row.prop(p, "atlas_feedback_lock_position")
                row.prop(p, "atlas_feedback_lock_rotation")
            layout.separator()
            layout.label(text="B5 constraints")
            layout.prop(p, "atlas_constraint_enabled")
            if p.atlas_constraint_enabled:
                layout.prop(p, "atlas_constraint_fixed")
                layout.prop(p, "atlas_constraint_preserve_radius")
                layout.prop(p, "atlas_constraint_max_cone_deg")
                layout.prop(p, "atlas_constraint_neighbors")
                layout.prop(p, "atlas_constraint_symmetry_group")
            layout.prop(p, "atlas_provenance")
            layout.prop(p, "atlas_source_note")
            if p.atlas_inference_note:
                layout.label(text=f"Auto-tag confidence: {p.atlas_inference_confidence:.2f}")
                layout.label(text=p.atlas_inference_note)
        if p.actor_type == "DYNAMIC_BODY":
            layout.prop(p, "velocity", text="Linear velocity")
            layout.prop(p, "angular_velocity")
            layout.prop(p, "body_mass")
            layout.prop(p, "collision_shape")
            if p.collision_shape == "SPHERE":
                layout.prop(p, "collision_radius")
            else:
                layout.prop(p, "collision_half_extents")
            layout.prop(p, "field_coupling")
            layout.prop(p, "thermal_coupling")
            layout.prop(p, "field_torque_coupling")
            layout.prop(p, "external_torque")
            row = layout.row(align=True)
            row.prop(p, "linear_drag")
            row.prop(p, "angular_drag")
            layout.prop(p, "restitution")
            layout.prop(p, "friction")
            layout.prop(p, "kinematic_body")
            layout.prop(p, "phase_transition_temperature")


CLASSES = (
    QFG_PT_Main, QFG_PT_Presets, QFG_PT_Core, QFG_PT_Dynamics, QFG_PT_Field,
    QFG_PT_ThermalHRM, QFG_PT_GaugeGravity, QFG_PT_Visualization,
    QFG_PT_Debug, QFG_PT_Diagnostics, QFG_PT_RF, QFG_PT_CavityMEMS,
    QFG_PT_Yb, QFG_PT_AtlasDirect, QFG_PT_Molecular, QFG_PT_Object,
)


def register_panels() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister_panels() -> None:
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
