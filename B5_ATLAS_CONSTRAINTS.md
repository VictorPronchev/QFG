# B5 — Constraint-aware Atlas / molecular relaxation

Version: **QFG Dynamics 0.9.0-alpha**

B5 is the geometry-admissibility layer placed between B4 field feedback and the
updated Atlas scene geometry.

```text
Atlas source geometry
      ↓
B3 Atlas → QFG field
      ↓
QFG evolution
      ↓
B4 force / torque proposal
      ↓
B5 topology + shell + cone + symmetry projection
      ↓
updated Atlas geometry
      ↓
optional B3 re-rasterization
```

## Scientific status

B5 does **not** introduce a new absolute BSM-SG force or energy normalization.
It constrains a B4 proposal to a declared geometric admissible set.  Captured
source topology may be `SOURCE` or `DERIVED`; the iterative projection law,
stiffnesses, tolerances and numerical safety clamps are always
**`CONDITIONAL`**.

The design follows the 5E freeze: rejected 24-channel counting, 3/24 isotope
counting and the rejected `n_E=1` normalization are not used.

## Constraint families

### 1. Captured pair connectivity

A pair constraint stores the distance present at capture time.  Connectivity can
come from:

- **Manual neighbours** — comma-separated object names; intended for reviewed
  BSM-SG/Atlas connectivity.
- **Parent-child** — Blender hierarchy interpreted as a DERIVED topology.
- **B2 source star** — VALENCE ↔ EQUATORIAL topology only.
- **None** — no pair-distance constraints.

B5 never guesses a complete graph.

### 2. Radial shell constraint

For an object with **Preserve shell radius**, B5 preserves its captured distance
from the selected Atlas nuclear centre, optionally allowing a scene-unit shell
tolerance.

This is useful for valence structures whose main admitted freedom is angular
rather than radial.

### 3. Angular freedom cone

Each Atlas object may declare an **Angular freedom cone** in degrees around its
captured radial direction.  `0°` disables the cone.  The value should be entered
from a source rule or an explicitly declared modelling assumption; B5 does not
invent an element-specific cone angle.

### 4. Symmetry groups with free collective polar tilt

Objects sharing the same **B5 symmetry group** preserve the captured azimuth
pattern around a group symmetry axis.  Crucially, B5 does **not** preserve the
captured polar tilt.  At every projection cycle it estimates the current common
polar tilt and restores only equivalence among group members.

For a three-arm C3 group this means:

- the three valence arms remain symmetry-equivalent;
- the captured 120° azimuth pattern is preserved;
- the common polar tilt is free to change;
- therefore the H-X-H-like pair angle is free to relax.

This is the intended setup for the N → P → As → Sb blind geometry tests.

## Recommended Group-15 workflow

1. Tag the three free valence nucleons as `VALENCE` and review provenance.
2. Give all three the same `B5 symmetry group`, for example `C3_valence`.
3. Enable **Preserve shell radius** if that is the intended Atlas source rule.
4. Set **Angular freedom cone** only when a justified range is available.
5. Use **Manual neighbours** only for real reviewed nuclear attachments; do not
   connect the three valence arms merely to force a molecular angle.
6. Capture B4 anchors.
7. Capture B5 constraints **before** revealing the molecular holdout.
8. Enable B3, B4 and B5; evolve/relax.
9. Run **Extract Atlas Geometry** on the relaxed state.
10. Freeze the derived angle, then reveal the experimental holdout.

## Numerical projection

The solver uses bounded iterative projection.  A single iteration may include:

1. pair-distance correction;
2. radial-shell correction;
3. angular-cone correction;
4. symmetry-group correction;
5. optional movable-centroid restoration.

Every individual correction may be bounded by `Max B5 correction / iter`.
This clamp is a numerical safety device, not a physical constant.

## Provenance rules

- `REJECTED` nodes and edges never participate.
- Manual reviewed connectivity can retain `SOURCE` provenance when both objects
  are `SOURCE`.
- Parent/child and B2 source-star connectivity are `DERIVED`.
- The projection result is always `CONDITIONAL`.
- Changing source topology, cone limits, symmetry groups or captured shell
  geometry requires **Capture B5 Constraints** again.

## Diagnostics

The panel reports:

- nodes / pair constraints / symmetry groups;
- projection iterations;
- final maximum pair-distance error;
- final maximum shell error;
- final angular-cone excess;
- largest B5 positional correction;
- symmetry-group mean pair angle before and after projection.

The final line is especially useful for blind Group-15 tests because it shows
whether the collective pyramid angle actually moved rather than being frozen by
the constraint layer.

## Current limitations

- No SI-calibrated BSM-SG constraint force or Lagrange multiplier is claimed.
- Symmetry axes are captured in world coordinates; a future version may attach
  them to a moving core frame.
- B5 currently constrains source positions.  B4 still owns orbital-frame
  rotation updates; a future extension can add explicit constrained orbital
  quaternion manifolds.
- Blender `bpy` UI/runtime must still be smoke-tested in Blender 5.2; the build
  environment covers pure numerical tests, Python syntax and package integrity.
