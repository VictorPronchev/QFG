# QFG Dynamics 0.5.0-alpha Test Report

Command:

```bash
python3 tests/run_pure_tests.py
```

Result:

```text
QFG Dynamics 0.5.0 Alpha pure numerical + Atlas Direct regression tests: PASS
```

Coverage added in 0.5.0:

- construction of an ideal three-arm C3v geometry from a known pair angle;
- recovery of that pair angle from 3-D vectors;
- zero spread for the ideal symmetric case;
- C3v h/r descriptor consistency;
- post-freeze experimental holdout comparison and provenance.

Blender UI/runtime registration is syntax-checked in this environment; interactive Blender 5.2 UI smoke-testing should still be performed after installation because `bpy` is unavailable in the headless pure-Python regression environment.
