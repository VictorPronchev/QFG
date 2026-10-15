# Build report — QFG Dynamics 0.8.0-alpha / B4

## Release scope

B4 adds bounded bidirectional Atlas↔QFG feedback on top of the 0.7.0 B3 field bridge.

Implemented:

- Blender-independent `atlas_feedback.py`;
- periodic QFG-density gradient sampling;
- density-gradient / spin-texture / hybrid orientation targets;
- per-source force/torque couplings and mobilities;
- anchor capture/reset and position/orientation restoring terms;
- translation, rotation and anchor-radius safety clamps;
- optional B3 re-rasterization after feedback;
- manual-step and timeline-bake integration;
- force/torque/work-proxy telemetry and session export;
- SOURCE/DERIVED filtering with REJECTED exclusion.

## Release status

- Pure numerical regression: PASS
- Python syntax/compile audit: PASS
- Blender UI/runtime smoke test: NOT RUN in the build container (`bpy` unavailable)
- Scientific provenance: B4 law explicitly CONDITIONAL

The release therefore remains **alpha**.
