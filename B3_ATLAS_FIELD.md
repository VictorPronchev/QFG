# B3 — Atlas → QFG Field Bridge

B3 connects the auditable Atlas geometry layer from B1/B2 to the reduced QFG numerical field.

## Scientific status

The geometry inputs can be `SOURCE` or `DERIVED`, but the field bridge itself is **CONDITIONAL**. B3 does not claim a closed BSM-SG energy normalization. Its kernel, source strengths, anisotropy amplitude, source radius, and vector coupling are explicit model parameters and are exported with provenance.

## Data path

`Atlas object transforms → direction/orbital normal → anisotropy tensor → source kernel → scalar potential + vector director field → QFG engine`

The scalar potential is added to the reduced QFG potential before the potential half of the split-step evolution. In `SPINOR` mode the local vector field also contributes a signed orientation projection to the two reduced spinor components.

## Source filters

B3 can use:

- `SOURCE only` — default and safest mode;
- `SOURCE + DERIVED` — permits reviewed name-inference tags;
- `All non-rejected` — diagnostic mode only.

Role filters are `VALENCE + EQUATORIAL`, `VALENCE only`, or all Atlas roles. `REJECTED` objects never drive B3.

## Kernels

- `GAUSSIAN` — finite localized source, recommended for numerical work.
- `SOFT_INV_R3` — softened inverse-cube geometry proxy. Scene-unit dependent and explicitly conditional.

## Anisotropy

Each source constructs a traceless orientation tensor from the valence/director axis and the orbital-plane normal. `Orbital-normal mix` selects how much each contributes. This is a reproducible orientation proxy, not a source-derived absolute BSM-SG force law.

## Vector field

- `DIRECTOR` — field follows the local source direction.
- `DIPOLE_PROXY` — generic `3(d·rhat)rhat-d` directional pattern.

The vector/spin scale defaults to zero. This keeps B3 scalar-only until the user explicitly activates the spin/orientation bridge.

## Per-object controls

Every `ATLAS_NUCLEON` object now has:

- B3 field-source enable;
- dimensionless source strength;
- source radius in Blender scene units;
- anisotropy amplitude.

## Runtime controls

The Atlas Direct panel exposes:

- enable/disable B3;
- apply automatically when the QFG engine is initialized/reset;
- optional refresh before every manual `Run QFG Steps` action;
- provenance and role filters;
- kernel, scaling and clipping controls;
- scalar/vector field diagnostics;
- Build/Apply and Clear operators.

## Diagnostics and export

B3 reports source count, scalar min/max/RMS, vector max/RMS and an `Atlas scalar energy` proxy. The full numerical snapshot includes the B3 scalar and vector grids. Atlas and complete-session exports include `atlas_b3_field.json` with configuration, source list and provenance.

## Deliberately not implemented

B3 does not derive SI units, a first-principles BSM-SG coupling constant, a solved integrated Bohr surface, or the missing microscopic absolute molecular normalization from the 5E ledger. Those remain open theory tasks rather than hidden calibration constants.
