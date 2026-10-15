# B4 — Bidirectional Atlas ↔ QFG feedback

Version: **QFG Dynamics 0.8.0-alpha**

## Purpose

B4 closes the reduced numerical loop introduced by Atlas Direct (B1), the Atlas interaction geometry tools (B2), and Atlas→QFG field rasterization (B3):

```text
reviewed Atlas geometry
      ↓
B3 conditional scalar/vector field
      ↓
QFGEngine3D evolution
      ↓
density / spin texture
      ↓
B4 bounded translation + rotation relaxation
      ↓
updated Atlas transforms
      ↓
optional B3 re-rasterization
```

The feedback law is deliberately **CONDITIONAL**.  It is a controlled research relaxation rule, not an SI-calibrated force law and not a claim that absolute BSM-SG interaction normalization has been derived.

## Numerical law

For each enabled, non-REJECTED Atlas source, B4 samples the QFG field at the source position.  The default translation proxy is

```text
F* = kF cF ∇ρ − k_anchor (x − x0)
Δx = μx F* Δt
```

The density gradient uses a **periodic central difference**, matching the periodic FFT field box.

The target direction for orientation may be:

- `DENSITY_GRADIENT`
- `SPIN_TEXTURE` (spinor mode; density-gradient fallback)
- `HYBRID`

The orientation proxy is

```text
τ* = kT cT [(1−m) d×t + m n×t]
     + krot [(1−m) d×d0 + m n×n0]
Δθ_vec = μθ τ* Δt
```

where `d` is the current Atlas director, `n` is the orbital-plane normal, `t` is the selected local QFG target, and the `0` quantities are captured anchor orientations.

## Safety limits

Every B4 cycle is independently bounded by:

- maximum translation per cycle;
- maximum rotation angle per cycle;
- maximum displacement from the captured anchor;
- optional position lock;
- optional rotation lock;
- optional position/orientation anchor restoring terms.

The clamp state is exported and shown in the UI.

## Work bookkeeping

B4 reports dimensionless diagnostic work proxies

```text
W*_F   = Σ F* · Δx
W*_τ   = Σ τ* · Δθ_vec
W*_tot = W*_F + W*_τ
```

These values are for numerical auditing only.  They are **not joules** and must not be presented as physical energy until an independently derived normalization exists.

## Provenance rules

- `REJECTED` sources never drive B4.
- Source/role filtering follows the reviewed B3 scope.
- SOURCE geometry is kept distinct from the CONDITIONAL feedback law.
- The feedback result itself is always recorded with `CONDITIONAL` provenance.

## Blender workflow

1. Tag/review Atlas objects with B1/B2 tools.
2. Enable and build the B3 Atlas field.
3. Initialize the QFG engine.
4. Enable **B4 bidirectional feedback**.
5. Capture anchors, or leave **Auto-capture anchors** enabled.
6. Set conservative translation/rotation limits.
7. Use **Apply B4 Feedback Once** for inspection, then **Run QFG Steps** or **Bake QFG Timeline**.
8. Watch moved/rotated/clipped counts, force/torque diagnostics, work proxy, and max anchor displacement.
9. Use **Reset to B4 Anchors** whenever the relaxation should be restarted from the reviewed source geometry.

When **Rebuild B3 after feedback** is enabled, each accepted B4 transform update re-rasterizes the Atlas field before the next solver cycle.

## Scientific boundary

B4 does not solve the missing 5E absolute molecular normalization and does not turn QFG Lab into a first-principles molecular-dynamics engine.  It supplies a reproducible, bounded numerical laboratory for asking whether a chosen conditional field law relaxes reviewed Atlas geometry toward stable configurations, and for exporting every assumption needed to repeat that test.
