# Atlas Direct — BSM-SG / QFG Blender bridge (0.5.0-alpha)

## Purpose

Atlas Direct turns tagged Blender source geometry into a reproducible numerical geometry record.  It is intentionally separated from the current molecular energy proxy.

Pipeline:

```text
BSM-SG / ANS source objects
        ↓
SOURCE tags (core / valence / bound / equatorial)
        ↓
world-space valence directions
        ↓
DERIVED pair angles / symmetry axis / C3v h/r
        ↓
Freeze Blind Prediction
        ↓
optional EXPERIMENTAL holdout reveal
        ↓
JSON + CSV audit report
```

## Object tagging

Select one or more source objects and use **QFG 5.2 → Atlas Direct / BSM-SG Geometry**.

Choose a nucleon type and tag the selection as:

- **Core** — contributes to the nuclear-center estimate.
- **Free valence** — included in the derived valence geometry.
- **Bound** — retained as source structure but excluded from principal valence.
- **Equatorial** — retained for later orbital/interaction-graph work.

Each Atlas object also exposes, in Object Properties → QFG Actor 5.2:

- nucleon type;
- Atlas role;
- direction rule;
- provenance;
- source note.

## Direction rules

`Center → object` uses the world-space vector from the chosen nuclear center to the object origin.  For source models where the free proton/deuteron club is represented by object orientation rather than object position, use `+/- Local X/Y/Z` instead.

No angle is inferred from a screenshot or camera projection.

## Center rules

- **Tagged core centroid** — recommended when the source model has tagged central structures.
- **Center object** — use a dedicated nucleus-center/He-chain reference object.
- **World origin** — useful only when the source model is intentionally centered there.

## Blind holdout

For N, P, As and Sb:

1. Extract geometry.
2. Inspect the DERIVED angle and spread.
3. Click **Freeze Blind Prediction**.
4. Only then click **Reveal Experimental Holdout**.

The experimental registry is not consulted by extraction or freezing.

## Provenance

- `SOURCE`: explicit BSM-SG/ANS source geometry or source metadata.
- `DERIVED`: deterministic calculation from SOURCE geometry.
- `CONDITIONAL`: a model bridge/hypothesis not fixed by source geometry alone.
- `CALIBRATED`: uses a measurement/reference to fix a parameter.
- `EXPERIMENTAL`: external measurement/reference.
- `REJECTED`: retained for audit/history only and must not drive predictions.

## Scientific boundary

Atlas Direct makes the geometry pipeline auditable; it does not establish that BSM-SG is a validated description of nuclear structure.  Current QFG molecular functionals remain proxies/conditional models.  Rejected 4-series multiplicity closures are intentionally not included in the Atlas Direct calculation.
