# Upgrading QFG Dynamics 0.4.0 -> 0.4.1

0.4.1 is backward-compatible with the 0.4.0 actor/runtime configuration. The numerical 6-DoF body model is retained; this release hardens playback and adds diagnostic visualization.

## New scene controls

- `Outside baked range`: Hold nearest baked frame / Clamp timeline / Status only.
- `6-DoF Debug Overlay` panel in the QFG sidebar.
- Toggles for HUD, contacts, force, torque, and angular-velocity vectors.
- Independent vector scale controls.

## Playback semantics

Heavy QFG computation still occurs only during explicit stepping or baking. Timeline handlers only resolve cached frames and update Blender display objects. In the default HOLD mode, requesting frame 188 from a cache ending at 120 keeps Blender on 188 but clearly reports and displays cached frame 120.
