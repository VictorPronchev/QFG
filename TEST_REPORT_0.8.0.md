# Test report — 0.8.0-alpha / B4

## Pure numerical regression

Command:

```text
python tests/run_pure_tests.py
```

Expected terminal result:

```text
QFG Dynamics 0.8.0 Alpha pure numerical + Atlas B4 feedback regression tests: PASS
```

B4-specific checks include:

- deterministic sampling of an off-centre density lobe;
- force direction toward increasing density;
- bounded translation and bounded axis-angle rotation;
- anchor-radius runaway prevention;
- exclusion of REJECTED provenance;
- Rodrigues rotation helper;
- periodic central-difference gradient consistency;
- finite force, torque and work-proxy bookkeeping;
- preservation of all B1/B2/B3 and pre-Atlas numerical regressions.

## Static package audit

All Python sources are compiled/parsed without importing Blender.  A final release gate is also run after extracting the packaged ZIP and rerunning the same regression suite.

## Not covered here

The container does not provide Blender 5.2 / `bpy`, so operator registration, panel rendering, Geometry Nodes and live viewport interaction require a short Blender-side smoke test after installation.
